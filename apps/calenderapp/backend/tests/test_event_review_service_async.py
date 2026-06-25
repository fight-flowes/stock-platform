from app.services.event_review_service import EventReviewService


def test_run_review_returns_completed_cache(monkeypatch):
    cached = {
        "found": True,
        "event_key": "evt_1",
        "review": {"review_status": "completed"},
    }

    monkeypatch.setattr(
        "app.services.event_review_service.StockkbProxyService.get_market_event_review",
        lambda event_key: cached.copy(),
    )

    result = EventReviewService.run_review("evt_1", force=False)

    assert result["source"] == "cache"
    assert result["review"]["review_status"] == "completed"


def test_run_review_enqueues_background_job(monkeypatch):
    existing = {"found": False, "event_key": "evt_2", "review": None}
    event = {
        "event_key": "evt_2",
        "event_name": "测试事件",
        "event_time_text": "2026-06-22",
        "event_content": "测试内容",
        "source_reports": [],
    }
    pending = {
        "found": True,
        "event_key": "evt_2",
        "review": {"review_status": "pending"},
        "event": event,
    }
    stored_after_enqueue = {
        "found": True,
        "event_key": "evt_2",
        "review": {"review_status": "pending"},
    }
    put_payloads = []
    get_review_calls = {"count": 0}

    def fake_get_review(event_key):
        get_review_calls["count"] += 1
        if get_review_calls["count"] == 1:
            return existing.copy()
        return stored_after_enqueue.copy()

    monkeypatch.setattr(
        "app.services.event_review_service.StockkbProxyService.get_market_event_review",
        fake_get_review,
    )
    monkeypatch.setattr(
        "app.services.event_review_service.StockkbProxyService.run_market_event_review",
        lambda event_key: pending.copy(),
    )
    monkeypatch.setattr(
        "app.services.event_review_service.StockkbProxyService.get_market_event_detail",
        lambda event_key: {"found": True, "event": event},
    )
    monkeypatch.setattr(
        "app.services.event_review_service.StockkbProxyService.put_market_event_review",
        lambda event_key, payload: put_payloads.append((event_key, payload)) or stored_after_enqueue.copy(),
    )
    monkeypatch.setattr(
        EventReviewService,
        "_acquire_session_id",
        classmethod(lambda cls, event_key, existing_review: "session_123"),
    )
    monkeypatch.setattr(
        EventReviewService,
        "_enqueue_review_job",
        classmethod(lambda cls, **kwargs: True),
    )

    result = EventReviewService.run_review("evt_2", force=False)

    assert result["source"] == "queued"
    assert result["session_id"] == "session_123"
    assert result["event"] == event
    assert put_payloads
    assert put_payloads[0][1]["review_status"] == "pending"
    assert put_payloads[0][1]["vibe_session_id"] == "session_123"


def test_run_review_reuses_existing_running_job(monkeypatch):
    existing = {"found": False, "event_key": "evt_3", "review": None}
    event = {
        "event_key": "evt_3",
        "event_name": "测试事件",
        "event_time_text": "",
        "event_content": "",
        "source_reports": [],
    }
    pending = {
        "found": True,
        "event_key": "evt_3",
        "review": {"review_status": "pending"},
        "event": event,
    }
    stored_after_enqueue = {
        "found": True,
        "event_key": "evt_3",
        "review": {"review_status": "pending"},
    }
    get_review_calls = {"count": 0}

    def fake_get_review(event_key):
        get_review_calls["count"] += 1
        if get_review_calls["count"] == 1:
            return existing.copy()
        return stored_after_enqueue.copy()

    monkeypatch.setattr(
        "app.services.event_review_service.StockkbProxyService.get_market_event_review",
        fake_get_review,
    )
    monkeypatch.setattr(
        "app.services.event_review_service.StockkbProxyService.run_market_event_review",
        lambda event_key: pending.copy(),
    )
    monkeypatch.setattr(
        "app.services.event_review_service.StockkbProxyService.get_market_event_detail",
        lambda event_key: {"found": True, "event": event},
    )
    monkeypatch.setattr(
        "app.services.event_review_service.StockkbProxyService.put_market_event_review",
        lambda event_key, payload: stored_after_enqueue.copy(),
    )
    monkeypatch.setattr(
        EventReviewService,
        "_acquire_session_id",
        classmethod(lambda cls, event_key, existing_review: "session_456"),
    )
    monkeypatch.setattr(
        EventReviewService,
        "_enqueue_review_job",
        classmethod(lambda cls, **kwargs: False),
    )

    result = EventReviewService.run_review("evt_3", force=False)

    assert result["source"] == "running"
    assert result["session_id"] == "session_456"
    assert result["review"]["review_status"] == "pending"


def test_normalize_review_payload_backfills_key_items_from_supporting():
    payload = {
        "status": "ok",
        "review": {
            "event_truth": "true",
            "time_truth": "time_aligned",
            "content_truth": "accurate",
            "disposition": "adopt",
            "confidence": 0.81,
            "headline": "headline",
            "summary": "summary",
        },
        "evidence": {
            "supporting": [
                {
                    "title": "evidence-1",
                    "url": "https://example.com/1",
                    "publisher": "Example",
                    "published_at": "2026-06-22T00:00:00",
                    "source_type": "mainstream",
                    "match_level": "strong",
                    "note": "supports claim",
                }
            ],
            "missing": ["missing-point"],
        },
        "next_action": ["follow-up"],
    }

    normalized = EventReviewService._normalize_review_payload(payload)

    assert normalized["evidence"]["supporting"] == payload["evidence"]["supporting"]
    assert normalized["evidence"]["key_items"] == payload["evidence"]["supporting"]
    assert normalized["evidence"]["missing"] == ["missing-point"]
