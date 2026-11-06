from datetime import date, datetime, timedelta, timezone

import pytest

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
    can_attempt_delivery,
    can_send_message,
    can_view_field_action,
    deadline_for,
    field_actions_for,
    find_open_case,
    gps_flagged,
    message_duplicate,
    override_priority,
    resolved_on_time,
    return_to_sender_date,
    sort_support_queue,
    support_queue,
    validate_exception_type,
    change_status,
)


def test_r1_one_open_case_matches_shipment_and_type():
    cases = [
        {"shipment_id": "1", "exception_type": "delay", "status": "in_progress"},
        {"shipment_id": "1", "exception_type": "delay", "status": "resolved"},
    ]
    assert find_open_case(cases, "1", ExceptionType.DELAY) is cases[0]
    assert find_open_case([], "1", ExceptionType.DELAY) is None


def test_r2_accepts_only_four_exception_types():
    assert validate_exception_type("customs_hold") is ExceptionType.CUSTOMS_HOLD
    with pytest.raises(RuleViolation):
        validate_exception_type("other")


@pytest.mark.parametrize(
    ("inputs", "priority", "rule_id"),
    [
        ({"key_account": True, "time_definite": True}, Priority.HIGH, "P1"),
        ({"time_definite": True}, Priority.HIGH, "P2"),
        ({"exception_type": ExceptionType.FAILED_DELIVERY, "failed_attempt": 2},
         Priority.HIGH, "P3"),
        ({"exception_type": ExceptionType.DELAY, "meets_promised_date": True},
         Priority.LOW, "P4"),
        ({"exception_type": ExceptionType.DELAY}, Priority.MEDIUM, "default"),
    ],
)
def test_r3_first_matching_priority_rule(inputs, priority, rule_id):
    arguments = {"exception_type": ExceptionType.DELAY}
    arguments.update(inputs)
    result = assess_priority(**arguments)
    assert (result.priority, result.rule_id, result.set_by) == (priority, rule_id, "auto")


def test_r3_override_requires_reason_and_is_attributed_to_user():
    with pytest.raises(RuleViolation):
        override_priority(Priority.HIGH, " ")
    assert override_priority(Priority.HIGH, "Verified shipment").set_by == "user"


def test_r4_assignments_are_ops_only_and_owner_is_region_specific():
    users = [
        {"user_id": "marta", "role": "ops", "region": "Kyiv-East"},
        {"user_id": "thomas", "role": "courier", "region": "Kyiv-East"},
    ]
    assert auto_owner("Kyiv-East", users) == "marta"
    assert can_assign_owner(Role.OPS) and can_assign_action(Role.OPS)
    assert not can_assign_owner(Role.SUPPORT) and not can_assign_action(Role.DEPOT)


def test_r5_status_change_records_old_new_actor_and_time():
    now = datetime.now(timezone.utc)
    assert change_status(CaseStatus.NEW, CaseStatus.IN_PROGRESS, actor="ops-user", at=now) == {
        "old_status": "new",
        "new_status": "in_progress",
        "actor": "ops-user",
        "at": now.isoformat(),
    }


def test_r6_deadline_is_48_hours_and_resolution_boundary_is_inclusive():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert deadline_for(created) == created + timedelta(hours=48)
    assert resolved_on_time(created, deadline_for(created))
    assert not resolved_on_time(created, deadline_for(created) + timedelta(seconds=1))


def test_r7_attempt_limit_and_five_weekdays():
    assert can_attempt_delivery(1) and can_attempt_delivery(3)
    assert not can_attempt_delivery(4)
    assert return_to_sender_date(date(2026, 11, 6)) == date(2026, 11, 13)


def test_r8_gps_flag_is_strictly_more_than_150_metres():
    assert not gps_flagged(150)
    assert gps_flagged(150.1)


def test_r9_only_support_sends_and_duplicate_template_is_blocked_for_24_hours():
    now = datetime.now(timezone.utc)
    sent = [{"template_id": "failed-delivery", "sent_at": now - timedelta(hours=23)}]
    assert can_send_message(Role.SUPPORT)
    assert not can_send_message(Role.OPS)
    assert message_duplicate(sent, "failed-delivery", now)
    assert not message_duplicate(sent, "failed-delivery", now + timedelta(hours=2))


def test_r10_support_queue_state_and_priority_sort():
    assert support_queue({"status": "new", "messages_sent": False}) == "not_informed"
    assert support_queue({
        "status": "waiting_for_customer", "messages_sent": True
    }) == "waiting_for_customer"
    assert support_queue({
        "status": "resolved", "resolution_message_sent": False
    }) == "confirm_resolution"
    cases = [
        {"priority": "medium", "created_at": "2026-01-01"},
        {"priority": "high", "created_at": "2026-01-02"},
    ]
    assert sort_support_queue(cases) == [cases[1], cases[0]]


def test_r11_field_users_only_see_their_own_actions_for_today_in_route_order():
    today = date.today()
    actions = [
        {"assignee_id": "courier-a", "date": today.isoformat(), "route_order": 2},
        {"assignee_id": "courier-a", "date": today.isoformat(), "route_order": 1},
        {"assignee_id": "courier-b", "date": today.isoformat(), "route_order": 0},
    ]
    visible = field_actions_for(actions, user_id="courier-a", today=today)
    assert [action["route_order"] for action in visible] == [1, 2]
    assert can_view_field_action(Role.COURIER, "courier-a", visible[0])
    assert not can_view_field_action(Role.COURIER, "courier-b", visible[0])
    assert not can_view_field_action(Role.OPS, "courier-a", visible[0])
