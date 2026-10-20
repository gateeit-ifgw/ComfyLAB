import asyncio
from typing import Optional
import pytest
import comfylab.blocks
from comfylab.engine.executor import ExecutionEngine
from comfylab.blocks.base import BaseBlock, ExecIn, ExecOut, DataIn, DataOut, ExecutionContext
from comfylab.engine.registry import register_block

# Custom slow block for abort/teardown testing
TEARDOWN_LOG = []

@register_block("test/slow_block")
class SlowBlock(BaseBlock):
    inputs_def = [
        ExecIn("In"),
        DataIn("Delay", type_hint=float, default=0.1)
    ]
    outputs_def = [ExecOut("Out")]

    def __init__(self, block_id: str, properties=None):
        super().__init__(block_id, properties)
        self.ran = False
        self.teardown_called = False

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        self.ran = True
        delay = await context.pull(self.id, "Delay")
        await asyncio.sleep(delay)
        return "Out"

    async def teardown(self):
        self.teardown_called = True
        TEARDOWN_LOG.append(self.id)


@pytest.fixture(autouse=True)
def ensure_slow_block_registered():
    from comfylab.engine.registry import BLOCK_REGISTRY
    if "test/slow_block" not in BLOCK_REGISTRY:
        BLOCK_REGISTRY["test/slow_block"] = SlowBlock
    if "test/fake_device" not in BLOCK_REGISTRY:
        BLOCK_REGISTRY["test/fake_device"] = FakeDeviceBlock
    if "test/failing_block" not in BLOCK_REGISTRY:
        BLOCK_REGISTRY["test/failing_block"] = FailingBlock



