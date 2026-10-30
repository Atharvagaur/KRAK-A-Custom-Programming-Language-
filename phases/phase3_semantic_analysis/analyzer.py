"""Semantic analysis: does the (syntactically valid) program make sense?

Checks performed:
  - variable used before declaration -> SemanticError
  - variable redeclared in same scope -> SemanticError
  - type mismatches in expressions / reassignment -> KrakTypeError
  - calling an undefined function / wrong arg count -> SemanticError
  - RETURN outside a function -> SemanticError
"""

from phases.phase2_parsing.nodes import (
    Program, VarDecl, Assign, IndexAssign, IndexExpression, ArrayLiteral, PrintStatement, IfStatement, WhileStatement,
    FunctionDeclaration, ReturnStatement, CallExpression,
    BinaryExpression, UnaryExpression, Literal, Identifier,
)
from .symbol_table import SymbolTable
from phases.phase0_common.types import result_type_of_binop, NUMERIC
from phases.phase0_common.errors import SemanticError, KrakTypeError


class SemanticAnalyzer:
    def __init__(self):
        self.symtab = SymbolTable()
        self._in_function = 0

    def analyze(self, program: Program):
        for stmt in program.statements:
            self._statement(stmt)
        return self.symtab

    # ---- statements ----
    def _statement(self, node):
        if isinstance(node, VarDecl):
            self._var_decl(node)
        elif isinstance(node, Assign):
            self._assign(node)
        elif isinstance(node, IndexAssign):
            at = self._expr_type(node.array)
            if at not in ("ARRAY", "ANY"):
                raise KrakTypeError(f"Cannot index value of type {at}", node.line)
            it = self._expr_type(node.index)
            if it != "INT":
                raise KrakTypeError("Array index must be INT", node.line)
            self._expr_type(node.value)
        elif isinstance(node, PrintStatement):
            self._expr_type(node.value)
        elif isinstance(node, IfStatement):
            self._if_stmt(node)
        elif isinstance(node, WhileStatement):
            self._while_stmt(node)
        elif isinstance(node, FunctionDeclaration):
            self._func_decl(node)
        elif isinstance(node, ReturnStatement):
            self._return_stmt(node)
        elif isinstance(node, CallExpression):
            self._expr_type(node)  # bare call statement
        else:
            raise SemanticError(f"Unknown statement node {type(node).__name__}")

    def _var_decl(self, node: VarDecl):
        if self.symtab.is_declared_in_current_scope(node.name):
            raise SemanticError(f"Variable '{node.name}' is already declared", node.line)
        t = self._expr_type(node.value)
        self.symtab.declare(node.name, t)

    def _assign(self, node: Assign):
        sym = self.symtab.lookup(node.name)
        if sym is None:
            raise SemanticError(f"Variable '{node.name}' is not defined", node.line)
        t = self._expr_type(node.value)
        if t != sym.type and not (t in NUMERIC and sym.type in NUMERIC):
            raise KrakTypeError(
                f"Cannot assign {t} to '{node.name}' which was declared as {sym.type}", node.line
            )
        if sym.type in NUMERIC and t in NUMERIC:
            sym.type = "FLOAT" if (sym.type == "FLOAT" or t == "FLOAT") else "INT"

    def _if_stmt(self, node: IfStatement):
        cond_t = self._expr_type(node.condition)
        if cond_t != "BOOL":
            raise KrakTypeError("WHEN condition must be BOOL", node.line)
        self.symtab.push_scope()
        for s in node.then_block:
            self._statement(s)
        self.symtab.pop_scope()
        if node.else_block is not None:
            self.symtab.push_scope()
            for s in node.else_block:
                self._statement(s)
            self.symtab.pop_scope()

    def _while_stmt(self, node: WhileStatement):
        cond_t = self._expr_type(node.condition)
        if cond_t != "BOOL":
            raise KrakTypeError("REPEAT condition must be BOOL", node.line)
        self.symtab.push_scope()
        for s in node.body:
            self._statement(s)
        self.symtab.pop_scope()

    def _func_decl(self, node: FunctionDeclaration):
        self.symtab.declare_function(node.name, node.params)
        self.symtab.push_scope()
        for p in node.params:
            self.symtab.declare(p, "ANY")
        self._in_function += 1
        for s in node.body:
            self._statement(s)
        self._in_function -= 1
        self.symtab.pop_scope()

    def _return_stmt(self, node: ReturnStatement):
        if self._in_function == 0:
            raise SemanticError("RETURN used outside of a function", node.line)
        if node.value is not None:
            self._expr_type(node.value)

    # ---- expressions ----
    def _expr_type(self, node):
        if isinstance(node, Literal):
            return node.type
        if isinstance(node, ArrayLiteral):
            for element in node.elements:
                self._expr_type(element)
            return "ARRAY"
        if isinstance(node, IndexExpression):
            at = self._expr_type(node.array)
            if at not in ("ARRAY", "ANY"):
                raise KrakTypeError(f"Cannot index value of type {at}", node.line)
            it = self._expr_type(node.index)
            if it != "INT" and it != "ANY":
                raise KrakTypeError("Array index must be INT", node.line)
            return "ANY"
        if isinstance(node, Identifier):
            sym = self.symtab.lookup(node.name)
            if sym is None:
                raise SemanticError(f"Variable '{node.name}' is not defined", node.line)
            return sym.type
        if isinstance(node, UnaryExpression):
            t = self._expr_type(node.operand)
            if node.op == "-" and t not in NUMERIC:
                raise KrakTypeError(f"Cannot apply unary '-' to {t}", node.line)
            return t
        if isinstance(node, BinaryExpression):
            lt = self._expr_type(node.left)
            rt = self._expr_type(node.right)
            try:
                return result_type_of_binop(node.op, lt, rt)
            except ValueError as e:
                raise KrakTypeError(str(e), node.line)
        if isinstance(node, CallExpression):
            fn = self.symtab.lookup_function(node.name)
            if fn is None:
                raise SemanticError(f"Function '{node.name}' is not defined", node.line)
            if len(fn.params) != len(node.args):
                raise SemanticError(
                    f"Function '{node.name}' expects {len(fn.params)} argument(s), got {len(node.args)}",
                    node.line,
                )
            for a in node.args:
                self._expr_type(a)
            return "ANY"
        raise SemanticError(f"Unknown expression node {type(node).__name__}")
