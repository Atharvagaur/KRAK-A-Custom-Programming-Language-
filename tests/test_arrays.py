from compiler.pipeline import compile_and_run


def test_array_literal_empty_and_print():
    r = compile_and_run("MAKE $a = [10, 20, 30] !\nMAKE $empty = []!\nSAY $a!")
    assert not r["errors"]
    assert r["output"] == ["[10, 20, 30]"]


def test_index_reads_and_variable_index():
    r = compile_and_run("MAKE $a = [10, 20, 30, 40]!\nMAKE $i = 2!\nSAY $a[0]!\nSAY $a[2]!\nSAY $a[3]!\nSAY $a[$i]!")
    assert not r["errors"]
    assert r["output"] == ["10", "30", "40", "30"]


def test_mutation_persists_and_index_in_expression():
    r = compile_and_run("MAKE $a = [10, 20, 30]!\n$a[1] = 99!\nSAY $a[0] + $a[1]!\nSAY $a!")
    assert not r["errors"]
    assert r["output"] == ["109", "[10, 99, 30]"]


def test_array_elements_can_be_variables_and_expressions():
    r = compile_and_run("MAKE $x = 4!\nMAKE $a = [$x, $x + 3, 2 * 5]!\nSAY $a!")
    assert not r["errors"]
    assert r["output"] == ["[4, 7, 10]"]


def test_bad_indices_and_non_array_report_runtime_errors():
    for source, text in [
        ("MAKE $a = [1]!\nSAY $a[-1]!", "negative"),
        ("MAKE $a = [1]!\nSAY $a[1]!", "out of bounds"),
        ("MAKE $x = 1!\nFUNC get(a, i) { RETURN a[i]! }\nSAY get(1, 0)!", "non-array"),
        ("MAKE $a = [1]!\nFUNC get(a, i) { RETURN a[i]! }\nSAY get($a, 0.5)!", "integer"),
    ]:
        r = compile_and_run(source)
        assert r["errors"]
        assert text in r["errors"][0]["message"].lower()


def test_array_in_loop_condition():
    r = compile_and_run("MAKE $a = [1, 2]!\nMAKE $i = 0!\nREPEAT ($i < 2) { SAY $a[$i]!\n$i = $i + 1! }")
    assert not r["errors"]
    assert r["output"] == ["1", "2"]


def test_array_argument_mutation_uses_shared_array():
    r = compile_and_run("MAKE $a = [1]!\nFUNC set(a) { a[0] = 8! }\nset($a)!\nSAY $a[0]!")
    assert not r["errors"]
    assert r["output"] == ["8"]
