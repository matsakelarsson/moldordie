import json
import re
import sys

TERMINATOR = "\x1b[0m"
WARNING = "\x1b[1;33m [WARNING]: "
INFO = "\x1b[1;33m [INFO]: "
HINT = "\x1b[3;33m"
SUCCESS = "\x1b[1;32m [SUCCESS]: "

# The content of this string is evaluated by Jinja, and plays an important role.
# It updates the cookiecutter context to trim leading and trailing spaces
# from domain/email values
"""
{{ cookiecutter.update({ "domain_name": cookiecutter.domain_name | trim }) }}
{{ cookiecutter.update({ "email": cookiecutter.email | trim }) }}
"""

# The answers enter here as JSON, rendered after the update above, so that a
# free-text answer cannot break this script.
context = json.loads(r"""{{ cookiecutter | tojson }}""")

project_slug = context["project_slug"]
assert project_slug.isidentifier(), f"'{project_slug}' project slug is not a valid Python identifier."
assert project_slug == project_slug.lower(), f"'{project_slug}' project slug should be all lowercase"

# Escaping (see CONTEXT.md) makes any other character safe in the generated files.
FREE_TEXT_OPTIONS = ("project_name", "description", "author_name", "email", "domain_name", "version", "timezone")
for option in FREE_TEXT_OPTIONS:
    assert not re.search(r"[\x00-\x1f\x7f]", context[option]), (
        f"Don't include control characters (such as line breaks) in {option}."
    )
# Traefik's Host() rules embed the domain name with no escape, so only letters (in any
# script), digits, dots, hyphens and underscores may appear in it.
assert re.fullmatch(r"[\w.-]+", context["domain_name"]), (
    "Domain name may only contain letters, digits, dots, hyphens and underscores."
)

if context["use_whitenoise"].lower() == "n" and context["cloud_provider"] == "None":
    print("You should either use Whitenoise or select a Cloud Provider to serve static files")
    sys.exit(1)

if context["mail_service"] == "Amazon SES" and context["cloud_provider"] != "AWS":
    print("You should either use AWS or select a different Mail Service for sending emails.")
    sys.exit(1)
