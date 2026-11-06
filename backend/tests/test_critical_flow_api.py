from datetime import date

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import build_demo_items


SECRET = "local-only-demo-signing-key-change-me"


def make_token(user_id: str, role: str):
    return jwt.encode(
        {
            "iss": "http://localhost:9100",
            "sub": user_id,
            "cognito:groups": [role],
            "exp": 4_102_444_800,
        },
        SECRET,
        algorithm="HS256",
    )


class MemoryCaseRepository:
    def __init__(self):
        self.items = {
            (item["PK"], item["SK"]): dict(item)
            for item in build_demo_items()
        }

    def list_ops_cases(self, owner_id=None, tab="mine"):
        partition = {
            "mine": f"OPS#OWNER#{owner_id}",
            "unassigned": "OPS#ALL#OPEN",
            "overdue": "OPS#ALL#OPEN",
            "all_open": "OPS#ALL#OPEN",
        }[tab]
        return [item for item in self.items.values() if item.get("GSI1PK") == partition]

    def list_queue(self, index, partition):
        return [item for item in self.items.values() if item.get(f"{index}PK") == partition]

    def get_case(self, case_id):
        return [item for item in self.items.values() if item["PK"] == f"CASE#{case_id}"]

    def find_open_case(self, shipment_id, exception_type):
        return [
            item for item in self.items.values()
            if item.get("entity_type") == "case"
            and item.get("shipment_id") == shipment_id
            and item.get("exception_type") == exception_type
            and item.get("status") != "resolved"
        ]

    def get_shipment(self, shipment_id):
        return self.items.get((f"SHIPMENT#{shipment_id}", "META"))

    def get_user(self, user_id):
        return self.items.get((f"USER#{user_id}", "META"))

    def list_users(self, role=None):
        return [
            item for item in self.items.values()
            if item.get("entity_type") == "user" and (role is None or item.get("role") == role)
        ]

    def next_case_id(self):
        item = self.items[("SYSTEM#CASE_COUNTER", "META")]
        number = item["next_case_number"]
        item["next_case_number"] += 1
        return f"EX-{number}"

    def put_item(self, item):
        self.items[(item["PK"], item["SK"])] = dict(item)

    def delete_item(self, pk, sk):
        self.items.pop((pk, sk), None)

    def remove_case(self, case_id):
        for item in self.get_case(case_id):
            self.delete_item(item["PK"], item["SK"])

    def query_field_actions(self, user_id, day):
        return [
            item for item in self.items.values()
            if item.get("GSI3PK") == f"FIELD#{user_id}#{day}"
        ]

    def find_route_action(self, shipment_id, assignee_id, day):
        return next(
            (item for item in self.query_field_actions(assignee_id, day)
             if item.get("shipment_id") == shipment_id
             and item.get("action_type") in {"Delivery", "Redelivery"}
             and item.get("status") not in {"done", "cancelled"}),
            None,
        )

    def lookup_shipments(self, shipment_id):
        return self.get_shipment(shipment_id)


@pytest.fixture
def flow_client(monkeypatch):
    monkeypatch.setenv("LOCAL_DEV", "true")
    monkeypatch.setenv("LOCAL_JWT_SECRET", SECRET)
    monkeypatch.setenv("COGNITO_LOCAL_ISSUER", "http://localhost:9100")
    repository = MemoryCaseRepository()
    monkeypatch.setattr("app.features.cases.service.CaseRepository", lambda: repository)
    monkeypatch.setattr("app.features.communication.repository.CaseRepository", lambda: repository)
    return TestClient(app), repository


def auth(user_id: str, role: str):
    return {"Authorization": f"Bearer {make_token(user_id, role)}"}


