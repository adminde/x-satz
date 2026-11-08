from pathlib import Path

import pytest

from xsatz.config import Settings, read_settings
from xsatz.sounds import AudioSettings, CountIn, PartSound, Sound

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


def test_example_file_is_valid_and_leaves_the_theme_to_the_user():
    settings = read_settings(EXAMPLE)
    assert settings.logo is None and settings.color is None


def test_example_file_holds_the_audio_of_a_b_flat_band():
    audio = read_settings(EXAMPLE).audio

    assert audio.transpose["brass.trumpet"] == -2
    assert audio.transpose["brass.tuba"] == -14
    assert audio.count_in == CountIn(31, "f")
    sonatina = "Sonatina_Symphonic_Orchestra"
    assert audio.sounds["brass.trumpet"] == Sound(sonatina, 0, 27, 0.5, 0.01)
    assert audio.sounds["brass.trombone"] == Sound(sonatina, 0, 31, 0.5, 0.01)
    assert audio.softer == 21
    # The family names the SoundFont once and is no sound of its own.
    assert "brass" not in audio.sounds


def test_without_audio_section_the_score_plays_as_written(tmp_path):
    assert read_settings(tmp_path / "x-satz.conf").audio == AudioSettings()


def test_audio_settings_are_read(tmp_path):
    conf = tmp_path / "x-satz.conf"
    conf.write_text(
        "[audio]\nsofter = 9\nreverb = 0.5\n[audio.count_in]\n"
        '[audio.transpose]\n"brass" = -2\n'
        '[audio.sounds]\n"drum" = { soundfont = "Kit", bank = 128 }\n',
        encoding="utf-8",
    )

    audio = read_settings(conf).audio

    assert audio == AudioSettings(
        transpose={"brass": -2},
        sounds={"drum": Sound("Kit", 128, None)},
        count_in=CountIn(),
        reverb=0.5,
        softer=9.0,
    )


@pytest.mark.parametrize(
    "content",
    [
        "[audio]\nloud = 1\n",
        "[audio]\nreverb = 2\n",
        '[audio]\nsofter = "a"\n',
        '[audio.count_in]\ndynamic = "loud"\n',
        "[audio.count_in]\nkey = 200\n",
        '[audio.transpose]\n"brass" = "low"\n',
        '[audio.sounds]\n"brass" = { program = 3 }\n',
        '[audio.sounds]\n"brass" = { soundfont = "A", preset = 3 }\n',
        '[audio.sounds.brass]\nsoundfont = "A"\ntrumpet = 3\n',
        '[audio.sounds]\n"brass" = { soundfont = "A", volume = 20 }\n',
    ],
)
def test_wrong_audio_settings_are_errors(tmp_path, content):
    conf = tmp_path / "x-satz.conf"
    conf.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="audio"):
        read_settings(conf)


def test_nested_tables_give_the_instrument_sounds_and_pass_on_the_soundfont(tmp_path):
    conf = tmp_path / "x-satz.conf"
    conf.write_text(
        "[audio.transpose.brass]\ntrumpet = -2\ntuba = -14\n"
        '[audio.sounds.brass]\nsoundfont = "Orchestra"\nbank = 1\n'
        "trumpet.program = 27\n"
        'tuba = { soundfont = "Other", program = 34 }\n'
        '[audio.sounds.metal]\nsoundfont = "Kit"\n',
        encoding="utf-8",
    )

    audio = read_settings(conf).audio

    assert audio.transpose == {"brass.trumpet": -2, "brass.tuba": -14}
    assert audio.sounds == {
        "brass.trumpet": Sound("Orchestra", 1, 27),
        "brass.tuba": Sound("Other", 1, 34),
        # A family without instruments of its own is a sound for all of it.
        "metal": Sound("Kit", 0, None),
    }


def test_parts_shaping_and_the_soundfont_dir_are_read(tmp_path):
    conf = tmp_path / "x-satz.conf"
    conf.write_text(
        '[audio]\nsoundfont_dir = "fonts"\n'
        '[audio.sounds.brass]\nsoundfont = "Orchestra"\nswell = 0.5\n'
        "[audio.sounds.brass.horn]\nprogram = 29\nfade_in = 0.01\n"
        "[audio.sounds.brass.tuba]\nprogram = 34\nswell = 0.3\n"
        '[audio.sounds.parts."Trompete 3"]\nprogram = 28\nfade_in = 0.02\n',
        encoding="utf-8",
    )

    audio = read_settings(conf).audio

    # An instrument inherits swell and fade-in from its family and may change them.
    assert audio.sounds == {
        "brass.horn": Sound("Orchestra", 0, 29, 0.5, 0.01),
        "brass.tuba": Sound("Orchestra", 0, 34, 0.3, None),
    }
    assert audio.parts == {"Trompete 3": PartSound(program=28, fade_in=0.02)}
    assert audio.soundfont_dir == tmp_path / "fonts"


def test_example_file_shapes_sonatina_and_gives_trumpet_3_the_section():
    audio = read_settings(EXAMPLE).audio

    assert audio.parts["Trompete 3"] == PartSound(program=28)
    assert audio.soundfont_dir is not None


@pytest.mark.parametrize(
    "content",
    [
        "[audio.sounds.parts.A]\nvolume = 3\n",
        "[audio.sounds.parts.A]\nprogram = 300\n",
        '[audio.sounds.brass]\nsoundfont = "A"\nswell = 1.5\n',
        '[audio.sounds.brass]\nsoundfont = "A"\nfade_in = -1\n',
        "[audio]\nsoundfont_dir = 3\n",
        '[audio.soundfonts.A]\nfile = "a.sf2"\n',
    ],
)
def test_wrong_parts_and_soundfonts_are_errors(tmp_path, content):
    conf = tmp_path / "x-satz.conf"
    conf.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="audio"):
        read_settings(conf)


def test_a_tilde_in_the_soundfont_dir_stands_for_the_home_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    conf = tmp_path / "x-satz.conf"
    conf.write_text('[audio]\nsoundfont_dir = "~/fonts"\n', encoding="utf-8")

    assert read_settings(conf).audio.soundfont_dir == tmp_path / "home" / "fonts"


def test_output_asks_for_the_musescore_files(tmp_path):
    conf = tmp_path / "x-satz.conf"
    conf.write_text("[output]\nmscz = true\n", encoding="utf-8")
    assert read_settings(conf).mscz is True
    assert read_settings(EXAMPLE).mscz is False

    conf.write_text('[output]\nmscz = "yes"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="mscz must be true or false"):
        read_settings(conf)


def test_output_asks_for_midi_files(tmp_path):
    conf = tmp_path / "x-satz.conf"
    conf.write_text("[output]\nmidi = true\n", encoding="utf-8")
    assert (read_settings(conf).midi, read_settings(conf).mscz) == (True, False)

    conf.write_text("[output]\nmidi = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="midi must be true or false"):
        read_settings(conf)
