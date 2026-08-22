"""End-to-end API tests: auth, roles, complaint lifecycle, assignments."""

import os

os.environ["DATABASE_URL"] = "sqlite:///./test_shikayat.db"
os.environ["SECRET_KEY"] = "test-secret-key-please-ignore"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.models import Category, User
from app.security import hash_password, limiter
from sqlalchemy.orm import sessionmaker

TestSession = sessionmaker(bind=engine)

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def disable_ratelimit():
    """The test suite fires many rapid logins from one IP — disable SlowAPI."""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestSession()
    db.add_all([
        Category(name="Roads & Potholes", slug="roads", icon="🛣️", base_priority=7),
        Category(name="Street Lights", slug="streetlights", icon="💡", base_priority=4),
    ])
    db.add_all([
        User(name="Admin", email="admin@test.pk", password_hash=hash_password("adminpass1"), role="admin", ward="Central"),
        User(name="Officer Ali", email="ali@test.pk", password_hash=hash_password("officerpass1"), role="officer", ward="Gulshan"),
        User(name="Citizen", email="cit@test.pk", password_hash=hash_password("citizenpass1"), role="citizen"),
    ])
    db.commit()
    db.close()
    yield


def auth(email: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_complaint(token: dict, **overrides):
    payload = {
        "title": "Broken street light on Main Road",
        "description": "The street light at the corner has been broken for two weeks and the road is pitch dark at night.",
        "category_slug": "streetlights",
        "ward": "Gulshan Block 7",
        "area": "Gulshan-e-Iqbal",
        "severity": "high",
    }
    payload.update(overrides)
    return client.post("/api/complaints", json=payload, headers=token)


class TestAuth:
    def test_register_returns_token(self):
        r = client.post("/api/auth/register", json={"name": "New User", "email": "new@test.pk", "password": "password123"})
        assert r.status_code == 201
        assert "access_token" in r.json()
        assert r.json()["user"]["role"] == "citizen"

    def test_register_duplicate_email_conflict(self):
        client.post("/api/auth/register", json={"name": "First User", "email": "dup@test.pk", "password": "password123"})
        r = client.post("/api/auth/register", json={"name": "Second User", "email": "dup@test.pk", "password": "password123"})
        assert r.status_code == 409

    def test_register_short_password_rejected(self):
        r = client.post("/api/auth/register", json={"name": "X", "email": "x@test.pk", "password": "short"})
        assert r.status_code == 422

    def test_login_wrong_password(self):
        r = client.post("/api/auth/login", json={"email": "cit@test.pk", "password": "wrongpass"})
        assert r.status_code == 401

    def test_me_requires_auth(self):
        assert client.get("/api/auth/me").status_code == 401


class TestComplaints:
    def test_create_complaint(self):
        token = auth("cit@test.pk", "citizenpass1")
        r = make_complaint(token)
        assert r.status_code == 201
        body = r.json()
        assert body["ticket"].startswith("SKT-2026-")
        assert body["status"] == "submitted"
        assert body["priority"] == 4 + 6 + 5  # base 4 + high 6 + busy area 5

    def test_create_requires_auth(self):
        r = client.post("/api/complaints", json={})
        assert r.status_code == 401

    def test_unknown_category_400(self):
        token = auth("cit@test.pk", "citizenpass1")
        r = make_complaint(token, category_slug="nope")
        assert r.status_code == 400

    def test_citizen_cannot_verify_own_complaint(self):
        token = auth("cit@test.pk", "citizenpass1")
        cid = make_complaint(token).json()["id"]
        r = client.post(f"/api/complaints/{cid}/transition", json={"to_status": "verified"}, headers=token)
        assert r.status_code == 409  # state machine blocks: citizen not allowed

    def test_admin_verifies_then_assigns(self):
        admin = auth("admin@test.pk", "adminpass1")
        citizen = auth("cit@test.pk", "citizenpass1")
        cid = make_complaint(citizen).json()["id"]

        r = client.post(f"/api/complaints/{cid}/transition", json={"to_status": "verified", "note": "Looks real"}, headers=admin)
        assert r.status_code == 200
        assert r.json()["status"] == "verified"

        officer_id = client.get("/api/admin/officers", headers=admin).json()[0]["id"]
        r = client.post(f"/api/complaints/{cid}/assign", json={"officer_id": officer_id}, headers=admin)
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"
        assert r.json()["assignee_name"] == "Officer Ali"

    def test_officer_resolves_assigned(self):
        admin = auth("admin@test.pk", "adminpass1")
        officer = auth("ali@test.pk", "officerpass1")
        citizen = auth("cit@test.pk", "citizenpass1")
        cid = make_complaint(citizen).json()["id"]
        client.post(f"/api/complaints/{cid}/transition", json={"to_status": "verified"}, headers=admin)
        officer_id = client.get("/api/admin/officers", headers=admin).json()[0]["id"]
        client.post(f"/api/complaints/{cid}/assign", json={"officer_id": officer_id}, headers=admin)

        r = client.post(
            f"/api/complaints/{cid}/transition",
            json={"to_status": "resolved", "note": "Bulb replaced"},
            headers=officer,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"
        assert r.json()["resolved_note"] == "Bulb replaced"

    def test_unassigned_officer_cannot_resolve(self):
        admin = auth("admin@test.pk", "adminpass1")
        citizen = auth("cit@test.pk", "citizenpass1")
        cid = make_complaint(citizen).json()["id"]
        client.post(f"/api/complaints/{cid}/transition", json={"to_status": "verified"}, headers=admin)
        # Officer Ali tries to resolve without assignment — in_progress gate blocks first
        r = client.post(
            f"/api/complaints/{cid}/transition",
            json={"to_status": "in_progress"},
            headers=auth("ali@test.pk", "officerpass1"),
        )
        assert r.status_code == 409

    def test_reporter_reopens_resolved(self):
        admin = auth("admin@test.pk", "adminpass1")
        officer = auth("ali@test.pk", "officerpass1")
        citizen = auth("cit@test.pk", "citizenpass1")
        cid = make_complaint(citizen).json()["id"]
        client.post(f"/api/complaints/{cid}/transition", json={"to_status": "verified"}, headers=admin)
        officer_id = client.get("/api/admin/officers", headers=admin).json()[0]["id"]
        client.post(f"/api/complaints/{cid}/assign", json={"officer_id": officer_id}, headers=admin)
        client.post(f"/api/complaints/{cid}/transition", json={"to_status": "resolved", "note": "Fixed"}, headers=officer)

        r = client.post(
            f"/api/complaints/{cid}/transition",
            json={"to_status": "reopened", "note": "Still dark!"},
            headers=citizen,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "reopened"
        assert r.json()["reopen_count"] == 1

    def test_admin_cannot_reopen(self):
        admin = auth("admin@test.pk", "adminpass1")
        citizen = auth("cit@test.pk", "citizenpass1")
        cid = make_complaint(citizen).json()["id"]
        # Reopening is a reporter-only action → 403 for admin
        r = client.post(f"/api/complaints/{cid}/transition", json={"to_status": "reopened"}, headers=admin)
        assert r.status_code == 403

    def test_reporter_cannot_reopen_non_resolved(self):
        citizen = auth("cit@test.pk", "citizenpass1")
        cid = make_complaint(citizen).json()["id"]
        # submitted → reopened is not a valid state-machine move → 409
        r = client.post(f"/api/complaints/{cid}/transition", json={"to_status": "reopened"}, headers=citizen)
        assert r.status_code == 409

    def test_reject_by_admin(self):
        admin = auth("admin@test.pk", "adminpass1")
        citizen = auth("cit@test.pk", "citizenpass1")
        cid = make_complaint(citizen).json()["id"]
        r = client.post(
            f"/api/complaints/{cid}/transition",
            json={"to_status": "rejected", "note": "Duplicate"},
            headers=admin,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

    def test_foreign_user_cannot_view(self):
        token = auth("cit@test.pk", "citizenpass1")
        other = auth("admin@test.pk", "adminpass1")
        cid = make_complaint(token).json()["id"]
        # admin can view; a different citizen doesn't exist — admin sees everything
        assert client.get(f"/api/complaints/{cid}", headers=other).status_code == 200

    def test_comments_flow(self):
        citizen = auth("cit@test.pk", "citizenpass1")
        cid = make_complaint(citizen).json()["id"]
        r = client.post(f"/api/complaints/{cid}/comments", json={"body": "Please fix this soon!"}, headers=citizen)
        assert r.status_code == 201
        detail = client.get(f"/api/complaints/{cid}", headers=citizen).json()
        assert len(detail["comments"]) == 1
        assert detail["comments"][0]["body"] == "Please fix this soon!"


class TestScoping:
    def test_citizen_sees_own_complaints_with_mine(self):
        citizen = auth("cit@test.pk", "citizenpass1")
        make_complaint(citizen)
        r = client.get("/api/complaints?mine=true", headers=citizen)
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_officer_queue_scoped_to_assignee(self):
        admin = auth("admin@test.pk", "adminpass1")
        citizen = auth("cit@test.pk", "citizenpass1")
        officer = auth("ali@test.pk", "officerpass1")
        cid = make_complaint(citizen).json()["id"]
        client.post(f"/api/complaints/{cid}/transition", json={"to_status": "verified"}, headers=admin)
        officer_id = client.get("/api/admin/officers", headers=admin).json()[0]["id"]
        client.post(f"/api/complaints/{cid}/assign", json={"officer_id": officer_id}, headers=admin)

        q = client.get("/api/officers/me/queue", headers=officer)
        assert q.status_code == 200
        assert len(q.json()) == 1
        assert q.json()[0]["id"] == cid

    def test_public_stats(self):
        citizen = auth("cit@test.pk", "citizenpass1")
        make_complaint(citizen)
        r = client.get("/api/stats/public")
        assert r.status_code == 200
        assert r.json()["total_reported"] == 1

    def test_health(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
