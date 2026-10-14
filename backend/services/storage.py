"""Archivos guardados fuera de la base: en un depósito de Amazon S3 (octubre de
2026). Los usan los respaldos de cada cliente, que no caben en el tier gratuito
de Atlas.

Nada de esto es público: se guarda **cifrado en reposo** y solo se baja a
través del panel, con la sesión y comprobando de quién es. Sin `S3_BUCKET`, no
hay dónde guardar, y lo que lo necesita lo dice en vez de romperse.
"""

from __future__ import annotations

from config import Config


class StorageError(RuntimeError):
    """No se pudo hablar con S3. El detalle va al registro."""


def ready() -> bool:
    return bool(Config.S3_BUCKET)


def _client():
    # Importado aquí, como en el correo: desarrollar sin AWS nunca lo necesita.
    import boto3
    return boto3.client("s3", region_name=Config.AWS_REGION)


def put(key: str, data: bytes, content_type: str) -> None:
    try:
        _client().put_object(Bucket=Config.S3_BUCKET, Key=key, Body=data,
                             ContentType=content_type, ServerSideEncryption="AES256")
    except Exception as exc:  # noqa: BLE001 - one error for the caller
        print(f"  [s3] no se pudo guardar {key}: {type(exc).__name__}: {str(exc)[:160]}",
              flush=True)
        raise StorageError("s3 put") from exc


def get(key: str) -> bytes:
    try:
        return _client().get_object(Bucket=Config.S3_BUCKET, Key=key)["Body"].read()
    except Exception as exc:  # noqa: BLE001
        print(f"  [s3] no se pudo leer {key}: {type(exc).__name__}: {str(exc)[:160]}",
              flush=True)
        raise StorageError("s3 get") from exc


def delete(key: str) -> None:
    try:
        _client().delete_object(Bucket=Config.S3_BUCKET, Key=key)
    except Exception as exc:  # noqa: BLE001
        print(f"  [s3] no se pudo borrar {key}: {type(exc).__name__}: {str(exc)[:160]}",
              flush=True)
        raise StorageError("s3 delete") from exc
