"""Customer feedback after a refund is resolved.

A short survey: a rating from 1 to 5, an optional comment, and
whether the customer would recommend the shop. The summary keeps
the numbers the shop actually cares about: the average rating, how
many people would recommend it, and the recent comments in plain
words.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Feedback:
    """One customer's answers after their refund is resolved."""

    request_id: str
    rating: int                      # 1 (unhappy) to 5 (very happy)
    comment: str = ""
    would_recommend: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not 1 <= self.rating <= 5:
            raise ValueError("rating must be between 1 and 5")


class FeedbackBook:
    """Collects feedback and summarises it."""

    def __init__(self) -> None:
        self.entries: list[Feedback] = []

    def add(self, feedback: Feedback) -> Feedback:
        self.entries.append(feedback)
        return feedback

    def for_request(self, request_id: str) -> list[Feedback]:
        return [f for f in self.entries if f.request_id == request_id]

    def summary(self) -> dict:
        """Average rating, recommendation rate, and recent comments."""
        if not self.entries:
            return {
                "count": 0,
                "average_rating": None,
                "recommend_percent": None,
                "comments": [],
            }
        ratings = [f.rating for f in self.entries]
        recommend = sum(1 for f in self.entries if f.would_recommend)
        comments = [f.comment for f in self.entries if f.comment.strip()]
        return {
            "count": len(self.entries),
            "average_rating": round(sum(ratings) / len(ratings), 2),
            "recommend_percent": round(100 * recommend / len(self.entries), 1),
            "comments": comments[-5:],  # most recent five comments
        }
