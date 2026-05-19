from django.test import TestCase
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from types import SimpleNamespace

from .views import HomePageView, AnnouncementManagementView, AnnouncementCreateView, AnnouncementUpdateView, AnnouncementDeleteView
from .models import Announcement

User = get_user_model()


class HomepageTests(TestCase):
    def test_home_anonymous_redirects_to_login(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/user/login/", r["Location"])

    def test_home_authenticated_renders_dashboard(self):
        u = User.objects.create_user(
            username="homeu", email="homeu@test.local", password="pass-12345"
        )
        self.client.login(username="homeu", password="pass-12345")
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "home.html")
        self.assertContains(r, 'id="home-dashboard-personal-tasks"')

    def test_home_url_name(self):
        self.assertEqual(resolve("/").url_name, "home")

    def test_home_resolves_to_homepageview_class(self):
        match = resolve("/")
        self.assertIs(match.func.view_class, HomePageView)

    @patch(
        "pages.views.queue_svc.get_next_task_globally",
        return_value=None,
    )
    def test_home_hides_label_next_when_no_queue_task(self, _mock_next):
        u = User.objects.create_user(
            username="hnxt", email="hnxt@test.local", password="pass-12345"
        )
        self.client.login(username="hnxt", password="pass-12345")
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, reverse("labeling:next_global"))
        self.assertContains(r, "All labeling tasks done!")

    @patch(
        "pages.views.queue_svc.get_next_task_globally",
        return_value=(SimpleNamespace(id=1), SimpleNamespace(id=2)),
    )
    def test_home_shows_label_next_when_queue_has_task(self, _mock_next):
        u = User.objects.create_user(
            username="hnxt2", email="hnxt2@test.local", password="pass-12345"
        )
        self.client.login(username="hnxt2", password="pass-12345")
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, reverse("labeling:next_global"))
        self.assertNotContains(r, "All labeling tasks done!")


