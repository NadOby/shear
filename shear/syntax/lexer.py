"""Tokens of text syntax version 0 (docs/syntax.md section 2)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


RESERVED = frozenset(
    "fn cell let if else true false none quote unquote literal function "
    "activate trial label raw ref code linksof apply len item slice "
    "inspect record concat closure captures catch raise".split()
)


class SourceError(ValueError):
    """The text is not a valid program; ``line`` and ``column`` are 1-based."""

    def __init__(self, message: str, line: int = 1, column: int = 1) -> None:
        super().__init__(f"line {line}, column {column}: {message}")
        self.message = message
        self.line = line
        self.column = column


@dataclass(frozen=True)
class Token:
    """One token. ``kind`` is name, int, string, op, newline, indent, dedent
    or eof; a backquoted name has ``quoted`` set and is never a keyword.
    """

    kind: str
    value: Any
    line: int
    column: int
    quoted: bool = False


_NAME = re.compile(r"[^\W\d]\w*")


_INT = re.compile(r"\d+")


_STRING = re.compile(r'"(?:[^"\\\x00-\x1f]|\\.)*"')


_OPS = ("==", "..", "(", ")", ",", ":", "=", "+", "-", "*", "<", ".")


_NAME_ESCAPES = {"\\": "\\", "`": "`", "n": "\n", "r": "\r", "t": "\t"}


def _scan_name(line: str, start: int, number: int) -> tuple[str, int]:
    """Read a backquoted name starting at ``line[start]``."""

    out: list[str] = []
    i = start + 1

    while i < len(line):
        char = line[i]

        if char == "`":
            if not out:
                raise SourceError("empty name", number, start + 1)

            return "".join(out), i + 1

        if char == "\\":
            i += 1
            escape = line[i] if i < len(line) else ""

            if escape in _NAME_ESCAPES:
                out.append(_NAME_ESCAPES[escape])
            elif escape == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", line[i + 1:i + 5]):
                out.append(chr(int(line[i + 1:i + 5], 16)))
                i += 4
            else:
                raise SourceError("invalid escape in name", number, i + 1)
        else:
            out.append(char)

        i += 1

    raise SourceError("unterminated name", number, start + 1)


def tokenize(text: str) -> list[Token]:
    """Split program text into tokens, with INDENT and DEDENT for blocks."""

    tokens: list[Token] = []
    indents = [0]
    lines = text.split("\n")

    for number, raw_line in enumerate(lines, 1):
        line = raw_line[:-1] if raw_line.endswith("\r") else raw_line
        body = line.lstrip(" ")
        indent = len(line) - len(body)

        if not body.strip() or body.lstrip("\t ").startswith("#"):
            continue

        if body.startswith("\t"):
            raise SourceError("tabs are not allowed in indentation", number, indent + 1)

        if indent > indents[-1]:
            indents.append(indent)
            tokens.append(Token("indent", None, number, indent + 1))
        else:
            while indent < indents[-1]:
                indents.pop()
                tokens.append(Token("dedent", None, number, indent + 1))

            if indent != indents[-1]:
                raise SourceError("inconsistent indentation", number, indent + 1)

        pos = indent

        while pos < len(line):
            char = line[pos]
            column = pos + 1

            if char == " ":
                pos += 1
            elif char == "\t":
                raise SourceError("tabs are not allowed", number, column)
            elif char == "#":
                break
            elif char == '"':
                match = _STRING.match(line, pos)

                if match is None:
                    raise SourceError("unterminated or invalid string", number, column)

                try:
                    value = json.loads(match.group())
                except ValueError:
                    raise SourceError("invalid escape in string", number, column) from None

                tokens.append(Token("string", value, number, column))
                pos = match.end()
            elif char == "`":
                name, pos = _scan_name(line, pos, number)
                tokens.append(Token("name", name, number, column, quoted=True))
            elif (match := _NAME.match(line, pos)) is not None:
                tokens.append(Token("name", match.group(), number, column))
                pos = match.end()
            elif (match := _INT.match(line, pos)) is not None:
                pos = match.end()

                if pos < len(line) and (line[pos].isalnum() or line[pos] == "_"):
                    raise SourceError("invalid number", number, column)

                tokens.append(Token("int", int(match.group()), number, column))
            else:
                for op in _OPS:
                    if line.startswith(op, pos):
                        tokens.append(Token("op", op, number, column))
                        pos += len(op)
                        break
                else:
                    raise SourceError(f"unexpected character {char!r}", number, column)

        tokens.append(Token("newline", None, number, len(line) + 1))

    last = len(lines)

    for _ in indents[1:]:
        tokens.append(Token("dedent", None, last, 1))

    tokens.append(Token("eof", None, last, 1))
    return tokens
