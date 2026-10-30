"""Backward-compat shim: re-exports from phases.phase6_bytecode_generation.instructions."""
from phases.phase6_bytecode_generation.instructions import (  # noqa: F401
    Instr, PUSH_CONST, LOAD, STORE, ADD, SUB, MUL, DIV, NEG,
    CMP_LT, CMP_GT, CMP_LE, CMP_GE, CMP_EQ, CMP_NEQ,
    JUMP, JUMP_IF_FALSE, PRINT, CALL, RETURN, POP, HALT,
    LABEL, FUNC_ENTRY, MAKE_ARRAY, GET_INDEX, SET_INDEX,
)
