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
import os
import uuid
import logging
import math
from typing import Dict, List, Any, Optional, Callable, Union

from comfylab.engine.models import BlueprintModel
from comfylab.engine.registry import get_block_class
from comfylab.engine.locks import ResourceLockManager
from comfylab.blocks.base import BaseBlock, ExecutionContext, ExecIn, DataIn, ExecOut
from backend.workspace import get_workspace_path
from comfylab.engine.logging import run_id_var, set_block_context, reset_block_context

logger = logging.getLogger("comfylab.engine.executor")

PERSISTENT_IGNORED_KEYS = {"isPersistent", "autoClearPersistent"}

async def _detect_persistent_changes(block: BaseBlock, context: ExecutionContext) -> tuple[bool, Dict[str, Any]]:
    """
    Checks if a persistent block's parameters or input pin data have changed since the last execution.
    Returns (has_changes, current_inputs).
    Properties are checked first (cheap, no I/O) and short-circuit before any upstream pull.
    """
    properties_changed = False
    for k, v in block.properties.items():
        if k not in PERSISTENT_IGNORED_KEYS and getattr(block, "_last_properties", {}).get(k) != v:
            properties_changed = True
            break
    for k in getattr(block, "_last_properties", {}):
        if k not in PERSISTENT_IGNORED_KEYS and k not in block.properties:
            properties_changed = True
            break

    if properties_changed:
        return True, {}

    current_inputs = {}
    for name, pin in block.inputs.items():
        if isinstance(pin, DataIn):
            current_inputs[name] = await context.pull(block.id, name)

    inputs_changed = False
    last_inputs = getattr(block, "_last_inputs", {})
    for k, v in current_inputs.items():
        if last_inputs.get(k) != v:
            inputs_changed = True
            break
    for k in last_inputs:
        if k not in current_inputs:
            inputs_changed = True
            break

    return inputs_changed, current_inputs

