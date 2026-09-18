# Copyright (C) 2026 Paulo Felipe Jarschel
#
# Automated tests for Horiba H20 UVL / VUV Monochromator Clusters & Blueprint.

import json
import os
import sys
from pathlib import Path
import pytest

# Ensure src is in sys.path
src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from comfylab.engine.models import ClusterDefinitionModel, BlueprintModel
from comfylab.blocks.cluster import register_cluster_block
from comfylab.engine.registry import BLOCK_REGISTRY
from comfylab.blocks.loader import load_all_blocks
from comfylab.engine.executor import ExecutionEngine


def _get_horiba_clusters_dir() -> Path:
    store_c_dir = src_dir / "dist" / "comfylab-store" / "clusters" / "horiba" / "vuv_spectroscopy"
    if store_c_dir.exists():
        return store_c_dir
    return src_dir / "comfylab" / "clusters"


def _get_horiba_blueprint_path() -> Path:
    store_bp = src_dir / "dist" / "comfylab-store" / "blueprints" / "horiba" / "vuv_spectroscopy" / "Horiba_H20_UVL_Spectroscopy.json"
    if store_bp.exists():
        return store_bp
    return src_dir / "comfylab" / "examples" / "Horiba_H20_UVL_Spectroscopy.json"


def test_horiba_clusters_schema_validation():
    """Validates that all 4 Horiba VUV cluster JSON files conform to ClusterDefinitionModel schema."""
    clusters_dir = _get_horiba_clusters_dir()
    expected_clusters = [
        "vuv_setup_instruments.cluster.json",
        "vuv_measure_point.cluster.json",
        "vuv_accumulate_data.cluster.json",
        "vuv_export_dataset.cluster.json",
    ]

    for c_file in expected_clusters:
        file_path = clusters_dir / c_file
        assert file_path.exists(), f"Cluster file {c_file} does not exist at {file_path}"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cluster_def = ClusterDefinitionModel.model_validate(data)
        assert cluster_def.type_name.startswith("builtin/cluster/vuv_")
        assert len(cluster_def.internal_blueprint.blocks) > 0
        assert len(cluster_def.boundary_pins.data_ins) > 0 or len(cluster_def.boundary_pins.exec_ins) > 0
        print(f"  ✓ Validated cluster schema: {cluster_def.display_name} ({cluster_def.type_name})")


