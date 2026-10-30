# KRAK Grammar (v1)

```
program
    -> statement*

statement
    -> variable_declaration
    -> assignment
    -> print_statement
    -> if_statement
    -> while_statement
    -> function_declaration
    -> return_statement
    -> call_statement

variable_declaration
    -> MAKE IDENTIFIER ASSIGN expression STATEMENT_END

assignment
    -> IDENTIFIER ASSIGN expression STATEMENT_END

print_statement
    -> SAY expression STATEMENT_END

if_statement
    -> WHEN LPAREN expression RPAREN block ( OTHERWISE block )?

while_statement
    -> REPEAT LPAREN expression RPAREN block

function_declaration
    -> FUNC IDENTIFIER LPAREN param_list? RPAREN block

param_list
    -> IDENTIFIER ( COMMA IDENTIFIER )*

return_statement
    -> RETURN expression? STATEMENT_END

call_statement
    -> call_expression STATEMENT_END

block
    -> LBRACE statement* RBRACE

expression
    -> equality

equality
    -> comparison ( ( "==" | "!=" ) comparison )*

comparison
    -> term ( ( ">" | "<" | ">=" | "<=" ) term )*

term
    -> factor ( ( "+" | "-" ) factor )*

factor
    -> unary ( ( "*" | "/" ) unary )*

unary
    -> ( "-" ) unary
    -> primary

primary
    -> NUMBER
    -> STRING
    -> IDENTIFIER
    -> call_expression
    -> LPAREN expression RPAREN

call_expression
    -> IDENTIFIER LPAREN arg_list? RPAREN

arg_list
    -> expression ( COMMA expression )*
```

## The Mirror String Rule (weird rule, on purpose)

Every string literal must be written **backwards** in the source file.
The lexer reverses it back to the real value before the parser ever sees it.

```
SAY "olleH"!            # prints: Hello
SAY "!dlrow olleH"!     # prints: Hello world!
MAKE $name = "nayaS"!   # $name == "Sayan"
```

This has zero practical benefit and is entirely for demo/viva flavor --
it's a good example of a lexical transformation happening before syntax
or semantics are even considered.
