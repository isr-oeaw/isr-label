from django.urls import path, include, re_path
from allauth.account import app_settings as allauth_app_settings
from allauth.account import urls as allauth_account_urls
from allauth.account import views as allauth_account_views

from user.views import (
    AccountDeleteView, SettingsView, SignupPageView, 
    UsersUpdateView, UsersListView, UserCreateView, RoleListView, RoleCreateView, 
    RoleUpdateView, RoleDeleteView, user_management_view, data_export_view,
    PendingUsersView, approve_user, reject_user, UserProfileView, resend_email_verification
)


def _allauth_account_urlpatterns():
    """
    django-allauth's default `confirm-email` route uses `[-:\\w]+`, which omits
    `=` and other characters that can appear in signed keys (e.g. base64 padding),
    leading to 404 on the confirmation link. Use any non-slash segment for `key`
    and keep a single `account_confirm_email` name.
    """
    base = list(allauth_account_urls.urlpatterns)
    by_code = getattr(
        allauth_app_settings, "EMAIL_VERIFICATION_BY_CODE_ENABLED", False
    )
    if by_code:
        return base
    without = [
        p for p in base if getattr(p, "name", None) != "account_confirm_email"
    ]
    if len(without) == len(base):
        return base
    return [
        re_path(
            r"^confirm-email/(?P<key>[^/]+)/$",
            allauth_account_views.confirm_email,
            name="account_confirm_email",
        )
    ] + without


urlpatterns = [
    # User Management
    path('delete/', AccountDeleteView.as_view(), name='user-delete'),
    path('settings/', SettingsView, name='user-settings'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('profile/<int:user_id>/', UserProfileView.as_view(), name='user-profile-detail'),
    path('data-export/', data_export_view, name='data-export'),
    path("signup/", SignupPageView.as_view(), name="user-signup"),
    path('list/', UsersListView.as_view(), name='user-list'),
    path('create/', UserCreateView.as_view(), name='user-create'),
    path('edit/<int:user_id>/', UsersUpdateView.as_view(), name='user-edit'),
    
    # User Approval
    path('pending/', PendingUsersView.as_view(), name='pending-users'),
    path('approve/<int:user_id>/', approve_user, name='approve-user'),
    path('reject/<int:user_id>/', reject_user, name='reject-user'),
    
    # Role Management
    path('roles/', RoleListView.as_view(), name='role-list'),
    path('roles/create/', RoleCreateView.as_view(), name='role-create'),
    path('roles/<int:pk>/edit/', RoleUpdateView.as_view(), name='role-edit'),
    path('roles/<int:pk>/delete/', RoleDeleteView.as_view(), name='role-delete'),
    
    # User Management Dashboard
    path('management/', user_management_view, name='user-management'),
    
    # Email Verification
    path('resend-verification/', resend_email_verification, name='resend-email-verification'),
    
    # Allauth URLs (confirm-email key pattern allows '=' etc.; see _allauth_account_urlpatterns)
    path("", include(_allauth_account_urlpatterns())),
]