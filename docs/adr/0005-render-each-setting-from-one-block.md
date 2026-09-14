---
status: accepted
---

# Render each setting from one block

The settings templates used to spell out one copy of a setting per combination of answers.
`config/settings/production.py` held three storage cells for cloud provider × WhiteNoise, one
mail block per service and the whole `LOGGING` dictionary twice, with and without Sentry, six
lines differing between copies that were thirty-five lines long. `config/settings/local.py`
held one mail block per mail catcher × Docker, five in all. A review proposed Jinja tables at
the top of each template with one rendered block per setting, the generated file staying the
same.

Each setting is now rendered from one block. Where the answers are independent axes, the block
forks on each axis at the place it decides: `STORAGES` forks the uploads on the cloud provider
and the static files on WhiteNoise, `LOGGING` forks on Sentry at the four places the two
configurations differ. Where the answer is a choice from a list, the data of every choice is a
table at the top of the template and the block renders the chosen row: for the mail service its
page in the Anymail documentation, its email backend and the `ANYMAIL` settings it reads as
(setting, variable, default) triples; for the mail catcher its Compose service and port. The
answers a module forks on are bound to names once at its top.

The rendered projects are byte-identical for every supported combination, checked by baking
all of them before and after the change and comparing every file with the drawn secrets
masked. The one difference is a blank line that the old `LOGGING` fork left before the
dictionary in the Sentry rendering and the new one does not.

## Considered options

- **One copy per cell**, the previous state: adding a provider or service means editing every
  cell it touches, and what differs between two cells is found by comparing them by eye.
- **A table for every axis**, the cloud provider included: with AWS the only provider, its row
  would hold the S3 options, the credentials block and the URLs, which is code kept as data,
  and the `None` row would hold nothing. The fork on the axis reads better.
- **Rows that hold Python**, for the `ANYMAIL` dictionaries: the rows hold the setting names,
  the environment variables and the defaults, and the block renders the `env()` calls. A
  service whose settings need another kind of read extends the block, not the rows.
- **Tables in the generated file**, a dictionary of every provider or service keyed by an
  answer read at runtime: every project would carry every provider's configuration, against
  the rule that a generated project holds only what it chose.

## Consequences

A new mail service or mail catcher is a row in the table, next to the pin, the option and its
documentation. The generation tests pin the rendered cells through the reader: the storage
backends per (cloud provider, WhiteNoise) cell, the email backend, the pin's extra and the
`ANYMAIL` reads per mail service, and the host and port per mail catcher with and without
Docker, which needs two paired rows in the matrix because the catcher's Docker arm was
reached by no combination before. The `LOGGING` block shows what its two configurations
differ in; whether they should differ is not decided here.
