import io
import zipfile

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from labeling.models import Annotation, AnnotationDraft, ImageAsset, LabelDataset, LabelSchema, Task, TaskLock
from labeling.services.exporters import package as export_package
from labeling.services import queue
from projects.models import Project, ProjectMembership

from .serializers import AnnotationSerializer, DraftSerializer, ImageAssetSerializer, LabelDatasetSerializer, TaskSerializer


def get_project_for_user(user, project_pk) -> Project:
    p = get_object_or_404(Project, pk=project_pk)
    if not p.is_accessible_by(user):
        raise NotFound()
    return p


def _can_write_project(user, p: Project) -> bool:
    r = p.get_membership(user)
    if user.is_superuser or user.id == p.owner_id:
        return True
    return r and r.role == ProjectMembership.Role.ADMIN


class LabelDatasetListCreate(generics.ListCreateAPIView):
    serializer_class = LabelDatasetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        p = get_project_for_user(self.request.user, self.kwargs['project_pk'])
        return LabelDataset.objects.filter(project=p).order_by('name')

    def perform_create(self, serializer):
        p = get_project_for_user(self.request.user, self.kwargs['project_pk'])
        if not _can_write_project(self.request.user, p):
            raise PermissionDenied()
        serializer.save(project=p)


class LabelDatasetDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LabelDatasetSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'pk'

    def get_queryset(self):
        p = get_project_for_user(self.request.user, self.kwargs['project_pk'])
        return LabelDataset.objects.filter(project=p)

    def perform_update(self, serializer):
        p = get_project_for_user(self.request.user, self.kwargs['project_pk'])
        if not _can_write_project(self.request.user, p):
            raise PermissionDenied()
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        p = get_project_for_user(self.request.user, self.kwargs['project_pk'])
        if not _can_write_project(self.request.user, p):
            raise PermissionDenied()
        super().perform_destroy(instance)


