#!/bin/bash

WORK_DIR="$(dirname "$0")"
PROJECT_DIR="$(dirname "$WORK_DIR")"

uv --version >/dev/null 2>&1 || {
    echo >&2 -e "\nuv is required but it's not installed."
    echo >&2 -e "You can install it by following the instructions at https://github.com/astral-sh/uv#installation"
    exit 1;
}

# No ``--locked``: the lock file is written by this first sync when the project
# does not have one yet.
uv sync
