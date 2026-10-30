from compiler.pipeline import compile_and_run


def test_constant_folding_reduces_arithmetic():
    r = compile_and_run("MAKE $x = 10 + 20 * 2!\nSAY $x!")
    assert r["errors"] == []
    assert r["output"] == ["50"]
    assert any("constant folded" in n for n in r["optimizer_notes"])


def test_constant_propagation():
    r = compile_and_run("MAKE $x = 10!\nMAKE $y = $x + 5!\nSAY $y!")
    assert r["output"] == ["15"]


def test_dead_store_elimination_drops_overwritten_assignment():
    r = compile_and_run("MAKE $x = 10!\n$x = 20!\nSAY $x!")
    assert r["output"] == ["20"]
    assert any("dead store eliminated" in n for n in r["optimizer_notes"])


def test_algebraic_simplification_plus_zero():
    # use a function param (dynamically typed / not a known constant) so this
    # exercises the algebraic-simplify pass rather than being fully folded away
    r = compile_and_run("FUNC f(n) { RETURN n + 0! }\nSAY f(5)!")
    assert r["output"] == ["5"]
    assert any("simplified" in n for n in r["optimizer_notes"])


def test_optimized_ir_is_shorter_or_equal():
    r = compile_and_run("MAKE $x = 10 + 20 * 2!\nSAY $x!")
    assert len(r["ir_after"]) <= len(r["ir_before"])
