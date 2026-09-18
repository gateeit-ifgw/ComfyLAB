# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import comfylab
from comfylab.engine.registry import register_block, BLOCK_REGISTRY
from comfylab.blocks.base import BaseBlock, ExecIn, ExecOut, DataIn, DataOut, ExecutionContext, Pin
from comfylab.engine.models import ClusterDefinitionModel
from comfylab.engine.security import evaluate_trust, verify_json

logger = logging.getLogger("comfylab.blocks.cluster")

MAX_CLUSTER_DEPTH = 10


class ClusterExecutionContext(ExecutionContext):
    """
    Execution context for blocks running inside a cluster sub-graph.
    Delegates boundary pulls to the parent context and sub-engine pulls internally.
    """
    def __init__(self, parent_context: ExecutionContext, sub_engine: Any,
                 boundary_data_in_map: Dict[str, tuple], boundary_data_out_map: Dict[str, tuple],
                 cluster_block_id: str):
        self.parent_context = parent_context
        self.sub_engine = sub_engine
        self.boundary_data_in_map = boundary_data_in_map
        self.boundary_data_out_map = boundary_data_out_map
        self._cluster_block_id = cluster_block_id
        self.lock_manager = parent_context.lock_manager
        self.engine = sub_engine
        self.run_id = parent_context.run_id
        self._data_cache: Dict[str, Dict[str, Any]] = {}
        self._triggered_exec_out = None

    async def pull(self, block_id: str, input_pin_name: str) -> Any:
        key = (block_id, input_pin_name)
        if key in self.boundary_data_in_map:
            external_pin_name = self.boundary_data_in_map[key]
            return await self.parent_context.pull(self._cluster_block_id, external_pin_name)
        return await self.sub_engine.pull_data(block_id, input_pin_name, self)

    def cache_value(self, block_id: str, pin_name: str, value: Any):
        if block_id not in self._data_cache:
            self._data_cache[block_id] = {}
        self._data_cache[block_id][pin_name] = value

    def get_cached(self, block_id: str, pin_name: str) -> tuple:
        if block_id in self._data_cache and pin_name in self._data_cache[block_id]:
            return True, self._data_cache[block_id][pin_name]
        return False, None

    def clear_cache(self):
        self._data_cache.clear()

    async def send_telemetry(self, block_id: str, data: Any):
        prefixed_id = f"{self._cluster_block_id}/{block_id}"
        if hasattr(self.parent_context, "send_telemetry"):
            await self.parent_context.send_telemetry(prefixed_id, data)


