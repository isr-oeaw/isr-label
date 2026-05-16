from django.utils import timezone, translation
from django.contrib.auth import get_user_model

User = get_user_model()


class UserLanguageMiddleware:
    """
    Middleware to activate user's preferred language
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def process_request(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'language') and request.user.language:
            translation.activate(request.user.language)
            request.LANGUAGE_CODE = request.user.language
        else:
            current_language = translation.get_language()
            translation.activate(current_language)
        return None

    def process_response(self, request, response):
        if hasattr(request, 'LANGUAGE_CODE'):
            response['Content-Language'] = request.LANGUAGE_CODE
        return response

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        return self.process_response(request, response)


class FirstLoginMiddleware:
    """
    Middleware to track the user's first login date
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request
        if (request.user.is_authenticated and 
            request.user.first_login_date is None and
            request.path != '/admin/'):  # Don't track admin logins
            request.user.first_login_date = timezone.now()
            request.user.save(update_fields=['first_login_date'])

        response = self.get_response(request)
        return response