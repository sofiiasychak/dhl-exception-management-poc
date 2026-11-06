from datetime import date

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app


SECRET = "local-only-demo-signing-key-change-me"


def token(*roles: str, user_id: str = "demo-user"):
    return jwt.encode(
        {
            "iss": "http://localhost:9100",
            "sub": user_id,
            "aud": "local-demo-app-client",
            "cognito:groups": list(roles),
            "exp": 4_102_444_800,
        },
        SECRET,
        algorithm="HS256",
    )


class FakeCaseService:
    def list_cases(self, user):
        return [{"owner_id": user.user_id}]

    def case_detail(self, case_id):
        return {"case_id": case_id, "timeline": [], "actions": [], "messages": []}


class FakeFieldService:
    def list_actions(self, user, day: date):
        return [{"assignee_id": user.user_id, "date": day.isoformat()}]


@pytest.fixture(autouse=True)
def local_auth(monkeypatch):
    monkeypatch.setenv("LOCAL_DEV", "true")
    monkeypatch.setenv("LOCAL_JWT_SECRET", SECRET)
    monkeypatch.setenv("COGNITO_LOCAL_ISSUER", "http://localhost:9100")


def test_case_api_requires_jwt_and_ops_group(monkeypatch):
    monkeypatch.setattr("app.features.cases.router.CaseService", FakeCaseService)
    client = TestClient(app)
    assert client.get("/api/cases").status_code == 401
    assert client.get(
        "/api/cases", headers={"Authorization": f"Bearer {token('support')}"}
    ).status_code == 403
    response = client.get(
        "/api/cases", headers={"Authorization": f"Bearer {token('ops', user_id='marta-l')}"}
    )
    assert response.status_code == 200
    assert response.json() == [{"owner_id": "marta-l"}]


def test_field_actions_require_field_role_and_are_scoped_to_token_user(monkeypatch):
    monkeypatch.setattr("app.features.field.router.FieldService", FakeFieldService)
    client = TestClient(app)
    assert client.get(
        "/api/field/actions",
        headers={"Authorization": f"Bearer {token('ops')}"},
    ).status_code == 403
    response = client.get(
        "/api/field/actions",
        headers={"Authorization": f"Bearer {token('courier', user_id='thomas-a')}"},
    )
    assert response.status_code == 200
    assert response.json()[0]["assignee_id"] == "thomas-a"


def test_case_detail_is_available_to_ops_and_support_only(monkeypatch):
    monkeypatch.setattr("app.features.cases.router.CaseService", FakeCaseService)
    client = TestClient(app)
    assert client.get(
        "/api/cases/EX-1",
        headers={"Authorization": f"Bearer {token('depot')}"},
    ).status_code == 403
    assert client.get(
        "/api/cases/EX-1",
        headers={"Authorization": f"Bearer {token('support')}"},
    ).json()["case_id"] == "EX-1"


def test_communication_queues_are_support_only(monkeypatch):
    class FakeCommunicationService:
        def list_queue(self, queue_name):
            return [{"queue_name": queue_name}]

    monkeypatch.setattr(
        "app.features.communication.router.CommunicationService",
        FakeCommunicationService,
    )
    client = TestClient(app)
    assert client.get(
        "/api/communication/queues/not_informed",
        headers={"Authorization": f"Bearer {token('ops')}"},
    ).status_code == 403
    response = client.get(
        "/api/communication/queues/not_informed",
        headers={"Authorization": f"Bearer {token('support')}"},
    )
    assert response.json() == [{"queue_name": "not_informed"}]


def test_token_with_multiple_role_groups_is_rejected():
    response = TestClient(app).get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token('ops', 'support')}"},
    )
    assert response.status_code == 401


def test_webhook_requires_the_shared_secret(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SHARED_SECRET", "test-secret")
    client = TestClient(app)
    payload = {"case_id": "EX-1", "option_type": "pickup_point"}
    assert client.post("/api/webhooks/odd", json=payload).status_code == 401


def test_webhook_accepts_only_the_shared_secret(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SHARED_SECRET", "test-secret")

    class FakeWebhookService:
        def record_choice(self, case_id, option_type, slot):
            return {"case_id": case_id, "option_type": option_type, "slot": slot}

    monkeypatch.setattr("app.features.webhooks.router.WebhookService", FakeWebhookService)
    response = TestClient(app).post(
        "/api/webhooks/odd",
        json={"case_id": "EX-1", "option_type": "redelivery", "slot": "09:00-12:00"},
        headers={"X-Webhook-Secret": "test-secret"},
    )
    assert response.status_code == 200
    assert response.json()["case_id"] == "EX-1"


def test_authenticator_code_requires_six_digits(monkeypatch):
    monkeypatch.setenv("LOCAL_DEV", "false")
    response = TestClient(app).post(
        "/api/auth/challenge",
        json={"email": "user@example.com", "session": "session", "code": "123"},
    )
    assert response.status_code == 422
