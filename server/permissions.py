"""
Permissions system for Company Brain MCP Server.
Implements role-based access control for document categories.
"""

from typing import List, Dict, Set
from enum import Enum
from dataclasses import dataclass


class Role(Enum):
    """User roles with different access levels."""
    ADMIN = "admin"
    ENGINEER = "engineer"
    PRODUCT = "product"
    HR = "hr"
    GUEST = "guest"


@dataclass
class Permission:
    """Permission definition."""
    role: Role
    categories: Set[str]
    can_read: bool = True
    can_search: bool = True
    can_list: bool = True


class PermissionManager:
    """Manages permissions for document access."""
    
    def __init__(self):
        # Define role-based permissions
        self.role_permissions: Dict[Role, Permission] = {
            Role.ADMIN: Permission(
                role=Role.ADMIN,
                categories={"policies", "product", "engineering", "meetings", "internal"},
                can_read=True,
                can_search=True,
                can_list=True
            ),
            Role.ENGINEER: Permission(
                role=Role.ENGINEER,
                categories={"engineering", "product", "meetings"},
                can_read=True,
                can_search=True,
                can_list=True
            ),
            Role.PRODUCT: Permission(
                role=Role.PRODUCT,
                categories={"product", "meetings", "policies"},
                can_read=True,
                can_search=True,
                can_list=True
            ),
            Role.HR: Permission(
                role=Role.HR,
                categories={"policies", "internal", "meetings"},
                can_read=True,
                can_search=True,
                can_list=True
            ),
            Role.GUEST: Permission(
                role=Role.GUEST,
                categories={"product"},  # Only public product docs
                can_read=True,
                can_search=True,
                can_list=False  # Cannot list all documents
            )
        }
    
    def get_permission(self, role: Role) -> Permission:
        """Get permissions for a role."""
        return self.role_permissions.get(role, self.role_permissions[Role.GUEST])
    
    def can_access_category(self, role: Role, category: str) -> bool:
        """Check if a role can access a category."""
        permission = self.get_permission(role)
        return category in permission.categories
    
    def can_read_document(self, role: Role, category: str) -> bool:
        """Check if a role can read documents in a category."""
        permission = self.get_permission(role)
        return permission.can_read and category in permission.categories
    
    def can_search_category(self, role: Role, category: str) -> bool:
        """Check if a role can search a category."""
        permission = self.get_permission(role)
        return permission.can_search and category in permission.categories
    
    def can_list_category(self, role: Role, category: str) -> bool:
        """Check if a role can list documents in a category."""
        permission = self.get_permission(role)
        return permission.can_list and category in permission.categories
    
    def get_accessible_categories(self, role: Role) -> Set[str]:
        """Get all categories accessible to a role."""
        permission = self.get_permission(role)
        return permission.categories
    
    def role_from_string(self, role_str: str) -> Role:
        """Convert string to Role enum."""
        try:
            return Role(role_str.lower())
        except ValueError:
            return Role.GUEST  # Default to guest for unknown roles
