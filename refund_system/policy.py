"""The policy engine.

One job: given a refund request and the shop's policy settings, say
what to do — and explain it in plain words, so staff never have to
guess under pressure. The rules live in policies.json; change the
file, not the code, to tune them.

Decision order (first matching rule wins):

1. No proof of purchase -> store credit for the full amount.
2. Damaged on arrival or a quality problem -> full refund inside the
   defect window, part refund after it.
3. Late delivery -> full refund when the delivery really was late.
4. Wrong size or colour -> exchange when the item is unused, part
   refund when it has been used, store credit when it is out of
   window.
5. Changed mind (or a late delivery that was not actually late) ->
   full refund when unused and early, store credit when unused and
   inside the window, no refund when the item was used or the window
   has passed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import Condition, Outcome, Reason, RefundRequest

DEFAULT_POLICIES = {
    "return_window_days": 30,
    "changed_mind_full_refund_days": 14,
    "defect_window_days": 60,
    "partial_refund_percent": 50,
    "review_sla_hours": 48,
    "max_open_per_staff": 5,
    "late_delivery_grace_days": 7,
}


def load_policies(path: str | Path | None = None) -> dict:
    """Load policy settings from a JSON file, falling back to defaults.

    Missing keys in the file keep their default values, so a short
    file only overrides what it mentions.
    """
    policies = dict(DEFAULT_POLICIES)
    if path is None:
        return policies
    with open(path, encoding="utf-8") as handle:
        policies.update(json.load(handle))
    return policies


@dataclass
class Recommendation:
    """What the policy engine suggests, with the reasoning attached."""

    outcome: Outcome
    refund_amount: float   # money back to the customer (0 for exchange/credit/deny)
    credit_amount: float   # store credit value (0 unless outcome is CREDIT)
    explanation: str       # plain-language reason, shown to staff and customer
    next_step: str         # the one thing staff should do next


def _money(amount: float) -> str:
    return f"${amount:,.2f}"


def recommend(
    request: RefundRequest,
    policies: dict | None = None,
    today: date | None = None,
) -> Recommendation:
    """Decide what to do with one refund request."""
    policies = dict(DEFAULT_POLICIES) if policies is None else policies
    today = today or date.today()
    days_since_purchase = (today - request.purchase_date).days
    partial = round(
        request.amount * policies["partial_refund_percent"] / 100, 2
    )

    def approve(text: str) -> Recommendation:
        return Recommendation(
            outcome=Outcome.APPROVE,
            refund_amount=request.amount,
            credit_amount=0.0,
            explanation=text,
            next_step="Issue the full refund — one click, no extra approval needed.",
        )

    def partial_refund(text: str) -> Recommendation:
        return Recommendation(
            outcome=Outcome.PARTIAL,
            refund_amount=partial,
            credit_amount=0.0,
            explanation=text,
            next_step=(
                f"Confirm the {_money(partial)} part refund with the customer, "
                "then issue it."
            ),
        )

    def exchange(text: str) -> Recommendation:
        return Recommendation(
            outcome=Outcome.EXCHANGE,
            refund_amount=0.0,
            credit_amount=0.0,
            explanation=text,
            next_step=(
                "Confirm the replacement size or colour with the customer, "
                "then mark the exchange complete."
            ),
        )

    def credit(text: str) -> Recommendation:
        return Recommendation(
            outcome=Outcome.CREDIT,
            refund_amount=0.0,
            credit_amount=request.amount,
            explanation=text,
            next_step=(
                f"Issue {_money(request.amount)} in store credit and share "
                "the code with the customer."
            ),
        )

    def deny(text: str) -> Recommendation:
        return Recommendation(
            outcome=Outcome.DENY,
            refund_amount=0.0,
            credit_amount=0.0,
            explanation=text,
            next_step=(
                "Send the message as written — it explains the reason kindly. "
                "If the item is unused, offer an exchange instead."
            ),
        )

    # 1. No proof of purchase: we cannot give money back, but we can
    #    still look after the customer with store credit.
    if not request.proof_of_purchase:
        return credit(
            f"No receipt or order proof was provided for order "
            f"{request.order_id}, so we cannot pay money back. We can offer "
            f"{_money(request.amount)} in store credit instead."
        )

    # 2. Damaged or faulty items: the shop's mistake, so the customer
    #    is looked after even after the normal window.
    if request.reason in (Reason.DAMAGED, Reason.QUALITY_ISSUE):
        what = (
            "arrived damaged"
            if request.reason == Reason.DAMAGED
            else "has a quality problem"
        )
        if days_since_purchase <= policies["defect_window_days"]:
            return approve(
                f"The {request.product} {what}. It was bought "
                f"{days_since_purchase} days ago, inside the "
                f"{policies['defect_window_days']}-day window for damaged or "
                f"faulty items, so a full refund of "
                f"{_money(request.amount)} applies."
            )
        return partial_refund(
            f"The {request.product} {what}, but it was bought "
            f"{days_since_purchase} days ago, past the "
            f"{policies['defect_window_days']}-day window for damaged or "
            f"faulty items. A part refund of {_money(partial)} "
            f"({policies['partial_refund_percent']}% of the price) applies."
        )

    # 3. Late delivery: full refund when the delivery really was late.
    if request.reason == Reason.LATE_DELIVERY:
        promised = request.promised_delivery_date
        actual = request.actual_delivery_date
        if promised is None or actual is None:
            return approve(
                f"The order {request.order_id} was reported as delivered "
                f"late, and no delivery dates are on file to check against, "
                f"so we take the customer's word for it. A full refund of "
                f"{_money(request.amount)} applies."
            )
        late_by = (actual - promised).days
        if late_by > policies["late_delivery_grace_days"]:
            return approve(
                f"The order was promised for {promised} but arrived on "
                f"{actual} — {late_by} days late, past the "
                f"{policies['late_delivery_grace_days']}-day grace period. "
                f"A full refund of {_money(request.amount)} applies."
            )
        # Not actually late: judge it like a change of mind instead.
        return _changed_mind(request, days_since_purchase, policies,
                             approve, credit, deny)

    # 4. Wrong size or colour.
    if request.reason == Reason.WRONG_SIZE_COLOR:
        if request.condition == Condition.UNUSED_WITH_TAGS:
            if days_since_purchase <= policies["return_window_days"]:
                return exchange(
                    f"The {request.product} is the wrong size or colour "
                    f"and still unused with its tags, bought "
                    f"{days_since_purchase} days ago. Offer an exchange for "
                    f"the right size or colour — or a full refund if the "
                    f"customer prefers."
                )
            return credit(
                f"The {request.product} is the wrong size or colour and "
                f"still unused, but it was bought {days_since_purchase} "
                f"days ago, past the "
                f"{policies['return_window_days']}-day return window. We "
                f"can offer {_money(request.amount)} in store credit."
            )
        return partial_refund(
            f"The {request.product} is the wrong size or colour but has "
            f"been used or washed, so it cannot be resold as new. A part "
            f"refund of {_money(partial)} "
            f"({policies['partial_refund_percent']}% of the price) applies."
        )

    # 5. Changed mind.
    return _changed_mind(request, days_since_purchase, policies,
                         approve, credit, deny)


def _changed_mind(request, days_since_purchase, policies,
                  approve, credit, deny) -> Recommendation:
    """Rules for a change of mind (and for a late delivery that was not
    actually late)."""
    if request.condition == Condition.USED_WASHED:
        return deny(
            f"The {request.product} has been used or washed, and the "
            f"return is a change of mind, so we cannot take it back."
        )
    if days_since_purchase <= policies["changed_mind_full_refund_days"]:
        return approve(
            f"The customer changed their mind about the {request.product}. "
            f"It is unused with its tags and was bought "
            f"{days_since_purchase} days ago, inside the "
            f"{policies['changed_mind_full_refund_days']}-day window for "
            f"change-of-mind refunds, so a full refund of "
            f"${request.amount:,.2f} applies."
        )
    if days_since_purchase <= policies["return_window_days"]:
        return credit(
            f"The customer changed their mind about the {request.product}. "
            f"It is unused, but it was bought {days_since_purchase} days "
            f"ago, past the "
            f"{policies['changed_mind_full_refund_days']}-day window for a "
            f"money refund. We can offer "
            f"${request.amount:,.2f} in store credit."
        )
    return deny(
        f"The {request.product} was bought {days_since_purchase} days ago, "
        f"past the {policies['return_window_days']}-day return window, so "
        f"we cannot refund or credit a change of mind."
    )
