from pathlib import Path

import pytest

from xsatz.config import Settings, read_settings

EXAMPLE = Path(__file__).parents[1] / "x-satz.example.conf"


def test_theme_with_a_logo_relative_to_the_file(tmp_path):
    conf = tmp_path / "x-satz.conf"
    conf.write_text('[theme]\nlogo = "design/logo.svg"\ncolor = "#711611"\n', encoding="utf-8")

    settings = read_settings(conf)

    assert settings == Settings(logo=tmp_path / "design" / "logo.svg", color="#711611")


def test_missing_file_and_empty_values_give_empty_settings(tmp_path):
    assert read_settings(tmp_path / "x-satz.conf") == Settings()
    conf = tmp_path / "x-satz.conf"
    conf.write_text('[theme]\nlogo = ""\n', encoding="utf-8")
    assert read_settings(conf) == Settings()


@pytest.mark.parametrize(
    "content",
    ['[brand]\nlogo = "a.svg"\n', '[theme]\nlogos = "a.svg"\n', "theme = 1\n", "[theme\n"],
)
def test_unknown_sections_keys_and_broken_toml_are_errors(tmp_path, content):
    conf = tmp_path / "x-satz.conf"
    conf.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="x-satz.conf"):
        read_settings(conf)


def test_example_file_is_valid():
    settings = read_settings(EXAMPLE)
    assert settings.logo is not None and settings.color == "#000000"
