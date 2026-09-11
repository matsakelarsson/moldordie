"""Unit tests for the hooks"""

import os
from pathlib import Path

import pytest

from hooks.post_gen_project import append_to_gitignore_file
from hooks.post_gen_project import remove_channels_files


@pytest.fixture
def working_directory(tmp_path):
    prev_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(prev_cwd)


def test_append_to_gitignore_file(working_directory):
    gitignore_file = working_directory / ".gitignore"
    gitignore_file.write_text("node_modules/\n")
    append_to_gitignore_file(".envs/*")
    linesep = os.linesep.encode()
    assert gitignore_file.read_bytes() == b"node_modules/" + linesep + b".envs/*" + linesep
    assert gitignore_file.read_text() == "node_modules/\n.envs/*\n"


@pytest.fixture
def channels_files(working_directory):
    """The files that only exist for ``realtime=channels``, laid out as the unrendered hook expects."""
    (working_directory / "config").mkdir()
    (working_directory / "config" / "websocket.py").touch()
    tests_path = working_directory / "{{ cookiecutter.project_slug }}" / "tests"
    tests_path.mkdir(parents=True)
    (tests_path / "__init__.py").touch()
    (tests_path / "test_websocket.py").touch()
    return tests_path


def test_remove_channels_files_drops_the_package_when_only_the_websocket_test_lives_there(channels_files):
    remove_channels_files()
    assert not (channels_files.parent.parent / "config" / "websocket.py").exists()
    assert not channels_files.exists()


def test_remove_channels_files_keeps_other_tests(channels_files):
    other_test = channels_files / "test_urls.py"
    other_test.touch()
    remove_channels_files()
    assert not (channels_files / "test_websocket.py").exists()
    assert other_test.exists()
    assert (channels_files / "__init__.py").exists()
