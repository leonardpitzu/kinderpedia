"""Tests for the Kinderpedia coordinator and timeline parser."""

from custom_components.kinderpedia.coordinator import _parse_timeline


class TestParseTimeline:
    """Tests for the _parse_timeline helper."""

    def test_full_timeline(self):
        """Test parsing a complete timeline with all data types."""
        raw = {
            "result": {
                "dailytimeline": {
                    "days": {
                        "2026-02-09": {
                            "data": [
                                {"id": "checkin", "subtitle": "08:15 - 16:30"},
                                {"id": "nap", "subtitle": "1 h and 30 min"},
                                {
                                    "id": "food_1",
                                    "details": {
                                        "food": {
                                            "meals": [
                                                {
                                                    "type": "md",
                                                    "percent": 80,
                                                    "menus": [{"name": "Cereal"}],
                                                    "totals": {"kcal": 200, "weight": 150},
                                                }
                                            ]
                                        }
                                    },
                                },
                            ]
                        },
                        "2026-02-10": {"data": []},
                        "2026-02-11": {"data": []},
                        "2026-02-12": {"data": []},
                        "2026-02-13": {"data": []},
                    }
                }
            }
        }

        result = _parse_timeline(raw)

        assert "monday" in result
        monday = result["monday"]
        assert monday["date"] == "2026-02-09"
        assert monday["checkin"] == "08:15 - 16:30"
        assert monday["nap"] == "1 h and 30 min"
        assert monday["nap_duration"] == 90
        assert monday["breakfast_items"] == ["Cereal"]
        assert monday["breakfast_kcal"] == 200
        assert monday["breakfast_weight"] == 150
        assert monday["breakfast_percent"] == 80

    def test_empty_days(self):
        """Test that empty day data returns defaults."""
        raw = {
            "result": {
                "dailytimeline": {
                    "days": {
                        "2026-02-09": {"data": []},
                        "2026-02-10": {"data": []},
                        "2026-02-11": {"data": []},
                        "2026-02-12": {"data": []},
                        "2026-02-13": {"data": []},
                    }
                }
            }
        }
        result = _parse_timeline(raw)

        assert result["monday"]["checkin"] == "unknown"
        assert result["monday"]["nap"] == "unknown"

    def test_nap_hours_and_minutes(self):
        """Test nap duration parsing with hours and minutes."""
        raw = {
            "result": {
                "dailytimeline": {
                    "days": {
                        "2026-02-09": {
                            "data": [{"id": "nap", "subtitle": "2 h and 15 min"}]
                        },
                        "2026-02-10": {"data": []},
                        "2026-02-11": {"data": []},
                        "2026-02-12": {"data": []},
                        "2026-02-13": {"data": []},
                    }
                }
            }
        }
        result = _parse_timeline(raw)
        assert result["monday"]["nap_duration"] == 135

    def test_nap_minutes_only(self):
        """Test nap duration parsing with only minutes."""
        raw = {
            "result": {
                "dailytimeline": {
                    "days": {
                        "2026-02-09": {
                            "data": [{"id": "nap", "subtitle": "45 min"}]
                        },
                        "2026-02-10": {"data": []},
                        "2026-02-11": {"data": []},
                        "2026-02-12": {"data": []},
                        "2026-02-13": {"data": []},
                    }
                }
            }
        }
        result = _parse_timeline(raw)
        assert result["monday"]["nap_duration"] == 45

    def test_lunch_percent_averages_mp_and_mp2(self):
        """Test that mp and mp2 percentages are averaged for lunch."""
        raw = {
            "result": {
                "dailytimeline": {
                    "days": {
                        "2026-02-09": {
                            "data": [
                                {
                                    "id": "food_1",
                                    "details": {
                                        "food": {
                                            "meals": [
                                                {
                                                    "type": "mp",
                                                    "percent": 80,
                                                    "menus": [{"name": "Soup"}],
                                                    "totals": {"kcal": 300, "weight": 200},
                                                },
                                                {
                                                    "type": "mp2",
                                                    "percent": 60,
                                                    "menus": [{"name": "Pasta"}],
                                                    "totals": {"kcal": 350, "weight": 250},
                                                },
                                            ]
                                        }
                                    },
                                }
                            ]
                        },
                        "2026-02-10": {"data": []},
                        "2026-02-11": {"data": []},
                        "2026-02-12": {"data": []},
                        "2026-02-13": {"data": []},
                    }
                }
            }
        }
        result = _parse_timeline(raw)
        assert result["monday"]["lunch_percent"] == 70.0

    def test_empty_json(self):
        """Test parsing with empty JSON returns 5 default weekdays."""
        result = _parse_timeline({})
        assert len(result) == 5
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
            assert result[day]["checkin"] == "unknown"
            assert result[day]["date"] == "unknown"

    def test_none_input(self):
        """Test parsing with None-like input returns 5 default weekdays."""
        result = _parse_timeline(None)
        assert len(result) == 5
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
            assert result[day]["checkin"] == "unknown"

    def test_missing_result_key(self):
        """Test parsing when result key is missing returns 5 default weekdays."""
        result = _parse_timeline({"other_key": {}})
        assert len(result) == 5
        assert result["monday"]["date"] == "unknown"

    def test_fewer_than_five_days(self):
        """Test timeline with fewer than 5 days fills remaining with defaults."""
        raw = {
            "result": {
                "dailytimeline": {
                    "days": {
                        "2026-02-09": {"data": []},
                        "2026-02-10": {"data": []},
                    }
                }
            }
        }
        result = _parse_timeline(raw)
        assert len(result) == 5
        assert result["monday"]["date"] == "2026-02-09"
        assert result["wednesday"]["date"] == "unknown"
        assert result["wednesday"]["breakfast_percent"] == 0

    def test_null_data_field(self):
        """Test when day data field is None."""
        raw = {
            "result": {
                "dailytimeline": {
                    "days": {
                        "2026-02-09": None,
                        "2026-02-10": {"data": []},
                        "2026-02-11": {"data": []},
                        "2026-02-12": {"data": []},
                        "2026-02-13": {"data": []},
                    }
                }
            }
        }
        result = _parse_timeline(raw)
        assert result["monday"]["checkin"] == "unknown"

    def test_nap_unparseable_format(self):
        """Test nap with an unrecognised format gets duration 0."""
        raw = {
            "result": {
                "dailytimeline": {
                    "days": {
                        "2026-02-09": {
                            "data": [{"id": "nap", "subtitle": "a long while"}]
                        },
                        "2026-02-10": {"data": []},
                        "2026-02-11": {"data": []},
                        "2026-02-12": {"data": []},
                        "2026-02-13": {"data": []},
                    }
                }
            }
        }
        result = _parse_timeline(raw)
        assert result["monday"]["nap_duration"] == 0
