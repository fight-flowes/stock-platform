from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from stockrag.api import create_app


class MarketEventReviewApiTests(unittest.TestCase):
    def test_put_market_event_review_uses_partial_update_payload(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch("stockrag.api.ExtractionService") as service_cls:
            instance = service_cls.return_value
            instance.kb_upsert_market_event_review.return_value = {
                "found": True,
                "event_key": "evt-1",
                "review": {"review_status": "completed"},
            }

            response = client.put(
                "/kb/simple/market-events/evt-1/review",
                json={"review_status": "completed", "vibe_session_id": ""},
            )

        self.assertEqual(response.status_code, 200)
        instance.kb_upsert_market_event_review.assert_called_once_with(
            "evt-1",
            {
                "review_status": "completed",
                "vibe_session_id": "",
            },
        )


if __name__ == "__main__":
    unittest.main()
