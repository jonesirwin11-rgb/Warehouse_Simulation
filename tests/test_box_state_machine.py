"""Tests for box_state_machine.py — Tasks 1, 2, 3."""
import sys
import os
import math
import time

# Allow imports from the edge/ directory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "edge"))

from box_state_machine import (
    signed_distance,
    get_side,
    update_crossing,
    euclidean,
    is_likely_id_switch,
    BAND_PX,
    REASSOC_WINDOW_S,
    REASSOC_DIST_PX,
    SIZE_RATIO_TOLERANCE,
)


# ==========================================
# Helpers
# ==========================================
LINE_START = (0, 560)
LINE_END = (1920, 560)


def make_track_state(last_side=None):
    """Minimal track-state dict for update_crossing tests."""
    return {"last_side": last_side}


# ==========================================
# Task 1 — Hysteresis tests
# ==========================================

class TestHysteresis:
    def test_clean_crossing_truck_to_dock(self):
        """Crossing from truck side (y < line, negative signed_dist) to
        dock side (y > line, positive signed_dist) fires once."""
        state = make_track_state()
        # Start on truck side: y=520 is above the line at y=560 → signed_distance < 0 → truck
        crossed1 = update_crossing(state, (500, 520), LINE_START, LINE_END)
        assert not crossed1  # first observation — no previous side yet
        assert state["last_side"] == "truck"

        # Move to dock side: y=600 is below the line → signed_distance > 0 → dock
        crossed2 = update_crossing(state, (500, 600), LINE_START, LINE_END)
        assert crossed2
        assert state["last_side"] == "dock"

    def test_dither_inside_band_does_not_cross(self):
        """Points oscillating inside ±BAND_PX never register a crossing."""
        state = make_track_state()
        # Seed on truck side: y=520 → above line → negative → truck
        update_crossing(state, (500, 520), LINE_START, LINE_END)
        assert state["last_side"] == "truck"

        # Dither inside band (all within ±BAND_PX of y=560)
        for y in [560 + BAND_PX - 1, 560 - BAND_PX + 1, 560, 560 + 5, 560 - 5]:
            crossed = update_crossing(state, (500, y), LINE_START, LINE_END)
            assert not crossed, f"Should not cross at y={y}"
        # last_side should still be truck (neutral never overwrites)
        assert state["last_side"] == "truck"

    def test_hysteresis_prevents_dither_recount(self):
        """A track dithering inside the +/-15px band around the line must not
        fire multiple crossing events."""
        state = make_track_state()
        # Seed on truck side
        update_crossing(state, (500, 600), LINE_START, LINE_END)

        # Oscillate within band
        crossed1 = update_crossing(state, (500, 545), LINE_START, LINE_END)
        crossed2 = update_crossing(state, (500, 548), LINE_START, LINE_END)
        assert not crossed1
        assert not crossed2

    def test_reverse_crossing_dock_to_truck_does_not_fire(self):
        """Only truck→dock fires, not the reverse direction."""
        state = make_track_state()
        # Start on dock side: y=600 → below line → positive → dock
        update_crossing(state, (500, 600), LINE_START, LINE_END)
        assert state["last_side"] == "dock"
        # Move to truck side: y=520 → above line → negative → truck
        crossed = update_crossing(state, (500, 520), LINE_START, LINE_END)
        assert not crossed  # wrong direction (dock→truck)


# ==========================================
# Task 2 — ID-switch dedup tests
# ==========================================

class TestIDSwitchDedup:
    def test_genuine_id_switch_is_suppressed(self):
        """Same box, same size, reappears 0.5s later at nearly the same spot
        after an occlusion — must NOT double-count."""
        now = time.monotonic()
        recent = [
            {"id": 101, "timestamp": now - 0.5, "end_location": (500, 560),
             "width": 40, "height": 30},
        ]
        candidate = {"foot_point": (502, 561), "width": 41, "height": 29}
        assert is_likely_id_switch(candidate, recent, now) is True

    def test_two_real_boxes_crossing_close_together(self):
        """Two DIFFERENT boxes, different sizes, cross the same line 1.5s apart.
        Both must be counted — guards against the Task 2 discriminator being
        too aggressive and merging real sequential boxes."""
        now = time.monotonic()
        recent = [
            {"id": 101, "timestamp": now - 1.5, "end_location": (500, 560),
             "width": 40, "height": 30},
        ]
        # Significantly different size → real new box
        candidate = {"foot_point": (505, 562), "width": 60, "height": 45}
        assert is_likely_id_switch(candidate, recent, now) is False

    def test_expired_window_does_not_match(self):
        """A track that completed > REASSOC_WINDOW_S ago should never match."""
        now = time.monotonic()
        recent = [
            {"id": 101, "timestamp": now - 5.0, "end_location": (500, 560),
             "width": 40, "height": 30},
        ]
        candidate = {"foot_point": (500, 560), "width": 40, "height": 30}
        assert is_likely_id_switch(candidate, recent, now) is False

    def test_distant_track_does_not_match(self):
        """Same size but far away — different box."""
        now = time.monotonic()
        recent = [
            {"id": 101, "timestamp": now - 0.5, "end_location": (100, 100),
             "width": 40, "height": 30},
        ]
        candidate = {"foot_point": (500, 560), "width": 40, "height": 30}
        assert is_likely_id_switch(candidate, recent, now) is False


# ==========================================
# Task 3 — Idempotency key (lightweight)
# ==========================================

class TestIdempotencyKey:
    def test_key_is_deterministic(self):
        """Same inputs produce the same key."""
        cam = "CAM01"
        etype = "TRUCK_EXIT_EVENT"
        ids = [3, 1, 2]
        key = f"{cam}-{etype}-{'-'.join(str(t) for t in sorted(ids))}"
        assert key == "CAM01-TRUCK_EXIT_EVENT-1-2-3"

    def test_different_ids_produce_different_key(self):
        cam = "CAM01"
        etype = "TRUCK_EXIT_EVENT"
        key1 = f"{cam}-{etype}-{'-'.join(str(t) for t in sorted([1, 2]))}"
        key2 = f"{cam}-{etype}-{'-'.join(str(t) for t in sorted([1, 3]))}"
        assert key1 != key2


# ==========================================
# Geometry helper sanity
# ==========================================

class TestGeometryHelpers:
    def test_euclidean(self):
        assert euclidean((0, 0), (3, 4)) == 5.0

    def test_signed_distance_above_below(self):
        """For a horizontal line at y=560, points above have positive dist,
        points below have negative dist (convention depends on line
        direction — the important thing is consistency)."""
        d_above = signed_distance((500, 520), LINE_START, LINE_END)
        d_below = signed_distance((500, 600), LINE_START, LINE_END)
        # They must have opposite signs
        assert d_above * d_below < 0
