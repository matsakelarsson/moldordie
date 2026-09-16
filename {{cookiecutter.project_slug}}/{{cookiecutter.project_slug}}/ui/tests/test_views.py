from http import HTTPStatus

from django.urls import reverse

from {{ cookiecutter.project_slug }}.ui.themes import configured_theme
from {{ cookiecutter.project_slug }}.ui.themes import render_stylesheet


def test_the_theme_stylesheet_is_css_and_never_stored(client):
    response = client.get(reverse("ui:theme"))
    assert response.status_code == HTTPStatus.OK
    assert response["Content-Type"] == "text/css; charset=utf-8"
    assert response["Cache-Control"] == "private, no-store"
    assert response.content.decode() == render_stylesheet(configured_theme())


def test_the_stylesheet_follows_the_settings(client, settings):
    settings.UI_PALETTE = "violet"
    css = client.get(reverse("ui:theme")).content.decode()
    assert css.startswith(":root{--ui-bg:#ffffff;")
    assert "--ui-accent:#6d28d9;" in css
    assert "--ui-accent:#a78bfa;" in css


def test_the_stylesheet_applies_the_brand(client, settings):
    settings.UI_BRAND = {"light": {"border": "#cccccc"}}
    css = client.get(reverse("ui:theme")).content.decode()
    assert "--ui-fg-muted:#5a6170;--ui-border:#cccccc;" in css
