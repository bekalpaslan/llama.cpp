"""
Validation tests for RunPod Hub configuration.

Ensures hub.json exists, parses correctly, and contains valid presets
with required fields for RunPod Hub discovery.
"""

import json
from pathlib import Path

import pytest

HUB_JSON_PATH = Path(__file__).parent.parent / ".runpod" / "hub.json"


@pytest.fixture
def hub_data():
    """Load and parse hub.json."""
    with open(HUB_JSON_PATH) as f:
        return json.load(f)


def test_hub_json_exists():
    """hub.json file exists at .runpod/hub.json."""
    assert HUB_JSON_PATH.exists(), f"hub.json not found at {HUB_JSON_PATH}"


def test_hub_json_valid():
    """hub.json parses as valid JSON dict."""
    with open(HUB_JSON_PATH) as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_hub_has_required_fields(hub_data):
    """Top-level hub.json has 'name', 'description', and 'presets' fields."""
    assert "name" in hub_data, "Missing 'name' field"
    assert "description" in hub_data, "Missing 'description' field"
    assert "presets" in hub_data, "Missing 'presets' field"


def test_hub_presets_structure(hub_data):
    """Each preset has 'name', 'description', 'env', 'gpu', and 'volume_size' fields."""
    for i, preset in enumerate(hub_data["presets"]):
        assert "name" in preset, f"Preset {i} missing 'name'"
        assert "description" in preset, f"Preset {i} missing 'description'"
        assert "env" in preset, f"Preset {i} missing 'env'"
        assert "gpu" in preset, f"Preset {i} missing 'gpu'"
        assert "volume_size" in preset, f"Preset {i} missing 'volume_size'"


def test_hub_presets_have_model_variant(hub_data):
    """Each preset's env dict has a 'MODEL_VARIANT' key."""
    for i, preset in enumerate(hub_data["presets"]):
        assert "MODEL_VARIANT" in preset["env"], (
            f"Preset {i} ({preset['name']}) missing MODEL_VARIANT in env"
        )


def test_hub_preset_count(hub_data):
    """At least 2 presets are defined."""
    assert len(hub_data["presets"]) >= 2, (
        f"Expected at least 2 presets, got {len(hub_data['presets'])}"
    )


def test_hub_turbo_preset(hub_data):
    """A preset with MODEL_VARIANT='turbo' exists."""
    turbo_presets = [
        p for p in hub_data["presets"]
        if p["env"].get("MODEL_VARIANT") == "turbo"
    ]
    assert len(turbo_presets) > 0, "No preset with MODEL_VARIANT='turbo' found"


def test_hub_multilingual_preset(hub_data):
    """A preset with MODEL_VARIANT='multilingual' exists."""
    multilingual_presets = [
        p for p in hub_data["presets"]
        if p["env"].get("MODEL_VARIANT") == "multilingual"
    ]
    assert len(multilingual_presets) > 0, "No preset with MODEL_VARIANT='multilingual' found"
