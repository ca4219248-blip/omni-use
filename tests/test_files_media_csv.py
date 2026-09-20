"""Files + media + csv toolset tests (all local, PIL where needed)."""

from __future__ import annotations

import json

from PIL import Image

from omniuse.tools import csvdata, files, media


# ---------------------------------------------------------------- files

def test_write_read_append(tmp_path):
    f = tmp_path / "sub" / "a.txt"
    assert "Wrote" in files.files_write(str(f), "hello")
    assert files.files_read(str(f)) == "hello"
    assert "Appended" in files.files_write(str(f), " world", append=True)
    assert files.files_read(str(f)) == "hello world"


def test_missing_file_error():
    assert "ERROR" in files.files_read("/definitely/not/here.txt")


def test_list_and_find(tmp_path):
    (tmp_path / "x.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "y.txt").write_text("y")
    assert "x.txt" in files.files_list(str(tmp_path))
    assert "y.txt" in files.files_find(str(tmp_path), "*.txt")


def test_organize_dry_run_then_move(tmp_path):
    for name in ("a.jpg", "b.png", "c.pdf", "d.xyz"):
        (tmp_path / name).write_text("x")
    r = files.files_organize(str(tmp_path), dry_run=True)
    assert "DRY RUN" in r and "a.jpg → images/a.jpg" in r
    assert "d.xyz" not in r  # unknown extension untouched
    assert "Moved 3/3" in files.files_organize(str(tmp_path), dry_run=False)
    assert (tmp_path / "images" / "a.jpg").is_file()
    assert (tmp_path / "d.xyz").is_file()


def test_duplicates(tmp_path):
    (tmp_path / "d1.bin").write_bytes(b"same-bytes")
    (tmp_path / "d2.bin").write_bytes(b"same-bytes")
    (tmp_path / "unique.bin").write_bytes(b"other")
    r = files.files_duplicates(str(tmp_path))
    assert "d1.bin" in r and "d2.bin" in r
    assert "1 duplicate group" in r


def test_backup(tmp_path):
    (tmp_path / "f.txt").write_text("data")
    r = files.files_backup(str(tmp_path))
    assert "Backup written" in r


# ---------------------------------------------------------------- media

def _img(tmp_path, w=400, h=200, color=(200, 30, 30), name="img.png"):
    p = tmp_path / name
    Image.new("RGB", (w, h), color).save(p)
    return str(p)


def test_media_info(tmp_path):
    assert "400x200" in media.media_info(_img(tmp_path))


def test_media_resize(tmp_path):
    p = _img(tmp_path)
    assert "200x100" in media.media_resize(p, percent=50)
    assert "100x50" in media.media_resize(p, width=100)
    assert "ERROR" in media.media_resize(p)


def test_media_crop_bounds(tmp_path):
    p = _img(tmp_path)
    assert "50x50" in media.media_crop(p, 0, 0, 50, 50)
    assert "ERROR" in media.media_crop(p, 0, 0, 900, 900)


def test_media_convert(tmp_path):
    p = _img(tmp_path)
    assert ".jpg" in media.media_convert(p, "jpg")
    assert "ERROR" in media.media_convert(p, "xyz")


def test_media_compress(tmp_path):
    assert "Compressed" in media.media_compress(_img(tmp_path))


def test_contact_sheet(tmp_path):
    _img(tmp_path)
    _img(tmp_path, 100, 100, (10, 10, 10), name="img2.png")
    r = media.media_contact_sheet(str(tmp_path))
    assert "contact-sheet" in r and "2 thumbnails" in r


# ---------------------------------------------------------------- csv

def _csv(tmp_path, rows="name,city,amount\nRahul,Delhi,100\nPriya,Mumbai,250\nAmit,Delhi,50\n"):
    p = tmp_path / "sales.csv"
    p.write_text(rows)
    return str(p)


def test_csv_summary(tmp_path):
    r = csvdata.csv_summary(_csv(tmp_path))
    assert "3 data row(s), 3 column(s)" in r and "mean 133.33" in r


def test_csv_head(tmp_path):
    assert "Rahul" in csvdata.csv_head(_csv(tmp_path), n=2)


def test_csv_filter(tmp_path):
    p = _csv(tmp_path)
    assert "Kept 2 of 3" in csvdata.csv_filter(p, "city", "equals", "Delhi")
    assert "Kept 2 of 3" in csvdata.csv_filter(p, "amount", "gt", "60")
    assert "Kept 1 of 3" in csvdata.csv_filter(p, "city", "contains", "Mum")
    assert "ERROR" in csvdata.csv_filter(p, "nope", "equals", "1")


def test_csv_select(tmp_path):
    r = csvdata.csv_select(_csv(tmp_path), "name,amount")
    assert "columns ['name', 'amount']" in r


def test_csv_merge_and_json(tmp_path):
    a = _csv(tmp_path)
    b = tmp_path / "more.csv"
    b.write_text("name,city,amount\nRahul,Delhi,100\nSara,Pune,300\n")
    r = csvdata.csv_merge(a, str(b))
    assert "1 added" in r and "1 duplicate" in r
    assert "Converted 3 row(s)" in csvdata.csv_to_json(a)
    j = json.loads((tmp_path / "sales.json").read_text())
    assert j[1]["city"] == "Mumbai"
