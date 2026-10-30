from compiler.pipeline import compile_and_run, compile_source
from compiler.vm.virtual_machine import VirtualMachine


def make_vm(source):
    compiled, chunks, functions = compile_source(source)
    assert not compiled["errors"]
    return VirtualMachine(chunks, functions, tracing=True), compiled


def finish(vm):
    while vm.status not in ("halted", "error"):
        vm.step()
    return vm.state()


def test_step_tracks_stack_ip_and_rewinds_exactly():
    source = "SAY 10 + 20!"
    vm, compiled = make_vm(source)
    before = vm.state()
    after_one = vm.step()
    assert after_one["step"] == 1
    assert after_one["stack"] == [10]
    assert after_one["instruction_pointer"]["index"] == 1
    vm.back()
    assert vm.state() == before
    replayed = vm.step()
    assert replayed["stack"] == after_one["stack"]
    assert replayed["instruction_pointer"] == after_one["instruction_pointer"]
    final = finish(vm)
    assert final["output"] == compile_and_run(source)["output"] == ["30"]
    assert compiled["bytecode"]["__main__"][0]["line"] == 1


def test_rewind_restores_mutable_arrays_and_output():
    source = "MAKE $a = [1, 2]!\n$a[0] = 9!\nSAY $a!"
    vm, _ = make_vm(source)
    while not (vm.state()["current_instruction"] or {}).get("op") == "PRINT":
        vm.step()
    before_print = vm.state()
    while vm.status not in ("halted", "error"):
        vm.step()
    assert vm.output == ["[9, 2]"]
    vm.back()  # HALT
    vm.back()  # PRINT
    assert vm.output == []
    assert vm.state()["variables"]["$a"] == [9, 2]
    while vm.status not in ("halted", "error"):
        vm.step()
    assert vm.output == ["[9, 2]"]
    assert before_print["step"] < vm.state()["step"]


def test_branch_loop_and_backward_jump_match_normal_vm():
    source = "MAKE $i = 0!\nREPEAT ($i < 3) { WHEN ($i == 1) { SAY 7! } OTHERWISE { SAY $i! }\n$i = $i + 1! }"
    vm, _ = make_vm(source)
    final = finish(vm)
    assert final["output"] == compile_and_run(source)["output"] == ["0", "7", "2"]
    assert any(event["kind"] == "jump" for event in final["events"])
    assert final["status"] == "halted"
    for _ in range(final["step"]):
        vm.back()
    assert vm.state()["step"] == 0 and vm.state()["output"] == []
    assert finish(vm)["output"] == ["0", "7", "2"]


def test_function_and_recursive_frames_match_normal_vm():
    source = "FUNC fact(n) { WHEN (n <= 1) { RETURN 1! } RETURN n * fact(n - 1)! }\nSAY fact(5)!"
    vm, _ = make_vm(source)
    max_frames = 0
    while vm.status not in ("halted", "error"):
        state = vm.step()
        max_frames = max(max_frames, len(state["frames"]))
    assert vm.output == compile_and_run(source)["output"] == ["120"]
    assert max_frames >= 5
    assert vm.state()["frames"][0]["function"] == "__main__"


def test_runtime_error_is_recorded_and_can_be_rewound():
    source = "SAY 1 / 0!"
    vm, _ = make_vm(source)
    final = finish(vm)
    assert final["status"] == "error"
    assert "Division by zero" in final["error"]["message"]
    vm.back()
    assert vm.state()["status"] == "paused"
    assert vm.state()["error"] is None
    assert vm.state()["instruction_pointer"]["index"] == final["events"][-1]["ip"]


def test_reset_replays_from_initial_state():
    source = "MAKE $x = 3!\nSAY $x!"
    vm, _ = make_vm(source)
    first = finish(vm)
    assert first["output"] == ["3"]
    state = vm.reset()
    assert state["step"] == 0 and state["status"] == "ready" and state["output"] == []
    second = finish(vm)
    assert second["output"] == first["output"]
    assert second["step"] == first["step"]


def test_normal_execution_does_not_use_debugger_history_limit():
    source = "\n".join("SAY 1!" for _ in range(550))
    result = compile_and_run(source)
    assert not result["errors"]
    assert len(result["output"]) == 550


def test_event_history_pages_and_historical_inspection():
    vm, _ = make_vm("\n".join("SAY 1!" for _ in range(90)))
    state = vm.run_to_end(max_steps=400)
    first_page = vm.events_before(before=state["history_start"] + 1, limit=100)
    assert len(first_page["events"]) == 100
    assert first_page["events"][0]["step"] == 62
    historical = vm.inspect(2)
    assert historical["step"] == 2
    assert historical["output"] == []
    assert vm.state()["step"] == state["step"]


def test_batched_play_can_pause_and_resume_without_losing_state():
    source = "MAKE $i = 0!\nREPEAT ($i < 5) { SAY $i!\n$i = $i + 1! }"
    vm, _ = make_vm(source)
    paused = vm.run_to_end(max_steps=9)
    assert paused["status"] == "paused"
    pause_step = paused["step"]
    resumed = finish(vm)
    assert resumed["step"] > pause_step
    assert resumed["output"] == compile_and_run(source)["output"] == ["0", "1", "2", "3", "4"]


def test_debug_api_compiles_without_running_then_supports_controls():
    import pytest
    pytest.importorskip("flask")
    from web.app import app

    client = app.test_client()
    source = "MAKE $x = 4!\nSAY $x + 1!"
    response = client.post("/api/debug/start", json={"source": source})
    assert response.status_code == 200
    data = response.get_json()
    session = data["session_id"]
    assert data["state"]["status"] == "ready"
    assert data["state"]["output"] == []
    assert data["compile"]["stage_reached"] == "bytecode"
    stepped = client.post(f"/api/debug/{session}/step").get_json()
    assert stepped["step"] == 1
    rewound = client.post(f"/api/debug/{session}/back").get_json()
    assert rewound["step"] == 0
    ran = client.post(f"/api/debug/{session}/run").get_json()
    assert ran["output"] == compile_and_run(source)["output"]
    reset = client.post(f"/api/debug/{session}/reset").get_json()
    assert reset["status"] == "ready" and reset["output"] == []
    client.delete(f"/api/debug/{session}")