class ExecutionEngine:
    """
    Main executor for ComfyLAB graphs.
    Coordinates graph loading, state transitions, execution token flow (push wires),
    lazy data evaluation (pull wires), block execution watchdogs, and safe global teardown.
    """
    def __init__(self):
        self.state: str = "IDLE"  # IDLE, RUNNING, PAUSED, ABORTED
        self.lock_manager = ResourceLockManager()
        self.blocks: Dict[str, BaseBlock] = {}
        self.persistent_blocks: Dict[str, BaseBlock] = {}
        # maps (target_block_id, target_pin_name) -> (source_block_id, source_pin_name)
        self.data_links: Dict[tuple[str, str], tuple[str, str]] = {}
        # maps (source_block_id, source_pin_name) -> (target_block_id, target_pin_name)
        self.exec_links: Dict[tuple[str, str], tuple[str, str]] = {}
        # Tracks blocks in the order they started executing to perform reverse teardown
        self.executed_blocks_order: List[str] = []
        # Telemetry callback: async def (run_id, message_dict)
        self.telemetry_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None
        self._resume_event = asyncio.Event()
        self._resume_event.set()
        self.current_run_id: Optional[str] = None
        self.current_raw_canvas: Optional[Dict[str, Any]] = None
        self._active_tasks = set()
        self._teardown_lock = asyncio.Lock()
        self._teardown_complete = False


    def load_blueprint(self, blueprint_data: Union[Dict[str, Any], BlueprintModel]):
        """
        Validates the blueprint JSON schema, instantiates the required blocks
        from the registry, and maps both data and execution links.
        Accepts a raw dict (validated here) or a pre-validated BlueprintModel (used directly).
        """
        if isinstance(blueprint_data, BlueprintModel):
            blueprint = blueprint_data
        else:
            blueprint = BlueprintModel.model_validate(blueprint_data)

        # 1. Clean up self.persistent_blocks that are not in the new blueprint (i.e. deleted from canvas)
        blueprint_block_ids = {block_model.id for block_model in blueprint.blocks}
        blocks_to_teardown = []
        for p_id in list(self.persistent_blocks.keys()):
            if p_id not in blueprint_block_ids:
                block = self.persistent_blocks.pop(p_id)
                blocks_to_teardown.append(block)

        self.blocks.clear()
        self.data_links.clear()
        self.exec_links.clear()
        self.executed_blocks_order.clear()

        # Instantiate blocks
        for block_model in blueprint.blocks:
            cls = get_block_class(block_model.type)
            if getattr(cls, "unauthorized", False):
                raise ValueError(f"Cannot execute unauthorized custom block '{block_model.type}'. The code is unsigned or untrusted.")
            
            block_id = block_model.id
            is_persistent = block_model.properties.get("isPersistent", False)
            auto_clear = block_model.properties.get("autoClearPersistent", True)  # Checked by default!

            # Check if this block is already cached as persistent
            if is_persistent and block_id in self.persistent_blocks:
                cached_block = self.persistent_blocks[block_id]

                # Check if parameters changed (ignoring isPersistent and autoClearPersistent)
                properties_changed = False
                for k, v in block_model.properties.items():
                    if k not in PERSISTENT_IGNORED_KEYS and cached_block.properties.get(k) != v:
                        properties_changed = True
                        break
                # Also check if any old property was deleted
                for k in cached_block.properties:
                    if k not in PERSISTENT_IGNORED_KEYS and k not in block_model.properties:
                        properties_changed = True
                        break

                if properties_changed and auto_clear:
                    logger.info(f"Auto-clearing persistent block '{block_id}' due to parameter changes.")
                    blocks_to_teardown.append(cached_block)
                    self.persistent_blocks.pop(block_id)
                    # Create new instance
                    block_instance = cls(block_id, block_model.properties)
                    self.blocks[block_id] = block_instance
                    self.persistent_blocks[block_id] = block_instance
                else:
                    # Reuse cached instance and update properties
                    cached_block.properties = block_model.properties
                    self.blocks[block_id] = cached_block
            else:
                # If it was persistent before but toggled off, tear it down
                if block_id in self.persistent_blocks:
                    block = self.persistent_blocks.pop(block_id)
                    blocks_to_teardown.append(block)

                # Create a new instance
                block_instance = cls(block_id, block_model.properties)
                self.blocks[block_id] = block_instance
                if is_persistent:
                    self.persistent_blocks[block_id] = block_instance

        # Run teardown in background/sync for deleted/cleared blocks
        for block in blocks_to_teardown:
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(block.teardown())
                # Log teardown failures instead of letting them vanish into the event loop
                def _log_teardown_result(t, block_id=block.id):
                    if t.cancelled():
                        return
                    exc = t.exception()
                    if exc is not None:
                        logger.error(f"Teardown failed for block '{block_id}': {exc}")
                task.add_done_callback(_log_teardown_result)
            except RuntimeError:
                try:
                    asyncio.run(block.teardown())
                except Exception as run_err:
                    logger.error(f"Teardown failed in sync context: {run_err}")

        # Map links
        for link in blueprint.links:
            if link.type == "data":
                self.data_links[(link.target_block, link.target_pin)] = (link.source_block, link.source_pin)
            elif link.type == "exec":
                self.exec_links[(link.source_block, link.source_pin)] = (link.target_block, link.target_pin)

    async def run(self, start_block_id: Optional[str] = None, start_pin_name: Optional[str] = None, run_id: Optional[str] = None):
        """
        Executes the currently loaded graph.
        If start_block_id and start_pin_name are provided, execution triggers there.
        Otherwise, triggers all entry blocks (blocks with execution inputs but no incoming execution links).
        """
        if self.state == "RUNNING" or self.state == "PAUSED":
            raise RuntimeError("Engine is already running or paused.")

        self.state = "RUNNING"
        self._resume_event.set()
        self.executed_blocks_order.clear()
        self._teardown_complete = False
        run_id = run_id or str(uuid.uuid4())
        self.current_run_id = run_id


        # Set run context variable
        run_token = run_id_var.set(run_id)
        logger.info(f"Execution run {run_id} started")

        context = ExecutionContext(self, run_id, self.lock_manager)

        original_cwd = os.getcwd()
        # Set the working directory to the workspace for this execution session.
        # This allows file-based blocks and script blocks to resolve relative paths
        # from the workspace root.
        ws_str = str(get_workspace_path())
        os.environ["COMFYLAB_WORKSPACE"] = ws_str
        os.environ["WORKSPACE"] = ws_str
        os.chdir(ws_str)

        try:
            if start_block_id and start_pin_name:
                task = asyncio.create_task(self.trigger_exec(start_block_id, start_pin_name, context))
                self._active_tasks.add(task)
                task.add_done_callback(self._active_tasks.discard)
                await task
            else:
                entry_points = self._find_entry_points()
                if entry_points:
                    tasks = []
                    for block_id, pin_name in entry_points:
                        task = asyncio.create_task(self.trigger_exec(block_id, pin_name, context))
                        self._active_tasks.add(task)
                        task.add_done_callback(self._active_tasks.discard)
                        tasks.append(task)
                    await asyncio.gather(*tasks)

            if self.state == "RUNNING":
                self.state = "IDLE"
                logger.info(f"Execution run {run_id} completed successfully")
        except asyncio.CancelledError:
            self.state = "ABORTED"
            logger.warning(f"Execution run {run_id} was cancelled/aborted")
        except Exception as e:
            self.state = "ABORTED"
            logger.error(f"Execution run {run_id} failed with error: {e}")
            raise
        finally:
            if self._active_tasks:
                for task in list(self._active_tasks):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._active_tasks, return_exceptions=True)
                self._active_tasks.clear()
            os.chdir(original_cwd)
            await self._teardown_all()
            self.current_run_id = None
            self.current_raw_canvas = None
            run_id_var.reset(run_token)

    def _find_entry_points(self) -> List[tuple[str, str]]:
        """
        Finds the blocks that start a run: blocks whose ExecIn pins have no incoming execution links.
        Each entry block is triggered once, on its first (primary) ExecIn pin. Secondary pins such as
        Timer 'Stop', Countdown 'Skip' or Accumulate 'Reset' must never fire on their own just because
        they are left unwired, and a block with any wired ExecIn is driven by its upstream flow instead.
        """
        exec_targets = set(self.exec_links.values())
        entry_points = []
        for block_id, block in self.blocks.items():
            exec_pins = [pin_name for pin_name, pin in block.inputs.items() if isinstance(pin, ExecIn)]
            if exec_pins and not any((block_id, pin_name) in exec_targets for pin_name in exec_pins):
                entry_points.append((block_id, exec_pins[0]))
        return entry_points

    async def trigger_exec(self, block_id: str, pin_name: str, context: ExecutionContext):
        """
        Triggers execution starting at a block input or output pin.
        If pin_name is an output pin (in exec_links), resolves it to target input pin first.
        Propagates execution token sequentially along execution wires.
        """
        current_block_id = block_id
        current_pin_name = pin_name

        block = self.blocks.get(block_id)
        if block and pin_name in block.outputs:
            if (block_id, pin_name) in self.exec_links:
                current_block_id, current_pin_name = self.exec_links[(block_id, pin_name)]
            else:
                # Output pin is not connected to anything downstream
                return
        elif (block_id, pin_name) in self.exec_links:
            current_block_id, current_pin_name = self.exec_links[(block_id, pin_name)]

        while current_block_id is not None:
            if self.state == "ABORTED":
                break

            if self.state == "PAUSED":
                await self._resume_event.wait()

            if self.state == "ABORTED":
                break

            block = self.blocks.get(current_block_id)
            if not block:
                break

            # Track execution order for safe reverse teardown
            if current_block_id not in self.executed_blocks_order:
                self.executed_blocks_order.append(current_block_id)

            # Broadcast block start running status
            await self._broadcast_status(context.run_id, current_block_id, "running")

            # Set block context variables (ID, Name, File)
            block_tokens = set_block_context(block)
            logger.debug(f"Executing block '{current_block_id}'")
            try:
                # Block execution watchdog / timeout
                timeout = block.properties.get("timeout", None)
                try:
                    async def execute_block():
                        if block.properties.get("disabled", False):
                            logger.info(f"Block '{block.id}' is disabled. Passing execution token ahead.")
                            for name, pin in block.outputs.items():
                                if isinstance(pin, ExecOut):
                                    return name
                            return None

                        is_persistent = block.properties.get("isPersistent", False)
                        if is_persistent and getattr(block, "_has_executed", False):
                            has_changes, current_inputs = await _detect_persistent_changes(block, context)
                            if not has_changes:
                                logger.info(f"Skipping execution for persistent block '{block.id}' - no changes detected.")
                                if hasattr(block, "_last_outputs"):
                                    block._outputs = dict(block._last_outputs)
                                return getattr(block, "_last_next_pin", None)
                                
                            if block.properties.get("autoClearPersistent", True):
                                logger.info(f"Persistent block '{block.id}' inputs or parameters changed. Auto-clearing state before execution.")
                                try:
                                    await block.teardown()
                                except Exception as teardown_err:
                                    logger.error(f"Teardown failed during auto-clear: {teardown_err}")
                                if hasattr(block, "clear_data"):
                                    await block.clear_data()

                        next_pin = await block.execute(context, current_pin_name)

                        if is_persistent:
                            current_inputs = {}
                            for name, pin in block.inputs.items():
                                if isinstance(pin, DataIn):
                                    current_inputs[name] = await context.pull(block.id, name)
                            block._last_inputs = current_inputs
                            block._last_properties = {k: v for k, v in block.properties.items() if k not in PERSISTENT_IGNORED_KEYS}
                            block._last_outputs = dict(block._outputs) if hasattr(block, "_outputs") else {}
                            block._last_next_pin = next_pin
                            block._has_executed = True

                        return next_pin

                    if timeout is not None:
                        next_pin = await asyncio.wait_for(
                            execute_block(), 
                            timeout=float(timeout)
                        )
                    else:
                        next_pin = await execute_block()
                    
                    # Broadcast block success status
                    await self._broadcast_status(context.run_id, current_block_id, "success")
                    logger.debug(f"Finished executing block '{current_block_id}' with next pin '{next_pin}'")
                except Exception as e:
                    # Broadcast block error status
                    await self._broadcast_status(context.run_id, current_block_id, "error", message=str(e))
                    logger.error(f"Block '{current_block_id}' execution failed: {e}")
                    if isinstance(e, asyncio.TimeoutError):
                        raise TimeoutError(f"Block '{current_block_id}' exceeded execution timeout of {timeout}s.")
                    raise
            finally:
                reset_block_context(block_tokens)

            # Clear data cache after each execution step so subsequent blocks get fresh calculations
            context.clear_cache()

            if not next_pin:
                break

            # Find next target pin in execution links
            link_key = (current_block_id, next_pin)
            if link_key in self.exec_links:
                current_block_id, current_pin_name = self.exec_links[link_key]
            else:
                break

    async def pull_data(self, target_block_id: str, target_pin_name: str, context: ExecutionContext) -> Any:
        """
        Evaluates data dependencies recursively (lazy pull evaluation).
        Retrieves cached values if already computed in the current step, or pulls from connected source.
        """
        link_key = (target_block_id, target_pin_name)
        target_block = self.blocks.get(target_block_id)
        if not target_block:
            raise ValueError(f"Target block '{target_block_id}' not found in graph.")
        pin = target_block.inputs.get(target_pin_name)

        val = None
        if link_key in self.data_links:
            source_block_id, source_pin_name = self.data_links[link_key]

            # Check cache
            cached, cached_val = context.get_cached(source_block_id, source_pin_name)
            if cached:
                val = cached_val
            else:
                source_block = self.blocks.get(source_block_id)
                if not source_block:
                    raise ValueError(f"Source block '{source_block_id}' not found in graph.")

                # Check if we can skip pulling (memoization)
                is_persistent = source_block.properties.get("isPersistent", False)
                skip_pull = False

                if is_persistent and getattr(source_block, "_has_pulled", False):
                    has_changes, current_inputs = await _detect_persistent_changes(source_block, context)
                    if not has_changes:
                        logger.info(f"Skipping pull_data for persistent block '{source_block.id}' - no changes detected.")
                        if hasattr(source_block, "_last_outputs") and source_pin_name in source_block._last_outputs:
                            val = source_block._last_outputs[source_pin_name]
                            skip_pull = True
                            
                    if has_changes and source_block.properties.get("autoClearPersistent", True):
                        logger.info(f"Persistent block '{source_block.id}' inputs or parameters changed. Auto-clearing state before pull.")
                        try:
                            await source_block.teardown()
                        except Exception as teardown_err:
                            logger.error(f"Teardown failed during auto-clear: {teardown_err}")
                        if hasattr(source_block, "clear_data"):
                            await source_block.clear_data()

                if not skip_pull:
                    is_disabled = source_block.properties.get("disabled", False)
                    if is_disabled:
                        logger.info(f"Block '{source_block_id}' is disabled. Attempting to pass-through data or return default.")
                        out_pin = source_block.outputs.get(source_pin_name)
                        in_pin = None
                        if out_pin:
                            for _, pin in source_block.inputs.items():
                                if isinstance(pin, DataIn) and pin.type_hint == out_pin.type_hint:
                                    in_pin = pin
                                    break
                        if in_pin:
                            val = await context.pull(source_block.id, in_pin.name)
                        else:
                            if out_pin:
                                th = out_pin.type_hint
                                if th in (float, int, "number"):
                                    val = 0
                                elif th in (bool, "boolean", "bool"):
                                    val = False
                                elif th in (str, "string"):
                                    val = ""
                                elif th in (list, "list", "array"):
                                    val = []
                                elif th in (dict, "dict", "object"):
                                    val = {}
                                else:
                                    val = None
                            else:
                                val = None
                    else:
                        # Set source block context variables during pulling
                        block_tokens = set_block_context(source_block)
                        logger.debug(f"Pulling data from block '{source_block_id}' output pin '{source_pin_name}'")
                        try:
                            # Pull data with optional watchdog timeout
                            timeout = source_block.properties.get("timeout", None)
                            try:
                                if timeout is not None:
                                    val = await asyncio.wait_for(
                                        source_block.pull_data(context, source_pin_name), 
                                        timeout=float(timeout)
                                    )
                                else:
                                    val = await source_block.pull_data(context, source_pin_name)
                            except asyncio.TimeoutError:
                                raise TimeoutError(f"Block '{source_block_id}' exceeded pull_data timeout of {timeout}s.")
                        finally:
                            reset_block_context(block_tokens)

                    # If persistent, cache current state
                    if is_persistent:
                        current_inputs = {}
                        for name, pin in source_block.inputs.items():
                            if isinstance(pin, DataIn):
                                current_inputs[name] = await context.pull(source_block.id, name)
                        source_block._last_inputs = current_inputs
                        source_block._last_properties = {k: v for k, v in source_block.properties.items() if k not in PERSISTENT_IGNORED_KEYS}
                        if not hasattr(source_block, "_last_outputs"):
                            source_block._last_outputs = {}
                        source_block._last_outputs[source_pin_name] = val
                        source_block._has_pulled = True

                context.cache_value(source_block_id, source_pin_name, val)
                await self.send_pin_values(
                    context.run_id, 
                    source_block_id, 
                    {source_pin_name: summarize_value(val)}
                )
        else:
            # Return property value if defined in blueprint, otherwise fallback to pin default value
            if isinstance(pin, DataIn):
                val = target_block.properties.get(target_pin_name)
                if val is None:
                    val = target_block.properties.get(target_pin_name.lower())
                if val is None:
                    val = pin.default

        # Safety range validation & clamping for DataIn pins
        if isinstance(pin, DataIn) and val is not None:
            if pin.min_val is not None or pin.max_val is not None:
                try:
                    numeric_val = float(val)
                    if pin.min_val is not None and numeric_val < pin.min_val:
                        logger.warning(f"Clamping value {numeric_val} for input pin '{target_pin_name}' on block '{target_block_id}' to min_val {pin.min_val}")
                        val = pin.min_val
                    elif pin.max_val is not None and numeric_val > pin.max_val:
                        logger.warning(f"Clamping value {numeric_val} for input pin '{target_pin_name}' on block '{target_block_id}' to max_val {pin.max_val}")
                        val = pin.max_val
                except (ValueError, TypeError):
                    pass

        return val

    async def abort(self):
        """Emergency stop. Forces engine into ABORTED state and triggers full teardown."""
        if self.state == "ABORTED":
            return
        self.state = "ABORTED"
        self._resume_event.set()  # Release any waiting task
        if self._active_tasks:
            for task in list(self._active_tasks):
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()
        await self._teardown_all()

    async def pause(self):
        """Pauses the execution loop."""
        if self.state == "RUNNING":
            self.state = "PAUSED"
            self._resume_event.clear()
            if self.current_run_id:
                await self._broadcast_run_status(self.current_run_id, "paused")

    async def resume(self):
        """Resumes the execution loop."""
        if self.state == "PAUSED":
            self.state = "RUNNING"
            self._resume_event.set()
            if self.current_run_id:
                await self._broadcast_run_status(self.current_run_id, "running")

    async def _broadcast_run_status(self, run_id: str, status: str, error: Optional[str] = None):
        if self.telemetry_callback:
            msg = {
                "type": "run_status",
                "status": status
            }
            if error is not None:
                msg["error"] = error
            try:
                await self.telemetry_callback(run_id, msg)
            except Exception as e:
                logger.error(f"Failed to send run status telemetry: {e}")

    async def _broadcast_status(self, run_id: str, block_id: str, status: str, message: Optional[str] = None):
        if self.telemetry_callback:
            msg = {
                "type": "status",
                "block_id": block_id,
                "status": status
            }
            if message is not None:
                msg["message"] = message
            try:
                await self.telemetry_callback(run_id, msg)
            except Exception as e:
                logger.error(f"Failed to send status telemetry: {e}")

    async def send_telemetry(self, run_id: str, block_id: str, data: Any):
        if self.telemetry_callback:
            if isinstance(data, bytes):
                # Prefix the bytes with the run_id (36 characters)
                payload = run_id.encode('utf-8') + data
                try:
                    await self.telemetry_callback(run_id, payload)
                except Exception as e:
                    logger.error(f"Failed to send binary telemetry: {e}")
            else:
                msg = {
                    "type": "telemetry",
                    "block_id": block_id,
                    "data": data
                }
                try:
                    await self.telemetry_callback(run_id, msg)
                except Exception as e:
                    logger.error(f"Failed to send telemetry data: {e}")

    async def send_pin_values(self, run_id: str, block_id: str, pin_values: Dict[str, Any]):
        if self.telemetry_callback:
            msg = {
                "type": "pin_values",
                "block_id": block_id,
                "pin_values": pin_values
            }
            try:
                await self.telemetry_callback(run_id, msg)
            except Exception as e:
                logger.error(f"Failed to send pin values telemetry: {e}")

    def _teardown_order(self) -> List[str]:
        """Returns all block IDs in topological dependency order, downstream blocks first."""
        # Build adjacency list of upstream dependencies.
        # Block u depends on v if there is a data link from v to u, or execution link from v to u.
        blocks_to_sort = list(self.blocks.keys())
        upstream_map = {block_id: set() for block_id in blocks_to_sort}

        # Data links: (target_block, target_pin) -> (source_block, source_pin)
        # target reads from source, so target depends on source.
        for (target_id, _), (source_id, _) in self.data_links.items():
            if target_id in upstream_map and source_id in upstream_map:
                upstream_map[target_id].add(source_id)

        # Exec links: (source_block, source_pin) -> (target_block, target_pin)
        # target executes after source, so target depends on source.
        for (source_id, _), (target_id, _) in self.exec_links.items():
            if target_id in upstream_map and source_id in upstream_map:
                upstream_map[target_id].add(source_id)

        # Cycle-safe post-order DFS to sort blocks topologically
        visited = set()
        visiting = set()
        ordered_blocks = []

        def dfs(block_id: str):
            if block_id in visiting:
                return  # Cycle detected, break to prevent infinite recursion
            if block_id in visited:
                return
            visiting.add(block_id)
            for upstream in upstream_map[block_id]:
                dfs(upstream)
            visiting.remove(block_id)
            visited.add(block_id)
            ordered_blocks.append(block_id)

        for block_id in blocks_to_sort:
            dfs(block_id)

        # ordered_blocks has upstream blocks first, downstream blocks last.
        # Reverse it so downstream blocks (which depend on upstream blocks) are torn down first.
        return list(reversed(ordered_blocks))

    async def _safe_state_block(self, block: BaseBlock):
        """Sends a surviving block's safety commands, then forgets its memoized results."""
        try:
            await block.safe_state()
        except Exception as e:
            logger.error(f"Safe-state failed for block '{block.id}': {e}")
        # Hardware may no longer match the cached outputs, so the next run must re-execute the block
        block._has_executed = False
        block._has_pulled = False

    async def safe_state_all(self):
        """Puts every block into a safe state without releasing connections (used by persistent clusters)."""
        for block_id in self._teardown_order():
            block = self.blocks.get(block_id)
            if block:
                await self._safe_state_block(block)

    async def _teardown_all(self):
        """
        Teardown all instantiated blocks in topological dependency order (downstream first).
        Persistent blocks keep their connections, but after an abort or error they still get
        their safe-state commands so a failed run never leaves e.g. a laser output enabled.
        """
        async with self._teardown_lock:
            if self._teardown_complete:
                return
            self._teardown_complete = True
            emergency = self.state == "ABORTED"

            # Execute teardown hooks
            for block_id in self._teardown_order():
                block = self.blocks.get(block_id)
                if block:
                    if block.properties.get("isPersistent", False):
                        if emergency:
                            logger.warning(f"Run aborted: sending safe-state to persistent block '{block_id}'")
                            await self._safe_state_block(block)
                        else:
                            logger.debug(f"Skipping teardown for persistent block '{block_id}'")
                        continue
                    try:
                        await block.teardown()
                    except Exception as e:
                        # Ensure one failing block teardown doesn't block other block teardowns
                        logger.error(f"Teardown failed for block '{block_id}': {e}")


