import base64
import io

import pymupdf
import pytest
from PIL import Image, ImageDraw

from xsatz.theme import (
    COLOR_ENV,
    LOGO_ENV,
    color_from_env,
    logo_from_env,
    parse_color,
    stamp_logo,
)


@pytest.fixture
def logo(tmp_path):
    """A red cross on a transparent square with a wide empty border, like a real logo file."""
    path = tmp_path / "logo.png"
    image = Image.new("RGBA", (400, 400), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.line((100, 150, 300, 250), fill=(210, 0, 30, 255), width=20)
    draw.line((100, 250, 300, 150), fill=(210, 0, 30, 255), width=20)
    image.save(path)
    return path


@pytest.fixture
def score(tmp_path):
    """Two landscape pages laid out like the X-Satz score style."""
    path = tmp_path / "score.pdf"
    doc = pymupdf.open()
    first = doc.new_page(width=842, height=595)
    first.insert_text((300, 60), "Example March", fontsize=24)
    first.insert_text((36, 95), "Full Score", fontsize=12)
    first.insert_text((100, 140), "Intro", fontsize=10)
    second = doc.new_page(width=842, height=595)
    second.insert_text((360, 36), "Example March", fontsize=10)
    second.insert_text((780, 36), "2 / 2", fontsize=10)
    doc.save(path)
    return path


def test_logo_on_every_page_and_rule_under_the_header(score, logo):
    before = logo.read_bytes()

    result = stamp_logo(score, logo)

    assert (result.pages, result.rules) == (2, 1)
    doc = pymupdf.open(score)
    first, second = doc[0], doc[1]
    assert len(first.get_images()) == 1
    assert len(second.get_images()) == 1
    (title,) = first.search_for("Example March")
    (logo_one,) = first.get_image_rects(first.get_images()[0][0])
    assert logo_one.x0 == pytest.approx(36)
    assert logo_one.x1 < title.x0  # left of the title, never on it
    assert logo_one.y0 < title.y1 and logo_one.y1 > title.y0  # on the title line
    (header,) = second.search_for("2 / 2")
    (logo_two,) = second.get_image_rects(second.get_images()[0][0])
    assert logo_two.height < logo_one.height
    lines = [d for d in second.get_drawings() if d["items"][0][0] == "l"]
    assert len(lines) == 1
    assert lines[0]["rect"].y0 > header.y1  # the rule runs under the header
    assert lines[0]["color"][0] > 0.6 and lines[0]["color"][1] < 0.2  # in the red of the logo
    assert logo.read_bytes() == before


def test_configured_colour_wins_over_the_logo(score, logo):
    result = stamp_logo(score, logo, color=parse_color("#1E50A0"))

    assert result.color == pytest.approx((0x1E / 255, 0x50 / 255, 0xA0 / 255))
    second = pymupdf.open(score)[1]
    (line,) = [d for d in second.get_drawings() if d["items"][0][0] == "l"]
    assert line["color"] == pytest.approx(result.color, abs=0.01)


@pytest.mark.parametrize("value", ["#d6001c", "D6001C", " #D6001C "])
def test_colours_are_read_as_hex(value):
    assert parse_color(value) == pytest.approx((0xD6 / 255, 0.0, 0x1C / 255))


@pytest.mark.parametrize("value", ["red", "#D600", "#D6001CFF", "rgb(214,0,28)"])
def test_other_colour_notations_are_refused(value):
    with pytest.raises(ValueError):
        parse_color(value)


def test_colour_from_env(monkeypatch):
    monkeypatch.delenv(COLOR_ENV, raising=False)
    assert color_from_env() is None
    monkeypatch.setenv(COLOR_ENV, "#000000")
    assert color_from_env() == (0.0, 0.0, 0.0)


def test_logo_stays_inside_the_printable_area(tmp_path, logo):
    path = tmp_path / "high.pdf"
    doc = pymupdf.open()
    doc.new_page(width=842, height=595).insert_text((300, 22), "Example March", fontsize=24)
    doc.save(path)

    stamp_logo(path, logo)

    page = pymupdf.open(path)[0]
    (rect,) = page.get_image_rects(page.get_images()[0][0])
    assert rect.y0 >= 5 / 25.4 * 72 - 0.01


SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">'
    '<path d="M100 150 L300 250 M100 250 L300 150" stroke="#D2001E" stroke-width="20"/>{extra}'
    "</svg>"
)


