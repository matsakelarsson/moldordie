{%- set service_tokens = cookiecutter.identity_provider != 'none' -%}
"""The metrics endpoint: what a scrape must present, and what it reads.

{% if service_tokens -%}
The tests of the configured credential carry no ``django_db`` mark: that path opens no
transaction and reads no table, so a query would be a mistake and these are where it
would show. The tests of a calling service's token do carry it, because a registration
and the permissions it holds are rows.
{%- else -%}
No test here carries the django_db mark. The endpoint opens no transaction and reads no
table, so a query would be a mistake, and these tests are where it would show.
{%- endif %}
"""

from __future__ import annotations

from http import HTTPStatus
from types import SimpleNamespace

{% if service_tokens -%}
import pytest
from django.contrib.auth.models import Permission
{% endif -%}
from django.urls import reverse
from prometheus_client import multiprocess

from config import gunicorn
{%- if service_tokens %}
from {{ cookiecutter.project_slug }}.identity.models import ServiceRegistration
from {{ cookiecutter.project_slug }}.identity.tests import services
from {{ cookiecutter.project_slug }}.identity.tests.services import LIFETIME
from {{ cookiecutter.project_slug }}.identity.tests.services import SUBJECT
from {{ cookiecutter.project_slug }}.identity.tests.services import service_claims
from {{ cookiecutter.project_slug }}.identity.tests.services import sign
{%- endif %}

CREDENTIAL = "the-credential-of-this-environment"
BEFORE = "django_prometheus.middleware.PrometheusBeforeMiddleware"
AFTER = "django_prometheus.middleware.PrometheusAfterMiddleware"
ENGINE = "django_prometheus.db.backends.postgresql"
{%- if service_tokens %}
# An issuer no branch verifies, so the credential is all that is left to compare
FOREIGN_ISSUER = "https://issuer.example.com"
{%- endif %}


def scrape(client, credential=None):
    """Read the endpoint, presenting ``credential`` as an Authorization header."""
    headers = {} if credential is None else {"Authorization": credential}
    return client.get(reverse("metrics"), headers=headers)


def refused(client, credential=None):
    """Whether the endpoint turned the scrape away."""
    return scrape(client, credential).status_code == HTTPStatus.UNAUTHORIZED


def test_a_scrape_without_a_credential_is_refused(client, settings):
    settings.METRICS_TOKEN = CREDENTIAL

    response = scrape(client)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    # The scheme it should have used, so the refusal says what was missing
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_a_scrape_with_another_scheme_is_refused(client, settings):
    settings.METRICS_TOKEN = CREDENTIAL

    assert refused(client, f"Basic {CREDENTIAL}")
    assert refused(client, CREDENTIAL)


def test_a_scrape_with_the_wrong_credential_is_refused(client, settings):
    settings.METRICS_TOKEN = CREDENTIAL

    assert refused(client, "Bearer another-credential")
    # Not ASCII, so a comparison over the strings would raise rather than refuse
    assert refused(client, "Bearer crédential")


def test_an_unset_token_refuses_every_scrape(client, settings):
    """A deployment that configured no credential has authorised nobody."""
    settings.METRICS_TOKEN = ""

    assert refused(client, "Bearer ")
    assert refused(client, "Bearer anything")
    assert refused(client)


def test_a_scrape_with_the_credential_reads_the_exposition(client, settings):
    settings.METRICS_TOKEN = CREDENTIAL

    response = scrape(client, f"Bearer {CREDENTIAL}")

    assert response.status_code == HTTPStatus.OK
    assert response.headers["Content-Type"].startswith("text/plain")
    # The middleware pair counts what arrives and what leaves
    assert "django_http_requests_before_middlewares_total" in response.content.decode()


