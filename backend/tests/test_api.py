"""API smoke tests, including the upload validation paths."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os

    os.environ["HARDWARE_SETS_STORAGE"] = str(tmp_path_factory.mktemp("storage"))
    import importlib

    from hardware_sets import api

    importlib.reload(api)
    with TestClient(api.app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def uploaded(client, fixtures_dir):
    pdf = fixtures_dir / "fixture_01_table_schedule.pdf"
    response = client.post(
        "/extract", files={"file": ("schedule.pdf", pdf.read_bytes(), "application/pdf")}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_extract_returns_the_full_result(uploaded):
    assert uploaded["filename"] == "schedule.pdf"
    numbers = [s["set_number"] for s in uploaded["result"]["hardware_sets"]]
    assert numbers == ["1", "2", "3", "4", "5"]


def test_document_can_be_fetched_again(client, uploaded):
    response = client.get(f"/documents/{uploaded['document_id']}")
    assert response.status_code == 200
    assert response.json()["result"] == uploaded["result"]


def test_page_image_renders(client, uploaded):
    response = client.get(f"/documents/{uploaded['document_id']}/pages/1.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_page_out_of_range(client, uploaded):
    assert client.get(f"/documents/{uploaded['document_id']}/pages/99.png").status_code == 404


def test_feedback_round_trip(client, uploaded):
    corrected = uploaded["result"]["hardware_sets"][:1]
    corrected[0]["components"][0]["mfr"] = "MCKINNEY"
    save = client.post(
        f"/documents/{uploaded['document_id']}/feedback",
        json={"hardware_sets": corrected, "note": "expanded the abbreviation"},
    )
    assert save.status_code == 200
    loaded = client.get(f"/documents/{uploaded['document_id']}/feedback").json()
    assert loaded["hardware_sets"][0]["components"][0]["mfr"] == "MCKINNEY"
    assert loaded["note"] == "expanded the abbreviation"


def test_non_pdf_upload_is_rejected(client):
    response = client.post("/extract", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415


def test_empty_upload_is_rejected(client):
    response = client.post("/extract", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert response.status_code == 400


def test_malformed_document_id_is_rejected(client):
    assert client.get("/documents/..%2Fetc/pages/1.png").status_code in (400, 404)
    assert client.get("/documents/not-a-uuid").status_code == 400
