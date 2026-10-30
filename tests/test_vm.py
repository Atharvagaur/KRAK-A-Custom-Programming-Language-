import pytest
from compiler.pipeline import compile_and_run


def test_simple_print():
    r = compile_and_run("MAKE $x = 10!\nSAY $x!")
    assert r["output"] == ["10"]


def test_arithmetic():
    r = compile_and_run("SAY 2 + 3 * 4!")
    assert r["output"] == ["14"]


def test_if_else_true_branch():
    r = compile_and_run('WHEN (5 > 2) { SAY "uoy"! } OTHERWISE { SAY "on"! }')
    assert r["output"] == ["you"]


def test_if_else_false_branch():
    r = compile_and_run('WHEN (1 > 2) { SAY "ouy"! } OTHERWISE { SAY "on"! }')
    assert r["output"] == ["no"]


def test_while_loop_counts():
    r = compile_and_run("MAKE $i = 0!\nREPEAT ($i < 3) { SAY $i!\n$i = $i + 1! }")
    assert r["output"] == ["0", "1", "2"]


def test_function_call_and_return():
    r = compile_and_run("FUNC add(a, b) { RETURN a + b! }\nSAY add(3, 4)!")
    assert r["output"] == ["7"]


def test_recursive_function():
    src = """
FUNC factorial(n) {
    WHEN (n <= 1) {
        RETURN 1!
    }
    RETURN n * factorial(n - 1)!
}
SAY factorial(5)!
"""
    r = compile_and_run(src)
    assert r["output"] == ["120"]


def test_division_by_zero_reports_runtime_error():
    r = compile_and_run("MAKE $x = 10!\nMAKE $y = 0!\nSAY $x / $y!")
    assert r["errors"]
    assert r["errors"][0]["kind"] == "Runtime Error"


def test_mirror_string_rule_end_to_end():
    r = compile_and_run('SAY "!dlroW olleH"!')
    assert r["output"] == ["Hello World!"]