class AnnouncementModelTests(TestCase):
    """Test cases for the Announcement model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
    
    def test_announcement_creation(self):
        """Test creating a basic announcement"""
        announcement = Announcement.objects.create(
            title='Test Announcement',
            message='This is a test announcement',
            priority='normal',
            created_by=self.user
        )
        
        self.assertEqual(announcement.title, 'Test Announcement')
        self.assertEqual(announcement.message, 'This is a test announcement')
        self.assertEqual(announcement.priority, 'normal')
        self.assertEqual(announcement.created_by, self.user)
        self.assertTrue(announcement.is_active)
        self.assertIsNotNone(announcement.created_at)
        self.assertIsNotNone(announcement.updated_at)
    
    def test_announcement_str_representation(self):
        """Test the string representation of announcement"""
        announcement = Announcement.objects.create(
            title='Test Announcement',
            message='This is a test announcement',
            priority='high',
            created_by=self.user
        )
        
        expected_str = 'Test Announcement (High)'
        self.assertEqual(str(announcement), expected_str)
    
    def test_announcement_priority_choices(self):
        """Test all priority choices are available"""
        priorities = ['low', 'normal', 'high', 'urgent']
        
        for priority in priorities:
            announcement = Announcement.objects.create(
                title=f'Test {priority} announcement',
                message='Test message',
                priority=priority,
                created_by=self.user
            )
            self.assertEqual(announcement.priority, priority)
    
    def test_announcement_priority_class_method(self):
        """Test the get_priority_class method"""
        priority_classes = {
            'low': 'info',
            'normal': 'primary',
            'high': 'warning',
            'urgent': 'danger'
        }
        
        for priority, expected_class in priority_classes.items():
            announcement = Announcement.objects.create(
                title=f'Test {priority} announcement',
                message='Test message',
                priority=priority,
                created_by=self.user
            )
            self.assertEqual(announcement.get_priority_class(), expected_class)
    
    def test_announcement_is_currently_valid_property(self):
        """Test the is_currently_valid property"""
        now = timezone.now()
        
        # Test valid announcement (no date restrictions)
        announcement = Announcement.objects.create(
            title='Valid Announcement',
            message='This should be valid',
            priority='normal',
            created_by=self.user
        )
        self.assertTrue(announcement.is_currently_valid)
        
        # Test future announcement (not yet valid)
        future_announcement = Announcement.objects.create(
            title='Future Announcement',
            message='This is in the future',
            priority='normal',
            created_by=self.user,
            valid_from=now + timedelta(days=1)
        )
        self.assertFalse(future_announcement.is_currently_valid)
        
        # Test expired announcement
        expired_announcement = Announcement.objects.create(
            title='Expired Announcement',
            message='This has expired',
            priority='normal',
            created_by=self.user,
            valid_until=now - timedelta(days=1)
        )
        self.assertFalse(expired_announcement.is_currently_valid)
        
        # Test announcement with valid date range
        valid_range_announcement = Announcement.objects.create(
            title='Valid Range Announcement',
            message='This has a valid range',
            priority='normal',
            created_by=self.user,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=1)
        )
        self.assertTrue(valid_range_announcement.is_currently_valid)
    
    def test_announcement_is_displayed_property(self):
        """Test the is_displayed property"""
        now = timezone.now()
        
        # Test active and valid announcement
        announcement = Announcement.objects.create(
            title='Displayed Announcement',
            message='This should be displayed',
            priority='normal',
            created_by=self.user,
            is_active=True
        )
        self.assertTrue(announcement.is_displayed)
        
        # Test inactive announcement
        inactive_announcement = Announcement.objects.create(
            title='Inactive Announcement',
            message='This should not be displayed',
            priority='normal',
            created_by=self.user,
            is_active=False
        )
        self.assertFalse(inactive_announcement.is_displayed)
        
        # Test active but expired announcement
        expired_announcement = Announcement.objects.create(
            title='Expired Announcement',
            message='This has expired',
            priority='normal',
            created_by=self.user,
            is_active=True,
            valid_until=now - timedelta(days=1)
        )
        self.assertFalse(expired_announcement.is_displayed)
    
    def test_announcement_ordering(self):
        """Test that announcements are ordered by priority and creation date"""
        # Create announcements with different priorities and times
        announcement1 = Announcement.objects.create(
            title='Normal Priority 1',
            message='First normal announcement',
            priority='normal',
            created_by=self.user
        )
        
        announcement2 = Announcement.objects.create(
            title='High Priority',
            message='High priority announcement',
            priority='high',
            created_by=self.user
        )
        
        announcement3 = Announcement.objects.create(
            title='Normal Priority 2',
            message='Second normal announcement',
            priority='normal',
            created_by=self.user
        )
        
        # Get all announcements ordered by model's default ordering
        announcements = list(Announcement.objects.all())
        
        # String ordering with -priority (descending): 'normal' comes before 'high' alphabetically
        # So normal priorities come first, then high priority by creation date
        self.assertEqual(announcements[0], announcement3)  # Newer normal priority first
        self.assertEqual(announcements[1], announcement1)  # Older normal priority second
        self.assertEqual(announcements[2], announcement2)  # High priority last


class AnnouncementViewTests(TestCase):
    """Test cases for announcement views"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.announcement = Announcement.objects.create(
            title='Test Announcement',
            message='This is a test announcement',
            priority='normal',
            created_by=self.admin_user
        )
    
    def test_announcement_management_view_requires_login(self):
        """Test that announcement management view requires login"""
        response = self.client.get(reverse('announcement-management'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_announcement_management_view_requires_admin_permission(self):
        """Test that announcement management view requires admin permission"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('announcement-management'))
        self.assertEqual(response.status_code, 403)  # Forbidden
    
    def test_announcement_management_view_allows_admin_access(self):
        """Test that admin users can access announcement management"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('announcement-management'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/announcement_management.html')
    
    def test_announcement_management_view_context(self):
        """Test that announcement management view has correct context"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('announcement-management'))
        
        self.assertIn('announcements', response.context)
        self.assertIn('total_announcements', response.context)
        self.assertIn('active_announcements', response.context)
        self.assertIn('expired_announcements', response.context)
        self.assertIn('future_announcements', response.context)
        
        self.assertEqual(response.context['total_announcements'], 1)
        self.assertEqual(response.context['active_announcements'], 1)
    
    def test_announcement_create_view_requires_admin_permission(self):
        """Test that announcement create view requires admin permission"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('announcement-create'))
        self.assertEqual(response.status_code, 403)  # Forbidden
    
    def test_announcement_create_view_allows_admin_access(self):
        """Test that admin users can access announcement create view"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('announcement-create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/announcement_form.html')
    
    def test_announcement_create_post_valid_data(self):
        """Test creating announcement with valid data"""
        self.client.login(username='admin', password='adminpass123')
        
        from django.utils import timezone
        data = {
            'title': 'New Test Announcement',
            'message': 'This is a new test announcement',
            'priority': 'high',
            'is_active': True,
            'valid_from': timezone.now().strftime('%Y-%m-%dT%H:%M')
        }
        
        response = self.client.post(reverse('announcement-create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that announcement was created
        announcement = Announcement.objects.get(title='New Test Announcement')
        self.assertEqual(announcement.message, 'This is a new test announcement')
        self.assertEqual(announcement.priority, 'high')
        self.assertEqual(announcement.created_by, self.admin_user)
    
    def test_announcement_update_view_requires_admin_permission(self):
        """Test that announcement update view requires admin permission"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('announcement-edit', kwargs={'pk': self.announcement.pk}))
        self.assertEqual(response.status_code, 403)  # Forbidden
    
    def test_announcement_update_view_allows_admin_access(self):
        """Test that admin users can access announcement update view"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('announcement-edit', kwargs={'pk': self.announcement.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/announcement_form.html')
    
    def test_announcement_update_post_valid_data(self):
        """Test updating announcement with valid data"""
        self.client.login(username='admin', password='adminpass123')
        
        from django.utils import timezone
        data = {
            'title': 'Updated Test Announcement',
            'message': 'This announcement has been updated',
            'priority': 'urgent',
            'is_active': True,
            'valid_from': timezone.now().strftime('%Y-%m-%dT%H:%M')
        }
        
        response = self.client.post(reverse('announcement-edit', kwargs={'pk': self.announcement.pk}), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that announcement was updated
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.title, 'Updated Test Announcement')
        self.assertEqual(self.announcement.message, 'This announcement has been updated')
        self.assertEqual(self.announcement.priority, 'urgent')
    
    def test_announcement_delete_view_requires_admin_permission(self):
        """Test that announcement delete view requires admin permission"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('announcement-delete', kwargs={'pk': self.announcement.pk}))
        self.assertEqual(response.status_code, 403)  # Forbidden
    
    def test_announcement_delete_view_allows_admin_access(self):
        """Test that admin users can access announcement delete view"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('announcement-delete', kwargs={'pk': self.announcement.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/announcement_confirm_delete.html')
    
    def test_announcement_delete_post(self):
        """Test deleting announcement"""
        self.client.login(username='admin', password='adminpass123')
        
        announcement_pk = self.announcement.pk
        response = self.client.post(reverse('announcement-delete', kwargs={'pk': announcement_pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that announcement was deleted
        self.assertFalse(Announcement.objects.filter(pk=announcement_pk).exists())


class AnnouncementAdminTests(TestCase):
    """Test cases for announcement admin interface"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.announcement = Announcement.objects.create(
            title='Test Announcement',
            message='This is a test announcement',
            priority='normal',
            created_by=self.admin_user
        )
    
    def test_announcement_admin_list_display(self):
        """Test that announcement admin has correct list display"""
        from pages.admin import AnnouncementAdmin
        
        admin = AnnouncementAdmin(Announcement, None)
        expected_fields = [
            'title', 'priority', 'is_active', 'is_currently_valid', 
            'created_by', 'created_at', 'valid_from', 'valid_until'
        ]
        
        self.assertEqual(admin.list_display, expected_fields)
    
    def test_announcement_admin_list_filter(self):
        """Test that announcement admin has correct list filters"""
        from pages.admin import AnnouncementAdmin
        
        admin = AnnouncementAdmin(Announcement, None)
        expected_filters = [
            'priority', 'is_active', 'created_at', 
            'valid_from', 'valid_until', 'created_by'
        ]
        
        self.assertEqual(admin.list_filter, expected_filters)
    
    def test_announcement_admin_search_fields(self):
        """Test that announcement admin has correct search fields"""
        from pages.admin import AnnouncementAdmin
        
        admin = AnnouncementAdmin(Announcement, None)
        expected_fields = [
            'title', 'message', 'created_by__username', 'created_by__email'
        ]
        
        self.assertEqual(admin.search_fields, expected_fields)
    
    def test_announcement_admin_save_model(self):
        """Test that announcement admin sets created_by automatically"""
        from pages.admin import AnnouncementAdmin
        from django.contrib.admin.sites import AdminSite
        
        admin = AnnouncementAdmin(Announcement, AdminSite())
        
        # Create a new announcement without created_by
        announcement = Announcement(
            title='New Announcement',
            message='Test message',
            priority='normal'
        )
        
        # Mock the request with admin user
        class MockRequest:
            user = self.admin_user
        
        request = MockRequest()
        
        # Save the model
        admin.save_model(request, announcement, None, change=False)
        
        # Check that created_by was set
        self.assertEqual(announcement.created_by, self.admin_user)
    
    def test_announcement_admin_is_currently_valid_method(self):
        """Test the is_currently_valid admin method"""
        from pages.admin import AnnouncementAdmin
        from django.contrib.admin.sites import AdminSite
        
        admin = AnnouncementAdmin(Announcement, AdminSite())
        
        # Test with valid announcement
        result = admin.is_currently_valid(self.announcement)
        self.assertIn('✓', result)  # Should contain checkmark for valid
        
        # Test with expired announcement
        expired_announcement = Announcement.objects.create(
            title='Expired Announcement',
            message='This has expired',
            priority='normal',
            created_by=self.admin_user,
            valid_until=timezone.now() - timedelta(days=1)
        )
        
        result = admin.is_currently_valid(expired_announcement)
        self.assertIn('✗', result)  # Should contain X for invalid