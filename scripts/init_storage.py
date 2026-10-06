import time
from botocore.exceptions import ClientError, EndpointConnectionError
from apps.api.storage import store

storage = store()
for attempt in range(30):
    try:
        try:
            storage.client.head_bucket(Bucket=storage.config.s3_bucket)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in {"404", "NoSuchBucket"}:
                raise
            storage.client.create_bucket(Bucket=storage.config.s3_bucket)
        # Versioning preserves originals. No public bucket policy is ever installed.
        storage.client.put_bucket_versioning(
            Bucket=storage.config.s3_bucket, VersioningConfiguration={"Status": "Enabled"}
        )
        print("Private object bucket ready")
        break
    except EndpointConnectionError:
        if attempt == 29:
            raise
        time.sleep(2)
