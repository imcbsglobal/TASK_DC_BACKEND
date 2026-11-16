from rest_framework.permissions import BasePermission

from .models import ClientUser


class IsClientUser(BasePermission):
    """Mobile app users: must be logged in with a Bearer token."""
    message = 'Login required.'

    def has_permission(self, request, view):
        return isinstance(request.user, ClientUser)