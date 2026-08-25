"""Provision the ADV SECURESTORE buckets in MinIO.

All configuration is read from the environment so that no credentials are ever
baked into the image or committed to this repository:

    MINIO_ENDPOINT               host:port of the MinIO API              (required)
    MINIO_ACCESS_KEY             MinIO access key / root user            (required)
    MINIO_SECRET_KEY             MinIO secret key / root password        (required)
    BUCKETS                      comma-separated bucket names            (required)
    MINIO_SECURE                 "true" to use HTTPS                     (default false)
    CONNECT_RETRIES              connection attempts before giving up    (default 30)
    CONNECT_RETRY_DELAY_SECONDS  seconds between attempts                (default 5)

Creating an existing bucket is a no-op, so this is safe to re-run.

The process exits non-zero if MinIO never becomes reachable, if the credentials
are rejected, or if any bucket could not be created — so that a Kubernetes Job
reports the failure instead of completing successfully with nothing done.
"""

import os
import sys
import time

from minio import Minio
from minio.error import S3Error

# Errors that will never be fixed by waiting, so retrying them only delays a
# failure the operator needs to see.
FATAL_S3_CODES = frozenset(
    {"InvalidAccessKeyId", "SignatureDoesNotMatch", "AccessDenied"}
)


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"FATAL: environment variable {name} is required but not set.")
    return value


def env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        sys.exit(f"FATAL: environment variable {name} must be an integer, got {raw!r}.")
    if value < 1:
        sys.exit(f"FATAL: environment variable {name} must be at least 1, got {value}.")
    return value


def connect(endpoint, access_key, secret_key, secure, retries, delay):
    """Return a client once MinIO answers, retrying while it starts up.

    A post-install Helm hook can run before MinIO is accepting connections, so
    transient connection errors are expected and retried. Rejected credentials
    are not retried.
    """
    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            client.list_buckets()
        except S3Error as exc:
            if exc.code in FATAL_S3_CODES:
                sys.exit(
                    f"FATAL: MinIO rejected the credentials ({exc.code}). Check the "
                    "Secret referenced by minio.auth.existingSecret."
                )
            last_error = exc
        except Exception as exc:  # noqa: BLE001 - connection errors are not all S3Error
            last_error = exc
        else:
            print(f"Connected to MinIO at {endpoint}.", flush=True)
            return client

        print(
            f"MinIO not reachable yet (attempt {attempt}/{retries}): {last_error}",
            flush=True,
        )
        if attempt < retries:
            time.sleep(delay)

    sys.exit(
        f"FATAL: could not reach MinIO at {endpoint} after {retries} attempts. "
        f"Last error: {last_error}"
    )


def ensure_buckets(client, buckets):
    """Create any missing buckets. Returns the list of names that failed."""
    failed = []
    for bucket in buckets:
        try:
            if client.bucket_exists(bucket):
                print(f"Bucket '{bucket}' already exists.", flush=True)
            else:
                client.make_bucket(bucket)
                print(f"Bucket '{bucket}' created.", flush=True)
        except S3Error as exc:
            print(f"ERROR: bucket '{bucket}' failed: {exc}", file=sys.stderr, flush=True)
            failed.append(bucket)
    return failed


def main():
    endpoint = require_env("MINIO_ENDPOINT")
    access_key = require_env("MINIO_ACCESS_KEY")
    secret_key = require_env("MINIO_SECRET_KEY")

    buckets = [name.strip() for name in require_env("BUCKETS").split(",") if name.strip()]
    if not buckets:
        sys.exit("FATAL: BUCKETS must list at least one bucket name.")

    client = connect(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=env_bool("MINIO_SECURE", False),
        retries=env_int("CONNECT_RETRIES", 30),
        delay=env_int("CONNECT_RETRY_DELAY_SECONDS", 5),
    )

    failed = ensure_buckets(client, buckets)
    if failed:
        sys.exit(
            f"FATAL: {len(failed)} of {len(buckets)} buckets could not be created: "
            f"{', '.join(failed)}"
        )

    print(f"All {len(buckets)} bucket(s) present: {', '.join(buckets)}", flush=True)


if __name__ == "__main__":
    main()