class TaskList(generics.ListAPIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        p = get_project_for_user(self.request.user, self.kwargs['project_pk'])
        return (
            Task.objects.filter(project=p)
            .select_related('image', 'schema', 'image__dataset')
            .order_by('inner_id')
        )


class TaskRetrieve(generics.RetrieveAPIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'pk'

    def get_object(self):
        task = get_object_or_404(
            Task.objects.select_related('project', 'image', 'schema', 'image__dataset'),
            pk=self.kwargs['pk'],
        )
        if not task.project.is_accessible_by(self.request.user):
            raise NotFound()
        return task


def can_label_user(user, p) -> bool:
    if user.is_superuser or p.owner_id == user.id:
        return True
    m = p.get_membership(user)
    if not m:
        return False
    return m.role in (
        ProjectMembership.Role.ADMIN,
        ProjectMembership.Role.REVIEWER,
        ProjectMembership.Role.ANNOTATOR,
    )


def can_review_user(user, p) -> bool:
    m = p.get_membership(user)
    if user.is_superuser or p.owner_id == user.id:
        return True
    return m and m.role in (ProjectMembership.Role.ADMIN, ProjectMembership.Role.REVIEWER)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def next_task(request, project_pk):
    p = get_project_for_user(request.user, project_pk)
    if not can_label_user(request.user, p):
        raise PermissionDenied()
    t = queue.get_next_task_for(request.user, p)
    if not t:
        return Response({'detail': 'No tasks available.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(TaskSerializer(t, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_lock(request, pk):
    task = get_object_or_404(Task, pk=pk)
    p = task.project
    if not p.is_accessible_by(request.user) or not can_label_user(request.user, p):
        raise NotFound()
    ok, _ = queue.acquire_lock(request.user, task)
    if not ok:
        return Response({'detail': 'Task locked by another user.'}, status=status.HTTP_409_CONFLICT)
    lock = TaskLock.objects.get(task=task, user=request.user)
    return Response({'ok': True, 'expires': lock.expire_at})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_unlock(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not task.project.is_accessible_by(request.user):
        raise NotFound()
    queue.release_lock(request.user, task)
    return Response({'ok': True})


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def task_draft(request, pk):
    task = get_object_or_404(Task, pk=pk)
    p = task.project
    if not p.is_accessible_by(request.user) or not can_label_user(request.user, p):
        raise PermissionDenied()
    if request.method == 'GET':
        d, _ = AnnotationDraft.objects.get_or_create(
            task=task, user=request.user, defaults={'result': []}
        )
        return Response(DraftSerializer(d).data)
    ser = DraftSerializer(data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    result = ser.validated_data.get('result', [])
    lt = ser.validated_data.get('lead_time', 0)
    d, _ = AnnotationDraft.objects.update_or_create(
        task=task,
        user=request.user,
        defaults={'result': result, 'lead_time': lt or 0},
    )
    return Response(DraftSerializer(d).data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def task_annotations(request, pk):
    task = get_object_or_404(Task, pk=pk)
    p = task.project
    if not p.is_accessible_by(request.user):
        raise NotFound()
    if request.method == 'GET':
        qs = task.annotations.filter(was_cancelled=False)
        if not can_review_user(request.user, p) and not _can_write_project(request.user, p):
            qs = qs.filter(completed_by=request.user)
        return Response(AnnotationSerializer(qs, many=True).data)
    if not can_label_user(request.user, p):
        raise PermissionDenied()
    result = request.data.get('result', [])
    if not isinstance(result, list):
        result = []
    ann = Annotation(
        task=task,
        completed_by=request.user,
        result=result,
        was_cancelled=bool(request.data.get('was_cancelled', False)),
        lead_time=request.data.get('lead_time'),
        ground_truth=bool(request.data.get('ground_truth', False)),
        status=Annotation.Status.SUBMITTED,
        schema_version=task.schema.version,
    )
    ann.save()
    AnnotationDraft.objects.filter(task=task, user=request.user).delete()
    queue.release_lock(request.user, task)
    return Response(AnnotationSerializer(ann).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def project_export(request, project_pk):
    from django.http import FileResponse

    p = get_project_for_user(request.user, project_pk)
    m = p.get_membership(request.user)
    u = request.user
    is_owner = p.owner_id == u.id
    is_rev = m and m.role in (
        ProjectMembership.Role.ADMIN,
        ProjectMembership.Role.REVIEWER,
    )
    if not (u.is_superuser or is_owner or is_rev):
        raise PermissionDenied()
    include = request.data.get('variants') or request.query_params.get('include') or 'coco,yolo,geojson'
    include = [x.strip() for x in str(include).split(',') if x.strip()]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        export_package.build_export_zip(p, zf, include)
        zf.writestr('README.txt', 'ISR Label export. See docs/08-export-formats.md\n')
    buf.seek(0)
    return FileResponse(
        buf,
        as_attachment=True,
        filename=f'project_{project_pk}_export.zip',
        content_type='application/zip',
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def image_upload(request, project_pk, dataset_pk):
    p = get_project_for_user(request.user, project_pk)
    if not _can_write_project(request.user, p):
        raise PermissionDenied()
    ds = get_object_or_404(LabelDataset, pk=dataset_pk, project=p)
    f = request.FILES.get('file')
    if not f:
        return Response({'file': 'Required'}, status=400)
    img = ImageAsset.objects.create(dataset=ds, file=f)
    schema = p.label_schemata.filter(is_active=True).order_by('-version').first()
    if not schema:
        schema = LabelSchema.objects.create(
            project=p, version=1, config=LabelSchema.default_config(), is_active=True
        )
    inner = queue.get_next_task_inner_id(p)
    t = Task.objects.create(
        project=p, image=img, schema=schema, inner_id=inner, overlap=1,
    )
    return Response(
        {
            'image': ImageAssetSerializer(img, context={'request': request}).data,
            'task': TaskSerializer(t, context={'request': request}).data,
        },
        status=201,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_geojson(request, project_pk):
    from labeling.services.exporters import geojson as gexp
    p = get_project_for_user(request.user, project_pk)
    return Response(gexp.project_images_geojson(p))


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def annotation_status(request, pk):
    """
    Review workflow: set Annotation.status to approved / rejected / needs_revision
    (project owner, superuser, or membership role admin/reviewer only).
    """
    ann = get_object_or_404(
        Annotation.objects.select_related('task', 'task__project'),
        pk=pk,
    )
    p = ann.task.project
    if not p.is_accessible_by(request.user):
        raise NotFound()
    if not can_review_user(request.user, p):
        raise PermissionDenied()
    st = request.data.get('status')
    valid = {
        Annotation.Status.SUBMITTED,
        Annotation.Status.APPROVED,
        Annotation.Status.REJECTED,
        Annotation.Status.NEEDS_REVISION,
    }
    if st not in valid:
        raise ValidationError({'status': f'Must be one of: {", ".join(valid)}'})
    ann.status = st
    ann.save(update_fields=['status', 'updated_at'])
    return Response(AnnotationSerializer(ann).data)
