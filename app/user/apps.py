from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user'
    
    def ready(self):
        from django.contrib import admin
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import User
        from django.contrib.auth.admin import UserAdmin
        from allauth.account.models import EmailAddress
        from .forms import CustomUserCreationForm, CustomUserEditForm
        from .models import Role
        
        CustomUser = get_user_model()
        
        class CustomUserAdmin(UserAdmin):
            add_form = CustomUserCreationForm
            form = CustomUserEditForm
            model = CustomUser
            list_display = [
                "email",
                "username",
                "is_superuser",
            ]
            list_filter = ['is_active', 'is_staff', 'is_superuser']
            fieldsets = (
                (None, {'fields': ('username', 'password')}),
                ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
                ('Role & Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
                ('Important dates', {'fields': ('last_login', 'date_joined')}),
            )
            add_fieldsets = (
                (None, {
                    'classes': ('wide',),
                    'fields': ('username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
                }),
            )
        
        # Unregister the default User model if it's registered
        try:
            admin.site.unregister(User)
        except admin.sites.NotRegistered:
            pass
        
        # Register our custom user model
        try:
            admin.site.register(CustomUser, CustomUserAdmin)
        except admin.sites.AlreadyRegistered:
            pass
        
        # Register Role model
        try:
            admin.site.register(Role)
        except admin.sites.AlreadyRegistered:
            pass
        
        # Unregister the EmailAddress model from admin
        try:
            admin.site.unregister(EmailAddress)
        except admin.sites.NotRegistered:
            pass
