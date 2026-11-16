from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import AuthToken


class ClientTokenAuthentication(BaseAuthentication):
    """Authorization: Bearer <token>"""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b'bearer':
            return None
        if len(parts) != 2:
            raise AuthenticationFailed('Invalid Authorization header.')
        try:
            token = AuthToken.objects.select_related('user').get(key=parts[1].decode())
        except (AuthToken.DoesNotExist, UnicodeDecodeError):
            raise AuthenticationFailed('Invalid token.')
        if token.expires_at <= timezone.now() or not token.user.is_active:
            raise AuthenticationFailed('Token expired or user disabled.')
        return token.user, token

    def authenticate_header(self, request):
        return 'Bearer'