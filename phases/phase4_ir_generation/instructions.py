"""Three-address-code style IR instructions."""

from dataclasses import dataclass
from typing import Any, Optional


class IRInstr:
    def to_line(self):
        raise NotImplementedError

    def to_dict(self):
        return {"op": type(self).__name__, "text": self.to_line(), "line": getattr(self, "source_line", None)}


@dataclass
class IRConst(IRInstr):
    target: str
    value: Any

    def to_line(self):
        v = f'"{self.value}"' if isinstance(self.value, str) else self.value
        return f"{self.target} = {v}"


@dataclass
class IRCopy(IRInstr):
    target: str
    source: str

    def to_line(self):
        return f"{self.target} = {self.source}"


@dataclass
class IRBinOp(IRInstr):
    target: str
    op: str
    left: str
    right: str

    def to_line(self):
        return f"{self.target} = {self.left} {self.op} {self.right}"


@dataclass
class IRUnaryOp(IRInstr):
    target: str
    op: str
    operand: str

    def to_line(self):
        return f"{self.target} = {self.op}{self.operand}"


@dataclass
class IRStore(IRInstr):
    var: str
    source: str

    def to_line(self):
        return f"{self.var} = {self.source}"


@dataclass
class IRArray(IRInstr):
    target: str
    elements: list

    def to_line(self):
        return f"{self.target} = ARRAY [{', '.join(self.elements)}]"


@dataclass
class IRGetIndex(IRInstr):
    target: str
    array: str
    index: str

    def to_line(self):
        return f"{self.target} = {self.array}[{self.index}]"


@dataclass
class IRSetIndex(IRInstr):
    array: str
    index: str
    value: str

    def to_line(self):
        return f"{self.array}[{self.index}] = {self.value}"


@dataclass
class IRPrint(IRInstr):
    value: str

    def to_line(self):
        return f"PRINT {self.value}"


@dataclass
class IRLabel(IRInstr):
    name: str

    def to_line(self):
        return f"{self.name}:"


@dataclass
class IRJump(IRInstr):
    label: str

    def to_line(self):
        return f"GOTO {self.label}"


@dataclass
class IRJumpIfFalse(IRInstr):
    cond: str
    label: str

    def to_line(self):
        return f"IF_FALSE {self.cond} GOTO {self.label}"


@dataclass
class IRFuncBegin(IRInstr):
    name: str
    params: list

    def to_line(self):
        return f"FUNC {self.name}({', '.join(self.params)}):"


@dataclass
class IRFuncEnd(IRInstr):
    name: str

    def to_line(self):
        return f"END {self.name}"


@dataclass
class IRReturn(IRInstr):
    value: Optional[str]

    def to_line(self):
        return f"RETURN {self.value}" if self.value is not None else "RETURN"


@dataclass
class IRCall(IRInstr):
    target: Optional[str]
    name: str
    args: list

    def to_line(self):
        call = f"{self.name}({', '.join(self.args)})"
        return f"{self.target} = CALL {call}" if self.target else f"CALL {call}"
