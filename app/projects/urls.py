from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.ProjectListView.as_view(), name='project_list'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_edit'),
    path('<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    path('<int:pk>/transfer-ownership/', views.ProjectTransferOwnershipView.as_view(), name='project_transfer_ownership'),
    path('<int:pk>/members/', views.ProjectMembersView.as_view(), name='project_members'),
    path(
        '<int:pk>/members/<int:user_id>/remove/',
        views.ProjectMemberRemoveView.as_view(),
        name='project_member_remove',
    ),
    path(
        '<int:pk>/members/<int:user_id>/role/',
        views.ProjectMemberUpdateRoleView.as_view(),
        name='project_member_edit',
    ),
]
