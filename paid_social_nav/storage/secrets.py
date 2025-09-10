from __future__ import annotations


def access_secret(*, project_id: str, secret_id: str, version: str = "latest") -> str:
    try:
        from google.cloud import secretmanager  # type: ignore
    except Exception as e:
        raise RuntimeError("google-cloud-secret-manager is not installed") from e
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode("UTF-8")
