import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import main as main_module
from database import init_db


@pytest.fixture
def client(tmp_path):
    db_file = str(tmp_path / "test.db")
    init_db(db_file)
    main_module.app.config["TESTING"] = True
    original = main_module.db_path
    main_module.db_path = db_file
    with main_module.app.test_client() as c:
        yield c
    main_module.db_path = original


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"

def test_submit_missing_url(client):
    resp = client.post("/api/v1/summaries", json={})
    assert resp.status_code == 400

def test_submit_invalid_url(client):
    resp = client.post("/api/v1/summaries", json={"url": "not-a-url"})
    assert resp.status_code == 400

def test_submit_success(client, mocker):
    mocker.patch("main.start_processing_thread")
    resp = client.post("/api/v1/summaries",
                       json={"url": "https://www.sec.gov/Archives/edgar/data/320193/test.txt"})
    assert resp.status_code == 202
    assert "id" in resp.get_json()

def test_get_not_found(client):
    assert client.get("/api/v1/summaries/9999").status_code == 404

def test_list_empty(client):
    data = client.get("/api/v1/summaries").get_json()
    assert data["total"] == 0

def test_list_and_get(client, mocker):
    mocker.patch("main.start_processing_thread")
    job_id = client.post("/api/v1/summaries",
                         json={"url": "https://www.sec.gov/Archives/edgar/data/320193/test.txt"}
                         ).get_json()["id"]
    assert client.get("/api/v1/summaries").get_json()["total"] == 1
    assert client.get(f"/api/v1/summaries/{job_id}").status_code == 200