def summarize_value(val: Any) -> str:
    if val is None:
        return "None"
    
    # Handle numpy arrays or other complex types with shape/dtype
    if hasattr(val, "shape") and hasattr(val, "dtype"):
        return f"ndarray{list(val.shape)} {val.dtype}"
        
    # bool must be checked before int/float (bool is a subclass of int)
    if isinstance(val, bool):
        return "True" if val else "False"
    if isinstance(val, (int, float)):
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                return str(val)
            if val == 0:
                return "0.0"
            if abs(val) < 1e-4 or abs(val) > 1e6:
                return f"{val:.4e}"
            return f"{val:.4f}".rstrip('0').rstrip('.')
        return str(val)
    if isinstance(val, str):
        if len(val) > 40:
            return f'"{val[:37]}..."'
        return f'"{val}"'
    if isinstance(val, (list, tuple)):
        if not val:
            return "[]" if isinstance(val, list) else "()"
        preview = ", ".join(summarize_value(x) for x in val[:3])
        suffix = ", ..." if len(val) > 3 else ""
        return f"List({len(val)}) [{preview}{suffix}]" if isinstance(val, list) else f"Tuple({len(val)}) ({preview}{suffix})"
    if isinstance(val, dict):
        if not val:
            return "{}"
        items = list(val.items())
        preview = ", ".join(f"{k}: {summarize_value(v)}" for k, v in items[:3])
        suffix = ", ..." if len(items) > 3 else ""
        return f"Dict({len(val)}) {{{preview}{suffix}}}"
    
    # Fallback to string representation, limited in size
    s = str(val)
    if len(s) > 50:
        return f"{s[:47]}..."
    return s


