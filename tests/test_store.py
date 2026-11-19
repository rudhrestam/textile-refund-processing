"""Tests for the SQLite store: save and load round trips."""
from datetime import date, datetime, timedelta

from refund_system import (
    Condition,
    Feedback,
    Reason,
    RefundRequest,
    RefundStore,
    Status,
    Workflow,
)

TODAY = date(2026, 11, 19)


def make_request(request_id="R-001"):
    return RefundRequest(
        id=request_id,
        order_id="TX-1000",
        customer_name="Meera Shah",
        product="cotton saree fabric",
        reason=Reason.DAMAGED,
        condition=Condition.DAMAGED_ON_ARRIVAL,
        purchase_date=TODAY - timedelta(days=5),
        amount=85.00,
        assigned_to="Asha",
    )


def test_request_round_trip_in_memory():
    store = RefundStore(":memory:")
    request = make_request()
    store.save_request(request)
    loaded = store.get_request("R-001")
    assert loaded is not None
    assert loaded.customer_name == "Meera Shah"
    assert loaded.amount == 85.00
    assert loaded.reason == Reason.DAMAGED
    assert loaded.status == Status.RECEIVED
    assert loaded.assigned_to == "Asha"
    store.close()


def test_list_requests_can_filter_by_status():
    store = RefundStore(":memory:")
    first = make_request("R-001")
    second = make_request("R-002")
    second.status = Status.CLOSED
    store.save_request(first)
    store.save_request(second)
    assert len(store.list_requests()) == 2
    assert len(store.list_requests(Status.CLOSED)) == 1
    assert store.list_requests(Status.CLOSED)[0].id == "R-002"
    store.close()


def test_audit_entries_round_trip():
    store = RefundStore(":memory:")
    workflow = Workflow()
    request = make_request()
    workflow.start_review(request, "Asha")
    for entry in workflow.audit:
        store.save_audit(entry)
    entries = store.list_audit("R-001")
    assert len(entries) == 1
    assert entries[0].action == "review started"
    assert entries[0].from_status == Status.RECEIVED
    assert entries[0].to_status == Status.UNDER_REVIEW
    store.close()


def test_feedback_round_trip():
    store = RefundStore(":memory:")
    store.save_feedback(Feedback(request_id="R-001", rating=5,
                                 comment="Very kind staff."))
    saved = store.list_feedback()
    assert len(saved) == 1
    assert saved[0].rating == 5
    assert saved[0].would_recommend is True
    store.close()


def test_file_store_keeps_data_between_opens(tmp_path):
    path = str(tmp_path / "refunds.db")
    first = RefundStore(path)
    first.save_request(make_request())
    first.close()
    second = RefundStore(path)
    loaded = second.get_request("R-001")
    assert loaded is not None
    assert loaded.order_id == "TX-1000"
    second.close()


def test_missing_request_returns_none():
    store = RefundStore(":memory:")
    assert store.get_request("R-404") is None
    store.close()
