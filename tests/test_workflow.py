"""Tests for the workflow: legal moves, refused moves, audit trail."""
from datetime import date, timedelta

import pytest

from refund_system import (
    Condition,
    Outcome,
    Reason,
    RefundRequest,
    Status,
    Workflow,
    load_policies,
    recommend,
)

TODAY = date(2026, 11, 19)
POLICIES = load_policies()


def make_request(**overrides):
    fields = {
        "id": "R-TEST",
        "order_id": "TX-1000",
        "customer_name": "Test Customer",
        "product": "cotton fabric",
        "reason": Reason.DAMAGED,
        "condition": Condition.DAMAGED_ON_ARRIVAL,
        "purchase_date": TODAY - timedelta(days=5),
        "amount": 100.00,
    }
    fields.update(overrides)
    return RefundRequest(**fields)


def run_to_decision(workflow, request, actor="Asha"):
    workflow.start_review(request, actor)
    rec = recommend(request, POLICIES, TODAY)
    workflow.apply_decision(request, rec, actor)
    return rec


def test_full_refund_path_reaches_closed():
    workflow = Workflow()
    request = make_request()
    run_to_decision(workflow, request)
    assert request.status == Status.APPROVED
    workflow.issue_refund(request, "Asha")
    assert request.status == Status.REFUND_ISSUED
    workflow.request_feedback(request, "Asha")
    workflow.close(request, "Asha")
    assert request.status == Status.CLOSED
    assert request.resolved_at is not None
    assert len(workflow.audit) == 5


def test_exchange_path_reaches_closed():
    workflow = Workflow()
    request = make_request(reason=Reason.WRONG_SIZE_COLOR,
                           condition=Condition.UNUSED_WITH_TAGS,
                           purchase_date=TODAY - timedelta(days=10))
    run_to_decision(workflow, request)
    assert request.status == Status.EXCHANGE_OFFERED
    workflow.complete_exchange(request, "Asha")
    workflow.request_feedback(request, "Asha")
    workflow.close(request, "Asha")
    assert request.status == Status.CLOSED


def test_denied_path_still_asks_for_feedback():
    workflow = Workflow()
    request = make_request(reason=Reason.CHANGED_MIND,
                           condition=Condition.USED_WASHED)
    run_to_decision(workflow, request)
    assert request.status == Status.DENIED
    workflow.request_feedback(request, "Asha")
    workflow.close(request, "Asha")
    assert request.status == Status.CLOSED


def test_illegal_moves_are_refused():
    workflow = Workflow()
    request = make_request()
    with pytest.raises(ValueError):
        workflow.issue_refund(request, "Asha")  # still RECEIVED
    with pytest.raises(ValueError):
        workflow.move(request, Status.APPROVED, "Asha", "skip review")


def test_cannot_skip_states():
    workflow = Workflow()
    request = make_request()
    workflow.start_review(request, "Asha")
    with pytest.raises(ValueError):
        workflow.issue_refund(request, "Asha")  # no decision yet


def test_closed_requests_cannot_move():
    workflow = Workflow()
    request = make_request()
    run_to_decision(workflow, request)
    workflow.issue_refund(request, "Asha")
    workflow.request_feedback(request, "Asha")
    workflow.close(request, "Asha")
    with pytest.raises(ValueError):
        workflow.start_review(request, "Asha")


def test_override_without_note_is_refused():
    workflow = Workflow()
    request = make_request()
    workflow.start_review(request, "Asha")
    rec = recommend(request, POLICIES, TODAY)
    assert rec.outcome == Outcome.APPROVE
    with pytest.raises(ValueError):
        workflow.apply_decision(request, rec, "Asha",
                                outcome=Outcome.DENY)


def test_override_with_note_is_recorded():
    workflow = Workflow()
    request = make_request()
    workflow.start_review(request, "Asha")
    rec = recommend(request, POLICIES, TODAY)
    workflow.apply_decision(request, rec, "Asha",
                            outcome=Outcome.DENY,
                            note="Customer agreed to an exchange instead.")
    assert request.status == Status.DENIED
    entry = workflow.audit[-1]
    assert "override" in entry.action
    assert "exchange instead" in entry.note


def test_history_returns_only_that_request():
    workflow = Workflow()
    first = make_request(id="R-001")
    second = make_request(id="R-002")
    workflow.start_review(first, "Asha")
    workflow.start_review(second, "Ravi")
    assert len(workflow.history("R-001")) == 1
    assert workflow.history("R-001")[0].actor == "Asha"
    assert len(workflow.history("R-002")) == 1