def _prefix_block_ids(blueprint: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    blocks = []
    id_map = {}
    for block in blueprint.get("blocks", []):
        new_id = f"{prefix}_{block['id']}"
        id_map[block["id"]] = new_id
        new_block = dict(block)
        new_block["id"] = new_id
        blocks.append(new_block)

    links = []
    for link in blueprint.get("links", []):
        new_link = dict(link)
        new_link["source_block"] = id_map.get(link["source_block"], link["source_block"])
        new_link["target_block"] = id_map.get(link["target_block"], link["target_block"])
        links.append(new_link)

    return {"blocks": blocks, "links": links}


def parse_cluster_boundary_pins(internal_blueprint: Dict[str, Any], default_boundary_pins: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scans the internal blueprint of a cluster for boundary input/output blocks
    and constructs the boundary pin mapping dict. If none are found, returns the default.
    """
    has_boundary_blocks = any(
        block.get("type") in ("cluster/boundary/input", "cluster/boundary/output")
        for block in internal_blueprint.get("blocks", [])
    )
    if not has_boundary_blocks:
        return default_boundary_pins

    exec_ins = []
    exec_outs = []
    data_ins = []
    data_outs = []
    
    for block in internal_blueprint.get("blocks", []):
        block_id = block.get("id")
        block_type = block.get("type")
        props = block.get("properties", {})
        
        def get_prop(name, default):
            val = props.get(name, default)
            if isinstance(val, dict) and "value" in val:
                return val["value"]
            return val
        
        if block_type == "cluster/boundary/input":
            name = get_prop("Name", "InputPin")
            pin_type = get_prop("Type", "data")
            data_type = get_prop("DataType", "any")
            if pin_type == "exec":
                exec_ins.append({
                    "name": name,
                    "maps_to": {
                        "block_id": block_id,
                        "pin": "Out"
                    }
                })
            else:
                data_ins.append({
                    "name": name,
                    "type": data_type,
                    "default": None,
                    "widget": None,
                    "optional": False,
                    "maps_to": {
                        "block_id": block_id,
                        "pin": "Value"
                    }
                })
        elif block_type == "cluster/boundary/output":
            name = get_prop("Name", "OutputPin")
            pin_type = get_prop("Type", "data")
            if pin_type == "exec":
                exec_outs.append({
                    "name": name,
                    "maps_from": {
                        "block_id": block_id,
                        "pin": "In"
                    }
                })
            else:
                data_outs.append({
                    "name": name,
                    "type": "any",
                    "maps_from": {
                        "block_id": block_id,
                        "pin": "Value"
                    }
                })
                
    return {
        "exec_ins": exec_ins,
        "exec_outs": exec_outs,
        "data_ins": data_ins,
        "data_outs": data_outs
    }


def register_cluster_block(cluster_def: ClusterDefinitionModel, file_path: str = ""):
    type_name = cluster_def.type_name
    boundary = cluster_def.boundary_pins
    internal_blueprint = cluster_def.internal_blueprint.model_dump()

    inputs_def: List[Pin] = []
    outputs_def: List[Pin] = []

    for ein in boundary.exec_ins:
        inputs_def.append(ExecIn(ein.name))
    for eout in boundary.exec_outs:
        outputs_def.append(ExecOut(eout.name))

    type_map = {"number": float, "boolean": bool, "text": str, "string": str, "list": list, "any": None}
    for din in boundary.data_ins:
        hint = type_map.get(din.type)
        inputs_def.append(DataIn(
            din.name, type_hint=hint, default=din.default,
            widget=din.widget, min_val=din.min_val, max_val=din.max_val,
            step=din.step, options=din.options, optional=din.optional
        ))
    for dout in boundary.data_outs:
        hint = type_map.get(dout.type)
        outputs_def.append(DataOut(dout.name, type_hint=hint))

    class DynamicClusterBlock(BaseBlock):
        category = cluster_def.category
        icon = cluster_def.icon
        display_name = cluster_def.display_name
        description = cluster_def.description
        i18n = getattr(cluster_def, "i18n", {}) or {}
        _cluster_file_path = file_path

        def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
            super().__init__(block_id, properties)
            self._cluster_def = cluster_def
            self._sub_engine = None
            self._computed_outputs: Dict[str, Any] = {}
            self._depth = self.properties.get("_cluster_depth", 0)
            self.inputs = {pin.name: pin for pin in self.__class__.inputs_def}
            self.outputs = {pin.name: pin for pin in self.__class__.outputs_def}

        def _build_boundary_maps(self):
            bdi_map: Dict[tuple, str] = {}
            for din in boundary.data_ins:
                bdi_map[(din.maps_to.block_id, din.maps_to.pin)] = din.name
            bdo_map: Dict[str, tuple] = {}
            for dout in boundary.data_outs:
                bdo_map[dout.name] = (dout.maps_from.block_id, dout.maps_from.pin)
            return bdi_map, bdo_map

        async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
            if self._depth > MAX_CLUSTER_DEPTH:
                raise RuntimeError(f"Cluster nesting depth exceeded ({self._depth} > {MAX_CLUSTER_DEPTH})")

            self._ensure_sub_engine()
            sub_engine = self._sub_engine
            prefix = f"cluster_{self.id}_d{self._depth}"

            bdi_map, bdo_map = self._build_boundary_maps()
            prefixed_bdi_map = {}
            for (block_id, pin), ext_name in bdi_map.items():
                prefixed_bdi_map[(f"{prefix}_{block_id}", pin)] = ext_name

            cluster_ctx = ClusterExecutionContext(
                context, sub_engine, prefixed_bdi_map, bdo_map, self.id
            )

            # Support triggering the specific entry point matching trigger_pin
            start_block_id, start_pin_name = None, None
            for ein in boundary.exec_ins:
                if ein.name == trigger_pin:
                    start_block_id = ein.maps_to.block_id
                    start_pin_name = ein.maps_to.pin
                    break
            
            # Fallback to the first exec_in if trigger_pin is not found but exec_ins exist
            if not start_block_id and boundary.exec_ins:
                start_block_id = boundary.exec_ins[0].maps_to.block_id
                start_pin_name = boundary.exec_ins[0].maps_to.pin

            if start_block_id:
                start_block_id = f"{prefix}_{start_block_id}"

            sub_engine.telemetry_callback = context.engine.telemetry_callback

            # Run the sub-engine manually using our ClusterExecutionContext (not its own plain context)
            run_error = None
            try:
                sub_engine.state = "RUNNING"
                sub_engine.executed_blocks_order.clear()

                original_cwd = os.getcwd()
                try:
                    if start_block_id and start_pin_name:
                        task = asyncio.create_task(sub_engine.trigger_exec(start_block_id, start_pin_name, cluster_ctx))
                        sub_engine._active_tasks.add(task)
                        task.add_done_callback(sub_engine._active_tasks.discard)
                        await task
                    else:
                        entry_points = sub_engine._find_entry_points()
                        if entry_points:
                            tasks = []
                            for nid, pname in entry_points:
                                task = asyncio.create_task(sub_engine.trigger_exec(nid, pname, cluster_ctx))
                                sub_engine._active_tasks.add(task)
                                task.add_done_callback(sub_engine._active_tasks.discard)
                                tasks.append(task)
                            await asyncio.gather(*tasks)

                    if sub_engine.state == "RUNNING":
                        sub_engine.state = "IDLE"
                except asyncio.CancelledError:
                    sub_engine.state = "ABORTED"
                except Exception as e:
                    sub_engine.state = "ABORTED"
                    run_error = e
                finally:
                    if sub_engine._active_tasks:
                        for task in list(sub_engine._active_tasks):
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(*sub_engine._active_tasks, return_exceptions=True)
                        sub_engine._active_tasks.clear()
                    os.chdir(original_cwd)

                # Collect boundary outputs — sub_engine stays alive, no teardown here
                self._computed_outputs = {}
                for dout in boundary.data_outs:
                    mapped_block_id = f"{prefix}_{dout.maps_from.block_id}"
                    mapped_pin = dout.maps_from.pin
                    block = sub_engine.blocks.get(mapped_block_id)
                    if block:
                        val = await block.pull_data(cluster_ctx, mapped_pin)
                        self._computed_outputs[dout.name] = val

                if run_error and context.engine.state != "ABORTED":
                    raise run_error
            finally:
                pass  # Do NOT teardown — sub_engine lives until ClusterBlock.teardown() is called

            triggered_out = getattr(cluster_ctx, "_triggered_exec_out", None)
            if triggered_out is not None:
                return triggered_out
            if boundary.exec_outs:
                return boundary.exec_outs[0].name
            return None

        async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
            has_exec_in = bool(boundary.exec_ins)
            if has_exec_in and pin_name in self._computed_outputs:
                return self._computed_outputs[pin_name]

            for dout in boundary.data_outs:
                if dout.name == pin_name:
                    self._ensure_sub_engine()
                    prefix = f"cluster_{self.id}_d{self._depth}"
                    mapped_block_id = f"{prefix}_{dout.maps_from.block_id}"
                    mapped_pin = dout.maps_from.pin

                    bdi_map, bdo_map = self._build_boundary_maps()
                    prefixed_bdi_map = {}
                    for (nid, p), ext_name in bdi_map.items():
                        prefixed_bdi_map[(f"{prefix}_{nid}", p)] = ext_name

                    cluster_ctx = ClusterExecutionContext(
                        context, self._sub_engine, prefixed_bdi_map, bdo_map, self.id
                    )

                    block = self._sub_engine.blocks.get(mapped_block_id)
                    if block:
                        val = await block.pull_data(cluster_ctx, mapped_pin)
                        if has_exec_in:
                            self._computed_outputs[pin_name] = val
                        return val
                    return None

            return None

        async def clear_data(self):
            self._computed_outputs.clear()
            if self._sub_engine:
                for block in self._sub_engine.blocks.values():
                    if hasattr(block, "clear_data"):
                        await block.clear_data()

        def _ensure_sub_engine(self):
            if self._sub_engine is not None:
                return
            from comfylab.engine.executor import ExecutionEngine
            sub_engine = ExecutionEngine()
            prefix = f"cluster_{self.id}_d{self._depth}"
            prefixed_blueprint = _prefix_block_ids(internal_blueprint, prefix)
            sub_engine.load_blueprint(prefixed_blueprint)
            self._sub_engine = sub_engine

        async def teardown(self):
            if self._sub_engine:
                try:
                    await self._sub_engine._teardown_all()
                except Exception:
                    pass
            await super().teardown()

    DynamicClusterBlock.inputs_def = inputs_def
    DynamicClusterBlock.outputs_def = outputs_def
    DynamicClusterBlock.__name__ = type_name.replace("/", "_").replace("-", "_")
    DynamicClusterBlock.__qualname__ = DynamicClusterBlock.__name__

    _CLUSTER_TYPE_PREFIXES = ("user/cluster/", "workspace/cluster/", "builtin/cluster/", "cluster/", "clusters/")
    _BOUNDARY_TYPES = ("cluster/input", "cluster/output", "cluster/boundary/input", "cluster/boundary/output")
    missing_regular = []
    for bn in internal_blueprint.get("blocks", []):
        nt = bn.get("type")
        if not nt:
            continue
        if nt in BLOCK_REGISTRY:
            continue
        if nt.startswith(_CLUSTER_TYPE_PREFIXES) or nt in _BOUNDARY_TYPES:
            continue
        missing_regular.append(nt)

    if missing_regular:
        DynamicClusterBlock.broken = True
        DynamicClusterBlock.broken_reason = (
            "Cluster references unregistered block types: " + ", ".join(sorted(set(missing_regular)))
        )
        logger.error(
            "Cluster '%s' is broken (missing inner block types: %s). Source: %s",
            type_name, missing_regular, file_path or "<unknown>"
        )
    else:
        DynamicClusterBlock.broken = False
        DynamicClusterBlock.broken_reason = ""

    existing = BLOCK_REGISTRY.get(type_name)
    if missing_regular and existing is not None and not getattr(existing, "broken", False):
        logger.warning(
            "Skipping registration of broken cluster '%s' from '%s'; keeping existing working registration.",
            type_name, file_path or "<unknown>"
        )
        return DynamicClusterBlock

    register_block(type_name)(DynamicClusterBlock)
    return DynamicClusterBlock


def load_cluster_from_file(filepath: str):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Cluster file not found: {filepath}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Security/Signature check
    abs_path = path.resolve()
    type_name = data.get("type_name", "")

    # Core / Built-in determination
    is_core = type_name.startswith("builtin/cluster/")
    if not is_core:
        core_dir = Path(comfylab.__file__).parent.resolve()
        if core_dir in abs_path.parents or abs_path == core_dir:
            is_core = True
        elif getattr(sys, 'frozen', False):
            ext_core_dir = (Path(sys.executable).parent / "comfylab").resolve()
            meipass = getattr(sys, '_MEIPASS', None)
            if ext_core_dir in abs_path.parents or (meipass and Path(meipass).resolve() in abs_path.parents):
                is_core = True

    unauthorized = False
    creator = "system"
    if not is_core:
        creator, is_valid = verify_json(data)
        is_trusted = evaluate_trust(creator, is_valid)
        if not is_trusted:
            unauthorized = True

    cluster_def = ClusterDefinitionModel.model_validate(data)
    cls = register_cluster_block(cluster_def, str(path))
    cls.unauthorized = unauthorized
    cls.creator_identity = creator
    return cluster_def



def load_clusters_from_directory(directory_path: str) -> int:
    dir_path = Path(directory_path).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        return 0

    count = 0
    for root, dirs, files in os.walk(str(dir_path)):
        if ".temp" in dirs:
            dirs.remove(".temp")
        for file in files:
            if file.endswith(".cluster.json"):
                full_path = Path(root) / file
                try:
                    load_cluster_from_file(str(full_path))
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to load cluster from {full_path}: {e}")
    return count


def generate_cluster_json(blueprint_blocks: list, blueprint_links: list,
                        boundary_pins: dict, display_name: str,
                        type_name: str, category: str = "User/Clusters",
                        icon: str = "📦", description: str = "") -> dict:
    return {
        "name": display_name,
        "type_name": type_name,
        "category": category,
        "icon": icon,
        "display_name": display_name,
        "description": description,
        "internal_blueprint": {
            "blocks": blueprint_blocks,
            "links": blueprint_links
        },
        "boundary_pins": boundary_pins
    }