def test_critical_shipment_exception_flow_persists_every_step(flow_client):
    client, repository = flow_client
    courier = auth("thomas-a", "courier")
    operations = auth("marta-l", "ops")
    support = auth("kateryna-b", "support")

    actions = client.get("/api/field/actions", headers=courier)
    assert actions.status_code == 200
    target_action = next(
        action for action in actions.json() if action["shipment_id"] == "4836201759"
    )

    report = client.post(
        "/api/field/reports/failed-delivery",
        data={
            "shipment_id": "4836201759",
            "reason": "Not at home",
            "taps_count": "3",
            "duration_sec": "8",
        },
        headers=courier,
    )
    assert report.status_code == 200, report.text
    case_id = report.json()["case_id"]
    assert case_id == "EX-10482"

    ops_queue = client.get("/api/cases?tab=mine", headers=operations)
    assert ops_queue.status_code == 200
    assert any(case["case_id"] == case_id for case in ops_queue.json())
    case_before_action = client.get(f"/api/cases/{case_id}", headers=operations).json()
    assert case_before_action["gps_flagged"] is False
    assert any(item["event"] == "failed_delivery_reported" for item in case_before_action["timeline"])

    priority = client.post(
        f"/api/cases/{case_id}/priority",
        json={"priority": "medium", "reason": "Reassessed after customer contact"},
        headers=operations,
    )
    assert priority.status_code == 200, priority.text
    reassigned = client.post(
        f"/api/cases/{case_id}/owner",
        json={"owner_id": "oleh-s"},
        headers=operations,
    )
    assert reassigned.status_code == 200, reassigned.text
    returned = client.post(
        f"/api/cases/{case_id}/owner",
        json={"owner_id": "marta-l"},
        headers=operations,
    )
    assert returned.status_code == 200, returned.text

    assign = client.post(
        f"/api/cases/{case_id}/actions",
        json={"action_type": "Redelivery", "assignee_id": "thomas-a"},
        headers=operations,
    )
    assert assign.status_code == 200, assign.text
    assert assign.json()["assignee_id"] == "thomas-a"

    support_queue = client.get(
        "/api/communication/queues/not_informed", headers=support
    )
    assert support_queue.status_code == 200
    assert any(case["case_id"] == case_id for case in support_queue.json())
    lookup = client.get(
        "/api/communication/shipments/4836201759", headers=support
    )
    assert lookup.status_code == 200
    assert lookup.json()["shipment_id"] == "4836201759"

    message = client.post(
        f"/api/communication/cases/{case_id}/messages",
        json={
            "template_id": "failed-delivery-options",
            "channel": "SMS and Email",
            "body": "Please choose a delivery option.",
        },
        headers=support,
    )
    assert message.status_code == 200, message.text
    duplicate = client.post(
        f"/api/communication/cases/{case_id}/messages",
        json={
            "template_id": "failed-delivery-options",
            "channel": "SMS and Email",
            "body": "Duplicate update.",
        },
        headers=support,
    )
    assert duplicate.status_code == 409

    choice = client.post(
        "/api/communication/simulator/choice",
        json={
            "case_id": case_id,
            "option_type": "redelivery",
            "slot": "09:00–12:00",
        },
        headers=support,
    )
    assert choice.status_code == 200, choice.text
    assert choice.json()["customer_slot"] == "09:00–12:00"

    courier_actions = client.get("/api/field/actions", headers=courier).json()
    redelivery = next(action for action in courier_actions if action["case_id"] == case_id)
    assert redelivery["slot"] == "09:00–12:00"
    completed = client.post(
        f"/api/field/actions/{redelivery['action_id']}/complete",
        headers=courier,
    )
    assert completed.status_code == 200

    resolution = client.post(
        f"/api/cases/{case_id}/resolve",
        json={
            "outcome": "Delivered on the second attempt",
            "root_cause": "Recipient not at home",
            "send_confirmation": True,
        },
        headers=operations,
    )
    assert resolution.status_code == 200, resolution.text
    final = client.get(f"/api/cases/{case_id}", headers=operations).json()
    required_events = {
        "exception_case_created",
        "exception_priority_set",
        "case_owner_assigned",
        "failed_delivery_reported",
        "case_action_updated",
        "customer_notified",
        "resolution_option_recorded",
        "case_status_changed",
        "case_resolved",
    }
    assert required_events.issubset({entry["event"] for entry in final["timeline"]})
    assert final["status"] == "resolved"
    assert final["resolved_on_time"] is True
    assert len(final["messages"]) == 2
    assert repository.get_case(case_id)
    reopened = client.post(
        f"/api/cases/{case_id}/reopen",
        json={"reason": "Customer reports the parcel is still missing."},
        headers=operations,
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "in_progress"


def test_duplicate_report_adds_timeline_to_the_existing_open_case(flow_client):
    client, repository = flow_client
    courier = auth("thomas-a", "courier")
    data = {
        "shipment_id": "4836201759",
        "reason": "Not at home",
        "taps_count": "3",
        "duration_sec": "5",
    }
    first = client.post("/api/field/reports/failed-delivery", data=data, headers=courier)
    assert first.status_code == 200
    second = client.post("/api/field/reports/failed-delivery", data=data, headers=courier)
    assert second.status_code == 200
    assert second.json()["case_id"] == first.json()["case_id"]
    assert second.json()["created"] is False
    case = client.get(f"/api/cases/{first.json()['case_id']}", headers=auth("marta-l", "ops")).json()
    assert len([item for item in case["timeline"] if item["event"] == "failed_delivery_reported"]) == 2


def test_support_cannot_assign_or_reassign_case(flow_client):
    client, _repository = flow_client
    response = client.post(
        "/api/cases/EX-10480/actions",
        json={"action_type": "Redelivery", "assignee_id": "thomas-a"},
        headers=auth("kateryna-b", "support"),
    )
    assert response.status_code == 403
    response = client.post(
        "/api/cases/EX-10480/owner",
        json={"owner_id": "oleh-s"},
        headers=auth("kateryna-b", "support"),
    )
    assert response.status_code == 403


def test_depot_damage_requires_photo_and_creates_shared_case(flow_client, monkeypatch):
    client, _repository = flow_client
    monkeypatch.setattr("app.features.field.router.save_photo", lambda *_args: "evidence/photo.jpg")
    response = client.post(
        "/api/field/reports/damage",
        data={
            "shipment_id": "4836201759",
            "damage_types": ["Crushed box"],
            "contents_checked": "true",
        },
        files=[("photos", ("parcel.jpg", b"image", "image/jpeg"))],
        headers=auth("anna-k", "depot"),
    )
    assert response.status_code == 200, response.text
    case = client.get(f"/api/cases/{response.json()['case_id']}", headers=auth("marta-l", "ops")).json()
    assert case["exception_type"] == "damaged_parcel"
    assert any(item["event"] == "field_report_added" for item in case["timeline"])


@pytest.mark.parametrize(
    ("taps_count", "duration_sec"),
    [(4, 8), (3, 15), (3, -1)],
)
def test_failed_delivery_reports_are_limited_to_three_taps_and_under_15_seconds(
    flow_client, taps_count, duration_sec
):
    client, _repository = flow_client
    response = client.post(
        "/api/field/reports/failed-delivery",
        data={
            "shipment_id": "4836201759",
            "reason": "Not at home",
            "taps_count": str(taps_count),
            "duration_sec": str(duration_sec),
        },
        headers=auth("thomas-a", "courier"),
    )
    assert response.status_code == 422


def test_undoing_first_report_restores_the_route_action(flow_client):
    client, _repository = flow_client
    courier = auth("thomas-a", "courier")
    report = client.post(
        "/api/field/reports/failed-delivery",
        data={
            "shipment_id": "4836201759",
            "reason": "Not at home",
            "taps_count": "3",
            "duration_sec": "5",
        },
        headers=courier,
    )
    assert report.status_code == 200
    case_id = report.json()["case_id"]

    undo = client.post(
        f"/api/field/reports/{case_id}/undo",
        json={"report_id": report.json()["report_id"]},
        headers=courier,
    )
    assert undo.status_code == 200
    assert client.get(f"/api/cases/{case_id}", headers=auth("marta-l", "ops")).status_code == 404
    actions = client.get("/api/field/actions", headers=courier).json()
    assert any(action["shipment_id"] == "4836201759" for action in actions)


def test_undoing_repeat_report_restores_attempt_and_redelivery_action(flow_client):
    client, repository = flow_client
    courier = auth("thomas-a", "courier")
    report_data = {
        "shipment_id": "4836201759",
        "reason": "Not at home",
        "taps_count": "3",
        "duration_sec": "5",
    }
    first = client.post(
        "/api/field/reports/failed-delivery", data=report_data, headers=courier
    )
    assert first.status_code == 200
    case_id = first.json()["case_id"]
    assigned = client.post(
        f"/api/cases/{case_id}/actions",
        json={"action_type": "Redelivery", "assignee_id": "thomas-a"},
        headers=auth("marta-l", "ops"),
    )
    assert assigned.status_code == 200

    repeat = client.post(
        "/api/field/reports/failed-delivery", data=report_data, headers=courier
    )
    assert repeat.status_code == 200
    report_event = next(
        item for item in repository.items.values()
        if item.get("report_id") == repeat.json()["report_id"]
        and item.get("event") == "failed_delivery_reported"
    )
    assert report_event["prior_attempt_count"] == 1
    assert report_event["created_case_before_report"] is False
    undo = client.post(
        f"/api/field/reports/{case_id}/undo",
        json={"report_id": repeat.json()["report_id"]},
        headers=courier,
    )
    assert undo.status_code == 200

    case = client.get(f"/api/cases/{case_id}", headers=auth("marta-l", "ops")).json()
    assert case["attempt_count"] == 1
    assert len([item for item in case["timeline"] if item["event"] == "failed_delivery_reported"]) == 1
    actions = client.get("/api/field/actions", headers=courier).json()
    assert any(
        action["case_id"] == case_id and action["status"] == "open"
        for action in actions
    )
