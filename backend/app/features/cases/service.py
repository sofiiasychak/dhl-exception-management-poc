from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.core.rules import (
    CaseStatus,
    ExceptionType,
    Priority,
    Role,
    RuleViolation,
    assess_priority,
    auto_owner,
    can_assign_action,
    can_assign_owner,
    can_escalate_to_operations,
    can_send_message,
    change_status,
    find_open_case,
    gps_flagged,
    message_duplicate,
    notified_before_customer_contact,
    return_to_sender_date,
    support_queue,
    validate_exception_type,
    validate_single_shipment,
)
from app.features.cases.repository import CaseRepository
from app.security import AuthenticatedUser


UTC = timezone.utc
OPEN_STATUSES = {
    CaseStatus.NEW.value,
    CaseStatus.IN_PROGRESS.value,
    CaseStatus.WAITING_FOR_CUSTOMER.value,
    CaseStatus.WAITING_FOR_CUSTOMS.value,
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def _time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _number(value: float | int) -> int | Decimal:
    if isinstance(value, float):
        return Decimal(str(value))
    return value


class CaseService:
    def __init__(self, repository: CaseRepository | None = None):
        self.repository = repository or CaseRepository()

    def _detail(self, case_id: str) -> dict | None:
        items = self.repository.get_case(case_id)
        case = next((item for item in items if item.get("SK") == "META"), None)
        if case is None:
            return None
        case["timeline"] = sorted(
            [item for item in items if item.get("entity_type") == "timeline"],
            key=lambda item: item.get("at", ""),
        )
        case["actions"] = [item for item in items if item.get("entity_type") == "action"]
        case["messages"] = [item for item in items if item.get("entity_type") == "message"]
        return case

    def case_detail(self, case_id: str, user: AuthenticatedUser | None = None):
        case = self._detail(case_id)
        if case is None:
            return None
        if user and user.role in {Role.COURIER, Role.DEPOT}:
            case["actions"] = [
                action for action in case["actions"]
                if action.get("assignee_id") == user.user_id
            ]
            if not case["actions"]:
                raise PermissionError("This case has no action assigned to you.")
        return case

    def list_cases(
        self,
        user: AuthenticatedUser,
        *,
        tab: str = "mine",
        exception_type: str | None = None,
        priority: str | None = None,
        region: str | None = None,
        status: str | None = None,
    ):
        if tab not in {"mine", "unassigned", "overdue", "all_open"}:
            raise RuleViolation("Unknown Operations queue.")
        cases = self.repository.list_ops_cases(user.user_id, tab)
        now = now_utc()
        selected = []
        seen = set()
        for item in cases:
            case_id = item.get("case_id")
            if case_id in seen:
                continue
            seen.add(case_id)
            if tab == "unassigned" and item.get("owner_id"):
                continue
            if tab == "overdue" and _time(item["deadline_at"]) >= now:
                continue
            if exception_type and item.get("exception_type") != exception_type:
                continue
            if priority and item.get("priority") != priority:
                continue
            if region and item.get("region") != region:
                continue
            if status and item.get("status") != status:
                continue
            selected.append(item)
        return selected

    def support_queue(self, user: AuthenticatedUser, queue_name: str):
        if user.role is not Role.SUPPORT:
            raise PermissionError("Support role required.")
        if queue_name not in {"not_informed", "waiting_for_customer", "confirm_resolution"}:
            raise RuleViolation("Unknown Support queue.")
        items = self.repository.list_queue("GSI2", f"SUPPORT#{queue_name}")
        return [self._detail(item["case_id"]) for item in items]

    def lookup_shipment(self, shipment_id: str):
        shipment = self.repository.lookup_shipments(shipment_id)
        if shipment is None:
            return None
        return shipment

    def _timeline(self, case_id: str, event: str, actor: str, **details):
        at = now_utc()
        self.repository.put_item({
            "PK": f"CASE#{case_id}",
            "SK": f"TL#{at.isoformat()}#{uuid4().hex}",
            "entity_type": "timeline",
            "event": event,
            "actor": actor,
            "at": at.isoformat(),
            **details,
        })

    def _put_ops_queue(self, case: dict):
        for sort_type in ("Q#OPS#OWNER", "Q#OPS#ALL"):
            self.repository.delete_item(case["PK"], sort_type)
        if case["status"] == CaseStatus.RESOLVED.value:
            return
        rank = {Priority.HIGH.value: "0", Priority.MEDIUM.value: "1", Priority.LOW.value: "2"}[
            case["priority"]
        ]
        deadline = case["deadline_at"]
        created = case["created_at"]
        sort_key = f"{rank}#{deadline}#{created}#{case['case_id']}"
        base = {
            "PK": case["PK"],
            "entity_type": "queue",
            "case_id": case["case_id"],
            "exception_type": case["exception_type"],
            "priority": case["priority"],
            "status": case["status"],
            "owner_id": case.get("owner_id"),
            "region": case["region"],
            "deadline_at": deadline,
            "created_at": created,
            "next_action": case.get("next_action"),
        }
        self.repository.put_item({
            **base,
            "SK": "Q#OPS#ALL",
            "GSI1PK": "OPS#ALL#OPEN",
            "GSI1SK": sort_key,
        })
        if case.get("owner_id"):
            self.repository.put_item({
                **base,
                "SK": "Q#OPS#OWNER",
                "GSI1PK": f"OPS#OWNER#{case['owner_id']}",
                "GSI1SK": sort_key,
            })

    def _put_support_queue(self, case: dict):
        for queue_name in ("not_informed", "waiting_for_customer", "confirm_resolution"):
            self.repository.delete_item(case["PK"], f"Q#SUPPORT#{queue_name}")
        queue_name = support_queue(case)
        if not queue_name:
            return
        rank = {Priority.HIGH.value: "0", Priority.MEDIUM.value: "1", Priority.LOW.value: "2"}[
            case["priority"]
        ]
        self.repository.put_item({
            "PK": case["PK"],
            "SK": f"Q#SUPPORT#{queue_name}",
            "entity_type": "queue",
            "case_id": case["case_id"],
            "exception_type": case["exception_type"],
            "priority": case["priority"],
            "status": case["status"],
            "created_at": case["created_at"],
            "GSI2PK": f"SUPPORT#{queue_name}",
            "GSI2SK": f"{rank}#{case['created_at']}#{case['case_id']}",
        })

    def _save_case(self, case: dict):
        self.repository.put_item(case)
        self._put_ops_queue(case)
        self._put_support_queue(case)

    def _status(self, case: dict, target: CaseStatus, actor: str):
        current = CaseStatus(case["status"])
        entry = change_status(current, target, actor=actor, at=now_utc())
        case["status"] = target.value
        case["updated_at"] = entry["at"]
        self._timeline(
            case["case_id"],
            "case_status_changed",
            actor,
            **{key: value for key, value in entry.items() if key != "actor"},
        )

    def create_case(
        self,
        *,
        shipment: dict,
        exception_type: ExceptionType,
        actor_id: str,
        actor_role: Role,
        owner_id: str | None = None,
        initial_status: str = CaseStatus.NEW.value,
        initial_priority: Priority | None = None,
        priority_rule: str | None = None,
        failed_attempt: int = 1,
        gps_distance_m: int | float | None = None,
        detection_method: str,
        report: dict | None = None,
    ):
        shipment_id = validate_single_shipment([shipment["shipment_id"]])
        existing_items = self.repository.find_open_case(shipment_id, exception_type.value)
        undo_metadata = report.get("undo_metadata", {}) if report else {}
        existing_cases = [
            {"shipment_id": item["shipment_id"], "exception_type": item["exception_type"],
             "status": item["status"], "case_id": item["case_id"]}
            for item in existing_items
        ]
        existing = find_open_case(existing_cases, shipment_id, exception_type)
        if existing:
            case_id = existing["case_id"]
            detail = self._detail(case_id)
            report_id = report.get("report_id", uuid4().hex) if report else uuid4().hex
            self._timeline(
                case_id,
                "failed_delivery_reported"
                if exception_type is ExceptionType.FAILED_DELIVERY
                else "field_report_added",
                actor_id,
                report_id=report_id,
                reason=report.get("reason") if report else None,
                taps_count=report.get("taps_count") if report else None,
                duration_sec=report.get("duration_sec") if report else None,
                photo_attached=bool(report.get("photo_keys")) if report else False,
                gps_distance_m=_number(gps_distance_m) if gps_distance_m is not None else None,
                gps_flagged=gps_flagged(gps_distance_m) if gps_distance_m is not None else False,
                photo_keys=report.get("photo_keys", []) if report else [],
                **undo_metadata,
            )
            detail["attempt_count"] = int(detail.get("attempt_count", 0)) + 1
            detail["gps_flagged"] = detail.get("gps_flagged", False) or (
                gps_flagged(gps_distance_m) if gps_distance_m is not None else False
            )
            self._save_case({k: v for k, v in detail.items() if k not in {"timeline", "actions", "messages"}})
            return {"case_id": case_id, "created": False, "report_id": report_id}

        owners = self.repository.list_users(Role.OPS.value)
        selected_owner = owner_id or auto_owner(shipment["region"], owners)
        priority = initial_priority or assess_priority(
            key_account=bool(shipment.get("key_account")),
            time_definite="time-definite" in str(shipment.get("product", "")).lower(),
            exception_type=exception_type,
            failed_attempt=failed_attempt,
            meets_promised_date=(
                exception_type is ExceptionType.DELAY
                and date.fromisoformat(shipment["promised_delivery_date"]) >= now_utc().date()
            ),
        ).priority
        if not priority_rule:
            priority_rule = assess_priority(
                key_account=bool(shipment.get("key_account")),
                time_definite="time-definite" in str(shipment.get("product", "")).lower(),
                exception_type=exception_type,
                failed_attempt=failed_attempt,
                meets_promised_date=(
                    exception_type is ExceptionType.DELAY
                    and date.fromisoformat(shipment["promised_delivery_date"]) >= now_utc().date()
                ),
            ).rule_id
        created = now_utc()
        case_id = self.repository.next_case_id()
        case = {
            "PK": f"CASE#{case_id}",
            "SK": "META",
            "entity_type": "case",
            "case_id": case_id,
            "shipment_id": shipment_id,
            "shipment": {
                key: value for key, value in shipment.items()
                if key not in {"PK", "SK", "entity_type"}
            },
            "exception_type": exception_type.value,
            "priority": priority.value,
            "priority_rule_id": priority_rule,
            "priority_set_by": "auto",
            "status": initial_status,
            "owner_id": selected_owner,
            "owner_role": Role.OPS.value,
            "assignment_type": "auto",
            "region": shipment["region"],
            "created_at": created.isoformat(),
            "updated_at": created.isoformat(),
            "deadline_at": (created + timedelta(hours=48)).isoformat(),
            "messages_sent": False,
            "customer_informed": False,
            "inbound_contacts": [],
            "resolution_message_sent": False,
            "attempt_count": failed_attempt,
            "return_to_sender_date": return_to_sender_date(created.date()).isoformat()
            if exception_type is ExceptionType.FAILED_DELIVERY else None,
            "gps_flagged": gps_flagged(gps_distance_m) if gps_distance_m is not None else False,
            "GSI3PK": f"SHIPMENT#{shipment_id}",
            "GSI3SK": f"CASE#{exception_type.value}#OPEN#{case_id}",
        }
        self._save_case(case)
        self._timeline(case_id, "exception_case_created", actor_id,
                       detection_method=detection_method, shipment_id=shipment_id)
        self._timeline(case_id, "exception_priority_set", "system",
                       priority=priority.value, rule_id=priority_rule, set_by="auto")
        self._timeline(case_id, "case_owner_assigned", "system",
                       owner_id=selected_owner, assignment_type="auto",
                       seconds_since_created=0)
        self._timeline(case_id, "case_status_changed", "system",
                       old_status="", new_status=initial_status, changed_by_role="system")
        if report:
            report_id = report.get("report_id", uuid4().hex)
            self._timeline(
                case_id,
                "failed_delivery_reported" if exception_type is ExceptionType.FAILED_DELIVERY
                else "field_report_added",
                actor_id,
                report_id=report_id,
                reason=report.get("reason"),
                taps_count=report.get("taps_count"),
                duration_sec=report.get("duration_sec"),
                photo_attached=bool(report.get("photo_keys")),
                gps_distance_m=_number(gps_distance_m) if gps_distance_m is not None else None,
                gps_flagged=case["gps_flagged"],
                note=report.get("note"),
                **undo_metadata,
            )
        if exception_type is ExceptionType.FAILED_DELIVERY:
            self._timeline(case_id, "failed_delivery_attempt_recorded", actor_id,
                           attempt_count=failed_attempt,
                           return_to_sender_date=case["return_to_sender_date"],
                           report_id=report.get("report_id") if report else None)
        return {"case_id": case_id, "created": True, "report_id": report.get("report_id") if report else None}

    def update_priority(self, case_id: str, priority: Priority, reason: str, user: AuthenticatedUser):
        case = self._detail(case_id)
        if not case:
            raise KeyError("Case not found.")
        if user.role is not Role.OPS:
            raise PermissionError("Only Operations can change priority.")
        if not reason.strip():
            raise RuleViolation("A reason is required to change priority.")
        old_priority = case["priority"]
        case["priority"] = priority.value
        case["priority_rule_id"] = "manual_override"
        case["priority_set_by"] = "user"
        self._timeline(case_id, "exception_priority_set", user.user_id,
                       old_priority=old_priority, priority=priority.value,
                       set_by="user", reason=reason.strip())
        self._save_case({k: v for k, v in case.items() if k not in {"timeline", "actions", "messages"}})
        return self._detail(case_id)

    def reassign_owner(self, case_id: str, owner_id: str, user: AuthenticatedUser):
        if not can_assign_owner(user.role):
            raise PermissionError("Only Operations can reassign the case owner.")
        case = self._detail(case_id)
        if not case:
            raise KeyError("Case not found.")
        owner = self.repository.get_user(owner_id)
        if not owner or owner.get("role") != Role.OPS.value:
            raise RuleViolation("The selected owner must be an Operations user.")
        old_owner = case.get("owner_id")
        case["owner_id"] = owner_id
        case["assignment_type"] = "manual"
        self._timeline(case_id, "case_owner_assigned", user.user_id,
                       old_owner_id=old_owner, owner_id=owner_id,
                       assignment_type="manual")
        self._save_case({k: v for k, v in case.items() if k not in {"timeline", "actions", "messages"}})
        return self._detail(case_id)

    def assign_action(
        self,
        case_id: str,
        action_type: str,
        assignee_id: str,
        user: AuthenticatedUser,
        *,
        date_value: str | None = None,
    ):
        if not can_assign_action(user.role):
            raise PermissionError("Only Operations can assign actions.")
        case = self._detail(case_id)
        if not case:
            raise KeyError("Case not found.")
        assignee = self.repository.get_user(assignee_id)
        if not assignee or assignee.get("role") not in {Role.COURIER.value, Role.DEPOT.value}:
            raise RuleViolation("Select an active courier or depot user.")
        shipment = case["shipment"]
        if action_type.lower() == "redelivery" and (
            assignee.get("role") != Role.COURIER.value
            or assignee.get("scope") != shipment.get("route")
        ):
            raise RuleViolation("Redelivery must be assigned to the courier on the shipment's route.")
        day = date_value or now_utc().date().isoformat()
        action_id = uuid4().hex
        route_order = int(case.get("shipment", {}).get("stop", 0))
        action = {
            "PK": case["PK"],
            "SK": f"ACTION#{action_id}",
            "entity_type": "action",
            "action_id": action_id,
            "case_id": case_id,
            "shipment_id": case["shipment_id"],
            "action_type": action_type,
            "assignee_id": assignee_id,
            "assignee_role": assignee["role"],
            "status": "open",
            "slot": case.get("customer_slot"),
            "date": day,
            "route_order": route_order,
            "GSI3PK": f"FIELD#{assignee_id}#{day}",
            "GSI3SK": f"{route_order:04d}#{action_id}",
        }
        self.repository.put_item(action)
        if case["status"] == CaseStatus.NEW.value:
            self._status(case, CaseStatus.IN_PROGRESS, user.user_id)
        case["next_action"] = action_type
        case["next_action_assignee_id"] = assignee_id
        self._timeline(case_id, "case_action_updated", user.user_id,
                       action_id=action_id, action_type=action_type,
                       assignee_id=assignee_id, action_status="open")
        self._save_case({k: v for k, v in case.items() if k not in {"timeline", "actions", "messages"}})
        return action

    def resolve_case(
        self,
        case_id: str,
        outcome: str,
        root_cause: str,
        send_confirmation: bool,
        user: AuthenticatedUser,
    ):
        if user.role is not Role.OPS:
            raise PermissionError("Only Operations can resolve cases.")
        case = self._detail(case_id)
        if not case:
            raise KeyError("Case not found.")
        if case["status"] == CaseStatus.RESOLVED.value:
            raise RuleViolation("The case is already resolved.")
        if send_confirmation:
            sent_messages = [
                {"template_id": item.get("template_id"), "sent_at": _time(item["sent_at"])}
                for item in case["messages"] if item.get("sent_at")
            ]
            if message_duplicate(sent_messages, "resolution-confirmation", now_utc()):
                raise RuleViolation(
                    "The resolution confirmation template was already sent for this case in the last 24 hours."
                )
        resolved_at = now_utc()
        case["outcome"] = outcome
        case["root_cause"] = root_cause
        case["resolved_at"] = resolved_at.isoformat()
        case["resolved_on_time"] = resolved_at <= _time(case["deadline_at"])
        case["resolution_message_sent"] = bool(send_confirmation)
        case.pop("GSI3PK", None)
        case.pop("GSI3SK", None)
        self._status(case, CaseStatus.RESOLVED, user.user_id)
        self._timeline(
            case_id, "case_resolved", user.user_id,
            exception_type=case["exception_type"],
            resolution_minutes=int((resolved_at - _time(case["created_at"])).total_seconds() // 60),
            resolved_on_time=case["resolved_on_time"],
            reopened=bool(case.get("reopen_count")),
        )
        if send_confirmation:
            self._append_message(case, "resolution-confirmation", "SMS and email",
                                 "Delivered, case closed.", user.user_id, resolved_at)
        self._save_case({k: v for k, v in case.items() if k not in {"timeline", "actions", "messages"}})
        return self._detail(case_id)

    def reopen_case(self, case_id: str, reason: str, user: AuthenticatedUser):
        if user.role is not Role.OPS:
            raise PermissionError("Only Operations can reopen cases.")
        case = self._detail(case_id)
        if not case:
            raise KeyError("Case not found.")
        if case["status"] != CaseStatus.RESOLVED.value:
            raise RuleViolation("Only a resolved case can be reopened.")
        if not reason.strip():
            raise RuleViolation("A reason is required to reopen a case.")
        case["reopened"] = True
        case["reopen_count"] = int(case.get("reopen_count", 0)) + 1
        case["resolved_at"] = None
        case["resolved_on_time"] = None
        case["resolution_message_sent"] = True
        case["GSI3PK"] = f"SHIPMENT#{case['shipment_id']}"
        case["GSI3SK"] = f"CASE#{case['exception_type']}#OPEN#{case_id}"
        self._status(case, CaseStatus.IN_PROGRESS, user.user_id)
        self._timeline(case_id, "case_reopened", user.user_id,
                       reason=reason.strip(), reopen_count=case["reopen_count"])
        self._save_case({k: v for k, v in case.items() if k not in {"timeline", "actions", "messages"}})
        return self._detail(case_id)

    def _append_message(self, case: dict, template_id: str, channel: str, body: str,
                        sender_id: str, sent_at: datetime):
        case["messages_sent"] = True
        case["customer_informed"] = True
        self.repository.put_item({
            "PK": case["PK"],
            "SK": f"MSG#{sent_at.isoformat()}#{uuid4().hex}",
            "entity_type": "message",
            "template_id": template_id,
            "channels": channel.split(" and "),
            "channel": channel,
            "body": body,
            "sender_id": sender_id,
            "sent_at": sent_at.isoformat(),
            "notified_before_customer_contact": notified_before_customer_contact(
                case.get("inbound_contacts", []), sent_at
            ),
        })
        self._timeline(case["case_id"], "customer_notified", sender_id,
                       template_id=template_id, channel=channel,
                       notified_before_customer_contact=notified_before_customer_contact(
                           case.get("inbound_contacts", []), sent_at
                       ),
                       seconds_since_created=int(
                           (sent_at - _time(case["created_at"])).total_seconds()
                       ))

    def send_message(
        self,
        case_id: str,
        template_id: str,
        channel: str,
        body: str,
        user: AuthenticatedUser,
    ):
        if not can_send_message(user.role):
            raise PermissionError("Only Support can send customer messages.")
        case = self._detail(case_id)
        if not case:
            raise KeyError("Case not found.")
        sent_at = now_utc()
        messages = [
            {"template_id": item.get("template_id"), "sent_at": _time(item["sent_at"])}
            for item in case["messages"] if item.get("sent_at")
        ]
        if message_duplicate(messages, template_id, sent_at):
            raise RuleViolation("This update was already sent for this case in the last 24 hours.")
        self._append_message(case, template_id, channel, body, user.user_id, sent_at)
        if case["status"] not in {CaseStatus.RESOLVED.value, CaseStatus.WAITING_FOR_CUSTOMS.value}:
            self._status(case, CaseStatus.WAITING_FOR_CUSTOMER, user.user_id)
        self._save_case({k: v for k, v in case.items() if k not in {"timeline", "actions", "messages"}})
        return self._detail(case_id)

    def escalate(self, case_id: str, message: str, user: AuthenticatedUser):
        if not can_escalate_to_operations(user.role):
            raise PermissionError("This role cannot escalate to Operations.")
        case = self._detail(case_id)
        if not case:
            raise KeyError("Case not found.")
        self._timeline(case_id, "escalated_to_operations", user.user_id,
                       message=message.strip())
        return self._detail(case_id)

    def record_choice(self, case_id: str, option_type: str, slot: str | None, actor: str = "system"):
        case = self._detail(case_id)
        if not case:
            raise KeyError("Case not found.")
        case["customer_slot"] = slot if option_type == "redelivery" else None
        case["resolution_option"] = option_type
        for action in case["actions"]:
            if (
                action.get("action_type", "").lower() == "redelivery"
                and action.get("status") in {"open", "pending_assignment"}
            ):
                action["slot"] = slot
                self.repository.put_item(action)
        self._timeline(case_id, "resolution_option_recorded", actor,
                       option_type=option_type, slot=slot)
        self._timeline(case_id, "case_action_updated", actor,
                       action_type="redelivery", action_status="open")
        if case["status"] == CaseStatus.WAITING_FOR_CUSTOMER.value:
            self._status(case, CaseStatus.IN_PROGRESS, actor)
        self._save_case({k: v for k, v in case.items() if k not in {"timeline", "actions", "messages"}})
        return self._detail(case_id)

    def record_delivery_report(
        self,
        *,
        shipment_id: str,
        reason: str,
        note: str | None,
        photo_keys: list[str],
        taps_count: int,
        duration_sec: int,
        user: AuthenticatedUser,
    ):
        if user.role is not Role.COURIER:
            raise PermissionError("Courier role required.")
        if taps_count != 3 or duration_sec < 0 or duration_sec >= 15:
            raise RuleViolation("Failed delivery reports must take exactly 3 taps and under 15 seconds.")
        shipment = self.repository.get_shipment(shipment_id)
        if not shipment:
            raise KeyError("Shipment not found.")
        existing_cases = self.repository.find_open_case(
            shipment_id, ExceptionType.FAILED_DELIVERY.value
        )
        prior_case = existing_cases[0] if existing_cases else None
        prior_attempt_count = 0
        prior_gps_flagged = False
        had_next_action = False
        prior_next_action = None
        if prior_case is not None:
            prior_attempt_count = int(prior_case.get("attempt_count", 1))
            prior_gps_flagged = bool(prior_case.get("gps_flagged", False))
            had_next_action = "next_action" in prior_case
            prior_next_action = prior_case.get("next_action")
        report_id = uuid4().hex
        previous = self.repository.find_route_action(
            shipment_id, user.user_id, now_utc().date().isoformat()
        )
        previous_action = None
        attempt = 1
        if previous:
            previous_action = {
                "action_id": previous["action_id"],
                "status": previous.get("status", "open"),
                "completed_at": previous.get("completed_at"),
            }
            previous["status"] = "done"
            previous["completed_at"] = now_utc().isoformat()
            self.repository.put_item(previous)
            previous_case = self._detail(previous.get("case_id", ""))
            if previous_case is not None:
                case = previous_case
                attempt = int(case.get("attempt_count", 1)) + 1
                self._timeline(case["case_id"], "case_action_updated", user.user_id,
                               action_type=previous["action_type"], action_status="failed",
                               report_id=report_id)
                if attempt > 3:
                    case["next_action"] = "Return to sender"
                    self._timeline(case["case_id"], "return_to_sender_required", "system",
                                   attempt_count=attempt)
                    self._save_case({k: v for k, v in case.items()
                                     if k not in {"timeline", "actions", "messages"}})
                    return {"case_id": case["case_id"], "created": False,
                            "next_action": "Return to sender"}
        report = {
            "report_id": report_id,
            "reason": reason,
            "note": note,
            "photo_keys": photo_keys,
            "taps_count": taps_count,
            "duration_sec": duration_sec,
            "undo_metadata": {
                "created_case_before_report": prior_case is None,
                "prior_attempt_count": prior_attempt_count,
                "prior_gps_flagged": prior_gps_flagged,
                "had_next_action": had_next_action,
                "prior_next_action": prior_next_action,
                "previous_action": previous_action,
            },
        }
        result = self.create_case(
            shipment=shipment,
            exception_type=ExceptionType.FAILED_DELIVERY,
            actor_id=user.user_id,
            actor_role=user.role,
            failed_attempt=attempt,
            gps_distance_m=18,
            detection_method="courier_report",
            report=report,
        )
        case = self._detail(result["case_id"])
        if case is None:
            raise KeyError("Case not found.")
        if not result["created"]:
            attempt = int(case.get("attempt_count", attempt))
        if attempt >= 3:
            case["next_action"] = "Return to sender"
            self._timeline(case["case_id"], "return_to_sender_required", "system",
                           attempt_count=attempt, report_id=report_id)
            self._save_case({k: v for k, v in case.items()
                             if k not in {"timeline", "actions", "messages"}})
            result["next_action"] = "Return to sender"
        elif attempt <= 3:
            case["attempt_count"] = attempt
            case["next_action"] = "Redelivery"
            self._save_case({k: v for k, v in case.items()
                             if k not in {"timeline", "actions", "messages"}})
        return result

    def undo_report(self, case_id: str, report_id: str, user: AuthenticatedUser):
        if user.role is not Role.COURIER:
            raise PermissionError("Courier role required.")
        case = self._detail(case_id)
        if not case:
            raise KeyError("Case not found.")
        report = next(
            (item for item in case["timeline"]
             if item.get("report_id") == report_id
             and item.get("event") in {"failed_delivery_reported", "field_report_added"}),
            None,
        )
        if report is None:
            raise RuleViolation("This report can no longer be undone.")
        if report.get("actor") != user.user_id:
            raise PermissionError("This report is not assigned to you.")
        if now_utc() - _time(report["at"]) > timedelta(seconds=10):
            raise RuleViolation("The 10-second undo period has ended.")
        later_activity = [
            item for item in case["timeline"]
            if item["at"] > report["at"]
            and item.get("report_id") != report_id
        ]
        if later_activity:
            raise RuleViolation("This case has activity that prevents undoing the report.")
        if report.get("event") == "failed_delivery_reported" and report.get(
            "created_case_before_report", case["attempt_count"] == 1
        ):
            self.repository.remove_case(case_id)
        else:
            for item in case["timeline"]:
                if item.get("report_id") == report_id:
                    self.repository.delete_item(item["PK"], item["SK"])
            prior_attempt = report.get("prior_attempt_count")
            if prior_attempt is not None:
                case["attempt_count"] = int(prior_attempt)
                case["gps_flagged"] = bool(report.get("prior_gps_flagged", False))
                if report.get("had_next_action"):
                    case["next_action"] = report.get("prior_next_action")
                else:
                    case.pop("next_action", None)
                self._save_case({k: v for k, v in case.items()
                                 if k not in {"timeline", "actions", "messages"}})
        previous_action = report.get("previous_action")
        if previous_action is not None:
            action = next(
                (item for item in self.repository.query_field_actions(
                    user.user_id, now_utc().date().isoformat()
                ) if item.get("action_id") == previous_action["action_id"]),
                None,
            )
            if action:
                action["status"] = previous_action["status"]
                if previous_action.get("completed_at") is None:
                    action.pop("completed_at", None)
                else:
                    action["completed_at"] = previous_action["completed_at"]
                self.repository.put_item(action)
        return {"undone": True, "case_id": case_id}

    def list_field_actions(self, user: AuthenticatedUser, day: date):
        items = self.repository.query_field_actions(user.user_id, day.isoformat())
        result = []
        for item in items:
            if item.get("status") in {"done", "cancelled"}:
                continue
            case = self._detail(item.get("case_id", ""))
            if case:
                result.append({**item, "case": case})
            else:
                shipment = self.repository.get_shipment(item.get("shipment_id", ""))
                if shipment:
                    result.append({**item, "shipment": shipment})
        return sorted(result, key=lambda item: (item.get("route_order", 0), item.get("action_id", "")))

    def complete_field_action(self, action_id: str, user: AuthenticatedUser):
        if user.role not in {Role.COURIER, Role.DEPOT}:
            raise PermissionError("Field role required.")
        actions = self.repository.query_field_actions(user.user_id, now_utc().date().isoformat())
        action = next((item for item in actions if item.get("action_id") == action_id), None)
        if not action or action.get("assignee_id") != user.user_id:
            raise KeyError("Assigned action not found.")
        action["status"] = "done"
        action["completed_at"] = now_utc().isoformat()
        self.repository.put_item(action)
        case = self._detail(action["case_id"]) if action.get("case_id") else None
        if case:
            self._timeline(action["case_id"], "case_action_updated", user.user_id,
                           action_type=action["action_type"], action_status="done")
        return {"action_id": action_id, "status": "done"}

    def report_damage(
        self,
        *,
        shipment_id: str,
        damage_types: list[str],
        contents_checked: bool,
        note: str | None,
        photo_keys: list[str],
        user: AuthenticatedUser,
    ):
        if user.role is not Role.DEPOT:
            raise PermissionError("Depot role required.")
        if not damage_types:
            raise RuleViolation("Select at least one damage type.")
        if not photo_keys:
            raise RuleViolation("At least one photo is required.")
        shipment = self.repository.get_shipment(shipment_id)
        if not shipment:
            raise KeyError("Shipment not found.")
        report = {
            "report_id": uuid4().hex,
            "reason": ", ".join(damage_types),
            "note": note,
            "photo_keys": photo_keys,
        }
        result = self.create_case(
            shipment=shipment,
            exception_type=ExceptionType.DAMAGED_PARCEL,
            actor_id=user.user_id,
            actor_role=user.role,
            detection_method="depot_report",
            report=report,
        )
        self._timeline(
            result["case_id"], "damage_report_details", user.user_id,
            damage_types=damage_types, contents_checked=contents_checked,
            note=note, photo_keys=photo_keys,
        )
        return result
