"""Role-based permissions for the dashboard API."""

from rest_framework.permissions import BasePermission

from .models import User


class IsAnalystOrAdmin(BasePermission):
    """Fraud analysts and administrators (the people who work the dashboard)."""

    message = "This area is for fraud analysts and administrators."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_analyst_or_admin)


class IsAdminRole(BasePermission):
    """Administrators only (settings and system status)."""

    message = "Only administrators can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and (user.role == User.Role.ADMIN or user.is_superuser)
        )
