from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.core.rules import ExceptionType, Priority
from app.features.auth.service import DEMO_USERS
from app.storage import ensure_local_table, get_table


UTC = timezone.utc
NOW = datetime.now(UTC)


def ago(**delta) -> datetime:
    return NOW - timedelta(**delta)


def base_shipment(shipment_id: str, region: str = "Kyiv-East", **updates):
    shipment = {
        "PK": f"SHIPMENT#{shipment_id}",
        "SK": "META",
        "entity_type": "shipment",
        "shipment_id": shipment_id,
        "product": "Standard",
        "key_account": False,
        "origin": "Warsaw",
        "destination": "Kyiv",
        "recipient_name": "Mock Recipient",
        "masked_phone": "+380 •• ••• •• ••",
        "masked_email": "r••••••••@•••.ua",
        "address": "Kyiv (fictional address)",
        "region": region,
        "route": "K-14",
        "stop": 6,
        "promised_delivery_date": (NOW + timedelta(days=1)).date().isoformat(),
    }
    shipment.update(updates)
    return shipment


def case_record(
    *,
    case_id: str,
    shipment: dict,
    exception_type: ExceptionType,
    priority: Priority,
    rule_id: str,
    status: str,
    owner_id: str | None,
    age: timedelta,
    messages_sent: bool,
    action_text: str,
):
    created = NOW - age
    deadline = created + timedelta(hours=48)
    rank = {Priority.HIGH: "0", Priority.MEDIUM: "1", Priority.LOW: "2"}[priority]
    sort_key = f"{rank}#{deadline.isoformat()}#{created.isoformat()}#{case_id}"
    support_state = (
        "not_informed"
        if not messages_sent
        else "waiting_for_customer"
        if status == "waiting_for_customer"
        else None
    )
    metadata = {
        "PK": f"CASE#{case_id}",
        "SK": "META",
        "entity_type": "case",
        "case_id": case_id,
        "shipment_id": shipment["shipment_id"],
        "exception_type": exception_type.value,
        "priority": priority.value,
        "priority_rule_id": rule_id,
        "priority_set_by": "auto",
        "status": status,
        "owner_id": owner_id,
        "owner_role": "ops",
        "assignment_type": "auto",
        "region": shipment["region"],
        "created_at": created.isoformat(),
        "deadline_at": deadline.isoformat(),
        "customer_informed": messages_sent,
        "messages_sent": messages_sent,
        "resolution_message_sent": False,
        "next_action": action_text,
        "gps_flagged": False,
        "shipment": {
            key: value
            for key, value in shipment.items()
            if key not in {"PK", "SK", "entity_type"}
        },
        "GSI3PK": f"SHIPMENT#{shipment['shipment_id']}",
        "GSI3SK": f"CASE#{exception_type.value}#OPEN#{case_id}",
    }
    records = [metadata]
    if owner_id:
        records.append({
            "PK": metadata["PK"],
            "SK": "Q#OPS#OWNER",
            "entity_type": "queue",
            "case_id": case_id,
            "exception_type": exception_type.value,
            "priority": priority.value,
            "status": status,
            "owner_id": owner_id,
            "region": shipment["region"],
            "deadline_at": deadline.isoformat(),
            "created_at": created.isoformat(),
            "GSI1PK": f"OPS#OWNER#{owner_id}",
            "GSI1SK": sort_key,
        })
    records.append({
        "PK": metadata["PK"],
        "SK": "Q#OPS#ALL",
        "entity_type": "queue",
        "case_id": case_id,
        "exception_type": exception_type.value,
        "priority": priority.value,
        "status": status,
        "owner_id": owner_id,
        "region": shipment["region"],
        "deadline_at": deadline.isoformat(),
        "created_at": created.isoformat(),
        "GSI1PK": "OPS#ALL#OPEN",
        "GSI1SK": sort_key,
    })
    if support_state:
        records.append({
            "PK": metadata["PK"],
            "SK": f"Q#SUPPORT#{support_state}",
            "entity_type": "queue",
            "case_id": case_id,
            "exception_type": exception_type.value,
            "priority": priority.value,
            "status": status,
            "created_at": created.isoformat(),
            "GSI2PK": f"SUPPORT#{support_state}",
            "GSI2SK": f"{rank}#{created.isoformat()}#{case_id}",
        })
    records.append({
        "PK": metadata["PK"],
        "SK": f"TL#{created.isoformat()}#created",
        "entity_type": "timeline",
        "event": "exception_case_created",
        "actor": "system",
        "at": created.isoformat(),
        "summary": "Platform created and classified the case.",
    })
    records.append({
        "PK": metadata["PK"],
        "SK": f"TL#{created.isoformat()}#priority",
        "entity_type": "timeline",
        "event": "exception_priority_set",
        "actor": "system",
        "at": created.isoformat(),
        "rule_id": rule_id,
        "priority": priority.value,
    })
    if owner_id:
        records.append({
            "PK": metadata["PK"],
            "SK": f"TL#{created.isoformat()}#owner",
            "entity_type": "timeline",
            "event": "case_owner_assigned",
            "actor": "system",
            "at": created.isoformat(),
            "owner_id": owner_id,
            "assignment_type": "auto",
        })
    if status == "waiting_for_customer":
        records.append({
            "PK": metadata["PK"],
            "SK": f"MSG#{created.isoformat()}#demo",
            "entity_type": "message",
            "template_id": "failed-delivery-options",
            "channels": ["sms", "email"],
            "sender_id": "kateryna-b",
            "sent_at": created.isoformat(),
            "notified_before_customer_contact": True,
            "body": "Fictional demo message body.",
        })
    if action_text != "— not assigned":
        records.append({
            "PK": metadata["PK"],
            "SK": f"ACTION#{uuid4().hex}",
            "entity_type": "action",
            "action_id": f"{case_id}-action",
            "action_type": action_text,
            "assignee_id": "thomas-a" if "Courier" in action_text else "anna-k",
            "status": "open",
        })
    return records


