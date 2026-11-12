"""Tests for backend/app.py — Task 5 (SQLite persistence) and Task 6 (advisory audit)."""
import sys
import os
import json
import pytest

# Allow imports from the backend/ directory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app import init_db, save_state, load_state, log_event, compute_trolley_analysis, app as flask_app
from audit import needs_review


# ==========================================
# Task 5 — SQLite persistence tests
# ==========================================

class TestSQLitePersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        """Basic save → load preserves all fields."""
        db_path = str(tmp_path / "test_inventory.db")
        conn = init_db(db_path)
        state = {"staged_boxes": 7, "truck_exit_events": 3,
                 "staging_arrival_events": 4, "last_event": "EVT-001", "last_audit": None}
        save_state(conn, state)
        restored = load_state(conn)
        assert restored["staged_boxes"] == 7
        assert restored["truck_exit_events"] == 3
        conn.close()

    def test_inventory_persists_across_restart(self, tmp_path):
        """Send a mock event, kill the 'server' (drop the in-memory state),
        reload from DB, confirm staged_boxes survived."""
        db_path = str(tmp_path / "test_inventory.db")
        conn = init_db(db_path)
        save_state(conn, {"staged_boxes": 7})
        conn.close()

        conn2 = init_db(db_path)  # simulates restart
        restored = load_state(conn2)
        assert restored["staged_boxes"] == 7
        conn2.close()

    def test_load_from_empty_db_returns_empty(self, tmp_path):
        """First startup: no persisted state → empty dict."""
        db_path = str(tmp_path / "empty.db")
        conn = init_db(db_path)
        assert load_state(conn) == {}
        conn.close()

    def test_upsert_overwrites_previous_state(self, tmp_path):
        """Multiple saves: last write wins."""
        db_path = str(tmp_path / "test_upsert.db")
        conn = init_db(db_path)
        save_state(conn, {"staged_boxes": 5})
        save_state(conn, {"staged_boxes": 12})
        restored = load_state(conn)
        assert restored["staged_boxes"] == 12
        conn.close()


# ==========================================
# Task 6 — Advisory audit / needs_review tests
# ==========================================

class TestNeedsReview:
    def test_within_absolute_threshold(self):
        """Small counts — absolute threshold applies (2)."""
        assert needs_review(10, 11) is False

    def test_exceeds_absolute_threshold(self):
        assert needs_review(10, 13) is True

    def test_percentage_threshold_dominates_for_large_counts(self):
        """At 100 tracked, 10% = 10, so difference of 8 should pass."""
        assert needs_review(100, 108) is False

    def test_percentage_threshold_exceeded(self):
        """At 100 tracked, difference of 12 > 10% → needs review."""
        assert needs_review(100, 112) is True

    def test_zero_tracked_uses_absolute(self):
        """Edge case: 0 tracked, 3 audit → exceeds abs threshold of 2."""
        assert needs_review(0, 3) is True


class TestTrolleyAnalysis:
    def test_empty_event_log_returns_zeroes(self, tmp_path):
        conn = init_db(str(tmp_path / "empty_analysis.db"))
        result = compute_trolley_analysis(conn)
        assert result["trolley_1"] == {"dock_boxes": 0, "side_boxes": 0, "boxes": 0, "time_sec": 0.0}
        assert result["trolley_2"] == {"dock_boxes": 0, "side_boxes": 0, "boxes": 0, "time_sec": 0.0}
        assert result["total"] == {"boxes": 0, "time_sec": 0.0, "tat_formatted": "0m 0s"}
        conn.close()

    def test_trolley_counting_and_tat_aggregation(self, tmp_path):
        conn = init_db(str(tmp_path / "trolley_analysis.db"))
        log_event(conn, {
            "event_id": "e1", "camera_id": "T1_CAM01", "event_type": "TRUCK_EXIT_EVENT",
            "quantity": 10, "tracker_ids": list(range(10)), "video_t_sec": [1.8, 7.87], "confidence": 0.8
        })
        log_event(conn, {
            "event_id": "e2", "camera_id": "T1_CAM02", "event_type": "STAGING_ARRIVAL_EVENT",
            "quantity": 30, "tracker_ids": list(range(30)), "video_t_sec": [16.43], "confidence": 0.5
        })
        log_event(conn, {
            "event_id": "e3", "camera_id": "T2_CAM01", "event_type": "TRUCK_EXIT_EVENT",
            "quantity": 6, "tracker_ids": list(range(6)), "video_t_sec": [12.1], "confidence": 0.8
        })
        log_event(conn, {
            "event_id": "e4", "camera_id": "T2_CAM02", "event_type": "STAGING_ARRIVAL_EVENT",
            "quantity": 5, "tracker_ids": list(range(5)), "video_t_sec": [14.6], "confidence": 0.6
        })
        result = compute_trolley_analysis(conn)
        assert result["trolley_1"]["dock_boxes"] == 10
        assert result["trolley_1"]["side_boxes"] == 30
        assert result["trolley_1"]["boxes"] == 30
        assert result["trolley_1"]["time_sec"] == 16.4
        assert result["trolley_2"]["dock_boxes"] == 6
        assert result["trolley_2"]["side_boxes"] == 5
        assert result["trolley_2"]["boxes"] == 18
        assert result["trolley_2"]["time_sec"] == 14.6
        assert result["total"]["boxes"] == 48
        assert result["total"]["time_sec"] == 31.0
        assert result["total"]["tat_formatted"] == "0m 31s"
        conn.close()

    def test_trolley_side_view_fallback_when_no_dock_events(self, tmp_path):
        conn = init_db(str(tmp_path / "trolley_side_only.db"))
        log_event(conn, {
            "event_id": "e1", "camera_id": "T1_CAM02", "event_type": "STAGING_ARRIVAL_EVENT",
            "quantity": 30, "tracker_ids": list(range(30)), "video_t_sec": [12.0], "confidence": 0.7
        })
        result = compute_trolley_analysis(conn)
        assert result["trolley_1"]["boxes"] == 30
        assert result["trolley_2"]["boxes"] == 0
        assert result["total"]["boxes"] == 30
        conn.close()

    def test_results_route_and_api_analysis(self):
        client = flask_app.test_client()
        assert client.get("/").status_code == 200
        assert client.get("/results").status_code == 200
        resp = client.get("/api/analysis")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert "trolley_1" in payload and "trolley_2" in payload and "total" in payload