def test_svg_logo_is_stamped_as_vector_and_cut_to_its_drawing(score, tmp_path):
    logo = tmp_path / "logo.svg"
    logo.write_text(SVG.format(extra=""), encoding="utf-8")

    result = stamp_logo(score, logo)

    assert result.warnings == []
    assert result.color[0] > 0.6 and result.color[1] < 0.2
    first = pymupdf.open(score)[0]
    assert first.get_images() == []  # no raster image, the drawing stays vector
    (title,) = first.search_for("Example March")
    strokes = [d["rect"] for d in first.get_drawings() if d.get("color")]
    left = min(r.x0 for r in strokes)
    right = max(r.x1 for r in strokes)
    # The empty border of the SVG is cut away up to the ink. The path rectangle runs along the
    # middle of the stroke, half a stroke width inside the ink.
    assert 36 <= left < 36 + 4
    assert right < title.x0
    assert (right - left) / (max(r.y1 for r in strokes) - min(r.y0 for r in strokes)) > 1.5


def test_svg_logo_with_text_warns_about_the_substitute_font(score, tmp_path):
    logo = tmp_path / "logo.svg"
    logo.write_text(SVG.format(extra='<text x="100" y="210">BAND</text>'), encoding="utf-8")

    result = stamp_logo(score, logo)

    assert len(result.warnings) == 1
    assert "paths" in result.warnings[0]


def test_svg_with_embedded_images_is_stamped_as_one_small_image(score, tmp_path):
    big = Image.new("RGBA", (3000, 3000), (255, 255, 255, 0))
    ImageDraw.Draw(big).ellipse((500, 1000, 2500, 2000), fill=(210, 0, 30, 255))
    buffer = io.BytesIO()
    big.save(buffer, format="PNG")
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    logo = tmp_path / "logo.svg"
    logo.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
        ' viewBox="0 0 300 300"><image width="3000" height="3000" transform="scale(0.1)"'
        f' xlink:href="data:image/png;base64,{data}"/></svg>',
        encoding="utf-8",
    )

    stamp_logo(score, logo)

    for page in pymupdf.open(score):
        (image,) = page.get_images(full=True)
        width, height = image[2], image[3]
        assert max(width, height) <= 1600
        assert width / height == pytest.approx(2, rel=0.05)  # cut to the ellipse


def test_title_block_gets_a_rule_between_it_and_the_music(score, logo):
    result = stamp_logo(score, logo, title_block=["Full Score"])

    assert result.rules == 2
    first = pymupdf.open(score)[0]
    (label,) = first.search_for("Full Score")
    (intro,) = first.search_for("Intro")
    (line,) = [d for d in first.get_drawings() if d["items"][0][0] == "l"]
    assert label.y1 < line["rect"].y0 < intro.y0


def test_no_title_block_rule_without_room(tmp_path, logo):
    path = tmp_path / "tight.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((300, 60), "Example March", fontsize=24)
    page.insert_text((36, 95), "Full Score", fontsize=12)
    page.insert_text((100, 100), "Intro", fontsize=10)
    doc.save(path)

    result = stamp_logo(path, logo, title_block=["Full Score"])

    assert result.rules == 0


def test_missing_logo_is_an_error(score, tmp_path):
    with pytest.raises(FileNotFoundError):
        stamp_logo(score, tmp_path / "missing.png")


def test_logo_from_env(monkeypatch, tmp_path):
    monkeypatch.delenv(LOGO_ENV, raising=False)
    assert logo_from_env() is None
    monkeypatch.setenv(LOGO_ENV, str(tmp_path / "logo.png"))
    assert logo_from_env() == tmp_path / "logo.png"


def test_logo_shrinks_to_fit_left_of_a_long_title(tmp_path, logo):
    path = tmp_path / "portrait.pdf"
    doc = pymupdf.open()
    doc.new_page(width=595, height=842).insert_text((70, 60), "A Long Example", fontsize=24)
    doc.save(path)

    stamp_logo(path, logo, margin=42)

    page = pymupdf.open(path)[0]
    (title,) = page.search_for("A Long Example")
    (rect,) = page.get_image_rects(page.get_images()[0][0])
    assert rect.x0 == pytest.approx(42)
    assert rect.x1 <= title.x0 - 6 + 0.01


def test_title_block_is_measured_by_its_glyphs_for_the_rule(tmp_path, logo):
    # The box of an italic label reaches below its letters and would leave no room.
    path = tmp_path / "tight.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((200, 60), "Example March", fontsize=24)
    page.insert_text((42, 95), "Horn", fontsize=12, fontname="tiit")
    page.insert_text((100, 112.5), "Intro", fontsize=10)
    doc.save(path)

    result = stamp_logo(path, logo, margin=42, title_block=["Horn"])

    assert result.rules == 1
    (line,) = [d for d in pymupdf.open(path)[0].get_drawings() if d["items"][0][0] == "l"]
    assert 95.1 < line["rect"].y0 < 102.2
