"""
API Key Authentication Backend for Django
"""
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from .models import APIKey

User = get_user_model()


class APIKeyBackend(BaseBackend):
    """
    Custom authentication backend that authenticates users via API keys.
    
    API keys can be provided in the Authorization header as:
    - Authorization: Api-Key <key>
    - Authorization: Bearer <key>
    
    Or as a query parameter:
    - ?api_key=<key>
    """
    
    def authenticate(self, request, api_key=None, **kwargs):
        """
        Authenticate a user using an API key.
        
        Args:
            request: The HTTP request object
            api_key: The API key string (optional, will be extracted from request if not provided)
            
        Returns:
            User object if authentication is successful, None otherwise
        """
        # If api_key is not provided, try to extract it from the request
        if api_key is None and request is not None:
            api_key = self._extract_api_key(request)
        
        if not api_key:
            return None
        
        try:
            # Look up the API key
            key_obj = APIKey.objects.select_related('user').get(key=api_key)
            
            # Check if the key is valid (active and not expired)
            if not key_obj.is_valid():
                return None
            
            # Update last used timestamp
            key_obj.update_last_used()
            
            # Return the associated user
            user = key_obj.user
            
            # Only authenticate active users
            if user.is_active:
                return user
                
        except APIKey.DoesNotExist:
            pass
        
        return None
    
    def _extract_api_key(self, request):
        """
        Extract API key from request headers or query parameters.
        
        Supports:
        - Authorization: Api-Key <key>
        - Authorization: Bearer <key>
        - Query parameter: ?api_key=<key>
        """
        # Try Authorization header first
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header:
            # Support both "Api-Key <key>" and "Bearer <key>" formats
            parts = auth_header.split(' ', 1)
            if len(parts) == 2:
                scheme, key = parts
                if scheme.lower() in ('api-key', 'bearer'):
                    return key.strip()
        
        # Try query parameter
        api_key = request.GET.get('api_key') or request.GET.get('apikey')
        if api_key:
            return api_key.strip()
        
        return None
    
    def get_user(self, user_id):
        """Retrieve a user by ID (required by Django's authentication system)"""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None




