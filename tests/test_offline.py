import json

from apps.api.db import Session
from apps.api.models import AuditEvent, Entry, Source
from apps.api.storage import digest
from sqlalchemy import select
from tests.conftest import build_dataset


def test_offline_export_is_private_deterministic_and_traceable(client, dictionary_bytes, governance):
    language, source, _ = build_dataset(client, dictionary_bytes, governance)
    url = f"/languages/{language['id']}/offline-export"
    body = {"source_ids": [source["id"]]}
    response = client.post(url, json=body)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert ".langai.json" in response.headers["content-disposition"]
    pack = response.json()
    assert pack["format"] == "langai-offline-v1"
    assert digest(pack["payload"].encode()) == pack["sha256"]
    content = json.loads(pack["payload"])
    assert content["engine"] == "langai-lexical-v1"
    assert content["language"] == {"id": language["id"], "name": language["name"]}
    assert len(content["entries"]) == 30
    assert content["sources"][0]["governance"]["redistribution_allowed"] is False
    assert content["sources"][0]["sha256"] == source["sha256"]
    assert "original_row" not in content["entries"][0]
    assert "views" not in content and "negative_corpus" not in content
    assert client.post(url, json=body).content == response.content
    assert client.post(url, json=body, headers={"Authorization": "Bearer viewer"}).status_code == 200
    assert client.post(url, json=body, headers={"Authorization": "Bearer outsider"}).status_code == 404
    assert client.post(url, json=body, headers={"Authorization": "Bearer invalid"}).status_code == 401
    with Session() as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.action == "dictionary.offline-export"))
        assert event.details["sha256"] == pack["sha256"]


def test_offline_export_excludes_unreviewed_entries_and_supports_one_entry(
    client, dictionary_bytes, governance
):
    language, source, _ = build_dataset(client, dictionary_bytes, governance)
    with Session() as db:
        rows = list(db.scalars(select(Entry).where(Entry.source_id == source["id"]).order_by(Entry.id)))
        for row in rows[1:]:
            row.training_eligible = False
        rows[0].headword = "synthetic café's phrase"
        rows[0].alternate_spellings = ["synthetic variant"]
        rows[0].definitions = ["a phrase meaning"]
        db.commit()
    url = f"/languages/{language['id']}/offline-export"
    body = {"source_ids": [source["id"]]}
    response = client.post(url, json=body)
    content = json.loads(response.json()["payload"])
    assert len(content["entries"]) == 1
    assert content["entries"][0]["headword"] == "synthetic café's phrase"
    assert content["entries"][0]["alternate_spellings"] == ["synthetic variant"]
    with Session() as db:
        db.get(Entry, content["entries"][0]["id"]).approved = False
        db.commit()
    assert client.post(url, json=body).status_code == 422


def test_offline_export_requires_approved_same_language_sources(client, dictionary_bytes, governance):
    language, source, _ = build_dataset(client, dictionary_bytes, governance)
    other = client.post("/languages", json={"name": "Another synthetic language"}).json()
    assert (
        client.post(
            f"/languages/{other['id']}/offline-export", json={"source_ids": [source["id"]]}
        ).status_code
        == 422
    )
    with Session() as db:
        db.get(Source, source["id"]).status = "IMPORTED"
        db.commit()
    url = f"/languages/{language['id']}/offline-export"
    assert client.post(url, json={"source_ids": [source["id"]]}).status_code == 403
    assert client.post(url, json={"source_ids": []}).status_code == 422
    assert client.post(url, json={"source_ids": ["missing"]}).status_code == 404
