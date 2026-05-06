from django.urls import path

from . import views

app_name = 'labeling'

urlpatterns = [
    path('projects/<int:project_id>/', views.LabelingDashboard.as_view(), name='dashboard'),
    path('projects/<int:project_id>/datasets/', views.LabelDatasetList.as_view(), name='dataset_list'),
    path('projects/<int:project_id>/datasets/create/', views.LabelDatasetCreate.as_view(), name='dataset_create'),
    path(
        'projects/<int:project_id>/datasets/<int:dataset_id>/upload/',
        views.ImageUpload.as_view(),
        name='dataset_upload',
    ),
    path('projects/<int:project_id>/map/', views.MapView.as_view(), name='map'),
    path('projects/<int:project_id>/tasks/<int:task_id>/', views.TaskLabel.as_view(), name='task'),
    path('projects/<int:project_id>/next/', views.NextTaskRedirect.as_view(), name='next'),
    path('projects/<int:project_id>/schema/', views.LabelSchemaEdit.as_view(), name='schema'),
    path('projects/<int:project_id>/review/', views.ReviewList.as_view(), name='review'),
]
