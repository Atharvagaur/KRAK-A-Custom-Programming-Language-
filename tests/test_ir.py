from compiler.lexer.lexer import Lexer
from compiler.parser.parser import Parser
from compiler.ir.generator import IRGenerator
from compiler.ir.instructions import IRConst, IRCopy, IRBinOp, IRPrint


def gen_ir(source):
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    return IRGenerator().generate(prog)


def test_simple_declaration_generates_const_and_copy():
    code = gen_ir("MAKE $x = 10!")
    assert isinstance(code[0], IRConst)
    assert code[0].value == 10
    assert isinstance(code[1], IRCopy)
    assert code[1].target == "$x"


def test_binary_expression_generates_binop():
    code = gen_ir("MAKE $z = $x + $y!")
    binops = [i for i in code if isinstance(i, IRBinOp)]
    assert len(binops) == 1
    assert binops[0].op == "+"


def test_print_generates_irprint():
    code = gen_ir("SAY $x!")
    assert any(isinstance(i, IRPrint) for i in code)


def test_if_statement_generates_labels_and_jump():
    from compiler.ir.instructions import IRJumpIfFalse, IRLabel
    code = gen_ir('WHEN ($x > 1) { SAY "a"! }')
    assert any(isinstance(i, IRJumpIfFalse) for i in code)
    assert any(isinstance(i, IRLabel) for i in code)
