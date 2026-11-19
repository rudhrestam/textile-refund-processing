"""The staff queue: what to work on first, who should take it, and how
the day is going.

The ideas are deliberately simple, because a calm desk is a fast
desk:

- Overdue requests come first, then the biggest amounts, then the
  oldest — so nothing urgent hides at the bottom of the pile.
- New work goes to the person with the fewest open requests, and
  nobody is handed more than the configured maximum at once.
- The dashboard shows the whole day at a glance: what is open, what
  is overdue, what got resolved, and how customers rated the service.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .models import RefundRequest, Status

OPEN_STATUSES = {
    Status.RECEIVED,
    Status.UNDER_REVIEW,
    Status.APPROVED,
    Status.PARTIAL_APPROVED,
    Status.EXCHANGE_OFFERED,
    Status.CREDIT_ISSUED,
    Status.DENIED,
    Status.REFUND_ISSUED,
    Status.EXCHANGE_COMPLETED,
    Status.FEEDBACK_REQUESTED,
}


def sla_status(request: RefundRequest, now: datetime,
               policies: dict) -> tuple[str, float]:
    """How a request stands against its review deadline.

    Returns ("overdue" | "due_soon" | "on_track", hours left).
    Hours left is negative when the request is overdue.
    """
    deadline = request.created_at + timedelta(
        hours=policies["review_sla_hours"]
    )
    hours_left = (deadline - now).total_seconds() / 3600
    if hours_left < 0:
        return "overdue", round(hours_left, 1)
    if hours_left <= 8:
        return "due_soon", round(hours_left, 1)
    return "on_track", round(hours_left, 1)


def prioritize(requests: list[RefundRequest], now: datetime,
               policies: dict) -> list[RefundRequest]:
    """Order open requests so the most urgent is first.

    Overdue first (most overdue at the top), then the largest amounts,
    then the oldest requests. Closed requests are left out.
    """
    open_requests = [r for r in requests if r.status in OPEN_STATUSES]

    def sort_key(request: RefundRequest) -> tuple:
        status, hours_left = sla_status(request, now, policies)
        overdue_rank = 0 if status == "overdue" else 1
        # Most overdue first within the overdue group; otherwise the
        # hours left do not matter — amount, then age, decide.
        urgency = hours_left if status == "overdue" else 0.0
        return (overdue_rank, urgency, -request.amount,
                request.created_at)

    return sorted(open_requests, key=sort_key)


def assign_next(staff: list[str], open_counts: dict[str, int],
                max_open: int) -> str | None:
    """Pick who should take the next request.

    The person with the fewest open requests wins. Returns None when
    everyone is already at the maximum — a signal to the team lead,
    not a silent overload.
    """
    available = [name for name in staff
                 if open_counts.get(name, 0) < max_open]
    if not available:
        return None
    return min(available, key=lambda name: open_counts.get(name, 0))


def dashboard(requests: list[RefundRequest],
              feedback_summary: dict, now: datetime,
              policies: dict) -> dict:
    """The calm summary for the start of a shift."""
    open_requests = [r for r in requests if r.status in OPEN_STATUSES]
    overdue = sum(
        1 for r in open_requests
        if sla_status(r, now, policies)[0] == "overdue"
    )
    resolved_today = sum(
        1 for r in requests
        if r.status == Status.CLOSED and r.resolved_at is not None
        and r.resolved_at.date() == now.date()
    )
    per_staff: dict[str, int] = {}
    for request in open_requests:
        if request.assigned_to:
            per_staff[request.assigned_to] = (
                per_staff.get(request.assigned_to, 0) + 1
            )
    return {
        "open_requests": len(open_requests),
        "overdue_requests": overdue,
        "resolved_today": resolved_today,
        "average_rating": feedback_summary.get("average_rating"),
        "feedback_count": feedback_summary.get("count", 0),
        "open_per_staff": per_staff,
    }