def test_the_endpoint_answers_reads_only(client, settings):
    settings.METRICS_TOKEN = CREDENTIAL
    credential = {"Authorization": f"Bearer {CREDENTIAL}"}

    response = client.post(reverse("metrics"), headers=credential)

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_the_middlewares_wrap_the_chain(settings):
    """The pair times what happens between them, so no middleware is outside it."""
    assert settings.MIDDLEWARE[0] == BEFORE
    assert settings.MIDDLEWARE[-1] == AFTER


def test_the_database_backend_is_the_instrumented_one(settings):
    assert settings.DATABASES["default"]["ENGINE"] == ENGINE


def test_the_worker_exit_hook_reports_the_worker_that_left(monkeypatch):
    """Gunicorn's arbiter is the only process that learns a worker is gone, so the hook
    hands the client its pid. What the client then does is its own behaviour: it drops
    that worker's ``live`` gauge files and keeps its counters, which is what makes the
    container's totals survive a recycled worker. This checks the wiring, nothing else.
    """
    reported: list[int] = []
    monkeypatch.setattr(multiprocess, "mark_process_dead", reported.append)

    gunicorn.child_exit(server=object(), worker=SimpleNamespace(pid=4242))

    assert reported == [4242]
{%- if service_tokens %}


@pytest.mark.django_db
class TestAServiceToken:
    """A scraper the identity provider knows presents its own token instead.

    The registration has to hold ``identity.read_metrics``: the project decides what a
    service may read, and the provider only decides which service is calling.
    """

    @pytest.fixture(autouse=True)
    def keys(self, settings, monkeypatch):
        """Verify against an in-memory key source, with a credential configured too."""
        settings.METRICS_TOKEN = CREDENTIAL
        return services.configure(settings, monkeypatch)

    @pytest.fixture
    def registration(self):
        return ServiceRegistration.objects.create(name="Prometheus", subject=SUBJECT)

    def allow(self, registration):
        """Grant the registration the permission to read the metrics."""
        registration.permissions.add(
            Permission.objects.get(
                content_type__app_label="identity",
                codename="read_metrics",
            ),
        )

    def test_a_service_that_may_read_the_metrics_reads_them(self, client, registration):
        self.allow(registration)

        response = scrape(client, f"Bearer {sign(service_claims())}")

        assert response.status_code == HTTPStatus.OK
        exposition = response.content.decode()
        assert "django_http_requests_before_middlewares_total" in exposition

    def test_a_service_without_the_permission_is_refused(self, client, registration):
        """Registered and enabled is not enough; the grant is the answer to may it."""
        response = scrape(client, f"Bearer {sign(service_claims())}")

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_an_unregistered_service_is_refused(self, client):
        assert refused(client, f"Bearer {sign(service_claims())}")

    def test_a_disabled_registration_is_refused(self, client, registration):
        self.allow(registration)
        registration.enabled = False
        registration.save()

        assert refused(client, f"Bearer {sign(service_claims())}")

    def test_a_refused_provider_token_is_not_tried_as_the_credential(
        self,
        client,
        registration,
    ):
        """The issuer picks the branch, and a branch that refuses is the end."""
        self.allow(registration)
        expired = service_claims(exp=service_claims()["iat"] - 2 * LIFETIME)

        assert refused(client, f"Bearer {sign(expired)}")

    def test_the_configured_credential_still_reads_the_exposition(self, client):
        response = scrape(client, f"Bearer {CREDENTIAL}")

        assert response.status_code == HTTPStatus.OK

    def test_an_unset_credential_leaves_a_service_token_alone(
        self,
        client,
        settings,
        registration,
    ):
        """A deployment may authorise its services and draw no credential at all."""
        self.allow(registration)
        settings.METRICS_TOKEN = ""

        response = scrape(client, f"Bearer {sign(service_claims())}")

        assert response.status_code == HTTPStatus.OK

    def test_a_token_of_another_issuer_is_only_the_credential(self, client):
        """No branch verifies it, so it is compared with the credential and refused."""
        assert refused(client, f"Bearer {sign(service_claims(iss=FOREIGN_ISSUER))}")
{%- endif %}
