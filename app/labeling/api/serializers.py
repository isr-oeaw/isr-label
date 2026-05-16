from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from labeling.models import (
    Annotation,
    AnnotationDraft,
    ImageAsset,
    LabelDataset,
    LabelSchema,
    Task,
)
from projects.models import Project

User = get_user_model()


class LabelSchemaSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabelSchema
        fields = ['id', 'project', 'config', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class LabelDatasetSerializer(serializers.ModelSerializer):
    assigned_user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    assigned_group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    assigned_users = serializers.SerializerMethodField()
    assigned_groups = serializers.SerializerMethodField()

    class Meta:
        model = LabelDataset
        fields = [
            'id',
            'project',
            'name',
            'description',
            'created_at',
            'updated_at',
            'assigned_users',
            'assigned_groups',
            'assigned_user_ids',
            'assigned_group_ids',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'project', 'assigned_users', 'assigned_groups']

    def get_assigned_users(self, obj):
        return list(obj.assigned_users.values_list('id', flat=True))

    def get_assigned_groups(self, obj):
        return list(obj.assigned_groups.values_list('id', flat=True))

    def _apply_assignees(self, dataset, uids, gids):
        if uids is not None:
            want = list(dict.fromkeys(uids))
            valid = User.objects.filter(
                pk__in=want,
                project_memberships__project=dataset.project,
            ).distinct()
            if valid.count() != len(want):
                raise serializers.ValidationError(
                    {'assigned_user_ids': 'Each user id must be a member of this project.'}
                )
            dataset.assigned_users.set(valid)
        if gids is not None:
            want = list(dict.fromkeys(gids))
            found = list(Group.objects.filter(pk__in=want))
            if len(found) != len(want):
                raise serializers.ValidationError({'assigned_group_ids': 'Invalid group id.'})
            dataset.assigned_groups.set(found)

    def create(self, validated_data):
        uids = validated_data.pop('assigned_user_ids', None)
        gids = validated_data.pop('assigned_group_ids', None)
        d = super().create(validated_data)
        if uids is not None or gids is not None:
            self._apply_assignees(d, uids, gids)
        return d

    def update(self, instance, validated_data):
        uids = validated_data.pop('assigned_user_ids', None)
        gids = validated_data.pop('assigned_group_ids', None)
        d = super().update(instance, validated_data)
        if uids is not None or gids is not None:
            self._apply_assignees(d, uids, gids)
        return d


class ImageAssetSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    location_wkt = serializers.SerializerMethodField()

    class Meta:
        model = ImageAsset
        fields = [
            'id', 'dataset', 'file', 'file_url', 'width', 'height',
            'location_wkt', 'captured_at', 'checksum', 'created_at',
        ]
        read_only_fields = ['id', 'width', 'height', 'checksum', 'created_at', 'file_url', 'location_wkt']

    def get_file_url(self, obj):
        request = self.context.get('request')
        u = obj.file.url if obj.file else None
        if u and request is not None:
            return request.build_absolute_uri(u)
        return u

    def get_location_wkt(self, obj):
        if obj.location:
            return obj.location.wkt
        return None


class TaskSerializer(serializers.ModelSerializer):
    image = ImageAssetSerializer(read_only=True)
    schema = LabelSchemaSerializer(read_only=True)
    image_id = serializers.PrimaryKeyRelatedField(
        queryset=ImageAsset.objects.all(), source='image', write_only=True, required=False
    )

    class Meta:
        model = Task
        fields = [
            'id', 'project', 'image', 'image_id', 'schema', 'inner_id', 'overlap',
            'is_labeled', 'total_annotations', 'cancelled_annotations', 'data', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'is_labeled', 'total_annotations', 'cancelled_annotations', 'inner_id', 'created_at', 'updated_at',
        ]


class AnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Annotation
        fields = [
            'id', 'task', 'completed_by', 'result', 'was_cancelled', 'ground_truth', 'lead_time',
            'status', 'parent_annotation', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'completed_by', 'created_at', 'updated_at']


class DraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnotationDraft
        fields = ['result', 'lead_time', 'updated_at']
        read_only_fields = ['updated_at']


class ProjectMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'title', 'status']