def test_horiba_clusters_registration():
    """Validates that all 4 clusters register properly in BLOCK_REGISTRY."""
    from comfylab.blocks.loader import load_blocks_from_directory
    load_all_blocks()
    store_dir = src_dir / "dist" / "comfylab-store" / "instruments"
    if store_dir.exists():
        load_blocks_from_directory(str(store_dir))

    clusters_dir = _get_horiba_clusters_dir()
    expected_types = [
        "builtin/cluster/vuv_setup_instruments",
        "builtin/cluster/vuv_measure_point",
        "builtin/cluster/vuv_accumulate_data",
        "builtin/cluster/vuv_export_dataset",
    ]

    for c_file in [
        "vuv_setup_instruments.cluster.json",
        "vuv_measure_point.cluster.json",
        "vuv_accumulate_data.cluster.json",
        "vuv_export_dataset.cluster.json",
    ]:
        with open(clusters_dir / c_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        cluster_def = ClusterDefinitionModel.model_validate(data)
        register_cluster_block(cluster_def)

    for btype in expected_types:
        assert btype in BLOCK_REGISTRY, f"Cluster block {btype} was not found in BLOCK_REGISTRY"
        cls = BLOCK_REGISTRY[btype]
        assert hasattr(cls, "inputs_def")
        assert hasattr(cls, "outputs_def")
        print(f"  ✓ Verified registered cluster block: {btype}")


def test_horiba_blueprint_schema():
    """Validates that Horiba_H20_UVL_Spectroscopy.json is a valid ComfyLAB canvas blueprint."""
    bp_path = _get_horiba_blueprint_path()
    assert bp_path.exists(), f"Blueprint file does not exist at {bp_path}"

    with open(bp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "blocks" in data and len(data["blocks"]) > 0
    assert "edges" in data and len(data["edges"]) > 0

    # Convert canvas nodes/edges to engine blueprint model format
    blueprint_blocks = []
    for b in data["blocks"]:
        props = dict(b["data"])
        btype = props.pop("action", "")
        blueprint_blocks.append({
            "id": b["id"],
            "type": btype,
            "properties": props
        })

    blueprint_links = []
    for e in data["edges"]:
        is_exec = e.get("style", {}).get("animated", False) or "Out" in e.get("sourceHandle", "") or "Done" in e.get("sourceHandle", "") or "LoopBody" in e.get("sourceHandle", "") or "Plot" in e.get("targetHandle", "") or "Write" in e.get("targetHandle", "")
        blueprint_links.append({
            "id": e["id"],
            "type": "exec" if is_exec else "data",
            "source_block": e["source"],
            "source_pin": e["sourceHandle"],
            "target_block": e["target"],
            "target_pin": e["targetHandle"]
        })

    engine_blueprint = {
        "blocks": blueprint_blocks,
        "links": blueprint_links
    }

    bp_model = BlueprintModel.model_validate(engine_blueprint)
    assert len(bp_model.blocks) == len(data["blocks"])
    assert len(bp_model.links) == len(data["edges"])
    print("  ✓ Validated Horiba_H20_UVL_Spectroscopy canvas blueprint conversion to BlueprintModel")


@pytest.mark.asyncio
async def test_horiba_blueprint_simulated_execution(tmp_path):
    """Executes the full Horiba VUV spectroscopy blueprint in simulated mode with ExecutionEngine."""
    from comfylab.blocks.loader import load_blocks_from_directory
    load_all_blocks()
    store_dir = src_dir / "dist" / "comfylab-store" / "instruments"
    if store_dir.exists():
        load_blocks_from_directory(str(store_dir))

    if "devices/horiba/vuv_excitation/connect" not in BLOCK_REGISTRY:
        pytest.skip("Horiba store package not installed")

    clusters_dir = _get_horiba_clusters_dir()
    for c_file in [
        "vuv_setup_instruments.cluster.json",
        "vuv_measure_point.cluster.json",
        "vuv_accumulate_data.cluster.json",
        "vuv_export_dataset.cluster.json",
    ]:
        with open(clusters_dir / c_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        cluster_def = ClusterDefinitionModel.model_validate(data)
        register_cluster_block(cluster_def)

    bp_path = _get_horiba_blueprint_path()
    with open(bp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Set Simulation=true and small steps (e.g. 5 steps) for fast test execution
    for b in data["blocks"]:
        if b["id"] == "cluster_setup":
            b["data"]["Simulation"] = True
        if b["id"] == "cluster_measure":
            b["data"]["Simulation"] = True
            b["data"]["SettleDelay"] = 0.001
        if b["id"] == "block_wl_linspace":
            b["data"]["Start"] = 120.0
            b["data"]["Stop"] = 124.0
            b["data"]["Steps"] = 5

    blueprint_blocks = []
    for b in data["blocks"]:
        props = dict(b["data"])
        btype = props.pop("action", "")
        blueprint_blocks.append({
            "id": b["id"],
            "type": btype,
            "properties": props
        })

    blueprint_links = []
    for e in data["edges"]:
        is_exec = e.get("style", {}).get("animated", False) or "Out" in e.get("sourceHandle", "") or "Done" in e.get("sourceHandle", "") or "LoopBody" in e.get("sourceHandle", "") or "Plot" in e.get("targetHandle", "") or "Write" in e.get("targetHandle", "")
        blueprint_links.append({
            "id": e["id"],
            "type": "exec" if is_exec else "data",
            "source_block": e["source"],
            "source_pin": e["sourceHandle"],
            "target_block": e["target"],
            "target_pin": e["targetHandle"]
        })

    engine_blueprint = {
        "blocks": blueprint_blocks,
        "links": blueprint_links
    }

    engine = ExecutionEngine()
    telemetry_events = []
    async def mock_telemetry(run_id, msg):
        telemetry_events.append(msg)
    engine.telemetry_callback = mock_telemetry

    engine.load_blueprint(engine_blueprint)
    await engine.run(start_block_id="cluster_setup", start_pin_name="In")

    # Verify execution ran without aborting
    assert engine.state != "ABORTED", "Engine execution was aborted"

    # Verify telemetry events received display path or plot data
    display_telemetry = [
        e["data"]["value"] for e in telemetry_events 
        if isinstance(e, dict) and e.get("type") == "telemetry" and e.get("block_id") == "block_display_path"
    ]
    assert len(display_telemetry) > 0, f"No display telemetry received. Events: {telemetry_events}"
    saved_path = display_telemetry[-1]
    assert ".csv" in str(saved_path)
    print(f"  ✓ Full Horiba VUV blueprint execution succeeded! Exported to: {saved_path}")
