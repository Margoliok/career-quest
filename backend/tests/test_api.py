"""API интеграциялық тесттері (толтырылған дерекқор қажет: scripts.seed). ДҚ қолжетімсіз болса өткізіледі."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine


def _db_ready() -> bool:
    try:
        with engine.connect() as c:
            return bool(c.execute(text("SELECT count(*) FROM users")).scalar())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="seeded database is not available")


@pytest.fixture(scope="module")
def client():
    from app.main import app

    return TestClient(app)


def login(client, username):
    r = client.post("/api/auth/login", data={"username": username, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


def test_login_wrong_password(client):
    assert client.post("/api/auth/login", data={"username": "employee", "password": "x"}).status_code == 401


def test_employee_sees_only_self(client):
    h, me = login(client, "employee")
    assert client.get(f"/api/profiles/{me['employee_id']}/skills", headers=h).status_code == 200
    other = me["employee_id"] + 1
    assert client.get(f"/api/profiles/{other}/skills", headers=h).status_code == 403
    assert len(client.get("/api/employees", headers=h).json()) == 1
    assert client.get("/api/hr/audit", headers=h).status_code == 403


def test_manager_department_scope(client):
    h, me = login(client, "manager")
    emps = client.get("/api/employees", headers=h).json()
    assert emps and all(e["department_id"] == me["department_id"] for e in emps)


def test_employee_cannot_confirm_skill(client):
    h, me = login(client, "employee")
    skills = client.get(f"/api/profiles/{me['employee_id']}/skills", headers=h).json()
    r = client.patch(f"/api/profiles/{me['employee_id']}/skills", headers=h,
                     json={"esco_id": skills[0]["esco_id"], "status": "confirmed"})
    assert r.status_code == 403


def test_gap_and_recommendations(client):
    h, me = login(client, "employee")
    g = client.get(f"/api/profiles/{me['employee_id']}/gap", headers=h).json()
    assert 0 <= g["coverage"] <= 1
    pr = [m["priority"] for m in g["missing"]]
    assert pr == sorted(pr, reverse=True)
    r = client.get(f"/api/profiles/{me['employee_id']}/recommendations", params={"alpha": 0.0}, headers=h).json()
    covs = [x["coverage"] for x in r["roles"]]
    assert covs == sorted(covs, reverse=True)  # α = 0 → тек дағдылар бойынша рейтинг


def test_guardrail_refuses_salary_question(client):
    h, _ = login(client, "employee")
    r = client.post("/api/chat", headers=h, json={"message": "Маған қанша жалақы төлеу керек?"}).json()
    assert r["mode"] == "guardrail" and not r["tool_calls"]


def test_idp_workflow_requires_manager(client):
    h, me = login(client, "employee")
    idp = client.post("/api/idp", headers=h, json={"employee_id": me["employee_id"], "lang": "ru",
                                                   "use_llm": False}).json()
    assert idp["status"] == "draft" and idp["plan"]["phases"]
    assert client.patch(f"/api/idp/{idp['id']}/approve", headers=h, json={"decision": "approved"}).status_code == 403
    assert client.post(f"/api/idp/{idp['id']}/submit", headers=h).json()["status"] == "submitted"
    hm, _ = login(client, "manager")
    assert client.patch(f"/api/idp/{idp['id']}/approve", headers=hm,
                        json={"decision": "returned", "comment": "SQL бөлімін нақтылаңыз"}).json()["status"] == "returned"
