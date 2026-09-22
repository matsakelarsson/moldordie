{%- set headless = cookiecutter.headless -%}
from django.contrib.admin.views.decorators import staff_member_required
from ninja import NinjaAPI
{%- if headless %}

from {{ cookiecutter.project_slug }}.identity.auth import user_auth
{%- else %}
from ninja.security import SessionAuth
{%- endif %}

api = NinjaAPI(
    urls_namespace="api",
{%- if headless %}
    # An app-issued JWT, or the session cookie with its CSRF check
    auth=user_auth,
{%- else %}
    auth=SessionAuth(),
{%- endif %}
    docs_decorator=staff_member_required,
)

api.add_router("/users/", "{{ cookiecutter.project_slug }}.users.api.views.router")
{%- if headless %}
# Who is calling: a user or a registered service
api.add_router("/principal/", "{{ cookiecutter.project_slug }}.identity.api.router")
{%- endif %}
