from django.urls import path
from .views import (
    HomePageView, 
    DocumentationView,
    AnnouncementManagementView,
    AnnouncementCreateView,
    AnnouncementUpdateView,
    AnnouncementDeleteView
)

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("documentation/", DocumentationView.as_view(), name="documentation"),
    
    # Announcement Management URLs
    path("announcements/", AnnouncementManagementView.as_view(), name="announcement-management"),
    path("announcements/create/", AnnouncementCreateView.as_view(), name="announcement-create"),
    path("announcements/<int:pk>/edit/", AnnouncementUpdateView.as_view(), name="announcement-edit"),
    path("announcements/<int:pk>/delete/", AnnouncementDeleteView.as_view(), name="announcement-delete"),
]