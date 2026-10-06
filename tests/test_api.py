import json
import pytest
from apps.api.db import Session
from apps.api.models import Dataset, TrainingRun
from tests.conftest import build_dataset


def test_auth_and_roles(client):
    assert client.get("/languages", headers={"Authorization": ""}).status_code == 401
    assert (
        client.post(
            "/languages", json={"name": "Test"}, headers={"Authorization": "Bearer viewer"}
        ).status_code
        == 403
    )
    assert (
        client.post("/keys", json={"name": "x"}, headers={"Authorization": "Bearer editor"}).status_code
        == 403
    )
    result = client.post("/keys", json={"name": "Inference", "role": "viewer"})
    assert result.status_code == 201
    token = result.json()["token"]
    assert "token_hash" not in result.json()
    assert client.get("/languages", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.delete(f"/keys/{result.json()['id']}").status_code == 200
    assert client.get("/languages", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_import_approval_snapshot_and_isolation(client, dictionary_bytes, governance):
    lang, source, dataset = build_dataset(client, dictionary_bytes, governance)
    assert source["visibility"] == "PRIVATE"
    for path in [
        f"/languages/{lang['id']}",
        f"/dictionaries/{source['id']}/entries",
        f"/dictionaries/{source['id']}/original",
        f"/datasets/{dataset['id']}/samples",
    ]:
        assert client.get(path, headers={"Authorization": "Bearer outsider"}).status_code == 404
    assert client.get("/languages", headers={"Authorization": "Bearer outsider"}).json() == []
    assert (
        client.post(
            f"/dictionaries/{source['id']}/import", json={"mapping": source["suggested_mapping"]}
        ).status_code
        == 409
    )
    row = client.get(f"/dictionaries/{source['id']}/entries").json()["items"][0]
    assert (
        client.patch(
            f"/entries/{row['id']}", json={"approved": False, "training_eligible": False}
        ).status_code
        == 409
    )
    other = client.post("/languages", json={"name": "Other language"}).json()
    assert (
        client.post(f"/languages/{other['id']}/datasets", json={"source_ids": [source["id"]]}).status_code
        == 422
    )
    assert (
        client.post(
            f"/languages/{other['id']}/training-runs",
            json={"dataset_id": dataset["id"], "base_model": "test-tiny"},
        ).status_code
        == 422
    )
    with Session() as db:
        record = db.get(Dataset, dataset["id"])
        record.seed = 99
        with pytest.raises(ValueError, match="immutable"):
            db.commit()


def test_training_permission_required(client, dictionary_bytes, governance):
    governance["training_allowed"] = False
    lang = client.post("/languages", json={"name": "Restricted"}).json()
    source = client.post(
        f"/languages/{lang['id']}/dictionaries",
        files={"file": ("d.csv", dictionary_bytes)},
        data={"governance": json.dumps(governance)},
    ).json()
    assert (
        client.post(
            f"/dictionaries/{source['id']}/import", json={"mapping": source["suggested_mapping"]}
        ).status_code
        == 200
    )
    assert client.post(f"/dictionaries/{source['id']}/approve").status_code == 403
    assert (
        client.post(f"/languages/{lang['id']}/datasets", json={"source_ids": [source["id"]]}).status_code
        == 403
    )


def test_jobs_and_classifier_gate(client, dictionary_bytes, governance):
    lang, _, dataset = build_dataset(client, dictionary_bytes, governance)
    assert (
        client.post(
            f"/languages/{lang['id']}/training-runs",
            json={"dataset_id": dataset["id"], "task": "language-identification"},
        ).status_code
        == 422
    )
    result = client.post(
        f"/languages/{lang['id']}/training-runs",
        json={"dataset_id": dataset["id"], "base_model": "test-tiny"},
    )
    assert result.status_code == 202, result.text
    run = result.json()
    assert run["status"] == "QUEUED"
    assert (
        client.get(
            f"/training-runs/{run['id']}/events", headers={"Authorization": "Bearer outsider"}
        ).status_code
        == 404
    )
    with Session() as db:
        record = db.get(TrainingRun, run["id"])
        record.base_model = "changed"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
    assert client.post(f"/training-runs/{run['id']}/cancel").json()["status"] == "CANCELLED"
    from apps.worker.jobs import execute

    execute(run["id"])
    assert client.get(f"/training-runs/{run['id']}").json()["status"] == "CANCELLED"


def test_explicit_exclusion_survives_bulk_approval(client, dictionary_bytes, governance):
    lang = client.post("/languages", json={"name": "Review decisions"}).json()
    source = client.post(
        f"/languages/{lang['id']}/dictionaries",
        files={"file": ("fixture.csv", dictionary_bytes)},
        data={"governance": json.dumps(governance)},
    ).json()
    client.post(f"/dictionaries/{source['id']}/import", json={"mapping": source["suggested_mapping"]})
    entry = client.get(f"/dictionaries/{source['id']}/entries").json()["items"][0]
    assert (
        client.patch(
            f"/entries/{entry['id']}", json={"approved": False, "training_eligible": False}
        ).status_code
        == 200
    )
    approved = client.post(f"/dictionaries/{source['id']}/approve").json()
    assert approved["eligible_entries"] == 29


def test_training_inside_minimal_container_without_git(client, dictionary_bytes, governance, monkeypatch):
    lang, _, dataset = build_dataset(client, dictionary_bytes, governance)
    monkeypatch.setattr("apps.api.training.shutil.which", lambda _: None)
    result = client.post(
        f"/languages/{lang['id']}/training-runs",
        json={"dataset_id": dataset["id"], "base_model": "test-tiny"},
    )
    assert result.status_code == 202, result.text
    assert result.json()["git_commit"] == "unversioned-build"
