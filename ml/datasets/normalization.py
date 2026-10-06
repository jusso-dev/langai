import re
import unicodedata
from collections import Counter
from hashlib import sha256


def normalize(text: str, config: dict) -> str:
    if config.get("unicode_nfc", True):
        text = unicodedata.normalize("NFC", text)
    if config.get("trim_whitespace", True):
        text = text.strip()
    if config.get("collapse_whitespace", True):
        text = re.sub(r"\s+", " ", text)
    return text


def as_text(value):
    return "" if value is None else str(value)


def strings(value):
    # Never guess that punctuation separates meanings or spelling variants.
    return [as_text(v) for v in value] if isinstance(value, list) else [as_text(value)]


def canonicalize(rows, mapping, config, source_id, language_id):
    if not mapping.get("headword") or not mapping.get("definitions"):
        raise ValueError("Map both headword and definitions")
    entries = []
    seen = set()
    for index, row in enumerate(rows, 1):
        values = {field: row.get(column) for field, column in mapping.items()}
        headword = as_text(values.get("headword"))
        normalized = normalize(headword, config)
        definitions = [
            normalize(v, config) for v in strings(values.get("definitions")) if normalize(v, config)
        ]
        variants = [
            normalize(v, config) for v in strings(values.get("alternate_spellings")) if normalize(v, config)
        ]
        examples = [v for v in strings(values.get("examples")) if v.strip()]
        issues = []
        if not normalized:
            issues.append("missing_headword")
        if not definitions:
            issues.append("missing_definition")
        scalar_fields = ["headword", "part_of_speech", "dialect", "notes", "source"]
        array_fields = ["definitions", "alternate_spellings", "examples"]
        malformed = any(isinstance(values.get(f), (dict, list)) for f in scalar_fields)
        malformed |= any(
            isinstance(values.get(f), dict)
            or (isinstance(values.get(f), list) and any(isinstance(v, (dict, list)) for v in values[f]))
            for f in array_fields
        )
        if "__extra_cells__" in row or malformed:
            issues.append("malformed_row")
        texts = [headword, *definitions, *variants, *examples]
        if any(
            unicodedata.category(c) in {"Cc", "Cf", "Co", "Cs", "Cn"} and c not in "\t\r\n"
            for t in texts
            for c in t
        ):
            issues.append("unusual_unicode")
        if any(len(t) > 2000 for t in texts) or len(headword) > 200:
            issues.append("unusually_long")
        fingerprint = (normalized, tuple(sorted(definitions)), as_text(values.get("dialect")))
        if fingerprint in seen:
            issues.append("duplicate")
        seen.add(fingerprint)
        changes = []
        if normalized != headword:
            changes.append({"field": "headword", "before": headword, "after": normalized})
        original_definitions = [v for v in strings(values.get("definitions")) if v]
        if definitions != original_definitions:
            changes.append({"field": "definitions", "before": original_definitions, "after": definitions})
        original_variants = [v for v in strings(values.get("alternate_spellings")) if v]
        if variants != original_variants:
            changes.append({"field": "alternate_spellings", "before": original_variants, "after": variants})
        entries.append(
            {
                "id": sha256(f"{source_id}:{index}".encode()).hexdigest()[:32],
                "language_id": language_id,
                "source_id": source_id,
                "row_number": index,
                "original_row": row,
                "headword": headword,
                "normalized_headword": normalized,
                "definitions": definitions,
                "alternate_spellings": variants,
                "part_of_speech": as_text(values.get("part_of_speech")),
                "dialect": as_text(values.get("dialect")),
                "examples": examples,
                "notes": as_text(values.get("notes")),
                "source": as_text(values.get("source")),
                "entry_metadata": {"transformations": changes},
                "issues": issues,
                "approved": False,
                "training_eligible": False,
            }
        )
    return entries


def quality(entries):
    counts = Counter(issue for e in entries for issue in e["issues"])
    unique = {e["normalized_headword"] for e in entries if e["normalized_headword"]}
    definitions = {
        (e["normalized_headword"], d) for e in entries for d in e["definitions"] if e["normalized_headword"]
    }
    flagged = sum(bool(e["issues"]) for e in entries)
    return {
        "entries": len(entries),
        "unique_headwords": len(unique),
        "alternate_definitions": max(0, len(definitions) - len(unique)),
        "issues": dict(counts),
        "needs_review": flagged,
        "variants": sum(bool(e["alternate_spellings"]) for e in entries),
        "transformations": sum(bool(e["entry_metadata"]["transformations"]) for e in entries),
        "score": round(100 * (1 - flagged / max(1, len(entries))), 1),
        "score_method": "Percentage of rows without detected issues; not a measure of linguistic validity.",
    }
