"""KRAK recursive-descent parser: tokens -> AST."""

from phases.phase1_lexical_analysis.tokens import (
    MAKE, WHEN, OTHERWISE, REPEAT, FUNC, RETURN, SAY,
    IDENTIFIER, NUMBER, STRING,
    PLUS, MINUS, STAR, SLASH,
    ASSIGN, EQUAL, NOT_EQUAL, LESS, GREATER, LESS_EQUAL, GREATER_EQUAL,
    LPAREN, RPAREN, LBRACE, RBRACE, COMMA, LBRACKET, RBRACKET,
    STATEMENT_END, EOF,
)
from phases.phase2_parsing.nodes import (
    Program, VarDecl, Assign, PrintStatement, IfStatement, WhileStatement,
    FunctionDeclaration, ReturnStatement, CallExpression,
    BinaryExpression, UnaryExpression, Literal, Identifier, ArrayLiteral, IndexExpression, IndexAssign,
)
from phases.phase0_common.errors import SyntaxError_


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ---- token stream helpers ----
    def _peek(self, offset=0):
        i = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[i]

    def _advance(self):
        tok = self.tokens[self.pos]
        if tok.type != EOF:
            self.pos += 1
        return tok

    def _check(self, type_):
        return self._peek().type == type_

    def _match(self, *types):
        if self._peek().type in types:
            return self._advance()
        return None

    def _expect(self, type_, what):
        tok = self._peek()
        if tok.type != type_:
            raise SyntaxError_(f"Expected {what}, got {tok.type} ({tok.value!r})", tok.line, tok.column)
        return self._advance()

    # ---- entry point ----
    def parse(self):
        statements = []
        while not self._check(EOF):
            statements.append(self._statement())
        return Program(statements=statements)

    # ---- statements ----
    def _block(self):
        self._expect(LBRACE, "'{'")
        stmts = []
        while not self._check(RBRACE) and not self._check(EOF):
            stmts.append(self._statement())
        self._expect(RBRACE, "'}'")
        return stmts

    def _statement(self):
        tok = self._peek()
        if tok.type == MAKE:
            return self._var_decl()
        if tok.type == SAY:
            return self._print_stmt()
        if tok.type == WHEN:
            return self._if_stmt()
        if tok.type == REPEAT:
            return self._while_stmt()
        if tok.type == FUNC:
            return self._func_decl()
        if tok.type == RETURN:
            return self._return_stmt()
        if tok.type == IDENTIFIER:
            # could be assignment ($x = ...) or a bare call statement (name(...)!)
            if self._peek(1).type == ASSIGN:
                return self._assignment()
            if self._peek(1).type == LBRACKET:
                return self._index_assignment()
            expr = self._expression()
            self._expect(STATEMENT_END, "'!'")
            return expr
        raise SyntaxError_(f"Unexpected token {tok.type} ({tok.value!r})", tok.line, tok.column)

    def _var_decl(self):
        line = self._peek().line
        self._advance()  # MAKE
        name = self._expect(IDENTIFIER, "identifier").value
        self._expect(ASSIGN, "'='")
        value = self._expression()
        self._expect(STATEMENT_END, "'!'")
        return VarDecl(name=name, value=value, line=line)

    def _assignment(self):
        tok = self._advance()  # IDENTIFIER
        self._expect(ASSIGN, "'='")
        value = self._expression()
        self._expect(STATEMENT_END, "'!'")
        return Assign(name=tok.value, value=value, line=tok.line)

    def _index_assignment(self):
        tok = self._advance()
        self._expect(LBRACKET, "'['")
        index = self._expression()
        self._expect(RBRACKET, "']'")
        self._expect(ASSIGN, "'='")
        value = self._expression()
        self._expect(STATEMENT_END, "'!'")
        return IndexAssign(array=Identifier(name=tok.value, line=tok.line), index=index, value=value, line=tok.line)

    def _print_stmt(self):
        line = self._peek().line
        self._advance()  # SAY
        value = self._expression()
        self._expect(STATEMENT_END, "'!'")
        return PrintStatement(value=value, line=line)

    def _if_stmt(self):
        line = self._peek().line
        self._advance()  # WHEN
        self._expect(LPAREN, "'('")
        cond = self._expression()
        self._expect(RPAREN, "')'")
        then_block = self._block()
        else_block = None
        if self._match(OTHERWISE):
            else_block = self._block()
        return IfStatement(condition=cond, then_block=then_block, else_block=else_block, line=line)

    def _while_stmt(self):
        line = self._peek().line
        self._advance()  # REPEAT
        self._expect(LPAREN, "'('")
        cond = self._expression()
        self._expect(RPAREN, "')'")
        body = self._block()
        return WhileStatement(condition=cond, body=body, line=line)

    def _func_decl(self):
        line = self._peek().line
        self._advance()  # FUNC
        name = self._expect(IDENTIFIER, "function name").value
        self._expect(LPAREN, "'('")
        params = []
        if not self._check(RPAREN):
            params.append(self._expect(IDENTIFIER, "parameter name").value)
            while self._match(COMMA):
                params.append(self._expect(IDENTIFIER, "parameter name").value)
        self._expect(RPAREN, "')'")
        body = self._block()
        return FunctionDeclaration(name=name, params=params, body=body, line=line)

    def _return_stmt(self):
        line = self._peek().line
        self._advance()  # RETURN
        value = None
        if not self._check(STATEMENT_END):
            value = self._expression()
        self._expect(STATEMENT_END, "'!'")
        return ReturnStatement(value=value, line=line)

    # ---- expressions (precedence climbing) ----
    def _expression(self):
        return self._equality()

    def _equality(self):
        expr = self._comparison()
        while self._check(EQUAL) or self._check(NOT_EQUAL):
            op = self._advance()
            right = self._comparison()
            expr = BinaryExpression(op=op.value, left=expr, right=right, line=op.line)
        return expr

    def _comparison(self):
        expr = self._term()
        while self._peek().type in (LESS, GREATER, LESS_EQUAL, GREATER_EQUAL):
            op = self._advance()
            right = self._term()
            expr = BinaryExpression(op=op.value, left=expr, right=right, line=op.line)
        return expr

    def _term(self):
        expr = self._factor()
        while self._peek().type in (PLUS, MINUS):
            op = self._advance()
            right = self._factor()
            expr = BinaryExpression(op=op.value, left=expr, right=right, line=op.line)
        return expr

    def _factor(self):
        expr = self._unary()
        while self._peek().type in (STAR, SLASH):
            op = self._advance()
            right = self._unary()
            expr = BinaryExpression(op=op.value, left=expr, right=right, line=op.line)
        return expr

    def _unary(self):
        if self._check(MINUS):
            op = self._advance()
            operand = self._unary()
            return UnaryExpression(op=op.value, operand=operand, line=op.line)
        return self._primary()

    def _primary(self):
        tok = self._peek()
        if tok.type == LBRACKET:
            self._advance()
            elements = []
            if not self._check(RBRACKET):
                elements.append(self._expression())
                while self._match(COMMA):
                    elements.append(self._expression())
            self._expect(RBRACKET, "']'")
            expr = ArrayLiteral(elements=elements, line=tok.line)
            while self._match(LBRACKET):
                index = self._expression()
                self._expect(RBRACKET, "']'")
                expr = IndexExpression(array=expr, index=index, line=tok.line)
            return expr
        if tok.type == NUMBER:
            self._advance()
            t = "FLOAT" if isinstance(tok.value, float) else "INT"
            return Literal(value=tok.value, type=t, line=tok.line)
        if tok.type == STRING:
            self._advance()
            return Literal(value=tok.value, type="STRING", line=tok.line)
        if tok.type == IDENTIFIER:
            # function call?
            if self._peek(1).type == LPAREN:
                return self._call_expression()
            self._advance()
            expr = Identifier(name=tok.value, line=tok.line)
            while self._match(LBRACKET):
                index = self._expression()
                self._expect(RBRACKET, "']'")
                expr = IndexExpression(array=expr, index=index, line=tok.line)
            return expr
        if tok.type == LPAREN:
            self._advance()
            expr = self._expression()
            self._expect(RPAREN, "')'")
            return expr
        raise SyntaxError_(f"Unexpected token {tok.type} ({tok.value!r}) in expression", tok.line, tok.column)

    def _call_expression(self):
        tok = self._advance()  # IDENTIFIER (function name)
        self._expect(LPAREN, "'('")
        args = []
        if not self._check(RPAREN):
            args.append(self._expression())
            while self._match(COMMA):
                args.append(self._expression())
        self._expect(RPAREN, "')'")
        return CallExpression(name=tok.value, args=args, line=tok.line)
