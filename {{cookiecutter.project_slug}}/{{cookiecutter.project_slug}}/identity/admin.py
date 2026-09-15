from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import ServiceRegistration


@admin.register(ServiceRegistration)
class ServiceRegistrationAdmin(admin.ModelAdmin[ServiceRegistration]):
    list_display = ["name", "subject", "enabled", "updated_at"]
    list_filter = ["enabled"]
    search_fields = ["name", "subject"]
    filter_horizontal = ["permissions"]
    fieldsets = (
        (None, {"fields": ("name", "enabled", "subject")}),
        (_("Permissions"), {"fields": ("permissions",)}),
        (_("Important dates"), {"fields": ("created_at", "updated_at")}),
    )

    def get_readonly_fields(
        self,
        request: object,
        obj: ServiceRegistration | None = None,
    ) -> list[str]:
        # The subject binds the registration to one identity for good
        timestamps = ["created_at", "updated_at"]
        return [*timestamps, "subject"] if obj is not None else timestamps
