"""Storage: one SQLite file, no server needed.

Three small tables — requests, the audit trail, and feedback — with
plain save/load methods. Pass ":memory:" as the path for tests and
demos, or a file path (for example "refunds.db") to keep data between
runs.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

from .feedback import Feedback
from .models import Condition, Reason, RefundRequest, Status
from .workflow import AuditEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    product TEXT NOT NULL,
    reason TEXT NOT NULL,
    condition TEXT NOT NULL,
    purchase_date TEXT NOT NULL,
    amount REAL NOT NULL,
    proof_of_purchase INTEGER NOT NULL,
    promised_delivery_date TEXT,
    actual_delivery_date TEXT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    assigned_to TEXT,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    would_recommend INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class RefundStore:
    """A SQLite-backed store for requests, audit entries, and feedback."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- requests -----------------------------------------------------
    def save_request(self, request: RefundRequest) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO requests
               (id, order_id, customer_name, product, reason, condition,
                purchase_date, amount, proof_of_purchase,
                promised_delivery_date, actual_delivery_date, created_at,
                status, assigned_to, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request.id,
                request.order_id,
                request.customer_name,
                request.product,
                request.reason.value,
                request.condition.value,
                request.purchase_date.isoformat(),
                request.amount,
                1 if request.proof_of_purchase else 0,
                request.promised_delivery_date.isoformat()
                if request.promised_delivery_date else None,
                request.actual_delivery_date.isoformat()
                if request.actual_delivery_date else None,
                request.created_at.isoformat(),
                request.status.value,
                request.assigned_to,
                request.resolved_at.isoformat()
                if request.resolved_at else None,
            ),
        )
        self.conn.commit()

    def get_request(self, request_id: str) -> RefundRequest | None:
        row = self.conn.execute(
            "SELECT * FROM requests WHERE id = ?", (request_id,)
        ).fetchone()
        return self._row_to_request(row) if row else None

    def list_requests(self, status: Status | None = None) -> list[RefundRequest]:
        if status is None:
            rows = self.conn.execute(
                "SELECT * FROM requests ORDER BY created_at"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM requests WHERE status = ? ORDER BY created_at",
                (status.value,),
            ).fetchall()
        return [self._row_to_request(row) for row in rows]

    @staticmethod
    def _row_to_request(row: tuple) -> RefundRequest:
        return RefundRequest(
            id=row[0],
            order_id=row[1],
            customer_name=row[2],
            product=row[3],
            reason=Reason(row[4]),
            condition=Condition(row[5]),
            purchase_date=_parse_date(row[6]),
            amount=row[7],
            proof_of_purchase=bool(row[8]),
            promised_delivery_date=_parse_date(row[9]),
            actual_delivery_date=_parse_date(row[10]),
            created_at=_parse_datetime(row[11]),
            status=Status(row[12]),
            assigned_to=row[13],
            resolved_at=_parse_datetime(row[14]),
        )

    # -- audit --------------------------------------------------------
    def save_audit(self, entry: AuditEntry) -> None:
        self.conn.execute(
            """INSERT INTO audit
               (request_id, actor, action, from_status, to_status, note,
                created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.request_id,
                entry.actor,
                entry.action,
                entry.from_status.value,
                entry.to_status.value,
                entry.note,
                entry.created_at.isoformat(),
            ),
        )
        self.conn.commit()

    def list_audit(self, request_id: str) -> list[AuditEntry]:
        rows = self.conn.execute(
            "SELECT * FROM audit WHERE request_id = ? ORDER BY id",
            (request_id,),
        ).fetchall()
        return [
            AuditEntry(
                request_id=row[1],
                actor=row[2],
                action=row[3],
                from_status=Status(row[4]),
                to_status=Status(row[5]),
                note=row[6],
                created_at=_parse_datetime(row[7]),
            )
            for row in rows
        ]

    # -- feedback -----------------------------------------------------
    def save_feedback(self, feedback: Feedback) -> None:
        self.conn.execute(
            """INSERT INTO feedback
               (request_id, rating, comment, would_recommend, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                feedback.request_id,
                feedback.rating,
                feedback.comment,
                1 if feedback.would_recommend else 0,
                feedback.created_at.isoformat(),
            ),
        )
        self.conn.commit()

    def list_feedback(self) -> list[Feedback]:
        rows = self.conn.execute(
            "SELECT * FROM feedback ORDER BY id"
        ).fetchall()
        return [
            Feedback(
                request_id=row[1],
                rating=row[2],
                comment=row[3],
                would_recommend=bool(row[4]),
                created_at=_parse_datetime(row[5]),
            )
            for row in rows
        ]
