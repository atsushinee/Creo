"""Tests for the in-memory session service."""

from app.services.session_service import DEFAULT_TITLE, InMemorySessionService


def test_ensure_creates_and_reuses() -> None:
    service = InMemorySessionService()
    first = service.ensure("s1")
    second = service.ensure("s1")
    assert first.id == second.id == "s1"
    assert first.title == DEFAULT_TITLE


def test_list_orders_by_updated_at_desc() -> None:
    service = InMemorySessionService()
    service.ensure("older")
    service.ensure("newer")
    service.touch("older")
    ids = [session.id for session in service.list()]
    assert ids == ["older", "newer"]


def test_touch_sets_title_only_once() -> None:
    service = InMemorySessionService()
    service.ensure("s1")
    service.touch("s1", title="计算 123 * 456")
    assert service.get("s1").title == "计算 123 * 456"
    service.touch("s1", title="second message")
    assert service.get("s1").title == "计算 123 * 456"


def test_title_is_truncated() -> None:
    service = InMemorySessionService()
    service.ensure("s1")
    service.touch("s1", title="x" * 200)
    title = service.get("s1").title
    assert len(title) <= 49
    assert title.endswith("…")


def test_delete() -> None:
    service = InMemorySessionService()
    service.ensure("s1")
    assert service.delete("s1") is True
    assert service.get("s1") is None
    assert service.delete("s1") is False
