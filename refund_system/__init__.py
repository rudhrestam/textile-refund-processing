"""Textile refund processing — a calm refund desk for a textile shop.

Staff get a clear policy answer for every request, one-click next
steps, and a queue that never overloads anyone. Customers get plain,
kind messages and a short feedback survey after their refund.

All names, orders, and amounts in this project are invented sample
data. There is no real customer or company data here.
"""

from .feedback import Feedback, FeedbackBook
from .messages import feedback_message, render
from .models import Condition, Outcome, Reason, RefundRequest, Status
from .policy import DEFAULT_POLICIES, Recommendation, load_policies, recommend
from .queue import assign_next, dashboard, prioritize, sla_status
from .store import RefundStore
from .workflow import AuditEntry, Workflow

__all__ = [
    "Condition",
    "Outcome",
    "Reason",
    "RefundRequest",
    "Status",
    "Recommendation",
    "AuditEntry",
    "Feedback",
    "FeedbackBook",
    "RefundStore",
    "Workflow",
    "DEFAULT_POLICIES",
    "load_policies",
    "recommend",
    "render",
    "feedback_message",
    "assign_next",
    "dashboard",
    "prioritize",
    "sla_status",
]
