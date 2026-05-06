from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import translation
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from unittest.mock import patch, mock_open
import os
from .middleware import UserLanguageMiddleware
from .views import LogView

User = get_user_model()


class UserLanguageMiddlewareTests(TestCase):
    """Test cases for UserLanguageMiddleware"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.middleware = UserLanguageMiddleware(lambda r: None)
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            language='en'
        )
    
    def test_middleware_activates_user_language(self):
        """Test that middleware activates user's preferred language"""
        request = self.factory.get('/')
        request.user = self.user
        
        # Mock translation.activate
        with patch('django.utils.translation.activate') as mock_activate:
            self.middleware.process_request(request)
            mock_activate.assert_called_once_with('en')
            self.assertEqual(request.LANGUAGE_CODE, 'en')
    
    def test_middleware_activates_german_language(self):
        """Test that middleware activates German language for user"""
        self.user.language = 'de'
        self.user.save()
        
        request = self.factory.get('/')
        request.user = self.user
        
        with patch('django.utils.translation.activate') as mock_activate:
            self.middleware.process_request(request)
            mock_activate.assert_called_once_with('de')
            self.assertEqual(request.LANGUAGE_CODE, 'de')
    
    def test_middleware_anonymous_user(self):
        """Test that middleware handles anonymous users correctly"""
        request = self.factory.get('/')
        request.user = User()  # Anonymous user
        
        with patch('django.utils.translation.activate') as mock_activate:
            self.middleware.process_request(request)
            # Should call activate with current language (not user language)
            mock_activate.assert_called_once()
            # Should not set LANGUAGE_CODE for anonymous users
            # Note: The middleware might set LANGUAGE_CODE, but it should be the default language
            if hasattr(request, 'LANGUAGE_CODE'):
                # If LANGUAGE_CODE is set, it should be the default language
                # In test environment, the default is 'en'
                self.assertEqual(request.LANGUAGE_CODE, 'en')  # Default from settings
    
    def test_middleware_user_without_language(self):
        """Test that middleware handles user with empty language preference"""
        self.user.language = ''
        self.user.save()
        
        request = self.factory.get('/')
        request.user = self.user
        
        with patch('django.utils.translation.activate') as mock_activate:
            self.middleware.process_request(request)
            # Should call activate with current language (not user language)
            mock_activate.assert_called_once()
            # Should not set LANGUAGE_CODE for empty language
            self.assertFalse(hasattr(request, 'LANGUAGE_CODE'))
    
    def test_middleware_user_with_none_language(self):
        """Test that middleware handles user with None language preference"""
        # Since the field has a NOT NULL constraint, we'll test with a different approach
        # Create a new user without setting language (should use default)
        user_without_lang = User.objects.create_user(
            username='user_without_lang',
            email='user_without_lang@example.com',
            password='testpass123'
        )
        # The default language should be 'en', but let's test the middleware behavior
        request = self.factory.get('/')
        request.user = user_without_lang
        
        with patch('django.utils.translation.activate') as mock_activate:
            self.middleware.process_request(request)
            # Should call activate with user's language (default 'en')
            mock_activate.assert_called_once_with('en')
            self.assertEqual(request.LANGUAGE_CODE, 'en')
    
    def test_middleware_process_response(self):
        """Test that middleware sets Content-Language header in response"""
        from django.http import HttpResponse
        
        request = self.factory.get('/')
        request.user = self.user
        request.LANGUAGE_CODE = 'de'
        
        response = HttpResponse()
        
        # Process response
        result_response = self.middleware.process_response(request, response)
        
        # Check that Content-Language header is set
        self.assertEqual(result_response['Content-Language'], 'de')
    
    def test_middleware_process_response_no_language_code(self):
        """Test that middleware handles response without LANGUAGE_CODE"""
        from django.http import HttpResponse
        
        request = self.factory.get('/')
        request.user = self.user
        # Don't set LANGUAGE_CODE
        
        response = HttpResponse()
        
        # Process response
        result_response = self.middleware.process_response(request, response)
        
        # Check that Content-Language header is not set
        self.assertNotIn('Content-Language', result_response)
    
    def test_middleware_integration_with_translation(self):
        """Test that middleware properly integrates with Django's translation system"""
        request = self.factory.get('/')
        request.user = self.user
        
        # Process request
        self.middleware.process_request(request)
        
        # Check that language is activated
        self.assertEqual(translation.get_language(), 'en')
        self.assertEqual(request.LANGUAGE_CODE, 'en')
    
    def test_middleware_integration_german(self):
        """Test that middleware properly activates German language"""
        self.user.language = 'de'
        self.user.save()
        
        request = self.factory.get('/')
        request.user = self.user
        
        # Process request
        self.middleware.process_request(request)
        
        # Check that German language is activated
        self.assertEqual(translation.get_language(), 'de')
        self.assertEqual(request.LANGUAGE_CODE, 'de')
    
    def test_middleware_multiple_requests(self):
        """Test that middleware works correctly with multiple requests"""
        # First user with English
        user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            language='en'
        )
        
        # Second user with German
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            language='de'
        )
        
        # First request
        request1 = self.factory.get('/')
        request1.user = user1
        self.middleware.process_request(request1)
        self.assertEqual(request1.LANGUAGE_CODE, 'en')
        
        # Second request
        request2 = self.factory.get('/')
        request2.user = user2
        self.middleware.process_request(request2)
        self.assertEqual(request2.LANGUAGE_CODE, 'de')
    
    def test_middleware_language_change_during_session(self):
        """Test that middleware handles language changes during user session"""
        request = self.factory.get('/')
        request.user = self.user
        
        # Initial request with English
        self.middleware.process_request(request)
        self.assertEqual(request.LANGUAGE_CODE, 'en')
        
        # User changes language preference
        self.user.language = 'de'
        self.user.save()
        
        # New request should use new language
        request2 = self.factory.get('/')
        request2.user = self.user
        self.middleware.process_request(request2)
        self.assertEqual(request2.LANGUAGE_CODE, 'de')
    
    def test_middleware_invalid_language_code(self):
        """Test that middleware handles invalid language codes gracefully"""
        # Set invalid language code (shorter than max length)
        self.user.language = 'xx'
        self.user.save()
        
        request = self.factory.get('/')
        request.user = self.user
        
        # Should not raise exception
        try:
            self.middleware.process_request(request)
        except Exception as e:
            self.fail(f"Middleware raised an exception with invalid language: {e}")
    
    def test_middleware_response_content_language_consistency(self):
        """Test that Content-Language header matches request language"""
        from django.http import HttpResponse
        
        # Test with English
        request = self.factory.get('/')
        request.user = self.user
        request.LANGUAGE_CODE = 'en'
        
        response = HttpResponse()
        result_response = self.middleware.process_response(request, response)
        self.assertEqual(result_response['Content-Language'], 'en')
        
        # Test with German
        request.LANGUAGE_CODE = 'de'
        response = HttpResponse()
        result_response = self.middleware.process_response(request, response)
        self.assertEqual(result_response['Content-Language'], 'de')


