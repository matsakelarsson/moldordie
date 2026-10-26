"""The renaming of the app template: each placeholder in each form, whole names only,
in one pass; and the names the template has already, which a new name cannot be."""

import pytest

from {{ cookiecutter.project_slug }}.scaffold.names import Names
from {{ cookiecutter.project_slug }}.scaffold.names import camel_case
from {{ cookiecutter.project_slug }}.scaffold.names import clashes
from {{ cookiecutter.project_slug }}.scaffold.names import identifiers_of
from {{ cookiecutter.project_slug }}.scaffold.names import rename

NAMES = Names(app="blog", model="Post")


@pytest.mark.parametrize(
    ("text", "renamed"),
    [
        ('name = "p.scaffold.app_template"', 'name = "p.blog"'),
        ("class AppTemplateConfig(AppConfig)", "class BlogConfig(AppConfig)"),
        ('app_name = "app_template"', 'app_name = "blog"'),
        ("admin:app_template_item_changelist", "admin:blog_post_changelist"),
        ("templates/app_template/item_list.html", "templates/blog/post_list.html"),
        ("class ItemForm(ModelForm[Item])", "class PostForm(ModelForm[Post])"),
        ("No item yet, Item 1", "No post yet, Post 1"),
        ('id="item-card"', 'id="post-card"'),
        ("list_items, Items", "list_posts, Posts"),
        ("def list_items(request)", "def list_posts(request)"),
        # Not the model's name: Tailwind's and daisyUI's class names, a word that
        # contains it, an attribute of something else (a dict's items, in Python or a
        # template)
        ('class="join-item items-center list-item"', None),
        ("MenuItem, data.items(), data.items, self.item", None),
    ],
)
def test_rename(text: str, renamed: str | None):
    assert rename(text, NAMES) == (text if renamed is None else renamed)


def test_a_multiword_model_is_lowercased_as_django_spells_it():
    names = Names(app="blog", model="BlogPost")

    renamed = rename("item_list.html, Items, items", names)

    assert renamed == "blogpost_list.html, BlogPosts, blogposts"


@pytest.mark.parametrize(
    ("names", "text", "renamed"),
    [
        (
            Names(app="item_tracker", model="Tracker"),
            'app_name = "app_template", for item in item_list',
            'app_name = "item_tracker", for tracker in tracker_list',
        ),
        (
            Names(app="items", model="Items"),
            "class AppTemplateConfig, Items, items",
            "class ItemsConfig, Itemss, itemss",
        ),
        (
            Names(app="blog", model="ItemGroup"),
            "Items, ItemForm",
            "ItemGroups, ItemGroupForm",
        ),
    ],
)
def test_a_name_that_holds_a_placeholder_word_is_put_in_once(names, text, renamed):
    assert rename(text, names) == renamed


def test_camel_case():
    assert camel_case("blog") == "Blog"
    assert camel_case("blog_posts") == "BlogPosts"


IDENTIFIERS = {"page", "element", "FilterForm", "ItemForm", "item", "Item", "list"}


@pytest.mark.parametrize(
    ("model", "taken"),
    [
        ("Post", set()),
        ("Page", {"page"}),
        ("Filter", {"FilterForm"}),
        ("List", {"list"}),
    ],
)
def test_clashes_are_the_names_the_renaming_would_double(model, taken):
    assert clashes(Names(app="blog", model=model), IDENTIFIERS) == taken


def test_identifiers_of_reads_the_python_and_the_templates(tmp_path):
    (tmp_path / "views.py").write_text(
        "from a.b import page as whole\nimport re\n\n\ndef f(item):\n"
        "    name = Item(item)\n\n\nclass ItemForm:\n    pass\n",
    )
    (tmp_path / "t.html").write_text(
        "{% raw %}{% for item in item_list %}{{ opts.name }}{% endfor %}"
        "{% with total=1 %}{% if not query %}x{% endif %}{% endwith %}{% endraw %}",
    )

    found = identifiers_of(tmp_path)

    bound = {"whole", "re", "f", "item", "name", "Item", "ItemForm"}
    named = {"item_list", "opts", "total", "query"}
    assert bound | named <= found
    assert not {"a", "b", "page", "for", "endfor", "with", "x"} & found
