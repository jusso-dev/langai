import pytest
from ml.datasets.generation import generate, split_entries


def entries(n=40):
    return [
        {
            "id": str(i),
            "normalized_headword": f"term{i}",
            "alternate_spellings": [],
            "definitions": [f"meaning {i}"],
        }
        for i in range(n)
    ]


def test_deterministic_order_independent_splits():
    rows = entries()
    assert split_entries(rows, 42) == split_entries(list(reversed(rows)), 42)
    assert split_entries(rows, 42)["entry_splits"] != split_entries(rows, 43)["entry_splits"]
    assert split_entries(rows)["counts"] == {"train": 32, "validation": 4, "test": 4}


def test_transitive_variant_duplicate_and_definition_grouping():
    rows = entries()
    rows[0]["alternate_spellings"] = ["TERM1"]
    rows[1]["alternate_spellings"] = ["term2"]
    rows[3]["definitions"] = rows[2]["definitions"]
    rows[4]["normalized_headword"] = "term3"
    assignment = split_entries(rows)["entry_splits"]
    assert len({assignment[str(i)] for i in range(5)}) == 1


def test_no_generated_sample_or_negative_crosses_split():
    data = generate(entries())
    for view in data["views"].values():
        for sample in view:
            assert sample["source_entry_id"] in sample["source_entry_ids"]
            for ref in sample["source_entry_ids"]:
                assert data["manifest"]["entry_splits"][ref] == sample["split"]
    assert len(data["views"]["instructions"]) == 80
    assert any(s["label"] == 0 for s in data["views"]["semantic"])
    assert all(s["label"] == 1 for s in data["views"]["language_identification"])


def test_external_negatives_explicit_provenance_and_overlap_removal():
    negative = {
        "id": "n",
        "texts": ["term0"] + [f"external {i}" for i in range(20)],
        "governance": {"training_allowed": True},
    }
    data = generate(entries(), negatives=negative)
    samples = [s for s in data["views"]["language_identification"] if s["label"] == 0]
    assert len(samples) == 20
    assert all(s["source_entry_id"] is None and s["external_corpus_id"] == "n" for s in samples)
    assert len({s["external_sample_id"] for s in samples}) == 20


def test_tiny_dataset_rejected():
    with pytest.raises(ValueError, match="At least 3"):
        split_entries(entries(2))


def test_related_variant_groups_are_never_negatives():
    rows = entries()
    rows[0]["alternate_spellings"] = ["term1"]
    rows[1]["definitions"] = ["distinct recorded sense"]
    snapshot = generate(rows)
    groups = {ref: i for i, group in enumerate(snapshot["manifest"]["groups"]) for ref in group}
    for row in snapshot["views"]["semantic"]:
        if row["label"] == 0:
            assert groups[row["source_entry_id"]] != groups[row["negative_entry_id"]]
