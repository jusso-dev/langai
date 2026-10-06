# ruff: noqa: E402
import os
import tempfile
from pathlib import Path
import pytest

# No test can accidentally connect to a developer's production database or storage.
_test_root = Path(tempfile.mkdtemp(prefix="langai-tests-"))
os.environ["LANGAI_DATABASE_URL"] = f"sqlite:///{_test_root}/test.db"
os.environ["LANGAI_BOOTSTRAP_TOKEN"] = "test-owner-secret-longer-than-32-characters"
os.environ["LANGAI_STORAGE_BACKEND"] = "local"
os.environ["LANGAI_STORAGE_DIR"] = str(_test_root / "objects")
os.environ["LANGAI_ARTIFACT_DIR"] = str(_test_root / "artifacts")
os.environ["LANGAI_ALLOW_TEST_ENCODER"] = "true"
os.environ["LANGAI_LOCAL_FILES_ONLY"] = "true"

from apps.api.db import Base, Session, engine
from apps.api.main import app
from apps.api.auth import bootstrap, token_hash
from apps.api.models import Identity
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    bootstrap()
    with Session() as db:
        db.add_all(
            [
                Identity(
                    name="Viewer", token_hash=token_hash("viewer"), workspace_id="local-owner", role="viewer"
                ),
                Identity(
                    name="Outsider", token_hash=token_hash("outsider"), workspace_id="other", role="owner"
                ),
                Identity(
                    name="Editor", token_hash=token_hash("editor"), workspace_id="local-owner", role="editor"
                ),
            ]
        )
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(
        app, headers={"Authorization": "Bearer test-owner-secret-longer-than-32-characters"}
    ) as client:
        yield client


@pytest.fixture
def governance():
    return {
        "owner": "Synthetic test author",
        "source": "Generated engineering fixture, no Indigenous vocabulary",
        "licence": "CC0 test data",
        "training_allowed": True,
    }


@pytest.fixture
def dictionary_bytes():
    # These are artificial identifiers, explicitly not words from an Indigenous language.
    words = [
        "river",
        "stone",
        "moon",
        "sun",
        "leaf",
        "cloud",
        "sand",
        "bird",
        "fish",
        "tree",
        "wind",
        "fire",
        "rain",
        "hill",
        "seed",
        "root",
        "bark",
        "path",
        "star",
        "water",
        "sky",
        "soil",
        "grass",
        "flower",
        "creek",
        "lake",
        "mountain",
        "valley",
        "ocean",
        "island",
    ]
    return (
        "word,definition\n" + "\n".join(f"synthetic-{i:03d},{word}" for i, word in enumerate(words))
    ).encode()


def build_dataset(client, dictionary_bytes, governance):
    import json

    lang = client.post("/languages", json={"name": "Synthetic test language"}).json()
    response = client.post(
        f"/languages/{lang['id']}/dictionaries",
        files={"file": ("fixture.csv", dictionary_bytes)},
        data={"governance": json.dumps(governance)},
    )
    assert response.status_code == 201, response.text
    source = response.json()
    response = client.post(
        f"/dictionaries/{source['id']}/import", json={"mapping": source["suggested_mapping"]}
    )
    assert response.status_code == 200, response.text
    assert client.post(f"/dictionaries/{source['id']}/approve").status_code == 200
    response = client.post(f"/languages/{lang['id']}/datasets", json={"source_ids": [source["id"]]})
    assert response.status_code == 201, response.text
    return lang, source, response.json()