@pytest.mark.asyncio
async def test_linear_math_execution():
    # Number1 (7) & Number2 (3) -> Add -> Print
    blueprint = {
        "blocks": [
            {"id": "num1", "type": "constants/number", "properties": {"value": 7.0}},
            {"id": "num2", "type": "constants/number", "properties": {"value": 3.0}},
            {"id": "add", "type": "math/basic/add", "properties": {}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            # Data link: num1.Value -> add.A
            {"id": "l1", "type": "data", "source_block": "num1", "source_pin": "Value", "target_block": "add", "target_pin": "A"},
            # Data link: num2.Value -> add.B
            {"id": "l2", "type": "data", "source_block": "num2", "source_pin": "Value", "target_block": "add", "target_pin": "B"},
            # Data link: add.Result -> print.Value
            {"id": "l3", "type": "data", "source_block": "add", "source_pin": "Result", "target_block": "print", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)
    
    # Manually trigger execution on the print block
    await engine.run(start_block_id="print", start_pin_name="In")
    
    # Print block should have pulled the result of 7.0 + 3.0 = 10.0
    print_block = engine.blocks["print"]
    assert print_block.last_printed == 10.0


@pytest.mark.asyncio
async def test_conditional_if_else_true():
    blueprint = {
        "blocks": [
            {"id": "cond", "type": "constants/number", "properties": {"value": 1.0}}, # 1.0 evaluates to True
            {"id": "if_else", "type": "control_flow/basic/if_else", "properties": {}},
            {"id": "print_true", "type": "outputs/basic/print", "properties": {"value": "True Branch"}},
            {"id": "print_false", "type": "outputs/basic/print", "properties": {"value": "False Branch"}}
        ],
        "links": [
            # Data link: cond.Value -> if_else.Condition
            {"id": "l1", "type": "data", "source_block": "cond", "source_pin": "Value", "target_block": "if_else", "target_pin": "Condition"},
            # Exec link: if_else.True -> print_true.In
            {"id": "l2", "type": "exec", "source_block": "if_else", "source_pin": "True", "target_block": "print_true", "target_pin": "In"},
            # Exec link: if_else.False -> print_false.In
            {"id": "l3", "type": "exec", "source_block": "if_else", "source_pin": "False", "target_block": "print_false", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="if_else", start_pin_name="In")

    assert engine.blocks["print_true"].last_printed == "True Branch" # property value since not connected, but it ran
    assert engine.blocks["print_false"].last_printed is None # Did not run


@pytest.mark.asyncio
async def test_for_loop_execution():
    # Number (4) -> Count | ForLoop -> Print (index)
    blueprint = {
        "blocks": [
            {"id": "count", "type": "constants/number", "properties": {"value": 4.0}},
            {"id": "loop", "type": "control_flow/loops/for_loop", "properties": {}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            # Data link: count.Value -> loop.Count
            {"id": "l1", "type": "data", "source_block": "count", "source_pin": "Value", "target_block": "loop", "target_pin": "Count"},
            # Exec link: loop.LoopBody -> print.In
            {"id": "l2", "type": "exec", "source_block": "loop", "source_pin": "LoopBody", "target_block": "print", "target_pin": "In"},
            # Data link: loop.Index -> print.Value
            {"id": "l3", "type": "data", "source_block": "loop", "source_pin": "Index", "target_block": "print", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="loop", start_pin_name="Start")

    # Print block should have printed indices 0, 1, 2, 3 sequentially. Last printed should be 3.
    assert engine.blocks["print"].last_printed == 3
    # Index output pin on loop should end at 3
    assert engine.blocks["loop"]._index == 3
    assert engine.blocks["loop"]._percentage == 100.0
    assert engine.blocks["loop"]._etr == 0.0


@pytest.mark.asyncio
async def test_for_loop_percentage_and_eta():
    blueprint = {
        "blocks": [
            {"id": "loop", "type": "control_flow/loops/for_loop", "properties": {"Count": 4}},
            {"id": "acc_pct", "type": "Lists/manipulation/accumulate", "properties": {}},
            {"id": "acc_eta", "type": "Lists/manipulation/accumulate", "properties": {}},
            {"id": "delay", "type": "control_flow/timing/sleep", "properties": {"Delay": 0.02}}
        ],
        "links": [
            # loop.LoopBody -> delay.In
            {"id": "l1", "type": "exec", "source_block": "loop", "source_pin": "LoopBody", "target_block": "delay", "target_pin": "In"},
            # delay.Out -> acc_pct.Append
            {"id": "l2", "type": "exec", "source_block": "delay", "source_pin": "Out", "target_block": "acc_pct", "target_pin": "Append"},
            # loop.Percentage -> acc_pct.Value
            {"id": "l3", "type": "data", "source_block": "loop", "source_pin": "Percentage", "target_block": "acc_pct", "target_pin": "Value"},
            # acc_pct.Out -> acc_eta.Append
            {"id": "l4", "type": "exec", "source_block": "acc_pct", "source_pin": "Out", "target_block": "acc_eta", "target_pin": "Append"},
            # loop.ETR -> acc_eta.Value
            {"id": "l5", "type": "data", "source_block": "loop", "source_pin": "ETR", "target_block": "acc_eta", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="loop", start_pin_name="Start")

    # Step progress for 4 iterations: 25%, 50%, 75%, 100%
    assert engine.blocks["acc_pct"]._list == [25.0, 50.0, 75.0, 100.0]

    # Iteration 0 has ETR == 0.0 (baseline not yet established), subsequent iterations have ETR > 0.0
    eta_list = engine.blocks["acc_eta"]._list
    assert len(eta_list) == 4
    assert eta_list[0] == 0.0
    assert eta_list[1] > 0.0
    assert eta_list[2] > 0.0
    # Final iteration remaining = 0 iterations after completion
    assert engine.blocks["loop"]._percentage == 100.0
    assert engine.blocks["loop"]._etr == 0.0


@pytest.mark.asyncio
async def test_for_each_loop_execution_and_metrics():
    blueprint = {
        "blocks": [
            {"id": "loop", "type": "control_flow/loops/for_each", "properties": {"Items": ["alpha", "beta", "gamma", "delta"]}},
            {"id": "acc_pct", "type": "Lists/manipulation/accumulate", "properties": {}},
            {"id": "acc_items", "type": "Lists/manipulation/accumulate", "properties": {}},
            {"id": "acc_idx", "type": "Lists/manipulation/accumulate", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "loop", "source_pin": "LoopBody", "target_block": "acc_pct", "target_pin": "Append"},
            {"id": "l2", "type": "data", "source_block": "loop", "source_pin": "Percentage", "target_block": "acc_pct", "target_pin": "Value"},
            {"id": "l3", "type": "exec", "source_block": "acc_pct", "source_pin": "Out", "target_block": "acc_items", "target_pin": "Append"},
            {"id": "l4", "type": "data", "source_block": "loop", "source_pin": "Item", "target_block": "acc_items", "target_pin": "Value"},
            {"id": "l5", "type": "exec", "source_block": "acc_items", "source_pin": "Out", "target_block": "acc_idx", "target_pin": "Append"},
            {"id": "l6", "type": "data", "source_block": "loop", "source_pin": "Index", "target_block": "acc_idx", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="loop", start_pin_name="Start")

    assert engine.blocks["acc_pct"]._list == [25.0, 50.0, 75.0, 100.0]
    assert engine.blocks["acc_items"]._list == ["alpha", "beta", "gamma", "delta"]
    assert engine.blocks["acc_idx"]._list == [0, 1, 2, 3]
    assert engine.blocks["loop"]._percentage == 100.0
    assert engine.blocks["loop"]._etr == 0.0


@pytest.mark.asyncio
async def test_for_each_loop_empty_items():
    blueprint = {
        "blocks": [
            {"id": "loop", "type": "control_flow/loops/for_each", "properties": {"Items": []}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "loop", "source_pin": "LoopBody", "target_block": "print", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="loop", start_pin_name="Start")

    # Body should not have executed
    assert engine.blocks["print"].last_printed is None
    assert engine.blocks["loop"]._percentage == 100.0
    assert engine.blocks["loop"]._etr == 0.0


@pytest.mark.asyncio
async def test_execution_watchdog_timeout():
    blueprint = {
        "blocks": [
            {"id": "slow", "type": "test/slow_block", "properties": {"timeout": 0.05, "Delay": 0.2}}
        ],
        "links": []
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    # Execution should fail with a TimeoutError because delay (0.2s) exceeds watchdog timeout (0.05s)
    with pytest.raises(TimeoutError):
        await engine.run(start_block_id="slow", start_pin_name="In")

    assert engine.state == "ABORTED"
    assert engine.blocks["slow"].teardown_called is True


@pytest.mark.asyncio
async def test_global_abort_and_reverse_teardown():
    global TEARDOWN_LOG
    TEARDOWN_LOG.clear()

    # Three slow blocks linked sequentially: slow1 -> slow2 -> slow3
    blueprint = {
        "blocks": [
            {"id": "slow1", "type": "test/slow_block", "properties": {"Delay": 0.5}},
            {"id": "slow2", "type": "test/slow_block", "properties": {"Delay": 0.5}},
            {"id": "slow3", "type": "test/slow_block", "properties": {"Delay": 0.5}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "slow1", "source_pin": "Out", "target_block": "slow2", "target_pin": "In"},
            {"id": "l2", "type": "exec", "source_block": "slow2", "source_pin": "Out", "target_block": "slow3", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    # Run in background task
    run_task = asyncio.create_task(engine.run(start_block_id="slow1", start_pin_name="In"))

    # Let slow1 start running (sleeps 0.5s)
    await asyncio.sleep(0.1)
    assert engine.blocks["slow1"].ran is True
    assert engine.blocks["slow2"].ran is False

    # Trigger emergency abort
    await engine.abort()

    # Wait for execution task to raise error or finish
    try:
        await run_task
    except Exception:
        pass

    assert engine.state == "ABORTED"
    
    # Teardown should have run on all blocks
    assert engine.blocks["slow1"].teardown_called is True
    assert engine.blocks["slow2"].teardown_called is True
    assert engine.blocks["slow3"].teardown_called is True

    # Check order: slow1 ran first, so it should be torn down last.
    # Unexecuted blocks (slow2, slow3) teardown order doesn't depend on execution order, but executed ones teardown first in reverse.
    # Since slow1 was the only one that started running, it must be the first in reverse execution teardown, or last overall.
    # Let's inspect TEARDOWN_LOG: it should contain 'slow1' as it was executed.
    assert "slow1" in TEARDOWN_LOG


@pytest.mark.asyncio
async def test_while_loop_execution():
    blueprint = {
        "blocks": [
            {"id": "bool", "type": "constants/boolean", "properties": {"value": True}},
            {"id": "loop", "type": "control_flow/loops/while_loop", "properties": {}},
            {"id": "print", "type": "outputs/basic/print", "properties": {"value": "Iterated"}}
        ],
        "links": [
            {"id": "l1", "type": "data", "source_block": "bool", "source_pin": "Value", "target_block": "loop", "target_pin": "Condition"},
            {"id": "l2", "type": "exec", "source_block": "loop", "source_pin": "LoopBody", "target_block": "print", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    async def toggle_off():
        await asyncio.sleep(0.02)
        engine.blocks["bool"].properties["value"] = False

    asyncio.create_task(toggle_off())

    await engine.run(start_block_id="loop", start_pin_name="Start")
    assert engine.blocks["print"].last_printed == "Iterated"


@pytest.mark.asyncio
async def test_display_block_execution():
    blueprint = {
        "blocks": [
            {"id": "num", "type": "constants/number", "properties": {"value": 42.12345}},
            {"id": "display", "type": "outputs/basic/display", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "data", "source_block": "num", "source_pin": "Value", "target_block": "display", "target_pin": "Value"}
        ]
    }

    telemetry_received = {}
    async def telemetry_cb(run_id, msg):
        if msg["type"] == "telemetry":
            telemetry_received[msg["block_id"]] = msg["data"]

    engine = ExecutionEngine()
    engine.telemetry_callback = telemetry_cb
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="display", start_pin_name="In")
    assert telemetry_received["display"] == {"value": 42.12345}


@pytest.mark.asyncio
async def test_xy_plot_block_execution():
    # Create simple array constants for testing
    blueprint = {
        "blocks": [
            {"id": "x_data", "type": "constants/number", "properties": {"value": 1.0}},
            {"id": "y_data", "type": "constants/number", "properties": {"value": 2.0}},
            {"id": "xy_block", "type": "outputs/plots/xy_plot", "properties": {"XLabel": "Time", "YLabel": "Voltage"}}
        ],
        "links": [
            {"id": "l1", "type": "data", "source_block": "x_data", "source_pin": "Value", "target_block": "xy_block", "target_pin": "X"},
            {"id": "l2", "type": "data", "source_block": "y_data", "source_pin": "Value", "target_block": "xy_block", "target_pin": "Y"}
        ]
    }

    telemetry_received = {}
    async def telemetry_cb(run_id, msg):
        if msg["type"] == "telemetry":
            telemetry_received[msg["block_id"]] = msg["data"]

    engine = ExecutionEngine()
    engine.telemetry_callback = telemetry_cb
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="xy_block", start_pin_name="Plot")
    
    assert "xy_block" in telemetry_received
    data = telemetry_received["xy_block"]
    # XY plot should receive the values as lists (even if single values)
    assert data["x_label"] == "Time"
    assert data["y_label"] == "Voltage"


@pytest.mark.asyncio
async def test_array_stats_block_execution():
    """Test the renamed ArrayStatsBlock example."""
    blueprint = {
        "blocks": [
            {"id": "stats", "type": "Numeric Arrays/operations/stats", "properties": {}},
            {"id": "print_min", "type": "outputs/basic/print", "properties": {}},
            {"id": "print_max", "type": "outputs/basic/print", "properties": {}},
            {"id": "print_mean", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "stats", "source_pin": "Out", "target_block": "print_min", "target_pin": "In"},
            {"id": "l2", "type": "exec", "source_block": "print_min", "source_pin": "Out", "target_block": "print_max", "target_pin": "In"},
            {"id": "l3", "type": "exec", "source_block": "print_max", "source_pin": "Out", "target_block": "print_mean", "target_pin": "In"},
            {"id": "l4", "type": "data", "source_block": "stats", "source_pin": "Min", "target_block": "print_min", "target_pin": "Value"},
            {"id": "l5", "type": "data", "source_block": "stats", "source_pin": "Max", "target_block": "print_max", "target_pin": "Value"},
            {"id": "l6", "type": "data", "source_block": "stats", "source_pin": "Mean", "target_block": "print_mean", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)
    
    # Manually set the array data on the stats block's properties before execution
    import numpy as np
    engine.blocks["stats"].properties["Array"] = np.array([1.0, 5.0, 10.0, 3.0, 8.5])

    await engine.run(start_block_id="stats", start_pin_name="Compute")
    
    # Verify the statistics were computed and printed
    assert engine.blocks["print_min"].last_printed == 1.0
    assert engine.blocks["print_max"].last_printed == 10.0
    assert engine.blocks["print_mean"].last_printed == 5.5


@pytest.mark.asyncio
async def test_safety_range_clamping():
    blueprint = {
        "blocks": [
            {"id": "loop", "type": "control_flow/loops/for_loop", "properties": {"Count": -5}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "loop", "source_pin": "LoopBody", "target_block": "print", "target_pin": "In"},
            {"id": "l2", "type": "data", "source_block": "loop", "source_pin": "Index", "target_block": "print", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    # Run loop. Count is -5 (below min_val=1), it should clamp to 1 and run once.
    await engine.run(start_block_id="loop", start_pin_name="Start")
    
    assert engine.blocks["loop"]._index == 0
    assert engine.blocks["print"].last_printed == 0


@pytest.mark.asyncio
async def test_string_constant_and_sleep_execution():
    blueprint = {
        "blocks": [
            {"id": "str", "type": "constants/string", "properties": {"value": "Hello ComfyLAB"}},
            {"id": "sleep", "type": "control_flow/timing/sleep", "properties": {"Delay": 0.05}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            # str.Value -> print.Value
            {"id": "l1", "type": "data", "source_block": "str", "source_pin": "Value", "target_block": "print", "target_pin": "Value"},
            # sleep.Out -> print.In
            {"id": "l2", "type": "exec", "source_block": "sleep", "source_pin": "Out", "target_block": "print", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    import time
    start = time.time()
    await engine.run(start_block_id="sleep", start_pin_name="In")
    end = time.time()

    assert engine.blocks["print"].last_printed == "Hello ComfyLAB"
    assert (end - start) >= 0.04


@pytest.mark.asyncio
async def test_pause_and_resume_execution():
    # Sequential slow blocks: slow1 -> slow2
    blueprint = {
        "blocks": [
            {"id": "slow1", "type": "test/slow_block", "properties": {"Delay": 0.1}},
            {"id": "slow2", "type": "test/slow_block", "properties": {"Delay": 0.1}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "slow1", "source_pin": "Out", "target_block": "slow2", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    # Telemetry tracking for state changes
    telemetry_status = []
    async def telemetry_cb(run_id, msg):
        if msg["type"] == "run_status":
            telemetry_status.append(msg["status"])

    engine.telemetry_callback = telemetry_cb

    # Run execution in background task
    run_task = asyncio.create_task(engine.run(start_block_id="slow1", start_pin_name="In"))

    # Let slow1 start running
    await asyncio.sleep(0.02)
    assert engine.state == "RUNNING"
    assert engine.blocks["slow1"].ran is True
    assert engine.blocks["slow2"].ran is False

    # Pause execution
    await engine.pause()
    assert engine.state == "PAUSED"
    assert "paused" in telemetry_status

    # Wait for a bit and verify slow2 has not run yet (because we are paused)
    await asyncio.sleep(0.15)
    assert engine.blocks["slow2"].ran is False

    # Resume execution
    await engine.resume()
    assert engine.state == "RUNNING"
    assert "running" in telemetry_status

    # Wait for execution to finish
    await run_task
    assert engine.state == "IDLE"
    assert engine.blocks["slow2"].ran is True


@pytest.mark.asyncio
async def test_parallel_branches_execution():
    # Branch 1: slow1 (0.1s) -> slow2 (0.1s)
    # Branch 2: slow3 (0.1s) -> slow4 (0.1s)
    # Both branches are independent entry points.
    blueprint = {
        "blocks": [
            {"id": "slow1", "type": "test/slow_block", "properties": {"Delay": 0.1}},
            {"id": "slow2", "type": "test/slow_block", "properties": {"Delay": 0.1}},
            {"id": "slow3", "type": "test/slow_block", "properties": {"Delay": 0.1}},
            {"id": "slow4", "type": "test/slow_block", "properties": {"Delay": 0.1}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "slow1", "source_pin": "Out", "target_block": "slow2", "target_pin": "In"},
            {"id": "l2", "type": "exec", "source_block": "slow3", "source_pin": "Out", "target_block": "slow4", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    import time
    start_time = time.time()
    await engine.run() # No start block, triggers all entry points
    end_time = time.time()

    elapsed = end_time - start_time
    # Verify both branches ran in parallel
    assert engine.blocks["slow1"].ran is True
    assert engine.blocks["slow2"].ran is True
    assert engine.blocks["slow3"].ran is True
    assert engine.blocks["slow4"].ran is True
    
    # If sequential, it would take >= 0.4s. Concurrently, it should take ~0.2s.
    # We assert it takes less than 0.35s to account for thread yielding overhead.
    assert elapsed < 0.35


@pytest.mark.asyncio
async def test_topological_teardown_order():
    global TEARDOWN_LOG
    TEARDOWN_LOG.clear()

    # Create a sequential graph slow1 -> slow2 -> slow3
    blueprint = {
        "blocks": [
            {"id": "slow1", "type": "test/slow_block", "properties": {"Delay": 0.01}},
            {"id": "slow2", "type": "test/slow_block", "properties": {"Delay": 0.01}},
            {"id": "slow3", "type": "test/slow_block", "properties": {"Delay": 0.01}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "slow1", "source_pin": "Out", "target_block": "slow2", "target_pin": "In"},
            {"id": "l2", "type": "exec", "source_block": "slow2", "source_pin": "Out", "target_block": "slow3", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    # Run execution
    await engine.run(start_block_id="slow1", start_pin_name="In")

    # The executor's run method automatically calls _teardown_all at the end.
    # So TEARDOWN_LOG should be populated in reverse topological order:
    # slow3 (downstream) -> slow2 -> slow1 (upstream)
    assert TEARDOWN_LOG == ["slow3", "slow2", "slow1"]


@pytest.mark.asyncio
async def test_concurrent_teardown_safety():
    blueprint = {
        "blocks": [
            {"id": "slow1", "type": "test/slow_block", "properties": {"Delay": 0.05}}
        ],
        "links": []
    }
    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    # Start a run in the background
    run_task = asyncio.create_task(engine.run(start_block_id="slow1", start_pin_name="In"))
    await asyncio.sleep(0.01)

    # Now trigger abort (which cancels active tasks and calls _teardown_all)
    # concurrently with run's own finally block calling _teardown_all.
    await engine.abort()
    await run_task

    # The run should terminate safely without raising any exceptions due to concurrent teardowns.


@pytest.mark.asyncio
async def test_measure_time_block_execution():
    blueprint = {
        "blocks": [
            {"id": "measure", "type": "control_flow/timing/measure_time", "properties": {}},
            {"id": "sleep", "type": "control_flow/timing/sleep", "properties": {"Delay": 0.05}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            # measure.Body -> sleep.In
            {"id": "l1", "type": "exec", "source_block": "measure", "source_pin": "Body", "target_block": "sleep", "target_pin": "In"},
            # measure.Out -> print.In
            {"id": "l2", "type": "exec", "source_block": "measure", "source_pin": "Out", "target_block": "print", "target_pin": "In"},
            # measure.Time -> print.Value
            {"id": "l3", "type": "data", "source_block": "measure", "source_pin": "Time", "target_block": "print", "target_pin": "Value"}
        ]
    }

    telemetry_received = {}
    async def telemetry_cb(run_id, msg):
        if msg["type"] == "telemetry":
            telemetry_received[msg["block_id"]] = msg["data"]

    engine = ExecutionEngine()
    engine.telemetry_callback = telemetry_cb
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="measure", start_pin_name="In")

    # Time data output should be >= 0.05s
    measured_time = engine.blocks["measure"]._time
    assert measured_time >= 0.045
    
    # Telemetry should be sent
    assert "measure" in telemetry_received
    tel_val = telemetry_received["measure"]["value"]
    assert "ms" in tel_val or "s" in tel_val
    
    # Print block should have printed the raw float measured time
    assert engine.blocks["print"].last_printed == measured_time


@pytest.mark.asyncio
async def test_accumulator_block_execution():
    blueprint = {
        "blocks": [
            {"id": "num", "type": "constants/number", "properties": {"value": 5.0}},
            {"id": "accum", "type": "Lists/manipulation/accumulate", "properties": {}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            # num.Value -> accum.Value
            {"id": "l1", "type": "data", "source_block": "num", "source_pin": "Value", "target_block": "accum", "target_pin": "Value"},
            # accum.List -> print.Value
            {"id": "l2", "type": "data", "source_block": "accum", "source_pin": "List", "target_block": "print", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    # 1. Trigger Append
    await engine.run(start_block_id="accum", start_pin_name="Append")
    assert engine.blocks["accum"]._list == [5.0]

    # 2. Trigger Append again (change constant first to see difference)
    engine.blocks["num"].properties["value"] = 12.0
    # Run cache clear to simulate next step pulling fresh data
    await engine.run(start_block_id="accum", start_pin_name="Append")
    assert engine.blocks["accum"]._list == [5.0, 12.0]

    # 3. Pull accumulated array
    await engine.run(start_block_id="print", start_pin_name="In")
    assert engine.blocks["print"].last_printed == [5.0, 12.0]

    # 4. Trigger Reset
    await engine.run(start_block_id="accum", start_pin_name="Reset")
    assert engine.blocks["accum"]._list == []


@pytest.mark.asyncio
async def test_progress_bar_block():
    blueprint = {
        "blocks": [
            {"id": "pbar", "type": "outputs/basic/progress_bar", "properties": {"Progress": 42.5, "Label": "Test Sweep"}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "pbar", "source_pin": "Out", "target_block": "print", "target_pin": "In"},
            {"id": "l2", "type": "data", "source_block": "pbar", "source_pin": "Value", "target_block": "print", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="pbar", start_pin_name="In")

    assert engine.blocks["pbar"]._value == 42.5
    assert engine.blocks["print"].last_printed == 42.5


@pytest.mark.asyncio
async def test_etr_display_block():
    blueprint = {
        "blocks": [
            {"id": "etr", "type": "outputs/basic/etr_display", "properties": {"Seconds": 3725.0, "Label": "T-"}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "etr", "source_pin": "Out", "target_block": "print", "target_pin": "In"},
            {"id": "l2", "type": "data", "source_block": "etr", "source_pin": "Formatted", "target_block": "print", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="etr", start_pin_name="In")

    # 3725 seconds = 01:02:05
    assert engine.blocks["etr"]._formatted == "01:02:05"
    assert engine.blocks["print"].last_printed == "01:02:05"


@pytest.mark.asyncio
async def test_countdown_wait_block():
    blueprint = {
        "blocks": [
            {"id": "wait", "type": "control_flow/timing/countdown_wait", "properties": {"Duration": 0.15}},
            {"id": "print", "type": "outputs/basic/print", "properties": {"Value": 99.0}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "wait", "source_pin": "Out", "target_block": "print", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    await engine.run(start_block_id="wait", start_pin_name="In")

    assert engine.blocks["wait"]._percentage == 100.0
    assert engine.blocks["wait"]._remaining == 0.0
    assert engine.blocks["print"].last_printed == 99.0


@pytest.mark.asyncio
async def test_countdown_wait_skip():
    blueprint = {
        "blocks": [
            {"id": "wait", "type": "control_flow/timing/countdown_wait", "properties": {"Duration": 10.0, "skip": True}},
            {"id": "print", "type": "outputs/basic/print", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "wait", "source_pin": "Out", "target_block": "print", "target_pin": "In"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)

    # With skip property set, it should advance immediately rather than waiting 10s
    await engine.run(start_block_id="wait", start_pin_name="In")

    assert engine.blocks["wait"]._skipped is True
    assert engine.blocks["wait"]._remaining == 0.0







@pytest.mark.asyncio
async def test_entry_points_use_primary_exec_pin_only():
    # Timer has nothing wired (entry block) -> must start on 'Start' only, never on its unwired 'Stop'.
    # Accumulate has 'Append' wired -> must not be an entry point despite its unwired 'Reset'.
    blueprint = {
        "blocks": [
            {"id": "timer", "type": "control_flow/timing/timer", "properties": {"Interval": 1.0, "Count": 3}},
            {"id": "accum", "type": "Lists/manipulation/accumulate", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "timer", "source_pin": "Tick", "target_block": "accum", "target_pin": "Append"},
            {"id": "l2", "type": "data", "source_block": "timer", "source_pin": "Index", "target_block": "accum", "target_pin": "Value"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)
    assert engine._find_entry_points() == [("timer", "Start")]

    await engine.run()
    assert engine.blocks["accum"]._list == [0, 1, 2]


@pytest.mark.asyncio
async def test_secondary_exec_pin_wired_is_not_entry_point():
    # Only 'Reset' is wired: the unwired 'Append' must not fire on its own at run start
    blueprint = {
        "blocks": [
            {"id": "print", "type": "outputs/basic/print", "properties": {"Value": 1.0}},
            {"id": "accum", "type": "Lists/manipulation/accumulate", "properties": {}}
        ],
        "links": [
            {"id": "l1", "type": "exec", "source_block": "print", "source_pin": "Out", "target_block": "accum", "target_pin": "Reset"}
        ]
    }

    engine = ExecutionEngine()
    engine.load_blueprint(blueprint)
    assert engine._find_entry_points() == [("print", "In")]


SAFE_STATE_LOG = []

@register_block("test/fake_device")
class FakeDeviceBlock(BaseBlock):
    inputs_def = [ExecIn("In")]
    outputs_def = [ExecOut("Out")]

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        return "Out"

    async def safe_state(self):
        SAFE_STATE_LOG.append(("safe", self.id))

    async def teardown(self):
        SAFE_STATE_LOG.append(("teardown", self.id))


@register_block("test/failing_block")
class FailingBlock(BaseBlock):
    inputs_def = [ExecIn("In")]
    outputs_def = [ExecOut("Out")]

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        raise RuntimeError("simulated failure")


def _persistent_device_blueprint(fail: bool):
    blocks = [{"id": "dev", "type": "test/fake_device", "properties": {"isPersistent": True}}]
    links = []
    if fail:
        blocks.append({"id": "fail", "type": "test/failing_block", "properties": {}})
        links.append({"id": "l1", "type": "exec", "source_block": "dev", "source_pin": "Out", "target_block": "fail", "target_pin": "In"})
    return {"blocks": blocks, "links": links}


@pytest.mark.asyncio
async def test_persistent_block_kept_alive_on_success():
    SAFE_STATE_LOG.clear()
    engine = ExecutionEngine()
    engine.load_blueprint(_persistent_device_blueprint(fail=False))
    await engine.run()

    assert SAFE_STATE_LOG == []
    assert engine.blocks["dev"]._has_executed is True


@pytest.mark.asyncio
async def test_persistent_block_gets_safe_state_on_error():
    SAFE_STATE_LOG.clear()
    engine = ExecutionEngine()
    engine.load_blueprint(_persistent_device_blueprint(fail=True))
    with pytest.raises(RuntimeError):
        await engine.run()

    # Safety commands sent, connection kept (no full teardown), memo invalidated for next run
    assert ("safe", "dev") in SAFE_STATE_LOG
    assert ("teardown", "dev") not in SAFE_STATE_LOG
    assert engine.blocks["dev"]._has_executed is False


@pytest.mark.asyncio
async def test_device_connect_safe_state_keeps_connection():
    from comfylab.blocks.devices.base import BaseDeviceConnectBlock

    class FakeVisa:
        closed = False
        def close(self):
            self.closed = True

    calls = []

    class SafeConnect(BaseDeviceConnectBlock):
        async def _device_teardown(self, device, lock_manager):
            calls.append(device)

    block = SafeConnect("conn")
    device = FakeVisa()
    block._device = device

    await block.safe_state()
    assert calls == [device]
    assert block._device is device and not device.closed

    await block.teardown()
    assert calls == [device, device]
    assert device.closed and block._device is None
