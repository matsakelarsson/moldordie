"""django-allauth in daisyUI's classes: its elements, overridden under
``templates/allauth/elements/``, and the card each of its layouts gives a page."""

from http import HTTPStatus

import pytest
from allauth.account.models import EmailAddress
from django.forms.utils import ErrorList
from django.template.loader import render_to_string
from django.urls import reverse

from {{ cookiecutter.project_slug }}.tests.markup import element
from {{ cookiecutter.project_slug }}.tests.markup import elements

CARD = "card card-border bg-base-100 shadow-sm"
# The account card: a second-level heading at top level starts a section under a rule
ACCOUNT_BODY = (
    "card-body gap-4 [&>h2]:border-base-300 [&>h2]:mt-2 [&>h2]:border-t [&>h2]:pt-6"
)
# A panel: the same rule, its title in one of three columns, the rest in the other two
SECTION = "border-base-300 mt-2 grid gap-2 border-t pt-6 sm:grid-cols-3 sm:gap-6"
SECTION_BODY = "flex flex-col gap-4 sm:col-span-2"
ACTIONS = {"class": "flex flex-wrap items-center gap-2"}
HEADING = {"class": "text-lg font-semibold"}
CHECK_LABEL = "label text-base-content whitespace-normal"
ARIA = {"aria-invalid": "true", "aria-describedby": "mail_helptext mail_error"}


def of_class(html, tag, prefix):
    """The ``tag`` elements whose class starts with ``prefix``."""
    found = elements(html, tag)
    return [attrs for attrs in found if (attrs.get("class") or "").startswith(prefix)]


@pytest.fixture
def html(rf, fixture_templates):
    context = {"errors": ErrorList(["Bad address"], field_id="mail")}
    return render_to_string("tests/allauth.html", context, request=rf.get("/"))


def test_a_button_is_a_link_with_an_href_and_submits_without(html):
    remove, act, acme, wide = elements(html, "a")
    # a destructive link opens a page that asks first, so it is quiet
    assert remove == {"href": "/remove/", "class": "btn btn-ghost text-error"}
    assert act == {"href": "/act/", "class": "btn btn-primary"}
    # prominent is full width and outline an outline; neither chooses the colour
    assert wide == {"href": "/wide/", "class": "btn btn-primary btn-outline btn-block"}
    # a provider is a full-width link, named in its title as well
    assert acme == {"href": "/acme/", "class": "btn btn-block", "title": "Acme"}

    skip, go, delete = elements(html, "button")
    # a value is written even when empty; link is the quiet button
    assert skip == {
        "type": "submit",
        "class": "btn btn-ghost",
        "name": "action",
        "value": "",
    }
    # secondary is allauth's lesser action: the plain button, not a colour
    assert go == {"type": "submit", "class": "btn", "form": "other", "id": "go"}
    # a destructive button acts at once, so it is red
    assert delete == {
        "type": "submit",
        "class": "btn btn-error",
        "name": "action_remove",
    }


def test_badges_and_alerts_take_their_colour_from_allauth(html):
    badges = of_class(html, "span", "badge")
    assert [attrs["class"] for attrs in badges] == [
        "badge badge-sm badge-soft badge-success",
        "badge badge-sm badge-soft badge-error",
        "badge badge-sm badge-soft badge-primary",
        "badge badge-sm badge-soft badge-neutral",
    ]
    assert [attrs for attrs in badges if "title" in attrs] == [
        {"class": "badge badge-sm badge-soft badge-error", "title": "Why"},
    ]
    # in the page from the start, so it has no role and is not announced
    assert of_class(html, "div", "alert") == [{"class": "alert alert-info"}]


def test_the_structural_elements(html):
    # panel: a section under a rule, its heading beside its body and its actions
    assert element(html, "section") == {"class": SECTION}
    assert elements(html, "h2") == [HEADING, HEADING]
    assert of_class(html, "div", SECTION_BODY) == [{"class": SECTION_BODY}]
    # the panel's actions and the form's are the same row
    assert of_class(html, "div", ACTIONS["class"]) == [ACTIONS, ACTIONS]
    assert element(html, "h1") == {"class": "text-2xl font-bold"}
    assert element(html, "hr") == {"class": "border-base-300"}
    assert len(of_class(html, "div", "flex gap-2 flex-col")) == 1
    assert element(html, "details") == {
        "class": "collapse collapse-arrow border-base-300 bg-base-100 border",
    }
    assert element(html, "summary") == {"class": "collapse-title font-semibold"}
    assert element(html, "form") == {
        "class": "flex flex-col gap-4",
        "method": "post",
        "action": "/send/",
    }
    assert element(html, "img") == {
        "class": "rounded-box w-64 bg-white p-2",
        "src": "/qr.svg",
        "alt": "QR code",
    }
    assert element(html, "table") == {"class": "table"}
    lists = [attrs for attrs in elements(html, "ul") if "id" not in attrs]
    assert lists == [{"class": "flex flex-col gap-2"}]


