import pymupdf

from xsatz.compare import compare


def _pdf(path, text):
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((100, 100), text, fontsize=40)
    doc.save(path)


def test_identical_pdfs_overlap_fully(tmp_path):
    a = tmp_path / "a.pdf"
    _pdf(a, "X-Treme")
    res = compare(a, a, tmp_path / "cmp")
    assert res.pages_ref == res.pages_new == 1
    assert res.mean_overlap == 1.0
    assert (tmp_path / "cmp" / "overlay-01.png").exists()


def test_different_pdfs_overlap_less(tmp_path):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _pdf(a, "X-Treme")
    _pdf(b, "Gugge")
    assert compare(a, b, tmp_path / "cmp").mean_overlap < 0.5


def test_images_go_next_to_new_pdf_by_default(tmp_path):
    ref = tmp_path / "ref.pdf"
    new = tmp_path / "out" / "new.pdf"
    new.parent.mkdir()
    _pdf(ref, "X-Treme")
    _pdf(new, "X-Treme")

    res = compare(ref, new)

    assert res.out_dir == new.parent / "new-compare"
    assert (new.parent / "new-compare" / "side-01.png").exists()
