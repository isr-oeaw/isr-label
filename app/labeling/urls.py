from django.urls import path

from . import views

app_name = 'labeling'

urlpatterns = [
    path('next/', views.GlobalNextTaskRedirect.as_view(), name='next_global'),
    path('projects/<int:project_id>/', views.LabelingDashboard.as_view(), name='dashboard'),
    path(
        'projects/<int:project_id>/export/',
        views.ProjectLabelingExportDownloadView.as_view(),
        name='project_export_download',
    ),
    path('projects/<int:project_id>/datasets/create/', views.LabelDatasetCreate.as_view(), name='dataset_create'),
    path(
        'projects/<int:project_id>/datasets/<int:dataset_id>/upload/',
        views.ImageUpload.as_view(),
        name='dataset_upload',
    ),
    path(
        'projects/<int:project_id>/datasets/<int:dataset_id>/assignees/',
        views.DatasetAssigneesUpdate.as_view(),
        name='dataset_assignees',
    ),
    path(
        'projects/<int:project_id>/datasets/<int:dataset_id>/tasks/create/',
        views.DatasetCreateLabelTasksView.as_view(),
        name='dataset_create_tasks',
    ),
    path('projects/<int:project_id>/tasks/<int:task_id>/', views.TaskLabel.as_view(), name='task'),
    path('projects/<int:project_id>/next/', views.NextTaskRedirect.as_view(), name='next'),
    path(
        'projects/<int:project_id>/schemas/edit/',
        views.LabelSchemaEdit.as_view(),
        name='schema_edit',
    ),
    path(
        'projects/<int:project_id>/schemas/<int:schema_pk>/toggle-labeling/',
        views.LabelSchemaToggleLabeling.as_view(),
        name='schema_toggle_labeling',
    ),
    path(
        'projects/<int:project_id>/schemas/apply-template/',
        views.LabelSchemaApplyTemplate.as_view(),
        name='schema_apply_template',
    ),
    path('projects/<int:project_id>/schemas/', views.LabelSchemaList.as_view(), name='schema_list'),
    path('projects/<int:project_id>/schema/', views.LabelSchemaLegacyRedirect.as_view(), name='schema'),
    path('projects/<int:project_id>/review/', views.ReviewList.as_view(), name='review'),
]
