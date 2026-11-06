from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Iterable, Mapping


class Role(StrEnum):
    OPS = "ops"
    SUPPORT = "support"
    COURIER = "courier"
    DEPOT = "depot"


class ExceptionType(StrEnum):
    DELAY = "delay"
    FAILED_DELIVERY = "failed_delivery"
    DAMAGED_PARCEL = "damaged_parcel"
    CUSTOMS_HOLD = "customs_hold"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CaseStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    WAITING_FOR_CUSTOMS = "waiting_for_customs"
    RESOLVED = "resolved"


class RuleViolation(ValueError):
    pass


def validate_exception_type(value: str) -> ExceptionType:
    try:
        return ExceptionType(value)
    except ValueError as error:
        raise RuleViolation(f"Unsupported exception type: {value}.") from error


def validate_single_shipment(shipment_ids: Iterable[str]) -> str:
    linked = list(shipment_ids)
    if len(linked) != 1 or not linked[0].strip():
        raise RuleViolation("Every case must link to exactly one shipment.")
    return linked[0]


def find_open_case(
    cases: Iterable[Mapping[str, object]],
    shipment_id: str,
    exception_type: ExceptionType,
) -> Mapping[str, object] | None:
    return next(
        (
            case for case in cases
            if case.get("shipment_id") == shipment_id
            and case.get("exception_type") == exception_type.value
            and case.get("status") != CaseStatus.RESOLVED.value
        ),
        None,
    )


@dataclass(frozen=True)
class PriorityDecision:
    priority: Priority
    rule_id: str
    set_by: str = "auto"


def assess_priority(
    *,
    key_account: bool = False,
    time_definite: bool = False,
    exception_type: ExceptionType,
    failed_attempt: int = 1,
    meets_promised_date: bool = False,
) -> PriorityDecision:
    """Apply R3 in first-match order."""
    if key_account:
        return PriorityDecision(Priority.HIGH, "P1")
    if time_definite:
        return PriorityDecision(Priority.HIGH, "P2")
    if exception_type is ExceptionType.FAILED_DELIVERY and failed_attempt >= 2:
        return PriorityDecision(Priority.HIGH, "P3")
    if exception_type is ExceptionType.DELAY and meets_promised_date:
        return PriorityDecision(Priority.LOW, "P4")
    return PriorityDecision(Priority.MEDIUM, "default")


def override_priority(priority: Priority, reason: str) -> PriorityDecision:
    if not reason.strip():
        raise RuleViolation("A reason is required to change priority.")
    return PriorityDecision(priority, "manual_override", "user")


def auto_owner(region: str, users: Iterable[Mapping[str, str]]) -> str:
    for user in users:
        if user.get("role") == Role.OPS and user.get("region") == region:
            return user["user_id"]
    raise RuleViolation(f"No Operations owner is configured for region {region}.")


def can_assign_owner(role: Role) -> bool:
    return role is Role.OPS


def can_assign_action(role: Role) -> bool:
    return role is Role.OPS


def can_escalate_to_operations(role: Role) -> bool:
    return role in {Role.SUPPORT, Role.COURIER, Role.DEPOT}


def change_status(
    current: CaseStatus,
    target: CaseStatus,
    *,
    actor: str,
    at: datetime,
) -> dict[str, str]:
    if current is target:
        raise RuleViolation("The case already has that status.")
    return {
        "old_status": current.value,
        "new_status": target.value,
        "actor": actor,
        "at": at.astimezone(timezone.utc).isoformat(),
    }


def deadline_for(created_at: datetime) -> datetime:
    return created_at + timedelta(hours=48)


def resolved_on_time(created_at: datetime, resolved_at: datetime) -> bool:
    return resolved_at <= deadline_for(created_at)


def return_to_sender_date(after: date) -> date:
    """Return the date five weekdays after the failed attempt date."""
    result = after
    weekdays_added = 0
    while weekdays_added < 5:
        result += timedelta(days=1)
        if result.weekday() < 5:
            weekdays_added += 1
    return result


def can_attempt_delivery(attempt_number: int) -> bool:
    return 1 <= attempt_number <= 3


def gps_flagged(distance_m: int | float) -> bool:
    return distance_m > 150


def can_send_message(role: Role) -> bool:
    return role is Role.SUPPORT


def notified_before_customer_contact(
    inbound_contacts: Iterable[Mapping[str, object]],
    sent_at: datetime,
) -> bool:
    return not any(
        contact.get("occurred_at") < sent_at
        for contact in inbound_contacts
        if isinstance(contact.get("occurred_at"), datetime)
    )


def message_duplicate(
    case_messages: Iterable[Mapping[str, object]],
    template_id: str,
    now: datetime,
    *,
    window: timedelta = timedelta(hours=24),
) -> bool:
    """R9 blocks the same template for the same case for 24 hours."""
    return any(
        message.get("template_id") == template_id
        and now - message["sent_at"] < window
        for message in case_messages
    )


def support_queue(case: Mapping[str, object]) -> str | None:
    if case.get("status") == CaseStatus.RESOLVED:
        return None if case.get("resolution_message_sent") else "confirm_resolution"
    if not case.get("messages_sent"):
        return "not_informed"
    if case.get("status") == CaseStatus.WAITING_FOR_CUSTOMER:
        return "waiting_for_customer"
    return None


def sort_support_queue(cases: Iterable[Mapping[str, object]]) -> list[Mapping[str, object]]:
    order = {Priority.HIGH.value: 0, Priority.MEDIUM.value: 1, Priority.LOW.value: 2}
    return sorted(cases, key=lambda case: (
        order.get(str(case.get("priority", Priority.MEDIUM.value)), 1),
        case["created_at"],
    ))


def field_actions_for(
    actions: Iterable[Mapping[str, object]],
    *,
    user_id: str,
    today: date,
) -> list[Mapping[str, object]]:
    return sorted(
        (
            action for action in actions
            if action.get("assignee_id") == user_id
            and action.get("date") == today.isoformat()
        ),
        key=lambda action: (action.get("route_order", 0), action.get("action_id", "")),
    )


def can_view_field_action(role: Role, user_id: str, action: Mapping[str, object]) -> bool:
    return role in (Role.COURIER, Role.DEPOT) and action.get("assignee_id") == user_id
