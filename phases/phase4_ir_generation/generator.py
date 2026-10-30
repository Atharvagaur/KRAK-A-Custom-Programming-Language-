"""Translates the AST into linear three-address-code IR."""

from phases.phase2_parsing.nodes import (
    VarDecl, Assign, IndexAssign, IndexExpression, ArrayLiteral, PrintStatement, IfStatement, WhileStatement,
    FunctionDeclaration, ReturnStatement, CallExpression,
    BinaryExpression, UnaryExpression, Literal, Identifier,
)
from .instructions import (
    IRConst, IRCopy, IRBinOp, IRUnaryOp, IRPrint, IRLabel,
    IRJump, IRJumpIfFalse, IRFuncBegin, IRFuncEnd, IRReturn, IRCall,
    IRArray, IRGetIndex, IRSetIndex,
)


class IRGenerator:
    def __init__(self):
        self.code = []
        self._temp_count = 0
        self._label_count = 0
        self._source_line = None

    def _new_temp(self):
        self._temp_count += 1
        return f"t{self._temp_count}"

    def _new_label(self, hint):
        self._label_count += 1
        return f"L{self._label_count}_{hint}"

    def _emit(self, instr):
        instr.source_line = self._source_line
        self.code.append(instr)

    # ---- entry point ----
    def generate(self, program):
        main_stmts = [s for s in program.statements if not isinstance(s, FunctionDeclaration)]
        funcs = [s for s in program.statements if isinstance(s, FunctionDeclaration)]

        for stmt in main_stmts:
            self._statement(stmt)
        for fn in funcs:
            self._function(fn)
        return self.code

    # ---- statements ----
    def _statement(self, node):
        previous_line = self._source_line
        self._source_line = getattr(node, "line", None)
        if isinstance(node, VarDecl):
            val = self._expr(node.value)
            self._emit(IRCopy(target=node.name, source=val))
        elif isinstance(node, Assign):
            val = self._expr(node.value)
            self._emit(IRCopy(target=node.name, source=val))
        elif isinstance(node, IndexAssign):
            self._emit(IRSetIndex(array=self._expr(node.array), index=self._expr(node.index), value=self._expr(node.value)))
        elif isinstance(node, PrintStatement):
            val = self._expr(node.value)
            self._emit(IRPrint(value=val))
        elif isinstance(node, IfStatement):
            self._if_stmt(node)
        elif isinstance(node, WhileStatement):
            self._while_stmt(node)
        elif isinstance(node, ReturnStatement):
            val = self._expr(node.value) if node.value is not None else None
            self._emit(IRReturn(value=val))
        elif isinstance(node, CallExpression):
            self._expr(node)  # bare call, discard result
        else:
            raise NotImplementedError(f"IR gen: unsupported statement {type(node).__name__}")
        self._source_line = previous_line

    def _if_stmt(self, node: IfStatement):
        cond = self._expr(node.condition)
        else_label = self._new_label("else")
        end_label = self._new_label("endif")
        self._emit(IRJumpIfFalse(cond=cond, label=else_label))
        for s in node.then_block:
            self._statement(s)
        if node.else_block:
            self._emit(IRJump(label=end_label))
            self._emit(IRLabel(name=else_label))
            for s in node.else_block:
                self._statement(s)
            self._emit(IRLabel(name=end_label))
        else:
            self._emit(IRLabel(name=else_label))

    def _while_stmt(self, node: WhileStatement):
        start_label = self._new_label("loop")
        end_label = self._new_label("endloop")
        self._emit(IRLabel(name=start_label))
        cond = self._expr(node.condition)
        self._emit(IRJumpIfFalse(cond=cond, label=end_label))
        for s in node.body:
            self._statement(s)
        self._emit(IRJump(label=start_label))
        self._emit(IRLabel(name=end_label))

    def _function(self, node: FunctionDeclaration):
        self._emit(IRFuncBegin(name=node.name, params=node.params))
        for s in node.body:
            self._statement(s)
        self._emit(IRFuncEnd(name=node.name))

    # ---- expressions: return the "place" (temp/var/const-name) holding the value ----
    def _expr(self, node):
        if isinstance(node, Literal):
            t = self._new_temp()
            self._emit(IRConst(target=t, value=node.value))
            return t
        if isinstance(node, ArrayLiteral):
            elements = [self._expr(e) for e in node.elements]
            t = self._new_temp()
            self._emit(IRArray(target=t, elements=elements))
            return t
        if isinstance(node, IndexExpression):
            array, index = self._expr(node.array), self._expr(node.index)
            t = self._new_temp()
            self._emit(IRGetIndex(target=t, array=array, index=index))
            return t
        if isinstance(node, Identifier):
            return node.name
        if isinstance(node, UnaryExpression):
            operand = self._expr(node.operand)
            t = self._new_temp()
            self._emit(IRUnaryOp(target=t, op=node.op, operand=operand))
            return t
        if isinstance(node, BinaryExpression):
            left = self._expr(node.left)
            right = self._expr(node.right)
            t = self._new_temp()
            self._emit(IRBinOp(target=t, op=node.op, left=left, right=right))
            return t
        if isinstance(node, CallExpression):
            args = [self._expr(a) for a in node.args]
            t = self._new_temp()
            self._emit(IRCall(target=t, name=node.name, args=args))
            return t
        raise NotImplementedError(f"IR gen: unsupported expression {type(node).__name__}")
