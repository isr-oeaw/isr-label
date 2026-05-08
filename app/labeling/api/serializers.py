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


class LabelSchemaSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabelSchema
        fields = ['id', 'project', 'version', 'config', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class LabelDatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabelDataset
        fields = ['id', 'project', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'project']


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
            'status', 'schema_version', 'parent_annotation', 'created_at', 'updated_at',
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
