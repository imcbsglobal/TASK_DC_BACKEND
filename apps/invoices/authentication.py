from datetime import timedelta

from django.conf import settings
from django.core import signing
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

        now = timezone.now()
        if token.expires_at <= now or not token.user.is_active:
            raise AuthenticationFailed('Token expired or user disabled.')

        # sliding expiry: push the expiry forward, at most once a day
        ttl = timedelta(days=getattr(settings, 'TOKEN_TTL_DAYS', 30))
        if token.expires_at - now < ttl - timedelta(days=1):
            token.expires_at = now + ttl
            token.save(update_fields=['expires_at'])

        return token.user, token

    def authenticate_header(self, request):
        return 'Bearer'


ADMIN_SALT = 'taskdc-superuser'


class SuperUser:
    """Lightweight stand-in for request.user on the admin panel (no DB row)."""
    is_authenticated = True
    is_active = True
    is_superuser = True

    def __init__(self, username):
        self.username = username


def issue_admin_token(username):
    return signing.dumps({'u': username}, salt=ADMIN_SALT)


class AdminTokenAuthentication(BaseAuthentication):
    """Authorization: Token <signed-token>"""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b'token':
            return None
        if len(parts) != 2:
            raise AuthenticationFailed('Invalid Authorization header.')
        try:
            data = signing.loads(
                parts[1].decode(), salt=ADMIN_SALT,
                max_age=settings.ADMIN_TOKEN_TTL_SECONDS)
        except (signing.BadSignature, UnicodeDecodeError):
            raise AuthenticationFailed('Invalid or expired token.')
        return SuperUser(data['u']), None

    def authenticate_header(self, request):
        return 'Token'