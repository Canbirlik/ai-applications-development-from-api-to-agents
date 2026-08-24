---
name: calculator
description: >
    Evaluates mathematical expressions safely via AST parsing (no raw eval on
    untrusted strings). Supports arithmetic, exponentiation, floor division,
    modulo, trigonometric functions, and mathematical constants. Use this
    skill whenever the user asks to calculate, compute, evaluate, or solve a
    math expression (e.g. "what is 2^10?", "calculate sqrt(144) + sin(pi/2)").
---

# Calculator Skill

<!--
TODO: Fill in this SKILL.md with instructions telling the AI agent how to use the calculator skill.
The script is already implemented at scripts/calculate.py — study it to understand what it does.

Your SKILL.md should include the following sections:

## Quick Start
Provide the shell command to run the script.
Hint: the script takes an expression as a command-line argument:
  python /skills/calculator/scripts/calculate.py "<expression>"

## Supported Operations
List all supported operations (read calculate.py to discover them):
Arithmetic, Power / exponentiation, Square, Floor division and modulo operators, Trigonometric functions, Mathematical constants, Grouping with parentheses

## Workflow
Step-by-step instructions for the agent
-->

## Quick Start

Run the script with the expression as a single command-line argument:

```bash
python /skills/calculator/scripts/calculate.py "<expression>"
```

Example:

```bash
python /skills/calculator/scripts/calculate.py "sqrt(144) + sin(pi / 2)"
```

## Supported Operations

- **Arithmetic**: `+`, `-`, `*`, `/`
- **Power / exponentiation**: `**` or `^` (e.g. `2^10` or `2**10`)
- **Square root**: `sqrt(x)`
- **Floor division and modulo operators**: `//`, `%`
- **Trigonometric functions**: `sin(x)`, `cos(x)`, `tan(x)`
- **Other functions**: `abs(x)`, `round(x)`, `floor(x)`, `ceil(x)`, `log(x)`, `log10(x)`
- **Mathematical constants**: `pi`, `e`
- **Grouping with parentheses**: `(...)`

## Workflow

1. Translate the user's request into a single valid math expression string.
2. Run `python /skills/calculator/scripts/calculate.py "<expression>"` with that expression.
3. Read the script's output:
   - On success it prints `Expression: ...` and `Result: ...` — report the result to the user.
   - On failure it prints `Error: ...` (invalid syntax, unknown name/function, unsafe operation,
     or division by zero) — explain the issue to the user and, if possible, correct the
     expression and retry.
4. Always quote the expression so the shell doesn't interpret special characters like `*`, `(`, `)`.
