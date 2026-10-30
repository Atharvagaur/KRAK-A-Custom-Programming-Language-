from compiler.ir.cfg import build_cfg
from compiler.ir.instructions import IRConst, IRFuncBegin, IRFuncEnd, IRJump, IRJumpIfFalse, IRLabel, IRReturn


def test_cfg_splits_conditional_and_tracks_true_false_edges():
    code = [IRConst("c", True), IRJumpIfFalse("c", "else"), IRConst("x", 1),
            IRJump("end"), IRLabel("else"), IRConst("x", 2), IRLabel("end"), IRReturn(None)]
    graph = build_cfg(code)
    branch = graph.blocks[0]
    assert {edge["kind"] for edge in branch.successors} == {"true", "false"}
    assert graph.instruction_to_block["0"] == branch.id
    assert graph.validate()


def test_cfg_loop_backedge_and_function_entries_are_independent():
    code = [IRLabel("loop"), IRJumpIfFalse("c", "done"), IRJump("loop"),
            IRLabel("done"), IRFuncBegin("f", ["p"]), IRLabel("entry"),
            IRReturn("p"), IRFuncEnd("f")]
    graph = build_cfg(code)
    main = graph.functions["__main__"]
    fn = graph.functions["f"]
    assert main["entry"] != fn["entry"]
    assert any(edge["target"] == main["entry"] for block in graph.blocks for edge in block.successors)
    assert next(block for block in graph.blocks if block.id == fn["entry"]).entry


def test_cfg_rejects_dangling_jump_targets():
    try:
        build_cfg([IRJump("missing")])
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        assert False, "dangling jump should be rejected"
