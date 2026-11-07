from xsatz.config import load_env_file, read_env_file


def test_env_file_pairs_comments_and_quotes(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# Configuration\n"
        "\n"
        "XSATZ_LOGO=data/Brand/logo.svg\n"
        "XSATZ_COLOR=#711611\n"
        "EMPTY=\n"
        "QUOTED='a # b'\n"
        'export DOUBLE="x"\n'
        "WITH_COMMENT=value # explained\n"
        "not a pair\n",
        encoding="utf-8",
    )

    assert read_env_file(env) == {
        "XSATZ_LOGO": "data/Brand/logo.svg",
        "XSATZ_COLOR": "#711611",
        "EMPTY": "",
        "QUOTED": "a # b",
        "DOUBLE": "x",
        "WITH_COMMENT": "value",
    }


def test_environment_wins_over_the_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("XSATZ_COLOR=#711611\nXSATZ_LOGO=logo.svg\n", encoding="utf-8")
    environ = {"XSATZ_COLOR": "#000000"}

    taken = load_env_file(env, environ)

    assert taken == ["XSATZ_LOGO"]
    assert environ == {"XSATZ_COLOR": "#000000", "XSATZ_LOGO": "logo.svg"}


def test_missing_env_file_changes_nothing(tmp_path):
    environ: dict[str, str] = {}
    assert load_env_file(tmp_path / ".env", environ) == []
    assert environ == {}
