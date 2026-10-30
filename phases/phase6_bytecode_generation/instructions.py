"""KRAK bytecode -- our own tiny instruction set for the stack VM."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Instr:
    op: str
    arg: Any = None
    source_line: Optional[int] = None
    ir_index: Optional[int] = None

    def to_line(self):
        return f"{self.op} {self.arg}" if self.arg is not None else self.op

    def to_dict(self):
        return {"op": self.op, "arg": self.arg, "line": self.source_line,
                "ir_index": self.ir_index}


# Opcode name constants (for readability at call sites)
PUSH_CONST = "PUSH_CONST"
LOAD = "LOAD"
STORE = "STORE"
ADD = "ADD"
SUB = "SUB"
MUL = "MUL"
DIV = "DIV"
NEG = "NEG"
CMP_LT = "CMP_LT"
CMP_GT = "CMP_GT"
CMP_LE = "CMP_LE"
CMP_GE = "CMP_GE"
CMP_EQ = "CMP_EQ"
CMP_NEQ = "CMP_NEQ"
JUMP = "JUMP"
JUMP_IF_FALSE = "JUMP_IF_FALSE"
PRINT = "PRINT"
CALL = "CALL"
RETURN = "RETURN"
POP = "POP"
LABEL = "LABEL"     # resolved away before execution, kept for display
FUNC_ENTRY = "FUNC_ENTRY"
HALT = "HALT"
MAKE_ARRAY = "MAKE_ARRAY"
GET_INDEX = "GET_INDEX"
SET_INDEX = "SET_INDEX"
