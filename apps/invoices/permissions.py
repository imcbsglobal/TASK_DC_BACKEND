from rest_framework.permissions import BasePermission

from .models import ClientUser


class IsClientUser(BasePermission):
    """Mobile app users: must be logged in with a Bearer token."""
    message = 'Login required.'

    def has_permission(self, request, view):
        return isinstance(request.user, ClientUser)

class IsSuperAdmin(BasePermission):
    """Django superusers only (used by the React admin panel)."""
    message = 'Superadmin access only.'

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active
                    and getattr(u, 'is_superuser', False))        