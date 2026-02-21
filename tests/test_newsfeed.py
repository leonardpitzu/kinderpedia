"""Tests for Kinderpedia newsfeed parsing and sensor."""

from unittest.mock import MagicMock

from custom_components.kinderpedia.coordinator import _parse_newsfeed
from custom_components.kinderpedia.sensor import KinderpediaNewsfeedSensor
from tests.conftest import MOCK_CHILD, MOCK_NEWSFEED_RAW


class TestParseNewsfeed:
    """Tests for the _parse_newsfeed function."""

    def test_parse_gallery_summary(self):
        """Gallery items get a human-readable summary."""
        items = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        gallery = items[0]

        assert gallery["id"] == 37973
        assert gallery["type"] == "gallery"
        assert "New photos from Alina Vieriu (53)" in gallery["summary"]
        assert "Holiday fun" in gallery["summary"]
        assert gallery["author"] == "Alina Vieriu"
        assert gallery["likes"] == 8
        assert gallery["comments"] == 1
        assert gallery["group"] == "Arici"

    def test_parse_gallery_latest_comment(self):
        """Latest comment is a flat string."""
        items = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        comment = items[0]["latest_comment"]

        assert comment is not None
        assert "Jane Doe" in comment
        assert "Great photos!" in comment

    def test_parse_invoice_summary(self):
        """Invoice items produce a useful payment summary."""
        items = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        invoice = items[1]

        assert invoice["id"] == 37736
        assert invoice["type"] == "invoice"
        assert "GH018654" in invoice["summary"]
        assert "Due Date" in invoice["summary"]
        assert "380 EUR" in invoice["summary"]
        assert invoice["author"] == "Carmen Boier"
        assert invoice["latest_comment"] is None

    def test_parse_text_post_summary(self):
        """Text/wall posts get author + description summary."""
        data = {
            "result": {
                "feed": [
                    {
                        "id": 1,
                        "type": "text",
                        "user": {"first_name": "John", "last_name": "Doe"},
                        "title": "John Doe",
                        "date": "2026-02-01T10:00:00+0200",
                        "date_friendly": "1 February 2026 at 10:00",
                        "stats": {"likes": 2, "comments": 0},
                        "latest_comments": None,
                        "content": {
                            "type": "wall_post",
                            "description": "Hello everyone, welcome!",
                            "title": "",
                            "gallery": None,
                            "video": None,
                            "file": None,
                        },
                        "groups": [],
                        "children": None,
                    }
                ]
            }
        }
        items = _parse_newsfeed(data)
        assert len(items) == 1
        assert "John Doe" in items[0]["summary"]
        assert "Hello everyone" in items[0]["summary"]
        assert items[0]["group"] is None

    def test_parse_count(self):
        items = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        assert len(items) == 2

    def test_parse_empty_json(self):
        assert _parse_newsfeed({}) == []

    def test_parse_none_input(self):
        assert _parse_newsfeed(None) == []

    def test_parse_missing_result(self):
        assert _parse_newsfeed({"code": ""}) == []

    def test_parse_empty_feed(self):
        assert _parse_newsfeed({"result": {"feed": []}}) == []

    def test_no_image_or_video_fields(self):
        """Parsed items must not contain image/video URL fields."""
        items = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        for item in items:
            assert "image_count" not in item
            assert "first_image_url" not in item
            assert "video_url" not in item
            assert "file_url" not in item


class TestNewsfeedSensor:
    """Tests for KinderpediaNewsfeedSensor."""

    def _make_coordinator(self, feed_items):
        coordinator = MagicMock()
        coordinator.data = {
            "last_updated": "2026-02-21 12:00:00",
            "children": {
                "111_222": {
                    "child": dict(MOCK_CHILD),
                    "days": {},
                    "newsfeed": feed_items,
                }
            },
        }
        return coordinator

    def test_native_value_is_summary(self):
        feed = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        coordinator = self._make_coordinator(feed)
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")

        assert "New photos from Alina Vieriu" in sensor.native_value

    def test_native_value_none_when_empty(self):
        coordinator = self._make_coordinator([])
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")
        assert sensor.native_value is None

    def test_attributes_text_only(self):
        """Attributes must not contain image/video URLs."""
        feed = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        coordinator = self._make_coordinator(feed)
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")
        attrs = sensor.extra_state_attributes

        assert attrs["item_count"] == 2
        assert attrs["latest_type"] == "gallery"
        assert attrs["latest_author"] == "Alina Vieriu"
        assert attrs["latest_likes"] == 8
        assert attrs["latest_group"] == "Arici"
        assert "Jane Doe" in attrs["latest_comment"]

        # No image/video junk
        assert "latest_image_url" not in attrs
        assert "latest_image_count" not in attrs
        assert "latest_video_url" not in attrs

    def test_recent_items_are_summaries(self):
        feed = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        coordinator = self._make_coordinator(feed)
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")
        recent = sensor.extra_state_attributes["recent"]

        assert len(recent) == 2
        assert "summary" in recent[0]
        assert "date" in recent[0]
        assert "type" in recent[0]
        # No IDs, no URLs
        assert "id" not in recent[0]

    def test_attributes_empty_feed(self):
        coordinator = self._make_coordinator([])
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")
        attrs = sensor.extra_state_attributes

        assert attrs["item_count"] == 0
        assert "latest_type" not in attrs

    def test_no_coordinator_data(self):
        coordinator = MagicMock()
        coordinator.data = None
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")

        assert sensor.native_value is None
        assert sensor.extra_state_attributes["item_count"] == 0
