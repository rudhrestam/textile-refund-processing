"""Tests for customer messages: the right words for each outcome."""
from datetime import date, timedelta

from refund_system import (
    Condition,
    Outcome,
    Reason,
    RefundRequest,
    feedback_message,
    load_policies,
    recommend,
    render,
)

TODAY = date(2026, 11, 19)
POLICIES = load_policies()


def make_request(**overrides):
    fields = {
        "id": "R-TEST",
        "order_id": "TX-1000",
        "customer_name": "Meera Shah",
        "product": "cotton saree fabric",
        "reason": Reason.DAMAGED,
        "condition": Condition.DAMAGED_ON_ARRIVAL,
        "purchase_date": TODAY - timedelta(days=5),
        "amount": 85.00,
    }
    fields.update(overrides)
    return RefundRequest(**fields)


def test_approved_message_has_name_order_and_amount():
    request = make_request()
    rec = recommend(request, POLICIES, TODAY)
    text = render(Outcome.APPROVE, request, rec)
    assert "Meera Shah" in text
    assert "TX-1000" in text
    assert "$85.00" in text
    assert "full refund" in text


def test_partial_message_states_the_part_amount():
    request = make_request(purchase_date=TODAY - timedelta(days=70))
    rec = recommend(request, POLICIES, TODAY)
    assert rec.outcome == Outcome.PARTIAL
    text = render(Outcome.PARTIAL, request, rec)
    assert "$42.50" in text  # half of $85
    assert "half" in text


def test_exchange_message_offers_a_swap():
    request = make_request(reason=Reason.WRONG_SIZE_COLOR,
                           condition=Condition.UNUSED_WITH_TAGS,
                           purchase_date=TODAY - timedelta(days=10))
    rec = recommend(request, POLICIES, TODAY)
    text = render(Outcome.EXCHANGE, request, rec)
    assert "swap" in text
    assert "full refund" in text  # the fallback is mentioned too


def test_credit_message_has_the_code_and_amount():
    request = make_request(reason=Reason.CHANGED_MIND,
                           condition=Condition.UNUSED_WITH_TAGS,
                           purchase_date=TODAY - timedelta(days=20))
    rec = recommend(request, POLICIES, TODAY)
    text = render(Outcome.CREDIT, request, rec,
                  credit_code="CREDIT-TX-1000")
    assert "$85.00" in text
    assert "CREDIT-TX-1000" in text
    assert "never expires" in text


def test_denied_message_explains_the_reason_kindly():
    request = make_request(reason=Reason.CHANGED_MIND,
                           condition=Condition.USED_WASHED,
                           purchase_date=TODAY - timedelta(days=9))
    rec = recommend(request, POLICIES, TODAY)
    text = render(Outcome.DENY, request, rec)
    assert "sorry" in text.lower()
    assert "used" in text.lower()
    assert "exchange" in text.lower()  # a kind alternative is offered


def test_feedback_message_asks_for_a_rating():
    request = make_request()
    text = feedback_message(request)
    assert "Meera Shah" in text
    assert "TX-1000" in text
    assert "1 to 5" in text
