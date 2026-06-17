import json
import pytest
import base64
from pathlib import Path
from unittest.mock import MagicMock, patch
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jsonschema import validate
from jsonschema.validators import _RefResolver
import os

# Generate keys at module load time so they exist before ANY test imports
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_PRIVATE_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

_PUBLIC_PEM = _PUBLIC_KEY.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

os.environ["JWT_PUBLIC_KEY"] = base64.b64encode(_PUBLIC_PEM).decode("utf-8")
os.environ.pop("JWT_JWKS_URI", None)
os.environ["JWT_AUDIENCE"] = "care-episode"
os.environ["ENV"] = "test"
os.environ["APP_DATABASE_URL"] = "postgresql+psycopg://app:dummy@localhost/dummy"
os.environ["MIGRATION_DATABASE_URL"] = "postgresql+psycopg://template:dummy@localhost/dummy"
from src.app import create_app  # noqa: E402 — must import after env vars are set

_TIER1_ACTORS = frozenset({"operator", "study", "clinician", "patient", "demo"})

@pytest.fixture(scope="session")
def rsa_keypair():
    return {"private": _PRIVATE_PEM, "public": _PUBLIC_PEM}


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": True,
            "TIER1_ACTOR_CLASSES": _TIER1_ACTORS,
            "JWT_JWKS_URI": None,
            "JWT_PUBLIC_KEY": _PUBLIC_PEM.decode("utf-8"),
            "JWT_AUDIENCE": "care-episode",
        }
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _mock_auth_loader_db():
    """Prevent auth resource loaders from opening a real DB during route tests."""
    mock_db = MagicMock()
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_db
    mock_session.__exit__.return_value = False
    with (
        patch("src.services.care_episode_service.SessionLocal", return_value=mock_session),
        patch("src.services.care_episode_service.get_current_episode", return_value=None),
        patch("src.services.care_episode_service.get_episode_row", return_value=None),
    ):
        yield mock_db


@pytest.fixture
def api_spec():
    spec_path = Path(__file__).parent.parent / "openapi.json"
    with open(spec_path) as f:
        return json.load(f)


@pytest.fixture
def validate_response():
    def _validate(spec, endpoint, method, status_code, data):
        try:
            schema = spec["paths"][endpoint][method]["responses"][str(status_code)]["content"]["application/json"]["schema"]
        except KeyError:
            return
        resolver = _RefResolver.from_schema(spec)
        validate(instance=data, schema=schema, resolver=resolver)
    return _validate

