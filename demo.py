#!/usr/bin/env python3
"""Demo: one full day at a textile shop's refund desk.

Runs end to end with invented sample data and an in-memory database:

    intake -> policy recommendation -> staff decision -> customer
    message -> refund / exchange -> feedback -> dashboard

Run it with:  python demo.py
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from refund_system import (
    Condition,
    Feedback,
    FeedbackBook,
    Reason,
    RefundRequest,
    RefundStore,
    Workflow,
    assign_next,
    dashboard,
    feedback_message,
    load_policies,
    prioritize,
    recommend,
    render,
)

POLICIES = load_policies("policies.json")
TODAY = date.today()
NOW = datetime.now()
STAFF = ["Asha", "Ravi"]


def sample_requests() -> list[RefundRequest]:
    """Three invented customers, three different outcomes."""
    return [
        RefundRequest(
            id="R-001",
            order_id="TX-1042",
            customer_name="Meera Shah",
            product="handloom cotton saree fabric (6 metres)",
            reason=Reason.DAMAGED,
            condition=Condition.DAMAGED_ON_ARRIVAL,
            purchase_date=TODAY - timedelta(days=5),
            amount=85.00,
            proof_of_purchase=True,
            created_at=NOW - timedelta(hours=30),
        ),
        RefundRequest(
            id="R-002",
            order_id="TX-1043",
            customer_name="Arjun Patel",
            product="linen kurta, size L",
            reason=Reason.WRONG_SIZE_COLOR,
            condition=Condition.UNUSED_WITH_TAGS,
            purchase_date=TODAY - timedelta(days=10),
            amount=46.50,
            proof_of_purchase=True,
            created_at=NOW - timedelta(hours=50),
        ),
        RefundRequest(
            id="R-003",
            order_id="TX-1044",
            customer_name="Sara Khan",
            product="silk dupatta",
            reason=Reason.CHANGED_MIND,
            condition=Condition.USED_WASHED,
            purchase_date=TODAY - timedelta(days=9),
            amount=32.00,
            proof_of_purchase=True,
            created_at=NOW - timedelta(hours=5),
        ),
    ]


def main() -> None:
    store = RefundStore(":memory:")
    workflow = Workflow()
    feedback_book = FeedbackBook()

    print("=== Textile refund desk — demo day (sample data) ===\n")

    # -- intake: assign each request to the least busy staff member --
    counts = {name: 0 for name in STAFF}
    requests = sample_requests()
    for request in requests:
        request.assigned_to = assign_next(
            STAFF, counts, POLICIES["max_open_per_staff"]
        )
        counts[request.assigned_to] += 1
        store.save_request(request)
        print(
            f"Intake: {request.id} — {request.customer_name}, "
            f"{request.product}, order {request.order_id}, "
            f"${request.amount:.2f} -> assigned to {request.assigned_to}"
        )

    # -- prioritised queue: the overdue one comes first --
    print("\n--- Today's queue (most urgent first) ---")
    for request in prioritize(store.list_requests(), NOW, POLICIES):
        print(f"  {request.id}: {request.customer_name} "
              f"({request.reason.value}, ${request.amount:.2f})")

    # -- work each request through the flow --
    feedback_given = [
        ("R-001", 5, "Quick and kind, no arguing at all.", True),
        ("R-002", 5, "Swapped for the right size in one visit.", True),
        ("R-003", 4, "Understood the policy, staff were polite.", True),
    ]
    for request in requests:
        print(f"\n--- {request.id}: {request.customer_name} ---")
        recommendation = recommend(request, POLICIES, TODAY)
        print(f"Policy says: {recommendation.outcome.value}")
        print(f"  Why: {recommendation.explanation}")
        print(f"  Next step: {recommendation.next_step}")

        workflow.start_review(request, request.assigned_to)
        workflow.apply_decision(request, recommendation,
                                request.assigned_to)
        store.save_request(request)

        print("Message to customer:")
        print("  " + render(
            recommendation.outcome, request, recommendation,
            credit_code=f"CREDIT-{request.order_id}"))

        if request.status.value in ("approved", "partial_approved"):
            workflow.issue_refund(request, request.assigned_to)
        elif request.status.value == "exchange_offered":
            workflow.complete_exchange(request, request.assigned_to)
        workflow.request_feedback(request, request.assigned_to)
        store.save_request(request)

        print("Feedback request:")
        print("  " + feedback_message(request))
        for rid, rating, comment, would in feedback_given:
            if rid == request.id:
                feedback_book.add(Feedback(
                    request_id=rid, rating=rating, comment=comment,
                    would_recommend=would,
                ))
                print(f"Customer replied: {rating}/5 — \"{comment}\"")
        workflow.close(request, request.assigned_to)
        store.save_request(request)
        for entry in workflow.history(request.id):
            store.save_audit(entry)

    # -- end of day: the calm summary --
    summary = dashboard(store.list_requests(),
                        feedback_book.summary(), NOW, POLICIES)
    print("\n=== End-of-day dashboard ===")
    print(f"Open requests:   {summary['open_requests']}")
    print(f"Overdue:         {summary['overdue_requests']}")
    print(f"Resolved today:  {summary['resolved_today']}")
    print(f"Average rating:  {summary['average_rating']} "
          f"({summary['feedback_count']} reviews)")
    print(f"Open per staff:  {summary['open_per_staff'] or 'none — all clear'}")
    print("\nAudit trail entries recorded:", len(workflow.audit))
    store.close()


if __name__ == "__main__":
    main()
