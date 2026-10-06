import numpy as np
import pytest
from apps.worker.jobs import execute
from tests.conftest import build_dataset
from ml.encoders.tiny import TinyEncoder
from ml.encoders import load_encoder


@pytest.mark.ml
def test_encoder_save_load_and_real_training(client, dictionary_bytes, governance, tmp_path):
    original = TinyEncoder()
    before = original.encode(["synthetic word", "meaning"])
    original.save(tmp_path / "encoder")
    after = load_encoder(tmp_path / "encoder").encode(["synthetic word", "meaning"])
    np.testing.assert_allclose(before, after)
    np.testing.assert_allclose(np.linalg.norm(after, axis=1), 1, atol=1e-6)
    lang, _, dataset = build_dataset(client, dictionary_bytes, governance)
    response = client.post(
        f"/languages/{lang['id']}/training-runs",
        json={
            "dataset_id": dataset["id"],
            "base_model": "test-tiny",
            "hyperparameters": {"epochs": 2, "learning_rate": 0.001, "batch_size": 8},
        },
    )
    assert response.status_code == 202, response.text
    run = response.json()
    execute(run["id"])
    completed = client.get(f"/training-runs/{run['id']}").json()
    assert completed["status"] == "COMPLETED", completed
    assert completed["metrics"]["baseline"]["query_count"] == 3
    assert len(completed["metrics"]["training"]["history"]) == 2
    model = client.get(f"/languages/{lang['id']}/models").json()[0]
    assert model["status"] == "EVALUATED" and model["visibility"] == "PRIVATE"
    assert client.post(f"/models/{model['id']}/deploy").status_code == 409
    assert (
        client.post(f"/models/{model['id']}/approve", headers={"Authorization": "Bearer editor"}).status_code
        == 403
    )
    assert client.post(f"/models/{model['id']}/approve").status_code == 200
    assert client.post(f"/models/{model['id']}/deploy").status_code == 200
    query = {"language": lang["id"], "query": "water"}
    search = client.post("/v1/search", json=query)
    assert search.status_code == 200, search.text
    assert len(search.json()["matches"]) == 10
    assert all(-1 <= m["score"] <= 1 for m in search.json()["matches"])
    assert (
        client.post("/v1/search", json=query, headers={"Authorization": "Bearer outsider"}).status_code == 404
    )
    embedded = client.post("/v1/embed", json={"language": lang["id"], "texts": ["water"]}).json()
    assert embedded["dimensions"] == 32 and len(embedded["embeddings"]) == 1
    match = client.post("/v1/match", json={"language": lang["id"], "word": "synthetic-000"}).json()
    assert "definition" in match["matches"][0]
    compare = client.post(f"/models/{model['id']}/playground", json=query).json()
    assert compare["baseline"] and compare["fine_tuned"]
    assert client.get("/v1/dictionary/synthetic-000", params={"language": lang["id"]}).json()["entries"]
    assert client.get(f"/models/{model['id']}/lineage").json()["dataset"]["sha256"] == dataset["sha256"]
    execute(run["id"])
    assert len(client.get(f"/languages/{lang['id']}/models").json()) == 1


def test_failure_is_terminal(client, dictionary_bytes, governance, monkeypatch):
    lang, _, dataset = build_dataset(client, dictionary_bytes, governance)
    run = client.post(
        f"/languages/{lang['id']}/training-runs",
        json={"dataset_id": dataset["id"], "base_model": "test-tiny"},
    ).json()
    from apps.api.storage import store

    monkeypatch.setattr(
        store(), "json", lambda *args: (_ for _ in ()).throw(ValueError("sensitive dictionary content"))
    )
    execute(run["id"])
    result = client.get(f"/training-runs/{run['id']}").json()
    assert result["status"] == "FAILED"
    assert "sensitive" not in result["error"]
    assert result["completed_at"]


def test_late_worker_preserves_watchdog_failure(client, dictionary_bytes, governance, monkeypatch):
    from apps.api.db import Session, now
    from apps.api.models import TrainingRun
    from apps.worker.jobs import emit

    lang, _, dataset = build_dataset(client, dictionary_bytes, governance)
    run = client.post(
        f"/languages/{lang['id']}/training-runs",
        json={"dataset_id": dataset["id"], "base_model": "test-tiny"},
    ).json()

    def expired(*args, **kwargs):
        with Session() as db:
            record = db.get(TrainingRun, run["id"])
            record.status, record.error, record.completed_at = "FAILED", "Worker heartbeat expired", now()
            db.commit()
        emit(run["id"], "Late training progress")

    monkeypatch.setattr(TinyEncoder, "train", expired)
    execute(run["id"])
    result = client.get(f"/training-runs/{run['id']}").json()
    assert result["status"] == "FAILED" and result["error"] == "Worker heartbeat expired"
    assert client.get(f"/languages/{lang['id']}/models").json() == []
