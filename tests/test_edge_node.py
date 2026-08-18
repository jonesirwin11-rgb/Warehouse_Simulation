"""Tests for edge_node.py — Task 4 (dynamic class resolution)."""
import sys
import os
import pytest

# Allow imports from the edge/ directory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "edge"))

from edge_node import resolve_box_class_id


class TestResolveBoxClassId:
    def test_model_with_box_class_resolves_correctly(self):
        """Standard case: 'box' is present but not at index 0."""
        assert resolve_box_class_id({0: "person", 1: "box"}) == 1

    def test_model_with_box_at_zero(self):
        """Our actual model — box is at index 0."""
        assert resolve_box_class_id({0: "box"}) == 0

    def test_model_missing_box_class_fails_loudly(self):
        """If 'box' isn't in model.names, startup must refuse to run, not
        silently proceed with no class filter."""
        with pytest.raises(SystemExit):
            resolve_box_class_id(model_names={0: "person", 1: "car"})

    def test_model_with_many_classes(self):
        """Box buried among many classes — still found."""
        names = {0: "person", 1: "car", 2: "truck", 3: "box", 4: "pallet"}
        assert resolve_box_class_id(names) == 3
