from django.contrib import admin

from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin[Item]):
    list_display = ["name", "created"]
    search_fields = ["name"]
