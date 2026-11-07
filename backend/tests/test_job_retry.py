"""Manual job retry policy is bounded, explicit and excludes reinstall."""
import json

from fastapi.testclient import TestClient

from test_api import config
from test_ipa import sample_ipa
from viepn.api import create_app
from viepn.db import utcnow

AUTH = {"Authorization": "Bearer very-long-test-secret-token"}


def insert_job(manager, job_id, kind, state, payload, retry_of=None):
    manager.db.exec(
        "INSERT INTO jobs (id,kind,state,input_json,created_at,updated_at,retry_of) "
        "VALUES (?,?,?,?,?,?,?)",
        (job_id, kind, state, json.dumps(payload), utcnow(), utcnow(), retry_of),
    )


def test_retry_requires_confirmation_and_no_auto_reinstall(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        manager = app.state.manager
        ipa = manager.add_ipa(sample_ipa(tmp_path / "sample.ipa"))
        payload = {"ipa_id": ipa["id"], "udid": "a" * 40}
        insert_job(manager, "failed-install", "apple_install", "failed", payload)
        insert_job(manager, "failed-sign", "apple_sign", "failed", payload)
        url = "/api/jobs/failed-sign/retry"
        assert client.post(url, json={"confirm": "RETRY JOB"}).status_code == 401
        assert client.post(url, headers=AUTH, json={"confirm": "yes"}).status_code == 400
        assert client.post("/api/jobs/failed-install/retry", headers=AUTH,
                           json={"confirm": "RETRY JOB"}).status_code == 409
        ok = client.post(url, headers=AUTH, json={"confirm": "RETRY JOB"})
        assert ok.status_code == 200, ok.text
        assert manager.db.one("SELECT retry_of FROM jobs WHERE id=?",
                              (ok.json()["job_id"],))["retry_of"] == "failed-sign"


def test_retry_budget_per_payload_24_hours(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        manager = app.state.manager
        ipa = manager.add_ipa(sample_ipa(tmp_path / "sample.ipa"))
        payload = {"ipa_id": ipa["id"], "udid": "a" * 40}
        insert_job(manager, "base-sign", "sign", "failed", payload)
        for index in range(3):
            insert_job(manager, "attempt-" + str(index), "sign", "failed", payload,
                       retry_of="base-sign")
        response = client.post("/api/jobs/base-sign/retry", headers=AUTH,
                               json={"confirm": "RETRY JOB"})
        assert response.status_code == 409
        assert "3" in response.json()["detail"]


def test_renew_queue_deduplicated(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        manager = app.state.manager
        insert_job(manager, "active", "renew", "queued", {"installation_id": "renew-1"})
        response = client.post("/api/renew", headers=AUTH,
                               json={"installation_id": "renew-1"})
        assert response.status_code == 404  # No tracking: reject before enqueue.
        assert manager.db.query("SELECT id FROM jobs WHERE kind='renew'") == [{
            'id': 'active'
        }]