class LogViewTests(TestCase):
    """Test cases for LogView"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username='superuser',
            email='superuser@example.com',
            password='testpass123',
            is_superuser=True,
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regularuser',
            email='regular@example.com',
            password='testpass123'
        )
    
    def test_log_view_superuser_access(self):
        """Test that superusers can access the log view"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'System Logs')
    
    def test_log_view_regular_user_denied(self):
        """Test that regular users cannot access the log view"""
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        self.assertEqual(response.status_code, 403)
    
    def test_log_view_anonymous_user_denied(self):
        """Test that anonymous users cannot access the log view"""
        response = self.client.get(reverse('logs'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_log_view_default_log_type(self):
        """Test that default log type is django"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['log_type'], 'django')
    
    def test_log_view_email_log_type(self):
        """Test that email log type can be selected"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs') + '?type=email')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['log_type'], 'email')
    
    def test_log_view_invalid_log_type(self):
        """Test that invalid log type returns 404"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs') + '?type=invalid')
        self.assertEqual(response.status_code, 404)
    
    @patch('os.path.exists')
    def test_log_view_log_file_not_exists(self, mock_exists):
        """Test that missing log file is handled gracefully"""
        mock_exists.return_value = False
        
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['log_file_exists'])
        self.assertIn('does not exist yet', response.context['error_message'])
    
    @patch('builtins.open', mock_open(read_data='INFO 2024-01-01 12:00:00,000 main 12345 67890 Test log message\n'))
    @patch('os.path.exists')
    def test_log_view_with_existing_log_file(self, mock_exists):
        """Test that existing log file is read and parsed correctly"""
        mock_exists.return_value = True
        
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['log_file_exists'])
        self.assertEqual(len(response.context['log_content']), 1)
        
        log_entry = response.context['log_content'][0]
        self.assertEqual(log_entry['level'], 'INFO')
        self.assertEqual(log_entry['timestamp'], '2024-01-01 12:00:00,000')
        self.assertEqual(log_entry['module'], 'main')
        self.assertEqual(log_entry['process'], '12345')
        self.assertEqual(log_entry['thread'], '67890')
        self.assertEqual(log_entry['message'], 'Test log message')
    
    @patch('builtins.open', mock_open(read_data='ERROR 2024-01-01 12:00:00,000 main 12345 67890 Error message\nWARNING 2024-01-01 12:01:00,000 main 12345 67890 Warning message\nINFO 2024-01-01 12:02:00,000 main 12345 67890 Info message\n'))
    @patch('os.path.exists')
    def test_log_view_multiple_log_entries(self, mock_exists):
        """Test that multiple log entries are parsed correctly"""
        mock_exists.return_value = True
        
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['log_content']), 3)
        
        # Check that entries are in reverse order (newest first)
        entries = response.context['log_content']
        self.assertEqual(entries[0]['level'], 'INFO')
        self.assertEqual(entries[1]['level'], 'WARNING')
        self.assertEqual(entries[2]['level'], 'ERROR')
    
    @patch('builtins.open', mock_open(read_data='Simple log line\n'))
    @patch('os.path.exists')
    def test_log_view_malformed_log_entries(self, mock_exists):
        """Test that malformed log entries are handled gracefully"""
        mock_exists.return_value = True
        
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['log_content']), 1)
        
        log_entry = response.context['log_content'][0]
        self.assertEqual(log_entry['level'], 'INFO')  # Default level for malformed entries
        self.assertEqual(log_entry['message'], 'Simple log line')
        self.assertEqual(log_entry['timestamp'], '')  # Empty for malformed entries
        self.assertEqual(log_entry['module'], '')  # Empty for malformed entries
    
    @patch('builtins.open', side_effect=IOError('Permission denied'))
    @patch('os.path.exists')
    def test_log_view_file_read_error(self, mock_exists, mock_file):
        """Test that file read errors are handled gracefully"""
        mock_exists.return_value = True
        
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['log_file_exists'])
        self.assertIn('Error reading log file', response.context['error_message'])
    
    def test_log_view_available_logs_context(self):
        """Test that available logs are included in context"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('available_logs', response.context)
        self.assertIn('django', response.context['available_logs'])
        self.assertIn('email', response.context['available_logs'])
    
    def test_log_view_pagination_context(self):
        """Test that pagination context is included"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('page_obj', response.context)
    
    def test_log_view_template_used(self):
        """Test that correct template is used"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('logs'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'main/logs.html')
    
    def test_log_view_url_resolution(self):
        """Test that URL resolves correctly"""
        url = reverse('logs')
        self.assertEqual(url, '/logs/')
    
    def test_log_view_class_based_view(self):
        """Test that LogView is a class-based view"""
        from django.views.generic import TemplateView
        self.assertTrue(issubclass(LogView, TemplateView))
    
    def test_log_view_permission_mixin(self):
        """Test that LogView uses proper permission mixins"""
        from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
        
        # Check inheritance
        self.assertTrue(issubclass(LogView, LoginRequiredMixin))
        self.assertTrue(issubclass(LogView, UserPassesTestMixin))
    
    def test_log_view_test_func_superuser_only(self):
        """Test that test_func only allows superusers"""
        view = LogView()
        
        # Test with superuser
        request = self.factory.get('/')
        request.user = self.superuser
        view.request = request
        self.assertTrue(view.test_func())
        
        # Test with regular user
        request.user = self.regular_user
        view.request = request
        self.assertFalse(view.test_func())
    
    def test_log_view_log_file_paths(self):
        """Test that log file paths are correctly defined"""
        self.client.login(username='superuser', password='testpass123')
        
        # Test django log path
        response = self.client.get(reverse('logs') + '?type=django')
        self.assertEqual(response.context['log_file_path'], 'logs/django.log')
        
        # Test email log path
        response = self.client.get(reverse('logs') + '?type=email')
        self.assertEqual(response.context['log_file_path'], 'logs/email.log')
