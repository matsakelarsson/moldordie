from django.contrib import admin

from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin[Item]):
    list_display = ["name", "created"]
    search_fields = ["name"]
