"""Tests for feedback capture and scoring."""
import pytest

from refund_system import Feedback, FeedbackBook


def test_average_rating_and_recommend_rate():
    book = FeedbackBook()
    book.add(Feedback(request_id="R-1", rating=5, comment="Great service."))
    book.add(Feedback(request_id="R-2", rating=4, comment="Good.",
                      would_recommend=True))
    book.add(Feedback(request_id="R-3", rating=3, comment="Okay.",
                      would_recommend=False))
    summary = book.summary()
    assert summary["count"] == 3
    assert summary["average_rating"] == 4.0
    assert summary["recommend_percent"] == 66.7
    assert len(summary["comments"]) == 3


def test_empty_book_has_no_average():
    summary = FeedbackBook().summary()
    assert summary["count"] == 0
    assert summary["average_rating"] is None
    assert summary["recommend_percent"] is None
    assert summary["comments"] == []


def test_rating_must_be_between_1_and_5():
    with pytest.raises(ValueError):
        Feedback(request_id="R-1", rating=0)
    with pytest.raises(ValueError):
        Feedback(request_id="R-1", rating=6)


def test_only_the_latest_five_comments_are_kept():
    book = FeedbackBook()
    for i in range(7):
        book.add(Feedback(request_id=f"R-{i}", rating=5,
                          comment=f"comment {i}"))
    summary = book.summary()
    assert len(summary["comments"]) == 5
    assert summary["comments"][0] == "comment 2"
    assert summary["comments"][-1] == "comment 6"


def test_feedback_lookup_by_request():
    book = FeedbackBook()
    book.add(Feedback(request_id="R-1", rating=5))
    book.add(Feedback(request_id="R-2", rating=2))
    assert len(book.for_request("R-1")) == 1
    assert book.for_request("R-1")[0].rating == 5
    assert book.for_request("R-9") == []
