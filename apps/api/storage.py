import hashlib
import json
from functools import lru_cache
from apps.api.config import settings


def digest(data: bytes):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class ObjectStore:
    def __init__(self):
        self.config = settings()
        self.root = self.config.storage_dir.resolve()
        if self.config.storage_backend == "s3":
            import boto3

            self.client = boto3.client(
                "s3",
                endpoint_url=self.config.s3_endpoint,
                aws_access_key_id=self.config.s3_access_key,
                aws_secret_access_key=self.config.s3_secret_key,
            )

    def path(self, key):
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid object key")
        return path

    def put(self, key, data, content_type="application/octet-stream"):
        if self.config.storage_backend == "s3":
            self.client.put_object(Bucket=self.config.s3_bucket, Key=key, Body=data, ContentType=content_type)
        else:
            path = self.path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_bytes(data)
            temp.replace(path)
        return digest(data)

    def get(self, key, sha256=None):
        if self.config.storage_backend == "s3":
            data = self.client.get_object(Bucket=self.config.s3_bucket, Key=key)["Body"].read()
        else:
            data = self.path(key).read_bytes()
        if sha256 and digest(data) != sha256:
            raise ValueError("Object integrity check failed")
        return data

    def json(self, key, sha256=None):
        return json.loads(self.get(key, sha256))


@lru_cache
def store():
    return ObjectStore()
