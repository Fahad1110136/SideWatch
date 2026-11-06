from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.app.core import errors
from backend.app.core.errors import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)


class Body(BaseModel):
    n: int


@app.get("/forbidden")
def _forbidden():
    raise errors.forbidden()


@app.get("/boom")
def _boom():
    raise RuntimeError("secret internal detail")


@app.post("/validate")
def _validate(b: Body):
    return b


client = TestClient(app, raise_server_exceptions=False)


def test_app_error_shape():
    r = client.get("/forbidden")
    assert r.status_code == 403
    assert r.json()["code"] == "ACCESS_DENIED" and r.json()["request_id"]


def test_unexpected_error_hides_details():
    r = client.get("/boom")
    assert r.status_code == 500
    assert r.json()["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in r.text and "Traceback" not in r.text


def test_validation_error_does_not_echo_input():
    r = client.post("/validate", json={"n": "SENSITIVE-VALUE"})
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"
    assert "SENSITIVE-VALUE" not in r.text


def test_unknown_route_is_safe_404():
    assert client.get("/nope").json()["code"] == "NOT_FOUND"