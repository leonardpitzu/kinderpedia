"""Tests for Kinderpedia newsfeed parsing and sensor."""

from unittest.mock import MagicMock

from custom_components.kinderpedia.coordinator import _parse_newsfeed
from custom_components.kinderpedia.sensor import KinderpediaNewsfeedSensor
from tests.conftest import MOCK_CHILD, MOCK_NEWSFEED_RAW


class TestParseNewsfeed:
    """Tests for the _parse_newsfeed function."""

    def test_parse_gallery_item(self):
        """Gallery items are parsed with image info."""
        items = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        gallery = items[0]

        assert gallery["id"] == 37973
        assert gallery["type"] == "gallery"
        assert gallery["title"] == "Holiday fun: recap, play and lots of energy!"
        assert gallery["author"] == "Alina Vieriu"
        assert gallery["likes"] == 8
        assert gallery["comments"] == 1
        assert gallery["image_count"] == 53
        assert gallery["first_image_url"] == "https://images.kinderpedia.co/photo1.jpg"
        assert gallery["group"] == "Arici"
        assert gallery["description"] == "A wonderful week of activities."

    def test_parse_gallery_latest_comment(self):
        """Latest comment is extracted."""
        items = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        comment = items[0]["latest_comment"]

        assert comment is not None
        assert comment["author"] == "Jane Doe"
        assert comment["text"] == "Great photos!"

    def test_parse_invoice_item(self):
        """Invoice items are parsed with file URL and subtitles."""
        items = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        invoice = items[1]

        assert invoice["id"] == 37736
        assert invoice["type"] == "invoice"
        assert invoice["title"] == "Invoice number: #GH018654"
        assert invoice["author"] == "Carmen Boier"
        assert invoice["file_url"] == "https://app.kinderpedia.co/invoice.pdf"
        assert invoice["invoice_subtitle1"] == "Due Date: 28 February 2026"
        assert invoice["invoice_subtitle2"] == "Total amount: 380 EUR"
        assert invoice["latest_comment"] is None
        assert invoice["image_count"] == 0

    def test_parse_count(self):
        """Feed count matches input."""
        items = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        assert len(items) == 2

    def test_parse_empty_json(self):
        items = _parse_newsfeed({})
        assert items == []

    def test_parse_none_input(self):
        items = _parse_newsfeed(None)
        assert items == []

    def test_parse_missing_result(self):
        items = _parse_newsfeed({"code": ""})
        assert items == []

    def test_parse_empty_feed(self):
        items = _parse_newsfeed({"result": {"feed": []}})
        assert items == []

    def test_parse_no_gallery_no_video(self):
        """Items without gallery or video still parse cleanly."""
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
                            "description": "Hello everyone",
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
        assert items[0]["image_count"] == 0
        assert items[0]["first_image_url"] is None
        assert items[0]["video_url"] is None
        assert items[0]["file_url"] is None
        assert items[0]["group"] is None


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

    def test_native_value_returns_latest_title(self):
        feed = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        coordinator = self._make_coordinator(feed)
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")

        assert sensor.native_value == "Holiday fun: recap, play and lots of energy!"

    def test_native_value_none_when_empty(self):
        coordinator = self._make_coordinator([])
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")

        assert sensor.native_value is None

    def test_attributes_contain_latest_fields(self):
        feed = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        coordinator = self._make_coordinator(feed)
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")
        attrs = sensor.extra_state_attributes

        assert attrs["item_count"] == 2
        assert attrs["latest_id"] == 37973
        assert attrs["latest_type"] == "gallery"
        assert attrs["latest_author"] == "Alina Vieriu"
        assert attrs["latest_likes"] == 8
        assert attrs["latest_comments"] == 1
        assert attrs["latest_image_count"] == 53
        assert attrs["latest_image_url"] == "https://images.kinderpedia.co/photo1.jpg"
        assert attrs["latest_group"] == "Arici"
        assert attrs["latest_comment_author"] == "Jane Doe"
        assert attrs["latest_comment_text"] == "Great photos!"

    def test_attributes_recent_items(self):
        feed = _parse_newsfeed(MOCK_NEWSFEED_RAW)
        coordinator = self._make_coordinator(feed)
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")
        attrs = sensor.extra_state_attributes

        recent = attrs["recent_items"]
        assert len(recent) == 2
        assert recent[0]["id"] == 37973
        assert recent[1]["id"] == 37736

    def test_attributes_empty_feed(self):
        coordinator = self._make_coordinator([])
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")
        attrs = sensor.extra_state_attributes

        assert attrs["item_count"] == 0
        assert "latest_id" not in attrs

    def test_no_coordinator_data(self):
        coordinator = MagicMock()
        coordinator.data = None
        sensor = KinderpediaNewsfeedSensor(coordinator, 111, 222, "Alice Smith", "Alice")

        assert sensor.native_value is None
        assert sensor.extra_state_attributes["item_count"] == 0
