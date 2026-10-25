"""The renaming of the app template: each placeholder in each form, whole names only."""

import pytest

from {{ cookiecutter.project_slug }}.scaffold.names import Names
from {{ cookiecutter.project_slug }}.scaffold.names import camel_case
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


def test_camel_case():
    assert camel_case("blog") == "Blog"
    assert camel_case("blog_posts") == "BlogPosts"
