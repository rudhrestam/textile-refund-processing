# Textile Refund Processing

![CI](https://github.com/rudhrestam/textile-refund-processing/actions/workflows/ci.yml/badge.svg) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

A refund desk for a textile shop that takes the stress out of refunds — for staff and for customers. Staff get a clear policy answer for every request, one-click next steps, and a queue that never overloads anyone. Customers get plain, kind messages and a short feedback survey after their refund, so a refund ends in a good review instead of a lost customer.

> This is a representative demo of patterns used in production systems, built with sample data and original code. It contains no employer code, data, or internal details. All names, orders, and amounts are invented sample data.

## What it does

- **Refund intake** — order id, customer, product (fabric or garment), reason (damaged, wrong size/colour, late delivery, quality issue, changed mind), purchase date, amount, and proof of purchase.
- **Policy engine** — gives staff a clear recommendation (full refund, part refund, exchange, store credit, or no refund) with the reason written in plain words, so nobody has to decide under pressure.
- **Guided workflow** — received → under review → decision → refund/exchange → feedback requested → closed. Illegal moves are refused, and every step is written to an audit trail.
- **Customer messages** — a warm, jargon-free message for every outcome, ready to send by email or SMS.
- **Feedback capture** — a 1–5 rating, a comment, and a would-recommend flag after each resolution, with average rating and recent comments tracked.
- **Calm queue** — overdue requests first, work balanced across staff with a cap per person, and a dashboard that shows open requests, overdue items, today's resolved count, and the average rating at a glance.
- **Tunable policies** — return windows, part-refund percentages, and SLA hours live in `policies.json`. Change the file, not the code.
- **Storage** — SQLite (one file, no server) or in-memory for tests and demos.

## Project structure

```
textile-refund-processing/
├── demo.py                  # end-to-end demo day (sample data, in-memory)
├── policies.json            # tunable policy settings
├── refund_system/
│   ├── __init__.py          # public exports
│   ├── models.py            # request, reason, outcome, and status types
│   ├── policy.py            # the policy engine (recommendations + reasons)
│   ├── workflow.py          # state machine, one-click actions, audit trail
│   ├── messages.py          # customer message templates per outcome
│   ├── feedback.py          # feedback capture and scoring
│   ├── queue.py             # prioritisation, SLA, workload balance, dashboard
│   └── store.py             # SQLite storage (file or in-memory)
├── tests/                   # pytest suite (48 tests)
├── requirements.txt         # pytest only; the app itself is stdlib-only
└── .github/workflows/ci.yml # install, test, run demo
```

## Setup

Python 3.10+ and nothing else for the app itself. Tests need pytest:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## How to use

### 1. Run the demo

One command shows a full day at the refund desk — three sample customers, three different outcomes, feedback, and the end-of-day dashboard:

```bash
python demo.py
```

Sample output (real output, sample data):

```
=== Textile refund desk — demo day (sample data) ===

Intake: R-001 — Meera Shah, handloom cotton saree fabric (6 metres), order TX-1042, $85.00 -> assigned to Asha
Intake: R-002 — Arjun Patel, linen kurta, size L, order TX-1043, $46.50 -> assigned to Ravi
Intake: R-003 — Sara Khan, silk dupatta, order TX-1044, $32.00 -> assigned to Asha

--- Today's queue (most urgent first) ---
  R-002: Arjun Patel (wrong_size_color, $46.50)
  R-001: Meera Shah (damaged, $85.00)
  R-003: Sara Khan (changed_mind, $32.00)

--- R-001: Meera Shah ---
Policy says: approve
  Why: The handloom cotton saree fabric (6 metres) arrived damaged. It was bought 5 days ago, inside the 60-day window for damaged or faulty items, so a full refund of $85.00 applies.
  Next step: Issue the full refund — one click, no extra approval needed.
Message to customer:
  Hi Meera Shah, thank you for letting us know about your handloom cotton saree fabric (6 metres) (order TX-1042). We're sorry it didn't work out. We've approved a full refund of $85.00 — it will reach your original payment method within 3–5 working days. No need to do anything else. We hope to see you again soon.
Customer replied: 5/5 — "Quick and kind, no arguing at all."

--- R-002: Arjun Patel ---
Policy says: exchange
  Why: The linen kurta, size L is the wrong size or colour and still unused with its tags, bought 10 days ago. Offer an exchange for the right size or colour — or a full refund if the customer prefers.
Customer replied: 5/5 — "Swapped for the right size in one visit."

--- R-003: Sara Khan ---
Policy says: deny
  Why: The silk dupatta has been used or washed, and the return is a change of mind, so we cannot take it back.
Customer replied: 4/5 — "Understood the policy, staff were polite."

=== End-of-day dashboard ===
Open requests:   0
Overdue:         0
Resolved today:  3
Average rating:  4.67 (3 reviews)
Open per staff:  none — all clear

Audit trail entries recorded: 14
```

Note that R-002 comes first in the queue: it is the oldest against the 48-hour review deadline, so the queue surfaces it before the newer requests.

### 2. Process a refund step by step

The same flow the demo runs, in your own code:

```python
from datetime import date, timedelta
from refund_system import (
    Condition, Reason, RefundRequest, RefundStore, Workflow,
    load_policies, recommend, render,
)

policies = load_policies("policies.json")  # or load_policies() for defaults
store = RefundStore("refunds.db")         # file-based; ":memory:" for a demo
workflow = Workflow()

# 1. Intake — a customer brings back a damaged fabric
request = RefundRequest(
    id="R-101",
    order_id="TX-2001",
    customer_name="Meera Shah",
    product="handloom cotton saree fabric (6 metres)",
    reason=Reason.DAMAGED,
    condition=Condition.DAMAGED_ON_ARRIVAL,
    purchase_date=date.today() - timedelta(days=5),
    amount=85.00,
    proof_of_purchase=True,
)
store.save_request(request)

# 2. Policy recommendation — staff see the answer and the reason
recommendation = recommend(request, policies)
print(recommendation.outcome.value)   # approve
print(recommendation.explanation)     # ... inside the 60-day window ...
print(recommendation.next_step)       # Issue the full refund ...

# 3. Work it through — each call is one click, and each is audited
workflow.start_review(request, "Asha")
workflow.apply_decision(request, recommendation, "Asha")
workflow.issue_refund(request, "Asha")
workflow.request_feedback(request, "Asha")

# 4. Message the customer — warm, plain words, ready to send
print(render(recommendation.outcome, request, recommendation))

# 5. Close once feedback arrives
workflow.close(request, "Asha")
store.save_request(request)
for entry in workflow.history(request.id):
    store.save_audit(entry)
```

Overriding the recommendation is allowed, but only with a written note — the override and the note both land in the audit trail:

```python
workflow.apply_decision(request, recommendation, "Asha",
                        outcome=Outcome.DENY,
                        note="Customer agreed to an exchange instead.")
# raises ValueError if the note is missing
```

### 3. Customise the policies

Edit `policies.json` — no code changes needed:

```json
{
  "changed_mind_full_refund_days": 14,
  "defect_window_days": 60,
  "late_delivery_grace_days": 7,
  "max_open_per_staff": 5,
  "partial_refund_percent": 50,
  "return_window_days": 30,
  "review_sla_hours": 48
}
```

| Setting | What it means |
|---|---|
| `return_window_days` | How long after purchase a normal return is accepted (30) |
| `changed_mind_full_refund_days` | How long a change of mind still gets money back, not credit (14) |
| `defect_window_days` | How long damaged or faulty items get a full refund (60) |
| `partial_refund_percent` | What share of the price a part refund pays (50) |
| `late_delivery_grace_days` | How many days late a delivery must be to count as late (7) |
| `review_sla_hours` | How long staff have to review a request before it is overdue (48) |
| `max_open_per_staff` | Most open requests one person can hold at once (5) |

The decision rules, in order: no proof of purchase → store credit; damaged or faulty → full refund inside the defect window, part refund after it; late delivery → full refund when really late; wrong size/colour → exchange if unused, part refund if used, credit if out of window; changed mind → full refund if unused and early, credit if unused and inside the window, no refund if used or out of window.

### 4. Collect feedback and check the dashboard

```python
from refund_system import Feedback, FeedbackBook, dashboard

book = FeedbackBook()
book.add(Feedback(request_id="R-101", rating=5,
                  comment="Quick and kind, no arguing at all.",
                  would_recommend=True))
print(book.summary())
# {'count': 1, 'average_rating': 5.0, 'recommend_percent': 100.0,
#  'comments': ['Quick and kind, no arguing at all.']}

from datetime import datetime
summary = dashboard(store.list_requests(), book.summary(),
                    datetime.now(), policies)
print(summary)
# {'open_requests': 0, 'overdue_requests': 0, 'resolved_today': 1,
#  'average_rating': 5.0, 'feedback_count': 1, 'open_per_staff': {}}
```

### 5. Run the tests

```bash
python -m pytest -q
# 48 passed
```

The suite covers every policy outcome, legal and illegal workflow moves (including overrides without a note), every message template, feedback scoring and validation, queue ordering and SLA status, workload caps, and SQLite round trips.

## Tech stack

Python 3.10+ (standard library only) · SQLite · pytest

## What it demonstrates

- A rule engine with plain-language explanations for every decision
- A checked state machine with a full audit trail
- Customer communication written for the customer, not the system
- Feedback loops that turn a refund into a review
- Queue design that protects staff from overload (SLA + workload caps)
- Configuration over code changes for business rules
