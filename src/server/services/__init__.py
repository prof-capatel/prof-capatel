"""Server business logic and view helper services."""
from src.server.services.view_service import (
    templates,
    render_template,
    get_branding_dict,
    get_all_active_tenants,
    resolve_scoped_tenant_and_user,
    get_current_employee_session,
    check_employee_portal_redirect,
    get_tenant_roles_list,
)

__all__ = [
    "templates",
    "render_template",
    "get_branding_dict",
    "get_all_active_tenants",
    "resolve_scoped_tenant_and_user",
    "get_current_employee_session",
    "check_employee_portal_redirect",
    "get_tenant_roles_list",
    "seo_service",
]

from src.server.services import seo_service

