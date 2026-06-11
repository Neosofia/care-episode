import pytest
from flask import Flask, g

from src.authorization import entities

pytestmark = pytest.mark.unit


def test_principal_tenant_uuid_reads_namespaced_claim():
    app = Flask(__name__)
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": "00000000-0000-7000-8000-000000002847",
            "neosofia:tenant_uuid": "00000000-0000-7000-8000-000000000099",
        }
        assert entities.principal_tenant_uuid() == "00000000-0000-7000-8000-000000000099"


def test_principal_tenant_uuid_without_request_context():
    assert entities.principal_tenant_uuid() == ""
