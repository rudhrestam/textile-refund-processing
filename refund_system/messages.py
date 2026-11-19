"""Customer messages for every refund outcome.

Each template is short, warm, and free of jargon — the customer
should understand exactly what happens next without having to ask.
Templates are plain strings with {placeholders}; render() fills them
in from the request and the policy recommendation.
"""
from __future__ import annotations

from .models import Outcome, RefundRequest
from .policy import Recommendation

TEMPLATES = {
    Outcome.APPROVE: (
        "Hi {customer_name}, thank you for letting us know about your "
        "{product} (order {order_id}). We're sorry it didn't work out. "
        "We've approved a full refund of {amount} — it will reach your "
        "original payment method within 3–5 working days. No need to do "
        "anything else. We hope to see you again soon."
    ),
    Outcome.PARTIAL: (
        "Hi {customer_name}, thank you for letting us know about your "
        "{product} (order {order_id}). We're sorry it didn't work out. "
        "Because the item has been used, we can refund {amount} — half "
        "of the price — and it will reach your original payment method "
        "within 3–5 working days. If you have any questions, just reply "
        "to this message and we'll help."
    ),
    Outcome.EXCHANGE: (
        "Hi {customer_name}, thank you for letting us know about your "
        "{product} (order {order_id}). No problem at all — we'd be glad "
        "to swap it for the size or colour you wanted. Just bring the "
        "item (with its tags) to the shop, or reply to this message and "
        "we'll arrange it. If you'd rather have a full refund instead, "
        "that is fine too."
    ),
    Outcome.CREDIT: (
        "Hi {customer_name}, thank you for letting us know about your "
        "{product} (order {order_id}). We can offer you {amount} in "
        "store credit, which never expires and works on anything in the "
        "shop. Your credit code is {credit_code} — just show it at the "
        "till or mention it when you order. We're sorry the item didn't "
        "work out."
    ),
    Outcome.DENY: (
        "Hi {customer_name}, thank you for letting us know about your "
        "{product} (order {order_id}). We're sorry, but we can't offer a "
        "refund this time. {reason} If the item is still unused with its "
        "tags, we can happily exchange it instead — just let us know. "
        "Thank you for shopping with us, and we hope the next visit is "
        "a better one."
    ),
}

FEEDBACK_REQUEST = (
    "Hi {customer_name}, your refund for order {order_id} is sorted. "
    "Could you spare a minute to tell us how it went? A quick rating "
    "from 1 to 5, and anything we could do better, would really help "
    "us. Thank you!"
)


def render(outcome: Outcome, request: RefundRequest,
           recommendation: Recommendation,
           credit_code: str = "CREDIT-0000") -> str:
    """Build the customer message for one outcome."""
    template = TEMPLATES[outcome]
    amount = (
        f"${recommendation.refund_amount:,.2f}"
        if recommendation.refund_amount
        else f"${recommendation.credit_amount:,.2f}"
    )
    return template.format(
        customer_name=request.customer_name,
        order_id=request.order_id,
        product=request.product,
        amount=amount,
        reason=recommendation.explanation,
        credit_code=credit_code,
    )


def feedback_message(request: RefundRequest) -> str:
    """The short message that asks the customer for feedback."""
    return FEEDBACK_REQUEST.format(
        customer_name=request.customer_name,
        order_id=request.order_id,
    )
