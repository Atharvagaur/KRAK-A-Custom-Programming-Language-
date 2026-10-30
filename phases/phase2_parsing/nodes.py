"""AST node definitions for KRAK. Plain dataclasses -- the AST is the
central structure every later phase (semantic analysis, IR gen) walks."""

from dataclasses import dataclass, field
from typing import List, Optional, Any


class Node:
    def to_dict(self):
        """Recursively convert to a plain dict/list tree for JSON / UI display."""
        def conv(v):
            if isinstance(v, Node):
                return v.to_dict()
            if isinstance(v, list):
                return [conv(i) for i in v]
            return v
        d = {"node": type(self).__name__}
        for k, v in self.__dict__.items():
            d[k] = conv(v)
        return d


@dataclass
class Program(Node):
    statements: List[Any] = field(default_factory=list)


@dataclass
class VarDecl(Node):
    name: str
    value: Any
    line: int = 0


@dataclass
class Assign(Node):
    name: str
    value: Any
    line: int = 0


@dataclass
class IndexAssign(Node):
    array: Any
    index: Any
    value: Any
    line: int = 0


@dataclass
class PrintStatement(Node):
    value: Any
    line: int = 0


@dataclass
class IfStatement(Node):
    condition: Any
    then_block: List[Any]
    else_block: Optional[List[Any]] = None
    line: int = 0


@dataclass
class WhileStatement(Node):
    condition: Any
    body: List[Any]
    line: int = 0


@dataclass
class FunctionDeclaration(Node):
    name: str
    params: List[str]
    body: List[Any]
    line: int = 0


@dataclass
class ReturnStatement(Node):
    value: Optional[Any]
    line: int = 0


@dataclass
class CallExpression(Node):
    name: str
    args: List[Any]
    line: int = 0


@dataclass
class BinaryExpression(Node):
    op: str
    left: Any
    right: Any
    line: int = 0


@dataclass
class UnaryExpression(Node):
    op: str
    operand: Any
    line: int = 0


@dataclass
class Literal(Node):
    value: Any
    type: str  # INT | FLOAT | STRING | BOOL
    line: int = 0


@dataclass
class Identifier(Node):
    name: str
    line: int = 0


@dataclass
class ArrayLiteral(Node):
    elements: List[Any] = field(default_factory=list)
    line: int = 0


@dataclass
class IndexExpression(Node):
    array: Any
    index: Any
    line: int = 0
