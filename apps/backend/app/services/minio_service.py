import io
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from app.core.config import settings


class MinioService:
    def __init__(self):
        self._s3_client = None

    def _endpoint_url(self) -> str:
        scheme = "https" if settings.MINIO_SECURE else "http"
        return f"{scheme}://{settings.MINIO_ENDPOINT}"

    def _client(self):
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url(),
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(
                    signature_version="s3v4",        # MinIO requires SigV4
                    s3={"addressing_style": "path"},  # path-style: endpoint/bucket/key
                    retries={"max_attempts": 3, "mode": "adaptive"},
                ),
                region_name="us-east-1",             # boto3 requires a value; MinIO ignores it
            )
        return self._s3_client

    def _ensure_bucket(self, client, bucket: str) -> None:
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                client.create_bucket(Bucket=bucket)
            else:
                # Auth errors, permission errors — surface them, don't swallow
                raise

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        client = self._client()
        self._ensure_bucket(client, bucket)
        client.put_object(Bucket=bucket, Key=key, Body=io.BytesIO(data), ContentType=content_type)

    def download_bytes(self, bucket: str, key: str) -> bytes:
        resp = self._client().get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    def delete_object(self, bucket: str, key: str) -> None:
        self._client().delete_object(Bucket=bucket, Key=key)
