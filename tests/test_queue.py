"""Tests for the queue: ordering, SLA status, workload, dashboard."""
from datetime import date, datetime, timedelta

from refund_system import (
    Condition,
    Reason,
    RefundRequest,
    Status,
    assign_next,
    dashboard,
    load_policies,
    prioritize,
    sla_status,
)

NOW = datetime(2026, 11, 19, 10, 0, 0)
TODAY = date(2026, 11, 19)
POLICIES = load_policies()  # 48-hour review SLA, max 5 open per person


def make_request(request_id, amount=50.0, hours_ago=1, status=None):
    return RefundRequest(
        id=request_id,
        order_id=f"TX-{request_id}",
        customer_name="Test Customer",
        product="cotton fabric",
        reason=Reason.DAMAGED,
        condition=Condition.DAMAGED_ON_ARRIVAL,
        purchase_date=TODAY - timedelta(days=5),
        amount=amount,
        created_at=NOW - timedelta(hours=hours_ago),
        status=status or Status.RECEIVED,
    )


def test_overdue_requests_come_first():
    overdue = make_request("R-OLD", amount=20.0, hours_ago=60)
    fresh_big = make_request("R-BIG", amount=500.0, hours_ago=1)
    fresh_small = make_request("R-SMALL", amount=10.0, hours_ago=2)
    ordered = prioritize([fresh_big, fresh_small, overdue], NOW, POLICIES)
    assert ordered[0].id == "R-OLD"       # overdue beats everything
    assert ordered[1].id == "R-BIG"       # then the biggest amount
    assert ordered[2].id == "R-SMALL"


def test_closed_requests_are_left_out_of_the_queue():
    done = make_request("R-DONE", hours_ago=60, status=Status.CLOSED)
    open_one = make_request("R-OPEN", hours_ago=1)
    assert prioritize([done, open_one], NOW, POLICIES) == [open_one]


def test_sla_status_reports_overdue_due_soon_and_on_track():
    overdue = make_request("R-1", hours_ago=50)
    status, hours = sla_status(overdue, NOW, POLICIES)
    assert status == "overdue"
    assert hours < 0

    due_soon = make_request("R-2", hours_ago=44)  # 4 hours left
    status, hours = sla_status(due_soon, NOW, POLICIES)
    assert status == "due_soon"
    assert hours == 4.0

    on_track = make_request("R-3", hours_ago=1)
    status, hours = sla_status(on_track, NOW, POLICIES)
    assert status == "on_track"
    assert hours == 47.0


def test_new_work_goes_to_the_least_busy_person():
    staff = ["Asha", "Ravi", "Priya"]
    counts = {"Asha": 3, "Ravi": 1, "Priya": 2}
    assert assign_next(staff, counts, 5) == "Ravi"


def test_nobody_is_assigned_past_the_maximum():
    staff = ["Asha", "Ravi"]
    counts = {"Asha": 5, "Ravi": 5}
    assert assign_next(staff, counts, 5) is None
    counts["Ravi"] = 4
    assert assign_next(staff, counts, 5) == "Ravi"


def test_dashboard_counts_open_overdue_and_resolved_today():
    overdue = make_request("R-1", hours_ago=60)
    open_one = make_request("R-2", hours_ago=1)
    open_one.assigned_to = "Asha"
    resolved = make_request("R-3", hours_ago=1, status=Status.CLOSED)
    resolved.resolved_at = NOW - timedelta(hours=1)
    summary = dashboard(
        [overdue, open_one, resolved],
        {"count": 2, "average_rating": 4.5},
        NOW, POLICIES,
    )
    assert summary["open_requests"] == 2
    assert summary["overdue_requests"] == 1
    assert summary["resolved_today"] == 1
    assert summary["average_rating"] == 4.5
    assert summary["feedback_count"] == 2
    assert summary["open_per_staff"] == {"Asha": 1}
