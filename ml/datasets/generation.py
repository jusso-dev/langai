"""Entry-group splitting precedes every augmentation, including negative sampling."""

import hashlib
import random
import unicodedata
from collections import defaultdict

GENERATION_VERSION = "1.0.0"
SPLITS = ("train", "validation", "test")


def identity(text):
    return unicodedata.normalize("NFC", " ".join(text.split())).casefold()


def split_entries(entries, seed=42):
    # Union connected headwords/variants AND identical definitions. This is more conservative
    # than row-level splitting and prevents polysemous/duplicate records contaminating holdout.
    parent = {e["id"]: e["id"] for e in entries}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    tokens = {}
    for e in sorted(entries, key=lambda e: e["id"]):
        keys = [("word", identity(w)) for w in [e["normalized_headword"], *e["alternate_spellings"]]]
        keys += [("definition", identity(d)) for d in e["definitions"]]
        for token in keys:
            if not token[1]:
                continue
            if token in tokens:
                a, b = sorted((root(e["id"]), root(tokens[token])))
                parent[b] = a
            tokens[token] = e["id"]
    groups = defaultdict(list)
    for e in entries:
        groups[root(e["id"])].append(e["id"])
    groups = sorted([sorted(v) for v in groups.values()])
    if len(groups) < 3:
        raise ValueError(
            "At least 3 independent word/variant/definition groups are needed for train, validation and test"
        )
    random.Random(seed).shuffle(groups)
    holdout = max(1, round(len(groups) * 0.1))
    assignment = {}
    for i, group in enumerate(groups):
        split = "test" if i < holdout else "validation" if i < 2 * holdout else "train"
        assignment.update({entry_id: split for entry_id in group})
    return {
        "seed": seed,
        "ratios_requested": [0.8, 0.1, 0.1],
        "group_count": len(groups),
        "grouping": "NFC/casefold headwords, transitive variants and identical definitions",
        "entry_splits": assignment,
        "groups": groups,
        "counts": {s: sum(v == s for v in assignment.values()) for s in SPLITS},
    }


def generate(entries, seed=42, negatives=None):
    entries = sorted(entries, key=lambda e: e["id"])
    manifest = split_entries(entries, seed)
    views = {
        name: []
        for name in ["lexical", "reverse", "semantic", "language_identification", "variants", "instructions"]
    }
    group_of = {entry_id: i for i, group in enumerate(manifest["groups"]) for entry_id in group}
    for split in SPLITS:
        members = [e for e in entries if manifest["entry_splits"][e["id"]] == split]
        # Inverted term index avoids materializing a quadratic pair matrix.
        candidates = [(other, d) for other in members for d in other["definitions"]]
        term_index = defaultdict(list)
        for index, (_, definition) in enumerate(candidates):
            for term in set(identity(definition).split()):
                term_index[term].append(index)
        for e in members:
            ref = {"source_entry_id": e["id"], "source_entry_ids": [e["id"]], "split": split}
            for definition in e["definitions"]:
                word = e["normalized_headword"]
                views["lexical"].append({**ref, "word": word, "definition": definition})
                views["reverse"].append({**ref, "definition": definition, "word": word})
                views["semantic"].append({**ref, "anchor": word, "text": definition, "label": 1.0})
                views["instructions"].extend(
                    [
                        {
                            **ref,
                            "prompt": f"Define this dictionary word: {word}\nAnswer:",
                            "response": definition,
                        },
                        {
                            **ref,
                            "prompt": f"Give the dictionary word for: {definition}\nAnswer:",
                            "response": word,
                        },
                    ]
                )
                # Lexically hard candidates, mined exclusively within this split. Exclude known synonyms.
                overlaps = defaultdict(int)
                for term in set(identity(definition).split()):
                    for candidate_index in term_index[term]:
                        overlaps[candidate_index] += 1
                ranked = sorted(
                    overlaps, key=lambda i: (-overlaps[i], candidates[i][0]["id"], candidates[i][1])
                )
                known = set(map(identity, e["definitions"]))

                def eligible(index):
                    other, _ = candidates[index]
                    return group_of[other["id"]] != group_of[e["id"]] and not known.intersection(
                        map(identity, other["definitions"])
                    )

                choice = next((i for i in ranked if eligible(i)), None)
                if choice is None:
                    choice = next((i for i in range(len(candidates)) if eligible(i)), None)
                if choice is not None:
                    other, negative = candidates[choice]
                    views["semantic"].append(
                        {
                            **ref,
                            "source_entry_ids": [e["id"], other["id"]],
                            "negative_entry_id": other["id"],
                            "anchor": word,
                            "text": negative,
                            "label": 0.0,
                            "negative_method": "within-split lexical overlap; assumed unrelated",
                        }
                    )
            views["language_identification"].append({**ref, "text": e["normalized_headword"], "label": 1})
            for variant in e["alternate_spellings"]:
                views["variants"].append({**ref, "a": e["normalized_headword"], "b": variant})
    if negatives:
        positive_words = {
            identity(w) for e in entries for w in [e["normalized_headword"], *e["alternate_spellings"]]
        }
        texts = sorted(
            {
                identity(t): t
                for t in negatives["texts"]
                if identity(t) and identity(t) not in positive_words
            }.values()
        )
        if len(texts) < 10:
            raise ValueError("Need at least 10 distinct approved negatives after overlap removal")
        random.Random(seed).shuffle(texts)
        n = max(1, round(len(texts) * 0.1))
        for i, text in enumerate(texts):
            split = "test" if i < n else "validation" if i < 2 * n else "train"
            # External samples have their own explicit provenance, never invented dictionary IDs.
            views["language_identification"].append(
                {
                    "source_entry_id": None,
                    "source_entry_ids": [],
                    "external_corpus_id": negatives["id"],
                    "external_sample_id": hashlib.sha256(text.encode()).hexdigest(),
                    "text": text,
                    "label": 0,
                    "split": split,
                }
            )
    for samples in views.values():
        for sample in samples:
            assert all(manifest["entry_splits"][ref] == sample["split"] for ref in sample["source_entry_ids"])
    return {
        "generation_version": GENERATION_VERSION,
        "manifest": manifest,
        "entries": entries,
        "views": views,
        "negative_corpus": {k: v for k, v in negatives.items() if k != "texts"} if negatives else None,
    }