def test_a_field_names_its_help_text_and_its_errors(html):
    mail, saved, pick = elements(html, "input")[:3]
    assert mail == {
        "class": "input aria-invalid:input-error w-full",
        "name": "email",
        "id": "mail",
        "value": "a@example.com",
        **ARIA,
        "type": "email",
    }
    assert saved == {
        "class": "checkbox aria-invalid:checkbox-error",
        "name": "saved",
        "id": "saved",
        "type": "checkbox",
    }
    assert pick == {
        "class": "radio aria-invalid:radio-error",
        "name": "pick",
        "id": "pick",
        "value": "1",
        "type": "radio",
    }
    assert element(html, "textarea") == {
        "class": "textarea aria-invalid:textarea-error w-full",
        "rows": "3",
        "name": "bio",
        "id": "bio",
    }
    assert elements(html, "label") == [
        {"class": "fieldset-legend", "for": "mail"},
        {"class": CHECK_LABEL, "for": "saved"},
        {"class": "fieldset-legend", "for": "bio"},
        {"class": CHECK_LABEL, "for": "pick"},
    ]
    assert of_class(html, "div", "text-base-content/70") == [
        {"class": "text-base-content/70", "id": "mail_helptext"},
    ]
    errors = [attrs for attrs in elements(html, "ul") if "id" in attrs]
    assert errors == [{"class": "errorlist text-error text-sm", "id": "mail_error"}]


@pytest.mark.django_db
class TestPages:
    def test_the_entrance_pages_are_one_card(self, client):
        for name in ("account_login", "account_signup"):
            response = client.get(reverse(name))

            assert response.status_code == HTTPStatus.OK
            html = response.content.decode()
            assert of_class(html, "div", "card ") == [{"class": CARD}]
            assert of_class(html, "div", "card-body") == [{"class": "card-body gap-4"}]
            assert 'class="fieldset"' in html
            buttons = elements(html, "button")
            submits = [attrs for attrs in buttons if attrs.get("type") == "submit"]
            assert (submits[0]["class"] or "").startswith("btn btn-primary")
            assert element(html, "h1") == {"class": "text-2xl font-bold"}

    @pytest.mark.parametrize(
        "name",
        ["account_email", "account_change_password", "mfa_index", "account_logout"],
    )
    def test_an_account_page_is_one_card(self, user, client, name):
        client.force_login(user)

        response = client.get(reverse(name))

        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        assert len(of_class(html, "div", "mx-auto w-full max-w-2xl")) == 1
        assert of_class(html, "div", "card ") == [{"class": CARD}]
        assert of_class(html, "div", "card-body") == [{"class": ACCOUNT_BODY}]
        assert element(html, "h1") == {"class": "text-2xl font-bold"}

    def test_the_password_page_labels_its_fields(self, user, client):
        client.force_login(user)

        response = client.get(reverse("account_change_password"))

        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        # The form's labels; the drawer's two are the sidebar's, on every page
        assert of_class(html, "label", "fieldset-legend") == [
            {"class": "fieldset-legend", "for": "id_oldpassword"},
            {"class": "fieldset-legend", "for": "id_password1"},
            {"class": "fieldset-legend", "for": "id_password2"},
        ]

    def test_the_two_factor_page_is_sections(self, user, client):
        client.force_login(user)

        response = client.get(reverse("mfa_index"))

        assert response.status_code == HTTPStatus.OK
        html = response.content.decode()
        sections = elements(html, "section")
        assert sections
        assert all(attrs == {"class": SECTION} for attrs in sections)
        assert len(of_class(html, "h2", HEADING["class"])) == len(sections)
        # the authenticator app's action, a link to its activation page
        activate = element(html, "a", "href", reverse("mfa_activate_totp"))
        assert activate["class"] == "btn btn-primary"

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
        badges = of_class(html, "span", "badge")
        assert [attrs["class"] for attrs in badges] == [
            "badge badge-sm badge-soft badge-success",
            "badge badge-sm badge-soft badge-primary",
        ]
        # removing an address acts at once, so that button is red
        remove = element(html, "button", "name", "action_remove")
        assert remove["class"] == "btn btn-error"
