"""Check migration enforcement and private, versioned S3 on a synthetic verification stack."""

import httpx
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from apps.api.db import Session
from apps.api.models import Dataset, Source
from apps.api.storage import store

with Session() as db:
    dataset = db.scalar(select(Dataset).order_by(Dataset.created_at.desc()))
    assert dataset, "Run integration_smoke.py first"
    source = db.get(Source, dataset.source_ids[0])
    assert "synthetic" in source.filename.lower(), "This check requires synthetic verification data"
    key = source.object_key
    blocked = False
    try:
        db.execute(text("UPDATE datasets SET seed = seed + 1 WHERE id = :id"), {"id": dataset.id})
        db.flush()
    except DBAPIError:
        blocked = True
    finally:
        db.rollback()
    assert blocked, "The PostgreSQL immutability trigger did not reject mutation"

storage = store()
assert storage.client.get_bucket_versioning(Bucket=storage.config.s3_bucket)["Status"] == "Enabled"
original = storage.get(key)
assert original
url = f"{storage.config.s3_endpoint}/{storage.config.s3_bucket}/{key}"
assert httpx.get(url).status_code == 403, "Anonymous dictionary access must be denied"
print("PostgreSQL immutability, S3 versioning and anonymous-access denial passed")
