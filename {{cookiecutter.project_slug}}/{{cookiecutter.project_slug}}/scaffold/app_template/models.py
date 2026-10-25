"""The app's model: how a record is named, shown and addressed."""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class Item(models.Model):
    """One record of the app: a name, free-form notes and when it was created.

    Replace the fields with the app's own. The form, the templates and the tests name
    ``name`` and ``notes``, so they change in the same step.
    """

    name = models.CharField(_("name"), max_length=200)
    notes = models.TextField(_("notes"), blank=True)
    created = models.DateTimeField(_("created"), auto_now_add=True)

    # Declared, so the type checker reads the manager from this file: the app template
    # is checked as it stands, before it is anyone's installed app
    objects: ClassVar[models.Manager[Item]] = models.Manager()

    class Meta:
        ordering = ["-created", "-pk"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("app_template:detail", kwargs={"pk": self.pk})
