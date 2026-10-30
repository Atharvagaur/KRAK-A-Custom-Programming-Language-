"""KRAK's (deliberately tiny) type system."""

INT = "INT"
FLOAT = "FLOAT"
STRING = "STRING"
BOOL = "BOOL"
ANY = "ANY"   # type of function parameters -- KRAK functions are untyped/dynamic

NUMERIC = {INT, FLOAT}

ARITH_OPS = {"+", "-", "*", "/"}
COMPARE_OPS = {"<", ">", "<=", ">="}
EQUALITY_OPS = {"==", "!="}


def result_type_of_binop(op, left_type, right_type):
    """Returns the resulting type of `left_type op right_type`, or raises ValueError."""
    # Function parameters are dynamically typed (ANY): defer all checking to runtime.
    if left_type == ANY or right_type == ANY:
        if op in ARITH_OPS:
            return ANY
        if op in COMPARE_OPS or op in EQUALITY_OPS:
            return BOOL

    if op in ARITH_OPS:
        if op == "+" and left_type == STRING and right_type == STRING:
            return STRING
        if left_type in NUMERIC and right_type in NUMERIC:
            return FLOAT if (left_type == FLOAT or right_type == FLOAT) else INT
        raise ValueError(f"Cannot apply '{op}' to {left_type} and {right_type}")

    if op in COMPARE_OPS:
        if left_type in NUMERIC and right_type in NUMERIC:
            return BOOL
        raise ValueError(f"Cannot compare {left_type} and {right_type} with '{op}'")

    if op in EQUALITY_OPS:
        if left_type == right_type or (left_type in NUMERIC and right_type in NUMERIC):
            return BOOL
        raise ValueError(f"Cannot compare {left_type} and {right_type} with '{op}'")

    raise ValueError(f"Unknown operator '{op}'")
