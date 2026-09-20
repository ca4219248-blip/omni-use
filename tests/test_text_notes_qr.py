"""Text + notes + qr toolset tests (local, no LLM calls)."""

from __future__ import annotations

from omniuse.tools import notes, qr, text


# ---------------------------------------------------------------- text

def test_wordcount():
    r = text.text_wordcount("Hello world. This is a test.\n\nNew para.")
    assert "Words: 8" in r and "Paragraphs: 2" in r


def test_case_modes():
    assert text.text_case("hello world", "title") == "Hello World"
    assert text.text_case("abc", "upper") == "ABC"
    assert text.text_case("ABC", "lower") == "abc"
    assert "ERROR" in text.text_case("x", "spin")


def test_replace_counts():
    r = text.text_replace("one two one", "one", "1")
    assert r.startswith("1 two 1") and "2 replacements" in r


def test_extract_regex():
    assert text.text_extract("call 911 or 112", r"\d+") == "911\n112"


def test_slug():
    assert text.text_slug("Mera ₹300 wala Design!!") == "mera-300-wala-design"
    assert "ERROR" in text.text_slug("###")


def test_diff_and_head():
    assert "identical" in text.text_diff("a\nb", "a\nb")
    d = text.text_diff("a\nb", "a\nc")
    assert "-b" in d and "+c" in d
    assert text.text_head("l1\nl2\nl3", lines=1).startswith("l1")


def test_text_from_file(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("file content here")
    assert "Words: 3" in text.text_wordcount(str(f))


# ---------------------------------------------------------------- notes

def test_notes_lifecycle():
    assert "#1" in notes.notes_add("first note", tags="a, b")
    notes.notes_add("second note", tags="b")
    assert "first note" in notes.notes_list()
    assert "second note" in notes.notes_list(tag="b")
    assert "#2" in notes.notes_search("second")
    assert "No matching" in notes.notes_search("zzz-xyz")
    assert "deleted" in notes.notes_delete(1)
    assert "ERROR" in notes.notes_delete(99)


def test_notes_empty_text():
    assert "ERROR" in notes.notes_add("   ")


# ---------------------------------------------------------------- qr

def test_qr_text_creates_png():
    r = qr.qr_text("hello qr", name="unit")
    assert r.startswith("QR saved to ")
    from PIL import Image
    path = r.split("QR saved to ")[1].split(" ")[0]
    with Image.open(path) as img:
        assert img.size[0] > 50


def test_qr_errors():
    assert "ERROR" in qr.qr_text("")
    assert "ERROR" in qr.qr_wifi("", password="x")
    assert "ERROR" in qr.qr_wifi("ssid", password="")
    assert "ERROR" in qr.qr_vcard("")


def test_qr_vcard():
    r = qr.qr_vcard("Test User", phone="12345")
    assert r.startswith("QR saved to ")
