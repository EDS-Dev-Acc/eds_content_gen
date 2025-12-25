"""
Role-Based Permissions for EMCIP.

Maps OperatorProfile.role to DRF permission classes.

Roles:
- viewer: Read-only access to all resources
- operator: Read/write access, can trigger crawls and manage sources
- admin: Full access including destructive operations

Usage:
    from apps.core.permissions import IsOperator, IsAdmin, IsViewerOrHigher
    
    class MyView(APIView):
        permission_classes = [IsAuthenticated, IsOperator]
"""

from rest_framework.permissions import BasePermission
import logging

logger = logging.getLogger(__name__)


class RolePermission(BasePermission):
    """Base class for role-based permissions."""
    
    # Override in subclasses
    allowed_roles = []
    
    def has_permission(self, request, view):
        """Check if user has required role."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Get user's role from OperatorProfile
        try:
            from apps.core.models import OperatorProfile
            profile = OperatorProfile.objects.get(user=request.user)
            user_role = profile.role
        except Exception:
            # No profile or error - default to viewer
            user_role = 'viewer'
        
        return user_role in self.allowed_roles


class IsViewer(RolePermission):
    """
    Allow access to users with viewer role or higher.
    
    Viewers have read-only access.
    """
    allowed_roles = ['viewer', 'operator', 'admin']
    message = "Viewer access required."


class IsOperator(RolePermission):
    """
    Allow access to users with operator role or higher.
    
    Operators can:
    - Create and manage sources
    - Trigger crawls
    - Manage seeds
    - View and filter articles
    """
    allowed_roles = ['operator', 'admin']
    message = "Operator access required."


class IsAdmin(RolePermission):
    """
    Allow access to admin users only.
    
    Admins can:
    - Delete sources, schedules, seeds
    - Pause all schedules
    - Access system settings
    - Manage users
    """
    allowed_roles = ['admin']
    message = "Admin access required."


class IsOwnerOrAdmin(BasePermission):
    """
    Allow access if user owns the object or is admin.
    
    Useful for user-specific resources.
    """
    message = "You must be the owner or an admin."
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        # Check if user is admin
        try:
            from apps.core.models import OperatorProfile
            profile = OperatorProfile.objects.get(user=request.user)
            if profile.role == 'admin':
                return True
        except Exception:
            pass
        
        # Check ownership
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        if hasattr(obj, 'added_by'):
            return obj.added_by == request.user
        
        return False


class ReadOnlyForViewer(BasePermission):
    """
    Allow read-only access for viewers, full access for operators+.
    
    Useful for endpoints where viewers should only GET.
    """
    SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
    message = "Operator access required for write operations."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        # Get user's role
        try:
            from apps.core.models import OperatorProfile
            profile = OperatorProfile.objects.get(user=request.user)
            user_role = profile.role
        except Exception:
            user_role = 'viewer'
        
        # Viewers can only use safe methods
        if user_role == 'viewer':
            return request.method in self.SAFE_METHODS
        
        # Operators and admins can do anything
        return user_role in ('operator', 'admin')


class DestructiveActionPermission(BasePermission):
    """
    Require admin role for destructive actions (DELETE, bulk operations).
    
    Use this for endpoints like:
    - DELETE sources, schedules, seeds
    - Pause all schedules
    - Bulk delete operations
    """
    DESTRUCTIVE_METHODS = ('DELETE',)
    message = "Admin access required for destructive operations."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        # Non-destructive methods allowed for operators+
        if request.method not in self.DESTRUCTIVE_METHODS:
            try:
                from apps.core.models import OperatorProfile
                profile = OperatorProfile.objects.get(user=request.user)
                return profile.role in ('operator', 'admin')
            except Exception:
                return False
        
        # Destructive methods require admin
        try:
            from apps.core.models import OperatorProfile
            profile = OperatorProfile.objects.get(user=request.user)
            return profile.role == 'admin'
        except Exception:
            return False


def get_user_role(user):
    """
    Helper function to get user's role.
    
    Returns: 'viewer', 'operator', or 'admin'
    """
    if not user or not user.is_authenticated:
        return None
    
    if user.is_superuser:
        return 'admin'
    
    try:
        from apps.core.models import OperatorProfile
        profile = OperatorProfile.objects.get(user=user)
        return profile.role
    except Exception:
        return 'viewer'


def has_role(user, required_role):
    """
    Check if user has at least the required role level.
    
    Role hierarchy: admin > operator > viewer
    """
    role_levels = {
        'viewer': 1,
        'operator': 2,
        'admin': 3,
    }
    
    user_role = get_user_role(user)
    if not user_role:
        return False
    
    return role_levels.get(user_role, 0) >= role_levels.get(required_role, 0)
