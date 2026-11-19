"""The refund workflow: one request moves through states, one step at
a time.

Every move is checked — an illegal move is refused, never silently
allowed — and written to the audit trail, so nothing happens without
a record of who did it and why.

Flow:

    received -> under_review -> approved / partial_approved /
        exchange_offered / credit_issued / denied
    approved / partial_approved -> refund_issued
    exchange_offered -> exchange_completed
    credit_issued / denied / refund_issued / exchange_completed
        -> feedback_requested -> closed

Staff may override the policy engine's recommendation, but only with
a written note, and the override is recorded in the audit trail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import Outcome, RefundRequest, Status
from .policy import Recommendation

ALLOWED = {
    Status.RECEIVED: {Status.UNDER_REVIEW},
    Status.UNDER_REVIEW: {
        Status.APPROVED,
        Status.PARTIAL_APPROVED,
        Status.EXCHANGE_OFFERED,
        Status.CREDIT_ISSUED,
        Status.DENIED,
    },
    Status.APPROVED: {Status.REFUND_ISSUED},
    Status.PARTIAL_APPROVED: {Status.REFUND_ISSUED},
    Status.EXCHANGE_OFFERED: {Status.EXCHANGE_COMPLETED},
    Status.CREDIT_ISSUED: {Status.FEEDBACK_REQUESTED},
    Status.DENIED: {Status.FEEDBACK_REQUESTED},
    Status.REFUND_ISSUED: {Status.FEEDBACK_REQUESTED},
    Status.EXCHANGE_COMPLETED: {Status.FEEDBACK_REQUESTED},
    Status.FEEDBACK_REQUESTED: {Status.CLOSED},
    Status.CLOSED: set(),
}

DECISION_TO_STATUS = {
    Outcome.APPROVE: Status.APPROVED,
    Outcome.PARTIAL: Status.PARTIAL_APPROVED,
    Outcome.EXCHANGE: Status.EXCHANGE_OFFERED,
    Outcome.CREDIT: Status.CREDIT_ISSUED,
    Outcome.DENY: Status.DENIED,
}


@dataclass
class AuditEntry:
    """One recorded step in a request's history."""

    request_id: str
    actor: str
    action: str
    from_status: Status
    to_status: Status
    note: str = ""
    created_at: datetime = field(default_factory=datetime.now)


class Workflow:
    """Moves requests through their states and keeps the audit trail."""

    def __init__(self) -> None:
        self.audit: list[AuditEntry] = []

    def move(self, request: RefundRequest, to_status: Status,
             actor: str, action: str, note: str = "") -> AuditEntry:
        """Move a request to a new state, refusing illegal moves."""
        if to_status not in ALLOWED[request.status]:
            raise ValueError(
                f"cannot move request {request.id} from "
                f"{request.status.value} to {to_status.value}"
            )
        entry = AuditEntry(
            request_id=request.id,
            actor=actor,
            action=action,
            from_status=request.status,
            to_status=to_status,
            note=note,
        )
        request.status = to_status
        if to_status == Status.CLOSED:
            request.resolved_at = datetime.now()
        self.audit.append(entry)
        return entry

    def start_review(self, request: RefundRequest, actor: str) -> AuditEntry:
        return self.move(request, Status.UNDER_REVIEW, actor,
                         "review started")

    def apply_decision(self, request: RefundRequest,
                       recommendation: Recommendation,
                       actor: str, outcome: Outcome | None = None,
                       note: str = "") -> AuditEntry:
        """Apply the policy recommendation — or an override.

        Pass ``outcome`` to override the recommendation. Overrides
        need a written note, so the reason is on record.
        """
        chosen = outcome if outcome is not None else recommendation.outcome
        if chosen != recommendation.outcome and not note.strip():
            raise ValueError(
                "overriding the policy recommendation needs a written note"
            )
        action = (
            f"decision: {chosen.value}"
            if chosen == recommendation.outcome
            else f"decision: {chosen.value} (override of "
                 f"{recommendation.outcome.value})"
        )
        return self.move(request, DECISION_TO_STATUS[chosen], actor,
                         action, note)

    def issue_refund(self, request: RefundRequest, actor: str) -> AuditEntry:
        return self.move(request, Status.REFUND_ISSUED, actor,
                         "refund issued")

    def complete_exchange(self, request: RefundRequest,
                          actor: str) -> AuditEntry:
        return self.move(request, Status.EXCHANGE_COMPLETED, actor,
                         "exchange completed")

    def request_feedback(self, request: RefundRequest,
                         actor: str) -> AuditEntry:
        return self.move(request, Status.FEEDBACK_REQUESTED, actor,
                         "feedback requested")

    def close(self, request: RefundRequest, actor: str) -> AuditEntry:
        return self.move(request, Status.CLOSED, actor, "closed")

    def history(self, request_id: str) -> list[AuditEntry]:
        """Every recorded step for one request, in order."""
        return [e for e in self.audit if e.request_id == request_id]
