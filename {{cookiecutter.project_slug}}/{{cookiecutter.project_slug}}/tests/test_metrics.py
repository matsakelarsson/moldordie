"""The metrics endpoint: what a scrape must present, and what it reads.

No test here carries the django_db mark. The endpoint opens no transaction and reads no
table, so a query would be a mistake, and these tests are where it would show.
"""

from __future__ import annotations

from http import HTTPStatus

from django.urls import reverse

CREDENTIAL = "the-credential-of-this-environment"
BEFORE = "django_prometheus.middleware.PrometheusBeforeMiddleware"
AFTER = "django_prometheus.middleware.PrometheusAfterMiddleware"
ENGINE = "django_prometheus.db.backends.postgresql"


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
