from django.urls import path

from . import views

app_name = 'labeling_api'

urlpatterns = [
    path('v1/projects/<int:project_pk>/label_datasets/', views.LabelDatasetListCreate.as_view(), name='label_datasets_list'),
    path('v1/projects/<int:project_pk>/label_datasets/<int:pk>/', views.LabelDatasetDetail.as_view(), name='label_datasets_detail'),
    path('v1/projects/<int:project_pk>/tasks/', views.TaskList.as_view(), name='tasks_list'),
    path('v1/projects/<int:project_pk>/tasks/next/', views.next_task, name='tasks_next'),
    path('v1/projects/<int:project_pk>/export/', views.project_export, name='project_export'),
    path(
        'v1/projects/<int:project_pk>/datasets/<int:dataset_pk>/import_masks/',
        views.dataset_import_masks,
        name='dataset_import_masks',
    ),
    path(
        'v1/projects/<int:project_pk>/datasets/<int:dataset_pk>/images/',
        views.image_upload,
        name='image_upload',
    ),
    path('v1/tasks/<int:pk>/', views.TaskRetrieve.as_view(), name='task_detail'),
    path('v1/tasks/<int:pk>/lock/', views.task_lock, name='task_lock'),
    path('v1/tasks/<int:pk>/unlock/', views.task_unlock, name='task_unlock'),
    path('v1/tasks/<int:pk>/draft/', views.task_draft, name='task_draft'),
    path('v1/tasks/<int:pk>/annotations/', views.task_annotations, name='task_annotations'),
    path('v1/annotations/<int:pk>/', views.annotation_status, name='annotation_status'),
]
