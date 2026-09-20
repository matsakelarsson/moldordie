from django.db import models
from django.utils.translation import gettext_lazy as _


class ServiceRegistration(models.Model):
    """A calling service the API accepts: its identity at the provider, what it may do.

    A service is never a user: a token the provider signed for an unregistered
    subject, or a disabled registration, authorises nothing.
    """

    name = models.CharField(_("name"), max_length=100, unique=True)
    enabled = models.BooleanField(_("enabled"), default=True)
    subject = models.CharField(
        _("subject"),
        max_length=255,
        unique=True,
        {%- if cookiecutter.identity_provider == 'entra' %}
        help_text=_("The object id of the service's service principal in the tenant."),
        {%- else %}
        help_text=_(
            "The unique id of the service account (the sub claim of its tokens).",
        ),
        {%- endif %}
    )
    permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name=_("permissions"),
        blank=True,
        related_name="service_registrations",
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("service registration")
        verbose_name_plural = _("service registrations")
        ordering = ["name"]
        {%- if cookiecutter.observability == 'prometheus' %}
        # What a calling service must hold to read the exposition; a registration
        # grants it nothing by existing. See {{ cookiecutter.project_slug }}/metrics.py
        permissions = [("read_metrics", _("Can read the metrics"))]
        {%- endif %}

    def __str__(self) -> str:
        return self.name

    def has_perm(self, perm: str) -> bool:
        """Does the service hold ``perm``, the full ``app_label.codename``?

        A model gains no ``has_perm`` from the relationship, and a disabled service
        holds nothing.
        """
        if not self.enabled:
            return False
        app_label, _, codename = perm.partition(".")
        granted = self.permissions.filter(
            content_type__app_label=app_label,
            codename=codename,
        )
        return granted.exists()
