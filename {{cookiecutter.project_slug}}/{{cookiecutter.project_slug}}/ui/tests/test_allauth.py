"""django-allauth on the UI library: its elements on the components, and its pages."""

from http import HTTPStatus

import pytest
from allauth.account.models import EmailAddress
from django.forms.utils import ErrorList
from django.template.loader import render_to_string
from django.urls import reverse

from {{ cookiecutter.project_slug }}.ui.tests.markup import element
from {{ cookiecutter.project_slug }}.ui.tests.markup import elements


def badge_classes(html):
    spans = elements(html, "span")
    return [a["class"] for a in spans if (a.get("class") or "").startswith("ui-badge")]


def divs_of_class(html, css_class):
    return [a for a in elements(html, "div") if a.get("class") == css_class]


@pytest.mark.usefixtures("fixture_templates")
def test_the_elements_map_onto_the_components(rf):
    context = {"errors": ErrorList(["Bad address"], field_id="mail")}
    html = render_to_string("tests/allauth.html", context, request=rf.get("/"))

    # button: a button-link with an href, else a submit button; the tags choose
    remove, act, acme = elements(html, "a")
    assert remove == {"href": "/remove/", "class": "ui-button ui-button-danger"}
    assert act == {"href": "/act/", "class": "ui-button ui-button-primary"}
    skip, go = elements(html, "button")
    assert skip == {
        "type": "submit",
        "class": "ui-button ui-button-quiet",
        "name": "action",
        "value": "",
    }
    assert go == {
        "type": "submit",
        "class": "ui-button ui-button-secondary",
        "form": "other",
        "id": "go",
    }

    assert badge_classes(html) == [
        "ui-badge ui-badge-success",
        "ui-badge ui-badge-error",
        "ui-badge ui-badge-info",
        "ui-badge ui-badge-neutral",
    ]
    assert [a for a in elements(html, "span") if "title" in a] == [
        {"class": "ui-badge ui-badge-error", "title": "Why"},
    ]

    # alert: in the page from the start, so not announced
    alerts = [a for a in elements(html, "div") if "data-ui-alert" in a]
    assert alerts == [{"class": "ui-alert ui-alert-info", "data-ui-alert": None}]

    # panel: a card with a second-level heading and the actions in the footer
    assert element(html, "article") == {"class": "ui-card"}
    assert element(html, "h2") == {}
    assert element(html, "footer") == {"class": "ui-card-actions ui-actions"}

    assert len(divs_of_class(html, "ui-actions ui-actions-vertical")) == 1

    # provider list: secondary button-links
    assert acme == {
        "href": "/acme/",
        "class": "ui-button ui-button-secondary",
        "title": "Acme",
    }
    assert [a for a in elements(html, "ul") if "class" in a] == [
        {"class": "ui-provider-list"},
        {"class": "errorlist", "id": "mail_error"},
    ]

    # field: the component's wrappers, the help text and the error list associated
    assert elements(html, "input") == [
        {
            "name": "email",
            "id": "mail",
            "value": "a@example.com",
            "aria-invalid": "true",
            "aria-describedby": "mail_helptext mail_error",
            "type": "email",
        },
        {"name": "saved", "id": "saved", "type": "checkbox"},
    ]
    assert elements(html, "label") == [
        {"class": "ui-label", "for": "mail"},
        {"class": "ui-label ui-label-check", "for": "saved"},
    ]
    assert divs_of_class(html, "ui-help") == [
        {"class": "ui-help", "id": "mail_helptext"},
    ]


@pytest.mark.django_db
class TestPages:
    def test_the_entrance_pages_are_one_card(self, client):
        for name in ("account_login", "account_signup"):
            response = client.get(reverse(name))

            assert response.status_code == HTTPStatus.OK
            html = response.content.decode()
            assert '<div class="ui-entrance">' in html
            assert elements(html, "article") == [{"class": "ui-card"}]
            assert 'class="ui-field' in html
            buttons = elements(html, "button")
            submits = [a for a in buttons if a.get("type") == "submit"]
            assert submits[0]["class"] == "ui-button ui-button-primary"

    def test_the_password_page_is_one_card(self, user, client):
        client.force_login(user)

        response = client.get(reverse("account_change_password"))

        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        assert elements(html, "article") == [{"class": "ui-card"}]
        assert elements(html, "label") == [
            {"class": "ui-label", "for": "id_oldpassword"},
            {"class": "ui-label", "for": "id_password1"},
            {"class": "ui-label", "for": "id_password2"},
        ]

    def test_the_management_pages_stack_their_panels(self, user, client):
        client.force_login(user)

        response = client.get(reverse("mfa_index"))

        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        assert '<div class="ui-stack">' in html
        cards = elements(html, "article")
        assert cards
        assert all(attrs == {"class": "ui-card"} for attrs in cards)
        assert elements(html, "h2")

    def test_the_email_page_shows_its_badges(self, user, client):
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=True,
            primary=True,
        )
        client.force_login(user)

        response = client.get(reverse("account_email"))

        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        assert badge_classes(html) == [
            "ui-badge ui-badge-success",
            "ui-badge ui-badge-info",
        ]
