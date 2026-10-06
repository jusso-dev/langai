import io
import unicodedata
import pytest
from openpyxl import Workbook
from ml.datasets.importers import parse_file
from ml.datasets.normalization import canonicalize, normalize, quality


@pytest.mark.parametrize(
    "filename,data",
    [
        ("d.csv", b"headword,definition\na,b\n"),
        ("d.tsv", b"word\tenglish\na\tb\n"),
        ("d.txt", b"word\tmeaning\na\tb\n"),
        ("d.json", b'[{"word":"a","definition":["b","c"]}]'),
        ("d.json", b'{"a":"b"}'),
    ],
)
def test_supported_formats(filename, data):
    rows, columns, mapping = parse_file(filename, data)
    entries = canonicalize(rows, mapping, {}, "source", "language")
    assert entries[0]["normalized_headword"] == "a"
    assert entries[0]["definitions"][0] == "b"
    assert entries[0]["original_row"] == rows[0]


def test_xlsx():
    book = Workbook()
    sheet = book.active
    sheet.append(["headword", "definition"])
    sheet.append(["ŋá’", "meaning"])
    data = io.BytesIO()
    book.save(data)
    rows, _, mapping = parse_file("d.xlsx", data.getvalue())
    assert canonicalize(rows, mapping, {}, "s", "l")[0]["headword"] == "ŋá’"


def test_unicode_is_preserved():
    original = "  Ŋa\u0301’  X'  "
    normalized = normalize(original, {})
    assert normalized == "Ŋá’ X'"
    assert unicodedata.is_normalized("NFC", normalized)
    assert (
        normalize(original, {"unicode_nfc": False, "trim_whitespace": False, "collapse_whitespace": False})
        == original
    )
    rows = [{"word": original, "definition": "  a  meaning "}]
    entry = canonicalize(rows, {"headword": "word", "definitions": "definition"}, {}, "s", "l")[0]
    assert entry["headword"] == original
    assert entry["original_row"] == rows[0]
    assert len(entry["entry_metadata"]["transformations"]) == 2


def test_quality_issues_and_punctuation():
    rows = [
        {"word": "a’", "meaning": "first; second"},
        {"word": "a’", "meaning": "first; second"},
        {"word": "x", "meaning": ""},
        {"word": "y\u200b", "meaning": "z"},
        {"word": "x" * 201, "meaning": "z"},
        {"word": "b", "meaning": "m", "__extra_cells__": ["x"]},
    ]
    entries = canonicalize(rows, {"headword": "word", "definitions": "meaning"}, {}, "s", "l")
    report = quality(entries)
    assert entries[0]["definitions"] == ["first; second"]
    assert report["issues"] == {
        "duplicate": 1,
        "missing_definition": 1,
        "unusual_unicode": 1,
        "unusually_long": 1,
        "malformed_row": 1,
    }
    assert report["score"] == 16.7


@pytest.mark.parametrize(
    "name,data",
    [
        ("a.pdf", b"bad"),
        ("a.csv", b"x,x\na,b"),
        ("a.csv", b""),
        ("a.json", b"[1]"),
        ("a.csv", b"word,definition\n\xff,a"),
    ],
)
def test_invalid_files(name, data):
    with pytest.raises(ValueError):
        parse_file(name, data)
