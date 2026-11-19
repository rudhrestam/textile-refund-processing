"""Tests for the policy engine: every outcome, and the edges."""
from datetime import date, timedelta

import pytest

from refund_system import (
    Condition,
    Outcome,
    Reason,
    RefundRequest,
    load_policies,
    recommend,
)

TODAY = date(2026, 11, 19)
POLICIES = load_policies()  # defaults


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
        "proof_of_purchase": True,
    }
    fields.update(overrides)
    return RefundRequest(**fields)


def test_damaged_within_window_is_full_refund():
    rec = recommend(make_request(), POLICIES, TODAY)
    assert rec.outcome == Outcome.APPROVE
    assert rec.refund_amount == 100.00
    assert rec.credit_amount == 0.0
    assert "full refund" in rec.explanation
    assert rec.next_step  # staff always get a next step


def test_quality_issue_within_window_is_full_refund():
    rec = recommend(
        make_request(reason=Reason.QUALITY_ISSUE,
                     condition=Condition.DEFECTIVE),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.APPROVE
    assert rec.refund_amount == 100.00


def test_damaged_after_defect_window_is_part_refund():
    rec = recommend(
        make_request(purchase_date=TODAY - timedelta(days=70)),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.PARTIAL
    assert rec.refund_amount == 50.00  # 50% of $100


def test_wrong_size_unused_is_exchange():
    rec = recommend(
        make_request(reason=Reason.WRONG_SIZE_COLOR,
                     condition=Condition.UNUSED_WITH_TAGS,
                     purchase_date=TODAY - timedelta(days=10)),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.EXCHANGE
    assert rec.refund_amount == 0.0


def test_wrong_size_used_is_part_refund():
    rec = recommend(
        make_request(reason=Reason.WRONG_SIZE_COLOR,
                     condition=Condition.USED_WASHED),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.PARTIAL
    assert rec.refund_amount == 50.00


def test_wrong_size_out_of_window_is_store_credit():
    rec = recommend(
        make_request(reason=Reason.WRONG_SIZE_COLOR,
                     condition=Condition.UNUSED_WITH_TAGS,
                     purchase_date=TODAY - timedelta(days=40)),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.CREDIT
    assert rec.credit_amount == 100.00


def test_changed_mind_early_unused_is_full_refund():
    rec = recommend(
        make_request(reason=Reason.CHANGED_MIND,
                     condition=Condition.UNUSED_WITH_TAGS,
                     purchase_date=TODAY - timedelta(days=5)),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.APPROVE


def test_changed_mind_inside_window_is_store_credit():
    rec = recommend(
        make_request(reason=Reason.CHANGED_MIND,
                     condition=Condition.UNUSED_WITH_TAGS,
                     purchase_date=TODAY - timedelta(days=20)),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.CREDIT
    assert rec.credit_amount == 100.00


def test_changed_mind_used_is_denied():
    rec = recommend(
        make_request(reason=Reason.CHANGED_MIND,
                     condition=Condition.USED_WASHED,
                     purchase_date=TODAY - timedelta(days=9)),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.DENY
    assert rec.refund_amount == 0.0
    assert "used" in rec.explanation


def test_changed_mind_out_of_window_is_denied():
    rec = recommend(
        make_request(reason=Reason.CHANGED_MIND,
                     condition=Condition.UNUSED_WITH_TAGS,
                     purchase_date=TODAY - timedelta(days=40)),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.DENY
    assert "30-day" in rec.explanation


def test_no_proof_of_purchase_is_store_credit_even_when_damaged():
    rec = recommend(make_request(proof_of_purchase=False),
                    POLICIES, TODAY)
    assert rec.outcome == Outcome.CREDIT
    assert rec.credit_amount == 100.00
    assert "receipt" in rec.explanation or "proof" in rec.explanation


def test_late_delivery_is_full_refund():
    rec = recommend(
        make_request(
            reason=Reason.LATE_DELIVERY,
            condition=Condition.UNUSED_WITH_TAGS,
            promised_delivery_date=TODAY - timedelta(days=12),
            actual_delivery_date=TODAY - timedelta(days=2),
        ),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.APPROVE
    assert "10 days late" in rec.explanation


def test_delivery_on_time_falls_back_to_change_of_mind_rules():
    rec = recommend(
        make_request(
            reason=Reason.LATE_DELIVERY,
            condition=Condition.UNUSED_WITH_TAGS,
            promised_delivery_date=TODAY - timedelta(days=5),
            actual_delivery_date=TODAY - timedelta(days=5),
            purchase_date=TODAY - timedelta(days=5),
        ),
        POLICIES, TODAY)
    assert rec.outcome == Outcome.APPROVE  # unused, 5 days, change of mind


def test_custom_partial_percent_is_respected():
    custom = dict(POLICIES, partial_refund_percent=25)
    rec = recommend(
        make_request(purchase_date=TODAY - timedelta(days=70)),
        custom, TODAY)
    assert rec.outcome == Outcome.PARTIAL
    assert rec.refund_amount == 25.00


def test_every_recommendation_explains_itself():
    cases = [
        make_request(),
        make_request(reason=Reason.CHANGED_MIND,
                     condition=Condition.USED_WASHED),
        make_request(reason=Reason.WRONG_SIZE_COLOR,
                     condition=Condition.UNUSED_WITH_TAGS),
    ]
    for request in cases:
        rec = recommend(request, POLICIES, TODAY)
        assert len(rec.explanation) > 20
        assert len(rec.next_step) > 10


def test_zero_or_negative_amount_is_rejected_at_intake():
    with pytest.raises(ValueError):
        make_request(amount=0)
    with pytest.raises(ValueError):
        make_request(amount=-10)
