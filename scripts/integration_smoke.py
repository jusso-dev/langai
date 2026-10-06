"""Repeatable HTTP → S3 → queue → training → registry → inference check.

Uses only synthetic identifiers. Run against a disposable verification deployment.
"""

import argparse
import json
import os
import time
import uuid
from pathlib import Path

import httpx
from dotenv import dotenv_values

MEANINGS = (
    "river stone moon sun leaf cloud sand bird fish tree wind fire rain hill seed "
    "root bark path star water sky soil grass flower creek lake mountain valley ocean island"
).split()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.getenv("LANGAI_API_URL", "http://127.0.0.1:8100"))
    parser.add_argument("--base-model", default="test-tiny", help="Use auto to exercise the primary encoder")
    parser.add_argument("--adapter", action="store_true", help="Also run the full experimental LoRA model")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--output", type=Path, help="Optional non-secret verification report")
    args = parser.parse_args(argv)
    token = os.getenv("LANGAI_API_KEY") or os.getenv("LANGAI_BOOTSTRAP_TOKEN")
    token = token or dotenv_values(".env").get("LANGAI_BOOTSTRAP_TOKEN")
    if not token:
        parser.error("Provide LANGAI_API_KEY or LANGAI_BOOTSTRAP_TOKEN")
    with httpx.Client(
        base_url=args.api_url, headers={"Authorization": f"Bearer {token}"}, timeout=300
    ) as client:

        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        def train(task, base="auto"):
            run = call(
                "POST",
                f"/languages/{language['id']}/training-runs",
                json={
                    "dataset_id": dataset["id"],
                    "task": task,
                    "base_model": base,
                    "hyperparameters": {"epochs": 1, "batch_size": 2, "max_length": 32, "lora_rank": 2},
                },
            )
            print(f"Queued {task}: {run['id']}", flush=True)
            deadline = time.monotonic() + args.timeout
            last = None
            while time.monotonic() < deadline:
                current = call("GET", f"/training-runs/{run['id']}")
                if current["status"] != last:
                    last = current["status"]
                    print(f"{task}: {last}", flush=True)
                if last in {"COMPLETED", "FAILED", "CANCELLED"}:
                    break
                time.sleep(2)
            assert current["status"] == "COMPLETED", current.get("error") or "Training timed out"
            events = call("GET", f"/training-runs/{run['id']}/events")
            assert len(events) > 2
            models = call("GET", f"/languages/{language['id']}/models")
            model = next(m for m in models if m["training_run_id"] == run["id"])
            assert model["status"] == "EVALUATED" and model["visibility"] == "PRIVATE"
            assert model["metrics"] == current["metrics"]
            lineage = call("GET", f"/models/{model['id']}/lineage")
            assert lineage["dataset"]["sha256"] == dataset["sha256"]
            report["models"][task] = {"id": model["id"], "run": run["id"], "metrics": model["metrics"]}
            return model

        language = call(
            "POST",
            "/languages",
            json={
                "name": f"Synthetic verification {uuid.uuid4().hex[:12]}",
                "description": "Engineering fixture only; these are not Indigenous words.",
            },
        )
        report = {"language_id": language["id"], "models": {}, "status": "passed"}
        governance = {
            "owner": "Fixture author",
            "source": "Synthetic test identifiers",
            "licence": "CC0 test fixture",
            "training_allowed": True,
        }
        fixture = (
            "word,definition\n" + "\n".join(f"synthetic-{i:03d},{word}" for i, word in enumerate(MEANINGS))
        ).encode()
        source = call(
            "POST",
            f"/languages/{language['id']}/dictionaries",
            files={"file": ("synthetic.csv", fixture, "text/csv")},
            data={"governance": json.dumps(governance)},
        )
        original = client.get(f"/dictionaries/{source['id']}/original")
        assert original.status_code == 200 and original.content == fixture
        preview = call(
            "POST", f"/dictionaries/{source['id']}/preview", json={"mapping": source["suggested_mapping"]}
        )
        assert preview["quality"]["entries"] == 30
        call("POST", f"/dictionaries/{source['id']}/import", json={"mapping": source["suggested_mapping"]})
        call("POST", f"/dictionaries/{source['id']}/approve")
        assert (
            client.post(
                f"/dictionaries/{source['id']}/import", json={"mapping": source["suggested_mapping"]}
            ).status_code
            == 409
        )
        corpus = call(
            "POST",
            f"/languages/{language['id']}/negative-corpora",
            json={
                "name": "Synthetic negative corpus",
                "texts": [f"external-example-{i}" for i in range(30)],
                "governance": governance,
                "approved": True,
            },
        )
        dataset = call(
            "POST",
            f"/languages/{language['id']}/datasets",
            json={"source_ids": [source["id"]], "negative_corpus_id": corpus["id"]},
        )
        frozen = call("GET", f"/datasets/{dataset['id']}/export")
        for samples in frozen["views"].values():
            for sample in samples:
                assert all(
                    frozen["manifest"]["entry_splits"][ref] == sample["split"]
                    for ref in sample["source_entry_ids"]
                )
        assert len(frozen["views"]) == 6
        model = train("embeddings", args.base_model)
        assert client.post(f"/models/{model['id']}/deploy").status_code == 409
        call("POST", f"/models/{model['id']}/approve")
        call("POST", f"/models/{model['id']}/deploy")
        embedding = call("POST", "/v1/embed", json={"language": language["id"], "texts": ["water"]})
        assert len(embedding["embeddings"][0]) == embedding["dimensions"] > 0
        for mode in ["semantic", "word-to-meaning", "meaning-to-word", "similar-words"]:
            search = call(
                "POST", "/v1/search", json={"language": language["id"], "query": "water", "mode": mode}
            )
            assert len(search["matches"]) == 10
            assert all(-1 <= row["score"] <= 1 for row in search["matches"])
        matches = call("POST", "/v1/match", json={"language": language["id"], "word": "synthetic-000"})
        assert matches["matches"][0]["definition"]
        exact = call("GET", "/v1/dictionary/synthetic-000", params={"language": language["id"]})
        assert exact["entries"][0]["definitions"] == ["river"]
        classifier = train("language-identification")
        call("POST", f"/models/{classifier['id']}/approve")
        call("POST", f"/models/{classifier['id']}/deploy")
        classified = call(
            "POST", "/v1/classify-language", json={"language": language["id"], "query": "synthetic-000"}
        )
        assert 0 <= classified["confidence"] <= 1
        if args.adapter:
            adapter = train("dictionary-adapter")
            assert adapter["experimental"] and adapter["metrics"]["experimental"]
            call("POST", f"/models/{adapter['id']}/approve")
            assert client.post(f"/models/{adapter['id']}/deploy").status_code == 422
        viewer = call("POST", "/keys", json={"name": "Disposable verification viewer", "role": "viewer"})
        headers = {"Authorization": f"Bearer {viewer['token']}"}
        try:
            assert client.get("/languages", headers=headers).status_code == 200
            assert client.post(f"/models/{model['id']}/deploy", headers=headers).status_code == 403
            assert client.get("/languages", headers={"Authorization": ""}).status_code == 401
        finally:
            call("DELETE", f"/keys/{viewer['id']}")
        assert client.get("/languages", headers=headers).status_code == 401
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "status": "passed",
                    "language_id": language["id"],
                    "tasks": list(report["models"]),
                    "dimensions": embedding["dimensions"],
                }
            )
        )


if __name__ == "__main__":
    main()
