"""Unit checks for :mod:`media_caption_reconciler`.

Purpose
-------
Document the contract of the OpenAI-driven reconciler so future agents can run
confidence checks without touching external services. We focus on the helper
functions and tool wrappers that remain deterministic.

Style
-----
Inline comments include concrete before/after snippets, matching the user's
preferred documentation style.
"""

import json
import sys
from pathlib import Path
import unittest

# Place the testscripts directory on sys.path so imports stay local.
sys.path.append(str(Path(__file__).resolve().parent))

import media_caption_reconciler as mcr


class FakeStore:
    """Minimal in-memory stand-in for :class:`MongoMediaStore`."""

    def __init__(self, pending=None) -> None:
        self.pending = pending or []
        self.saved = []

    def list_pending_media(self, limit: int = 5):
        # Example before: agent needs structured items.
        # Example after: return the first ``limit`` entries verbatim.
        return self.pending[:limit]

    def save_caption(self, session_id: str, message_index: int, caption: str, source: str) -> None:
        # Example before: caption only exists in assistant reply.
        # Example after: caption lands in ``self.saved`` for assertions.
        self.saved.append(
            {
                "session_id": session_id,
                "message_index": message_index,
                "caption": caption,
                "source": source,
            }
        )


class MediaCaptionReconcilerTests(unittest.TestCase):
    """Test the helper using tiny, declarative fixtures."""

    def tearDown(self) -> None:
        # Reset global store to avoid bleeding state between tests.
        mcr.STORE = None

    def test_extract_media_url_strips_wrapper(self) -> None:
        """Ensure we peel off the ``[photo_url: ...]`` shell cleanly."""

        sample = "[photo_url: https://storage.googleapis.com/bucket/file.jpg]"
        # Example before: wrapped string with metadata markers.
        # Example after: plain URL ready for downstream captioning.
        self.assertEqual(
            mcr.extract_media_url(sample),
            "https://storage.googleapis.com/bucket/file.jpg",
        )

    def test_known_prefixes_cover_photo_stub(self) -> None:
        """Sanity check the recognised prefix list stays wired to photo uploads."""

        # Example before: missing "[photo_url:" would leave images unmatched.
        # Example after: prefix is present so media gets reconciled.
        self.assertIn("[photo_url:", mcr.MEDIA_PREFIXES)

    def test_iter_media_candidates_yields_user_followup(self) -> None:
        """The very next user turn becomes the human-authored description."""

        session = {
            "_id": "demo",
            "messages": [
                {"role": "user", "content": "[photo_url: https://example.com/pic.jpg]"},
                {"role": "assistant", "content": "Photo received."},
                {"role": "user", "content": "It shows onions after 40 minutes."},
            ],
        }

        candidates = list(mcr.iter_media_candidates(session))
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        # Example before: follow-up text hidden in later turn.
        # Example after: object exposes it as ``user_description``.
        self.assertEqual(candidate.user_description, "It shows onions after 40 minutes.")

    def test_list_pending_media_tool_uses_store(self) -> None:
        """Tool wrapper should delegate to the configured store."""

        fake = FakeStore(
            pending=[
                {
                    "session_id": "abc",
                    "message_index": 0,
                    "media_url": "https://example.com/a.jpg",
                    "user_description": "Handwritten note",
                    "needs_caption": False,
                }
            ]
        )
        mcr.STORE = fake

        payload = mcr.list_pending_media(limit=1)
        # Example before: empty response, agent cannot proceed.
        # Example after: ``items`` mirrors fake store output.
        self.assertEqual(payload["items"], fake.pending)

    def test_save_media_caption_records_entries(self) -> None:
        """Tool wrapper should persist captions via the injected store."""

        fake = FakeStore()
        mcr.STORE = fake

        result = mcr.save_media_caption(
            session_id="abc",
            message_index=2,
            caption="Caption from test",
            source="unit-test",
        )
        # Example before: nothing recorded.
        # Example after: fake store captured the caption.
        self.assertEqual(fake.saved[0]["caption"], "Caption from test")
        self.assertEqual(result["status"], "saved")

    def test_tool_result_serialises_to_json(self) -> None:
        """Ensure tool payloads can be sent back to OpenAI."""

        fake = FakeStore(
            pending=[
                {
                    "session_id": "abc",
                    "message_index": 1,
                    "media_url": "https://example.com/b.jpg",
                    "user_description": None,
                    "needs_caption": True,
                }
            ]
        )
        mcr.STORE = fake

        payload = mcr.list_pending_media(limit=1)
        # Example before: objects not JSON serialisable.
        # Example after: dumps succeeds.
        json.dumps(payload)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