def build_demo_items():
    users = [
        {
            "PK": f"USER#{user_id}",
            "SK": "META",
            "entity_type": "user",
            "user_id": user_id,
            "role": role,
            "name": name,
            "scope": scope,
            "email": DEMO_USERS[user_id]["email"],
        }
        for user_id, role, name, scope in [
            ("marta-l", "ops", "Marta L.", "Kyiv-East"),
            ("oleh-s", "ops", "Oleh S.", "Kyiv-West"),
            ("kateryna-b", "support", "Kateryna B.", ""),
            ("thomas-a", "courier", "Thomas A.", "K-14"),
            ("ivan-s", "courier", "Ivan S.", "K-09"),
            ("anna-k", "depot", "Anna K.", "Kyiv Hub"),
        ]
    ]
    shipment_data = [
        ("7710389245", {"product": "Standard", "key_account": True}),
        ("5127704361", {}),
        ("3398016627", {}),
        ("6620145873", {"product": "Time-definite · by 12:00"}),
        ("9054127738", {}),
        ("2261907345", {}),
        ("8840512276", {}),
        (
            "4836201759",
            {
                "product": "Time-definite · by 12:00",
                "recipient_name": "O. Hrytsenko",
                "masked_phone": "+380 •• ••• 41 27",
                "masked_email": "o.h•••@•••.ua",
                "address": "vul. Sadova 14, apt 9, Kyiv",
                "route": "K-14",
                "stop": 6,
                "promised_delivery_date": NOW.date().isoformat(),
            },
        ),
    ]
    shipments = [base_shipment(shipment_id, **details) for shipment_id, details in shipment_data]
    shipment_by_id = {shipment["shipment_id"]: shipment for shipment in shipments}
    route_addresses = {
        5: "vul. Lisova 7",
        6: "vul. Sadova 14, apt 9, Kyiv",
        7: "vul. Zelena 21, office 4",
        8: "vul. Sadova 30",
    }
    for stop in range(1, 24):
        shipment_id = "4836201759" if stop == 6 else f"48362017{stop:02d}"
        if shipment_id not in shipment_by_id:
            shipment = base_shipment(
                shipment_id,
                route="K-14",
                stop=stop,
                recipient_name="Demo Recipient",
                address=route_addresses.get(stop, f"vul. Demo {stop}, Kyiv"),
                product="Standard",
                promised_delivery_date=NOW.date().isoformat(),
            )
            shipments.append(shipment)
            shipment_by_id[shipment_id] = shipment
    definitions = [
        ("EX-10458", "7710389245", ExceptionType.CUSTOMS_HOLD, Priority.HIGH, "P1",
         "waiting_for_customs", "marta-l", timedelta(hours=50), True, "Customs broker"),
        ("EX-10463", "5127704361", ExceptionType.FAILED_DELIVERY, Priority.MEDIUM, "default",
         "waiting_for_customer", "marta-l", timedelta(hours=30), True, "Customer (choosing)"),
        ("EX-10466", "3398016627", ExceptionType.DELAY, Priority.MEDIUM, "default",
         "in_progress", "marta-l", timedelta(hours=26), True, "Linehaul · Warsaw hub"),
        ("EX-10471", "6620145873", ExceptionType.DAMAGED_PARCEL, Priority.HIGH, "P2",
         "in_progress", "marta-l", timedelta(hours=17), True, "Depot · Kyiv Hub (Anna K.)"),
        ("EX-10477", "9054127738", ExceptionType.DELAY, Priority.LOW, "P4",
         "in_progress", "marta-l", timedelta(hours=8), True, "Courier Ivan S."),
        ("EX-10480", "2261907345", ExceptionType.DAMAGED_PARCEL, Priority.MEDIUM, "default",
         "new", "marta-l", timedelta(minutes=9), False, "— not assigned"),
        ("EX-10481", "8840512276", ExceptionType.DELAY, Priority.MEDIUM, "default",
         "new", "marta-l", timedelta(minutes=4), False, "— not assigned"),
    ]
    cases = []
    for (case_id, shipment_id, exception_type, priority, rule_id, status, owner_id,
         age, messages_sent, action_text) in definitions:
        cases.extend(case_record(
            case_id=case_id,
            shipment=shipment_by_id[shipment_id],
            exception_type=exception_type,
            priority=priority,
            rule_id=rule_id,
            status=status,
            owner_id=owner_id,
            age=age,
            messages_sent=messages_sent,
            action_text=action_text,
        ))

    today = date.today().isoformat()
    field_actions = [
        {
            "PK": f"CASE#{case_id}",
            "SK": f"ACTION#{case_id}-route",
            "entity_type": "action",
            "action_id": f"{case_id}-route",
            "case_id": case_id,
            "shipment_id": shipment_id,
            "action_type": "Delivery",
            "assignee_id": assignee,
            "status": "open",
            "route_order": order,
            "date": today,
            "GSI3PK": f"FIELD#{assignee}#{today}",
            "GSI3SK": f"{order:04d}#{case_id}",
        }
        for order in range(1, 24)
        for case_id, shipment_id, assignee in [
            (
                f"ROUTE-STOP-{order:02d}",
                "4836201759" if order == 6 else f"48362017{order:02d}",
                "thomas-a",
            )
        ]
    ]
    cursor = {
        "PK": "SYSTEM#CASE_COUNTER",
        "SK": "META",
        "entity_type": "counter",
        "next_case_number": 10482,
    }
    return users + shipments + cases + field_actions + [cursor]


def seed():
    ensure_local_table()
    table = get_table()
    items = build_demo_items()
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    print(f"Seeded {len(items)} demo records.")


if __name__ == "__main__":
    seed()
