"""Data types for the textile refund system.

Plain dataclasses and small enums. Nothing here talks to a database or
makes a decision — those jobs live in store.py and policy.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class Reason(str, Enum):
    """Why the customer is asking for a refund."""

    DAMAGED = "damaged"
    WRONG_SIZE_COLOR = "wrong_size_color"
    LATE_DELIVERY = "late_delivery"
    QUALITY_ISSUE = "quality_issue"
    CHANGED_MIND = "changed_mind"


class Condition(str, Enum):
    """What state the item is in when the customer brings it back."""

    UNUSED_WITH_TAGS = "unused_with_tags"
    USED_WASHED = "used_washed"
    DAMAGED_ON_ARRIVAL = "damaged_on_arrival"
    DEFECTIVE = "defective"


class Outcome(str, Enum):
    """What the policy engine recommends doing."""

    APPROVE = "approve"          # full refund
    PARTIAL = "partial"          # part of the money back
    EXCHANGE = "exchange"        # swap for another size / colour
    CREDIT = "credit"            # store credit for the full amount
    DENY = "deny"                # no refund, with a reason


class Status(str, Enum):
    """Where a refund request sits in the workflow."""

    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PARTIAL_APPROVED = "partial_approved"
    EXCHANGE_OFFERED = "exchange_offered"
    CREDIT_ISSUED = "credit_issued"
    DENIED = "denied"
    REFUND_ISSUED = "refund_issued"
    EXCHANGE_COMPLETED = "exchange_completed"
    FEEDBACK_REQUESTED = "feedback_requested"
    CLOSED = "closed"


@dataclass
class RefundRequest:
    """One customer's refund request, as it arrives at the desk."""

    id: str
    order_id: str
    customer_name: str
    product: str
    reason: Reason
    condition: Condition
    purchase_date: date
    amount: float
    proof_of_purchase: bool = True
    promised_delivery_date: date | None = None
    actual_delivery_date: date | None = None
    created_at: datetime = field(default_factory=datetime.now)
    status: Status = Status.RECEIVED
    assigned_to: str | None = None
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.reason, str):
            self.reason = Reason(self.reason)
        if isinstance(self.condition, str):
            self.condition = Condition(self.condition)
        if isinstance(self.status, str):
            self.status = Status(self.status)
        if self.amount <= 0:
            raise ValueError("amount must be greater than zero")
