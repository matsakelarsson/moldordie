import json
import re
import sys

# The content of this string is evaluated by Jinja, and plays an important role.
# It updates the cookiecutter context before any project file is rendered: it
# trims leading and trailing spaces from the domain and email values, and it
# lowercases every flag option, so that the templates and both hooks all read
# them in one spelling. The catalogue in local_extensions.py says which options
# are flags; this script runs on its own and cannot import it, so it reads the
# catalogue through the option_names global that the catalogue's extension
# registers for the render.
"""
{{ cookiecutter.update({ "domain_name": cookiecutter.domain_name | trim }) }}
{{ cookiecutter.update({ "email": cookiecutter.email | trim }) }}
{% for name in option_names("flag") -%}
{{ cookiecutter.update({ name: cookiecutter[name] | lower }) }}
{% endfor -%}
"""

# The answers enter here as JSON, rendered after the update above, so that a
# free-text answer cannot break this script. The option names arrive the same way.
context = json.loads(r"""{{ cookiecutter | tojson }}""")
FREE_TEXT_OPTIONS = json.loads(r"""{{ option_names("free text") | tojson }}""")
FLAG_OPTIONS = json.loads(r"""{{ option_names("flag") | tojson }}""")

project_slug = context["project_slug"]
assert project_slug.isidentifier(), f"'{project_slug}' project slug is not a valid Python identifier."
assert project_slug == project_slug.lower(), f"'{project_slug}' project slug should be all lowercase"

# Escaping (see CONTEXT.md) makes any other character safe in the generated files.
for option in FREE_TEXT_OPTIONS:
    assert not re.search(r"[\x00-\x1f\x7f]", context[option]), (
        f"Don't include control characters (such as line breaks) in {option}."
    )
# Traefik's Host() rules embed the domain name with no escape, so only letters (in any
# script), digits, dots, hyphens and underscores may appear in it.
assert re.fullmatch(r"[\w.-]+", context["domain_name"]), (
    "Domain name may only contain letters, digits, dots, hyphens and underscores."
)

# The yes/no answers are typed as text, so unlike the list options Cookiecutter does not
# validate them. Lowercased above, anything but y or n is a typo that would otherwise
# silently generate the wrong project.
for option in FLAG_OPTIONS:
    assert context[option] in ("y", "n"), f"{option} must be answered with y or n, not {context[option]!r}."

if context["use_whitenoise"] == "n" and context["cloud_provider"] == "None":
    print("You should either use Whitenoise or select a Cloud Provider to serve static files")
    sys.exit(1)

if context["mail_service"] == "Amazon SES" and context["cloud_provider"] != "AWS":
    print("You should either use AWS or select a different Mail Service for sending emails.")
    sys.exit(1)
