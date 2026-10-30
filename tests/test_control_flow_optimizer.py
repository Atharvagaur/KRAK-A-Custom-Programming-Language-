from compiler.pipeline import compile_and_run, compile_source
from compiler.lexer.lexer import Lexer
from compiler.parser.parser import Parser
from compiler.ir.generator import IRGenerator
from compiler.optimizer.optimizer import Optimizer
from compiler.vm.virtual_machine import VirtualMachine
from compiler.ir.instructions import IRFuncBegin, IRFuncEnd, IRJump, IRLabel, IRReturn


def test_constant_branch_folding_removes_unreachable_alternative():
    source = 'MAKE $x = 1! WHEN ($x == 1) { SAY "sey"! } OTHERWISE { SAY "on"! }'
    result = compile_and_run(source)
    assert result["output"] == ["yes"]
    assert result["instruction_counts"]["blocks_after"] < result["instruction_counts"]["blocks_before"]
    assert any(r["pass"] == "constant branch folding" for r in result["optimizer_remarks"])


def test_changing_loop_condition_is_not_folded_from_initial_value():
    source = 'MAKE $i = 0! REPEAT ($i < 3) { $i = $i + 1! } SAY $i!'
    assert compile_and_run(source)["output"] == ["3"]


def test_dynamic_branch_merge_does_not_invent_constant():
    source = '''FUNC choose(n) {
        MAKE $x = 0!
        WHEN (n > 0) { $x = 1! } OTHERWISE { $x = 2! }
        RETURN $x!
    }
    SAY choose(1)!
    SAY choose(-1)!'''
    plain = compile_and_run(source, optimize=True, control_flow=False)
    control = compile_and_run(source, optimize=True, control_flow=True)
    assert control["output"] == plain["output"] == ["1", "2"]


def test_arrays_and_runtime_errors_preserve_observable_behavior():
    valid = 'MAKE $a = [1, 2]! $a[0] = 9! SAY $a[0]!'
    assert compile_and_run(valid, optimize=True, control_flow=False)["output"] == ["9"]
    assert compile_and_run(valid, optimize=True, control_flow=True)["output"] == ["9"]
    invalid = 'MAKE $a = [1]! SAY $a[3]!'
    optimized = compile_and_run(invalid, optimize=True, control_flow=True)
    plain = compile_and_run(invalid, optimize=False)
    assert optimized["errors"] and plain["errors"]
    assert optimized["errors"][0]["message"] == plain["errors"][0]["message"]


def test_optimizer_builds_correct_bytecode_to_cfg_map_and_is_stable():
    source = 'MAKE $x = 1! WHEN ($x == 1) { SAY $x! }'
    first, _, _ = compile_source(source)
    second, _, _ = compile_source(source)
    assert first["cfg_after"] == second["cfg_after"]
    mapping = first["bytecode_to_block"]["__main__"]
    assert mapping[0] is not None
    assert len(mapping) == len(first["bytecode"]["__main__"])


def test_reoptimizing_reaches_same_ir():
    source = 'MAKE $x = 1! WHEN ($x == 1) { SAY $x! } OTHERWISE { SAY 0! }'
    program = Parser(Lexer(source).tokenize()).parse()
    ir = IRGenerator().generate(program)
    once = Optimizer().optimize(ir)
    twice = Optimizer().optimize(once)
    assert [i.to_line() for i in once] == [i.to_line() for i in twice]


def test_vm_instruction_addresses_map_to_real_cfg_blocks():
    source = 'FUNC f(n) { RETURN n! } SAY f(2)!'
    compiled, chunks, functions = compile_source(source)
    vm = VirtualMachine(chunks, functions, tracing=True)
    while vm.state()["status"] not in ("halted", "error"):
        before = vm.state()["instruction_pointer"]
        state = vm.step()
        event = state["events"][-1]
        if event["chunk"] == before["chunk"] and event["ip"] == before["index"]:
            assert compiled["bytecode_to_block"][event["chunk"]][event["ip"]] is not None
    for name, instructions in compiled["bytecode"].items():
        assert len(compiled["bytecode_to_block"][name]) == len(instructions)
        assert all(block is not None for block in compiled["bytecode_to_block"][name])


def test_equal_constants_on_all_reachable_paths_are_propagated():
    source = '''FUNC choose(n) {
        MAKE $x = 0!
        WHEN (n > 0) { $x = 4! } OTHERWISE { $x = 4! }
        RETURN $x!
    }
    SAY choose(1)! SAY choose(-1)!'''
    old = compile_and_run(source, optimize=True, control_flow=False)
    new = compile_and_run(source, optimize=True, control_flow=True)
    assert old["output"] == new["output"] == ["4", "4"]
    assert any(r["pass"] == "global constant propagation" for r in new["optimizer_remarks"])


def test_jump_threading_keeps_function_label_scopes_separate():
    code = [IRJump("A"), IRLabel("A"), IRJump("B"), IRLabel("B"), IRJump("C"),
            IRLabel("C"), IRFuncBegin("f", []), IRLabel("B"), IRJump("D"),
            IRLabel("D"), IRReturn(None), IRFuncEnd("f")]
    optimized = Optimizer()._simplify_jumps(code)
    assert isinstance(optimized[0], IRJump) and optimized[0].label == "C"
