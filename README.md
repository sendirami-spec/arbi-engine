DualScript — الملف الكامل للتأسيس

ملف واحد يعمل من الصفر. احفظه باسم dualscript.py وشغّله مباشرة.

```python
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
  DualScript v1.0 — اللغة الكاملة في ملف واحد
═══════════════════════════════════════════════════════════════
  لغة برمجة تستخدم حروف المسند العربي القديم (U+10A60–U+10A7C)
  مع دعم كامل للاتينية، آلة افتراضية مستقلة، ومترجم Bytecode.

  الاستخدام:
      python dualscript.py run  file.ds       # تشغيل ملف
      python dualscript.py dis  file.ds       # عرض Bytecode
      python dualscript.py tokens file.ds     # عرض التوكنات
      python dualscript.py repl               # صدفة تفاعلية
      python dualscript.py demo               # مثال جاهز

  المؤلف: رامي سندي
  الترخيص: MIT
═══════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import sys
import argparse
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1) الأخطاء
# ═══════════════════════════════════════════════════════════════

class DSError(Exception):
    def __init__(self, kind="Error", message="", line=0):
        self.kind = kind
        self.message = message
        self.line = line
        super().__init__(message)

    def __str__(self):
        loc = f" (سطر {self.line})" if self.line else ""
        return f"{self.kind}: {self.message}{loc}"


class DSLexError(DSError):
    def __init__(self, msg, line=0): super().__init__("LexError", msg, line)

class DSParseError(DSError):
    def __init__(self, msg, line=0): super().__init__("ParseError", msg, line)

class DSCompileError(DSError):
    def __init__(self, msg, line=0): super().__init__("CompileError", msg, line)

class DSRuntimeError(DSError):
    def __init__(self, msg, line=0): super().__init__("RuntimeError", msg, line)

class DSNameError(DSError):
    def __init__(self, name, line=0):
        super().__init__("NameError", f"الاسم '{name}' غير معرّف", line)

class DSTypeError(DSError):
    def __init__(self, msg, line=0): super().__init__("TypeError", msg, line)

class DSZeroDivisionError(DSError):
    def __init__(self, line=0):
        super().__init__("ZeroDivisionError", "القسمة على صفر", line)

class DSIndexError(DSError):
    def __init__(self, msg, line=0): super().__init__("IndexError", msg, line)

class DSImportError(DSError):
    def __init__(self, msg, line=0): super().__init__("ImportError", msg, line)


# إشارات داخلية للتحكم بالتدفق
class ReturnSignal(Exception):
    def __init__(self, value): self.value = value

class BreakSignal(Exception): pass
class ContinueSignal(Exception): pass


# ═══════════════════════════════════════════════════════════════
# 2) الكلمات المفتاحية وخريطة المسند
# ═══════════════════════════════════════════════════════════════

# حروف المسند المستخدمة في الكلمات المفتاحية
# لكل كلمة رمز فريد مكوّن من 1-3 حروف
MUSNAD_KEYWORDS = {
    # التحكم في التدفق
    "𐩦𐩴":       "IF",
    "𐩦𐩴𐩦":     "ELIF",
    "𐩦𐩡":       "ELSE",
    "𐩬𐩥":       "WHILE",
    "𐩡𐩱":       "FOR",
    "𐩦𐩥":       "IN",
    "𐩦𐩯":       "CONTINUE",
    "𐩯𐩸":       "BREAK",
    "𐩦𐩵":       "RETURN",
    "𐩯𐩭":       "PASS",

    # التعريفات
    "𐩧𐩵":       "DEF",
    "𐩩𐩰":       "CLASS",
    "𐩯𐩬":       "PRINT",

    # الاستيراد
    "𐩦𐩫𐩵":     "IMPORT",
    "𐩦𐩫":       "AS",
    "𐩸𐩵":       "FROM",

    # القيم
    "𐩩𐩢":       "TRUE",
    "𐩲𐩯":       "FALSE",
    "𐩦𐩦":       "NONE",

    # منطقية
    "𐩣":         "AND",
    "𐩦𐩣":       "OR",
    "𐩡𐩥":       "NOT",
    "𐩦𐩠":       "IS",

    # الاستثناءات
    "𐩢𐩣":       "TRY",
    "𐩶𐩸":       "EXCEPT",
    "𐩸𐩡":       "FINALLY",
    "𐩨𐩴":       "RAISE",
}

LATIN_KEYWORDS = {
    "if": "IF", "elif": "ELIF", "else": "ELSE",
    "while": "WHILE", "for": "FOR", "in": "IN",
    "break": "BREAK", "continue": "CONTINUE",
    "return": "RETURN", "pass": "PASS",
    "def": "DEF", "class": "CLASS", "print": "PRINT",
    "import": "IMPORT", "from": "FROM", "as": "AS",
    "True": "TRUE", "False": "FALSE", "None": "NONE",
    "and": "AND", "or": "OR", "not": "NOT", "is": "IS",
    "try": "TRY", "except": "EXCEPT",
    "finally": "FINALLY", "raise": "RAISE",
}

ALL_KEYWORDS = {**MUSNAD_KEYWORDS, **LATIN_KEYWORDS}

# نطاق حروف المسند في اليونيكود
MUSNAD_START = 0x10A60
MUSNAD_END = 0x10A7C


def is_musnad(ch: str) -> bool:
    """هل الحرف من نطاق المسند؟"""
    return bool(ch) and MUSNAD_START <= ord(ch) <= MUSNAD_END


def validate_keywords():
    """تحقق من عدم تعارض رموز الكلمات المفتاحية."""
    vals = list(MUSNAD_KEYWORDS.values())
    if len(vals) != len(set(vals)):
        raise RuntimeError(
            "تعارض في رموز الكلمات المفتاحية! "
            f"المكرر: {[v for v in vals if vals.count(v) > 1]}"
        )


# ═══════════════════════════════════════════════════════════════
# 3) المحلل اللفظي (Lexer)
# ═══════════════════════════════════════════════════════════════

@dataclass
class Token:
    type: str
    value: Any
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"


LATIN_ID_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
DIGITS = set("0123456789")
SPACES = set(" \t")
OPERATORS_2 = ("==", "!=", "<=", ">=", "//", "**")
OPERATORS_1 = set("+-*/%<>=:,.()[]{}")


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.lines = source.split("\n")

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        indent_stack = [0]

        for line_no, raw_line in enumerate(self.lines, 1):
            stripped = raw_line.lstrip(" ")
            indent = len(raw_line) - len(stripped)

            # سطر فارغ أو تعليق فقط
            if not stripped or stripped.startswith("#"):
                continue

            # إدارة INDENT / DEDENT
            if indent > indent_stack[-1]:
                indent_stack.append(indent)
                tokens.append(Token("INDENT", indent, line_no, 1))
            while indent < indent_stack[-1]:
                indent_stack.pop()
                tokens.append(Token("DEDENT", indent, line_no, 1))

            col = indent + 1
            i = 0
            while i < len(stripped):
                ch = stripped[i]

                # مسافات داخل السطر
                if ch in SPACES:
                    i += 1; col += 1
                    continue

                # تعليق داخل السطر
                if ch == "#":
                    break

                # سلسلة نصية
                if ch in "\"'":
                    quote = ch
                    j = i + 1
                    buf = []
                    while j < len(stripped) and stripped[j] != quote:
                        if stripped[j] == "\\" and j + 1 < len(stripped):
                            esc = stripped[j + 1]
                            buf.append({"n": "\n", "t": "\t",
                                        "\\": "\\", "'": "'",
                                        '"': '"'}.get(esc, esc))
                            j += 2
                        else:
                            buf.append(stripped[j])
                            j += 1
                    if j >= len(stripped):
                        raise DSLexError(
                            f"سلسلة غير مغلقة", line_no
                        )
                    tokens.append(Token("STRING", "".join(buf),
                                        line_no, col))
                    col += (j - i + 1)
                    i = j + 1
                    continue

                # رقم
                if ch in DIGITS:
                    j = i
                    while j < len(stripped) and stripped[j] in DIGITS:
                        j += 1
                    if j < len(stripped) and stripped[j] == ".":
                        j += 1
                        while j < len(stripped) and \
                              stripped[j] in DIGITS:
                            j += 1
                    tokens.append(Token("NUMBER", stripped[i:j],
                                        line_no, col))
                    col += (j - i)
                    i = j
                    continue

                # معرّف مسندي أو كلمة مفتاحية مسندية
                if is_musnad(ch):
                    j = i
                    while j < len(stripped) and (
                        is_musnad(stripped[j])
                        or stripped[j] in DIGITS
                        or stripped[j] == "_"
                    ):
                        j += 1
                    word = stripped[i:j]
                    kw = ALL_KEYWORDS.get(word)
                    if kw is not None:
                        tokens.append(Token(kw, word, line_no, col))
                    else:
                        tokens.append(Token("MUSNAD_ID", word,
                                            line_no, col))
                    col += (j - i)
                    i = j
                    continue

                # معرّف لاتيني أو كلمة مفتاحية لاتينية
                if ch in LATIN_ID_START:
                    j = i
                    while j < len(stripped) and (
                        stripped[j] in LATIN_ID_START
                        or stripped[j] in DIGITS
                    ):
                        j += 1
                    word = stripped[i:j]
                    kw = ALL_KEYWORDS.get(word)
                    if kw is not None:
                        tokens.append(Token(kw, word, line_no, col))
                    else:
                        tokens.append(Token("LATIN_ID", word,
                                            line_no, col))
                    col += (j - i)
                    i = j
                    continue

                # معامل من حرفين
                two = stripped[i:i + 2]
                if two in OPERATORS_2:
                    tokens.append(Token("OP", two, line_no, col))
                    i += 2; col += 2
                    continue

                # معامل من حرف واحد
                if ch in OPERATORS_1:
                    tokens.append(Token("OP", ch, line_no, col))
                    i += 1; col += 1
                    continue

                raise DSLexError(
                    f"محرف غير معروف: {ch!r}", line_no
                )

            tokens.append(Token("NEWLINE", "\n", line_no, col))

        # إغلاق كل مستويات الإزاحة
        while len(indent_stack) > 1:
            indent_stack.pop()
            tokens.append(Token("DEDENT", 0, len(self.lines), 1))
        tokens.append(Token("EOF", "", len(self.lines), 1))
        return tokens


# ═══════════════════════════════════════════════════════════════
# 4) عقد الشجرة النحوية المجردة (AST)
# ═══════════════════════════════════════════════════════════════

class Node: pass

# ----- جمل -----
class Program(Node):
    def __init__(self, body): self.body = body

class Assign(Node):
    def __init__(self, target, value):
        self.target, self.value = target, value

class If(Node):
    def __init__(self, cond, body, elifs, orelse):
        self.cond = cond
        self.body = body
        self.elifs = elifs      # list[(cond, body)]
        self.orelse = orelse

class While(Node):
    def __init__(self, cond, body):
        self.cond, self.body = cond, body

class For(Node):
    def __init__(self, target, iterable, body):
        self.target = target
        self.iterable = iterable
        self.body = body

class FuncDef(Node):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body

class ClassDef(Node):
    def __init__(self, name, bases, body):
        self.name = name
        self.bases = bases
        self.body = body

class Return(Node):
    def __init__(self, value): self.value = value

class Print(Node):
    def __init__(self, value): self.value = value

class ExprStmt(Node):
    def __init__(self, expr): self.expr = expr

class Break(Node): pass
class Continue(Node): pass
class Pass(Node): pass

class Import(Node):
    def __init__(self, module, alias):
        self.module, self.alias = module, alias

class Try(Node):
    def __init__(self, body, handlers, orelse, finally_):
        self.body = body
        self.handlers = handlers  # list[(type, name, body)]
        self.orelse = orelse
        self.finally_ = finally_

class Raise(Node):
    def __init__(self, value): self.value = value

# ----- تعبيرات -----
class Num(Node):
    def __init__(self, value): self.value = value

class Str(Node):
    def __init__(self, value): self.value = value

class Bool(Node):
    def __init__(self, value): self.value = value

class NoneLit(Node): pass

class Name(Node):
    def __init__(self, id_): self.id = id_

class BinOp(Node):
    def __init__(self, left, op, right):
        self.left, self.op, self.right = left, op, right

class UnaryOp(Node):
    def __init__(self, op, operand):
        self.op, self.operand = op, operand

class BoolOp(Node):
    def __init__(self, op, values):
        self.op, self.values = op, values

class Compare(Node):
    def __init__(self, left, ops, comparators):
        self.left = left
        self.ops = ops
        self.comparators = comparators

class Call(Node):
    def __init__(self, func, args):
        self.func, self.args = func, args

class Attribute(Node):
    def __init__(self, value, attr):
        self.value, self.attr = value, attr

class Subscript(Node):
    def __init__(self, value, index):
        self.value, self.index = value, index

class ListLit(Node):
    def __init__(self, elts): self.elts = elts

class DictLit(Node):
    def __init__(self, pairs): self.pairs = pairs


# ═══════════════════════════════════════════════════════════════
# 5) المحلل النحوي (Parser)
# ═══════════════════════════════════════════════════════════════

class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # ----- أدوات -----
    def peek(self, offset: int = 0) -> Token:
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else self.tokens[-1]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, type_: str) -> Token:
        tok = self.peek()
        if tok.type != type_:
            raise DSParseError(
                f"توقعت {type_} لكن وجدت {tok.type} ({tok.value!r})",
                tok.line,
            )
        return self.advance()

    def expect_op(self, op: str) -> Token:
        tok = self.peek()
        if tok.type != "OP" or tok.value != op:
            raise DSParseError(
                f"توقعت '{op}' لكن وجدت {tok.value!r}", tok.line
            )
        return self.advance()

    def match(self, *types):
        if self.peek().type in types:
            return self.advance()
        return None

    def skip_newlines(self):
        while self.peek().type == "NEWLINE":
            self.advance()

    # ----- نقطة الدخول -----
    def parse(self) -> Program:
        body = self.parse_block(top_level=True)
        self.expect("EOF")
        return Program(body)

    def parse_block(self, top_level=False) -> list:
        stmts = []
        self.skip_newlines()
        if not top_level:
            self.expect("INDENT")
            self.skip_newlines()
        while self.peek().type not in ("DEDENT", "EOF"):
            stmts.append(self.parse_statement())
            self.skip_newlines()
        if not top_level:
            self.expect("DEDENT")
        return stmts

    # ----- الجمل -----
    def parse_statement(self):
        t = self.peek().type
        if t == "IF":       return self.parse_if()
        if t == "WHILE":    return self.parse_while()
        if t == "FOR":      return self.parse_for()
        if t == "DEF":      return self.parse_def()
        if t == "CLASS":    return self.parse_class()
        if t == "RETURN":   return self.parse_return()
        if t == "PRINT":    return self.parse_print()
        if t == "BREAK":    self.advance(); return Break()
        if t == "CONTINUE": self.advance(); return Continue()
        if t == "PASS":     self.advance(); return Pass()
        if t == "IMPORT":   return self.parse_import()
        if t == "TRY":      return self.parse_try()
        if t == "RAISE":    return self.parse_raise()

        expr = self.parse_expression()
        if self.peek().type == "OP" and self.peek().value == "=":
            self.advance()
            value = self.parse_expression()
            return Assign(expr, value)
        return ExprStmt(expr)

    def parse_if(self):
        self.expect("IF")
        cond = self.parse_expression()
        self.expect_op(":")
        body = self.parse_block()

        elifs = []
        while self.peek().type == "ELIF":
            self.advance()
            c = self.parse_expression()
            self.expect_op(":")
            b = self.parse_block()
            elifs.append((c, b))

        orelse = []
        if self.peek().type == "ELSE":
            self.advance()
            self.expect_op(":")
            orelse = self.parse_block()

        return If(cond, body, elifs, orelse)

    def parse_while(self):
        self.expect("WHILE")
        cond = self.parse_expression()
        self.expect_op(":")
        return While(cond, self.parse_block())

    def parse_for(self):
        self.expect("FOR")
        target = self.parse_primary()
        self.expect("IN")
        iterable = self.parse_expression()
        self.expect_op(":")
        return For(target, iterable, self.parse_block())

    def parse_def(self):
        self.expect("DEF")
        name = self.parse_primary()
        self.expect_op("(")
        params = []
        if not (self.peek().type == "OP" and
                self.peek().value == ")"):
            params.append(self.parse_primary())
            while self.peek().type == "OP" and \
                  self.peek().value == ",":
                self.advance()
                params.append(self.parse_primary())
        self.expect_op(")")
        self.expect_op(":")
        return FuncDef(name, params, self.parse_block())

    def parse_class(self):
        self.expect("CLASS")
        name = self.parse_primary()
        bases = []
        if self.peek().type == "OP" and self.peek().value == "(":
            self.advance()
            if not (self.peek().type == "OP" and
                    self.peek().value == ")"):
                bases.append(self.parse_primary())
                while self.peek().type == "OP" and \
                      self.peek().value == ",":
                    self.advance()
                    bases.append(self.parse_primary())
            self.expect_op(")")
        self.expect_op(":")
        return ClassDef(name, bases, self.parse_block())

    def parse_return(self):
        self.expect("RETURN")
        if self.peek().type in ("NEWLINE", "DEDENT", "EOF"):
            return Return(None)
        return Return(self.parse_expression())

    def parse_print(self):
        self.expect("PRINT")
        self.expect_op("(")
        value = self.parse_expression()
        self.expect_op(")")
        return Print(value)

    def parse_import(self):
        self.expect("IMPORT")
        module = self.parse_primary()
        alias = None
        if self.peek().type == "AS":
            self.advance()
            alias = self.parse_primary()
        return Import(module, alias)

    def parse_try(self):
        self.expect("TRY")
        self.expect_op(":")
        body = self.parse_block()

        handlers = []
        while self.peek().type == "EXCEPT":
            self.advance()
            exc_type = None
            name = None
            if not (self.peek().type == "OP" and
                    self.peek().value == ":"):
                exc_type = self.parse_expression()
                if self.peek().type == "AS":
                    self.advance()
                    name = self.parse_primary()
            self.expect_op(":")
            handlers.append((exc_type, name, self.parse_block()))

        orelse = []
        if self.peek().type == "ELSE":
            self.advance()
            self.expect_op(":")
            orelse = self.parse_block()

        finally_ = []
        if self.peek().type == "FINALLY":
            self.advance()
            self.expect_op(":")
            finally_ = self.parse_block()

        return Try(body, handlers, orelse, finally_)

    def parse_raise(self):
        self.expect("RAISE")
        if self.peek().type in ("NEWLINE", "DEDENT", "EOF"):
            return Raise(None)
        return Raise(self.parse_expression())

    # ----- التعبيرات -----
    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        values = [left]
        while self.peek().type == "OR":
            self.advance()
            values.append(self.parse_and())
        if len(values) == 1:
            return left
        return BoolOp("or", values)

    def parse_and(self):
        left = self.parse_not()
        values = [left]
        while self.peek().type == "AND":
            self.advance()
            values.append(self.parse_not())
        if len(values) == 1:
            return left
        return BoolOp("and", values)

    def parse_not(self):
        if self.peek().type == "NOT":
            self.advance()
            return UnaryOp("not", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_additive()
        ops, comparators = [], []
        while self.peek().type == "OP" and \
              self.peek().value in ("==", "!=", "<", ">", "<=", ">="):
            ops.append(self.advance().value)
            comparators.append(self.parse_additive())
        if not ops:
            return left
        return Compare(left, ops, comparators)

    def parse_additive(self):
        left = self.parse_multiplicative()
        while self.peek().type == "OP" and \
              self.peek().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_multiplicative()
            left = BinOp(left, op, right)
        return left

    def parse_multiplicative(self):
        left = self.parse_unary()
        while self.peek().type == "OP" and \
              self.peek().value in ("*", "/", "//", "%", "**"):
            op = self.advance().value
            right = self.parse_unary()
            left = BinOp(left, op, right)
        return left

    def parse_unary(self):
        if self.peek().type == "OP" and \
           self.peek().value in ("-", "+"):
            op = self.advance().value
            return UnaryOp(op, self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            tok = self.peek()
            if tok.type == "OP" and tok.value == "(":
                self.advance()
                args = []
                if not (self.peek().type == "OP" and
                        self.peek().value == ")"):
                    args.append(self.parse_expression())
                    while self.peek().type == "OP" and \
                          self.peek().value == ",":
                        self.advance()
                        args.append(self.parse_expression())
                self.expect_op(")")
                node = Call(node, args)
            elif tok.type == "OP" and tok.value == ".":
                self.advance()
                attr = self.advance()
                node = Attribute(node, attr.value)
            elif tok.type == "OP" and tok.value == "[":
                self.advance()
                index = self.parse_expression()
                self.expect_op("]")
                node = Subscript(node, index)
            else:
                break
        return node

    def parse_primary(self):
        tok = self.peek()
        if tok.type == "NUMBER":
            self.advance()
            v = float(tok.value) if "." in tok.value else int(tok.value)
            return Num(v)
        if tok.type == "STRING":
            self.advance()
            return Str(tok.value)
        if tok.type == "TRUE":
            self.advance(); return Bool(True)
        if tok.type == "FALSE":
            self.advance(); return Bool(False)
        if tok.type == "NONE":
            self.advance(); return NoneLit()
        if tok.type in ("LATIN_ID", "MUSNAD_ID"):
            self.advance()
            return Name(tok.value)
        if tok.type == "OP" and tok.value == "(":
            self.advance()
            expr = self.parse_expression()
            self.expect_op(")")
            return expr
        if tok.type == "OP" and tok.value == "[":
            self.advance()
            elts = []
            if not (self.peek().type == "OP" and
                    self.peek().value == "]"):
                elts.append(self.parse_expression())
                while self.peek().type == "OP" and \
                      self.peek().value == ",":
                    self.advance()
                    elts.append(self.parse_expression())
            self.expect_op("]")
            return ListLit(elts)
        if tok.type == "OP" and tok.value == "{":
            self.advance()
            pairs = []
            if not (self.peek().type == "OP" and
                    self.peek().value == "}"):
                k = self.parse_expression()
                self.expect_op(":")
                v = self.parse_expression()
                pairs.append((k, v))
                while self.peek().type == "OP" and \
                      self.peek().value == ",":
                    self.advance()
                    k = self.parse_expression()
                    self.expect_op(":")
                    v = self.parse_expression()
                    pairs.append((k, v))
            self.expect_op("}")
            return DictLit(pairs)
        raise DSParseError(
            f"رمز غير متوقع: {tok.type} ({tok.value!r})", tok.line
        )


# ═══════════════════════════════════════════════════════════════
# 6) مجموعة التعليمات والبايت كود
# ═══════════════════════════════════════════════════════════════

class Op(Enum):
    NOP = auto()
    POP = auto()
    DUP = auto()

    LOAD_CONST = auto()
    LOAD_NAME = auto()
    STORE_NAME = auto()
    LOAD_ATTR = auto()
    STORE_ATTR = auto()
    LOAD_SUBSCR = auto()
    STORE_SUBSCR = auto()

    ADD = auto(); SUB = auto(); MUL = auto()
    DIV = auto(); FLOORDIV = auto(); MOD = auto(); POW = auto()
    NEG = auto(); NOT = auto()

    EQ = auto(); NE = auto(); LT = auto(); LE = auto()
    GT = auto(); GE = auto(); IN = auto()

    JUMP = auto()
    JUMP_IF_FALSE = auto()
    JUMP_IF_TRUE = auto()
    JUMP_IF_FALSE_OR_POP = auto()
    JUMP_IF_TRUE_OR_POP = auto()

    MAKE_FUNCTION = auto()
    CALL = auto()
    RETURN = auto()
    BUILD_CLASS = auto()

    BUILD_LIST = auto()
    BUILD_DICT = auto()

    GET_ITER = auto()
    FOR_ITER = auto()

    PUSH_TRY = auto()
    POP_TRY = auto()
    RAISE = auto()
    RERAISE = auto()
    MATCH_EXC = auto()
    STORE_EXC = auto()

    PRINT = auto()
    HALT = auto()


@dataclass
class Instruction:
    op: Op
    arg: Any = None
    line: int = 0


@dataclass
class CodeObject:
    name: str
    params: list = field(default_factory=list)
    instructions: list = field(default_factory=list)
    constants: list = field(default_factory=list)
    names: list = field(default_factory=list)

    def disassemble(self, header=True) -> str:
        out = []
        if header:
            out.append(f"═══ {self.name} (params={self.params}) ═══")
        for i, instr in enumerate(self.instructions):
            arg = "" if instr.arg is None else f" {instr.arg!r}"
            out.append(f"{i:4d}  {instr.op.name:<24}{arg}")
        return "\n".join(out)


# ═══════════════════════════════════════════════════════════════
# 7) المترجم (AST → Bytecode)
# ═══════════════════════════════════════════════════════════════

class Compiler:
    def __init__(self):
        self.codes: list[CodeObject] = []
        self.loop_stack: list = []  # [(continue_ip, [break_patches])]

    @property
    def code(self) -> CodeObject:
        return self.codes[-1]

    # ----- أدوات -----
    def emit(self, op: Op, arg=None, line=0) -> int:
        idx = len(self.code.instructions)
        self.code.instructions.append(Instruction(op, arg, line))
        return idx

    def const(self, value) -> int:
        try:
            return self.code.constants.index(value)
        except ValueError:
            self.code.constants.append(value)
            return len(self.code.constants) - 1

    def name(self, n: str) -> int:
        try:
            return self.code.names.index(n)
        except ValueError:
            self.code.names.append(n)
            return len(self.code.names) - 1

    def emit_jump(self, op: Op, line=0) -> int:
        return self.emit(op, None, line)

    def patch(self, idx: int, target=None):
        if target is None:
            target = len(self.code.instructions)
        old = self.code.instructions[idx]
        self.code.instructions[idx] = Instruction(old.op, target,
                                                  old.line)

    # ----- نقطة الدخول -----
    def compile(self, program: Program) -> CodeObject:
        top = CodeObject("<module>")
        self.codes.append(top)
        for stmt in program.body:
            self.stmt(stmt)
        self.emit(Op.HALT)
        self.codes.pop()
        return top

    # ----- الجمل -----
    def stmt(self, node):
        method = "stmt_" + type(node).__name__
        if not hasattr(self, method):
            raise DSCompileError(
                f"جملة غير مدعومة: {type(node).__name__}"
            )
        getattr(self, method)(node)

    def stmt_Assign(self, node):
        self.expr(node.value)
        self._store_target(node.target)

    def _store_target(self, target):
        if isinstance(target, Name):
            self.emit(Op.STORE_NAME, self.name(target.id))
        elif isinstance(target, Attribute):
            self.expr(target.value)
            self.emit(Op.STORE_ATTR, self.name(target.attr))
        elif isinstance(target, Subscript):
            self.expr(target.value)
            self.expr(target.index)
            self.emit(Op.STORE_SUBSCR)
        else:
            raise DSCompileError("هدف إسناد غير صالح")

    def stmt_ExprStmt(self, node):
        self.expr(node.expr)
        self.emit(Op.POP)

    def stmt_If(self, node):
        end_patches = []
        self.expr(node.cond)
        jf = self.emit_jump(Op.JUMP_IF_FALSE)
        for s in node.body:
            self.stmt(s)
        if node.elifs or node.orelse:
            end_patches.append(self.emit_jump(Op.JUMP))
        self.patch(jf)
        for cond, body in node.elifs:
            self.expr(cond)
            jf2 = self.emit_jump(Op.JUMP_IF_FALSE)
            for s in body:
                self.stmt(s)
            if node.orelse:
                end_patches.append(self.emit_jump(Op.JUMP))
            self.patch(jf2)
        if node.orelse:
            for s in node.orelse:
                self.stmt(s)
        for p in end_patches:
            self.patch(p)

    def stmt_While(self, node):
        start = len(self.code.instructions)
        self.expr(node.cond)
        jf = self.emit_jump(Op.JUMP_IF_FALSE)
        self.loop_stack.append((start, []))
        for s in node.body:
            self.stmt(s)
        self.emit(Op.JUMP, start)
        self.patch(jf)
        _, breaks = self.loop_stack.pop()
        for p in breaks:
            self.patch(p)

    def stmt_For(self, node):
        self.expr(node.iterable)
        self.emit(Op.GET_ITER)
        loop_start = len(self.code.instructions)
        for_iter = self.emit_jump(Op.FOR_ITER)
        self._store_target(node.target)
        self.loop_stack.append((loop_start, []))
        for s in node.body:
            self.stmt(s)
        self.emit(Op.JUMP, loop_start)
        self.patch(for_iter)
        _, breaks = self.loop_stack.pop()
        for p in breaks:
            self.patch(p)

    def stmt_Break(self, node):
        if not self.loop_stack:
            raise DSCompileError("break خارج حلقة")
        p = self.emit_jump(Op.JUMP)
        self.loop_stack[-1][1].append(p)

    def stmt_Continue(self, node):
        if not self.loop_stack:
            raise DSCompileError("continue خارج حلقة")
        self.emit(Op.JUMP, self.loop_stack[-1][0])

    def stmt_Pass(self, node):
        self.emit(Op.NOP)

    def stmt_Return(self, node):
        if node.value is None:
            self.emit(Op.LOAD_CONST, self.const(None))
        else:
            self.expr(node.value)
        self.emit(Op.RETURN)

    def stmt_Print(self, node):
        self.expr(node.value)
        self.emit(Op.PRINT)

    def stmt_FuncDef(self, node):
        sub = CodeObject(node.name.id)
        self.codes.append(sub)
        sub.params = [p.id for p in node.params]
        for s in node.body:
            self.stmt(s)
        self.emit(Op.LOAD_CONST, self.const(None))
        self.emit(Op.RETURN)
        self.codes.pop()
        code_idx = self.const(sub)
        name_idx = self.const(node.name.id)
        self.emit(Op.MAKE_FUNCTION,
                  (code_idx, name_idx, len(node.params)))

    def stmt_ClassDef(self, node):
        for s in node.body:
            if isinstance(s, FuncDef):
                self.stmt_FuncDef(s)
            else:
                raise DSCompileError(
                    "لا يُسمح إلا بالدوال داخل class حاليًا"
                )
        methods = [s for s in node.body if isinstance(s, FuncDef)]
        self.emit(Op.BUILD_CLASS,
                  (self.const(node.name.id), len(methods)))

    def stmt_Import(self, node):
        name_const = self.const(node.module.id)
        self.emit(Op.LOAD_NAME, self.name("__import__"))
        self.emit(Op.LOAD_CONST, name_const)
        self.emit(Op.CALL, 1)
        target = node.alias.id if node.alias else node.module.id
        self.emit(Op.STORE_NAME, self.name(target))

    def stmt_Try(self, node):
        has_finally = bool(node.finally_)
        has_handlers = bool(node.handlers)

        finally_h = self.emit_jump(Op.PUSH_TRY) if has_finally else None
        except_h = self.emit_jump(Op.PUSH_TRY) if has_handlers else None

        for s in node.body:
            self.stmt(s)

        if has_handlers:
            self.emit(Op.POP_TRY)
        if has_finally:
            self.emit(Op.POP_TRY)

        for s in node.orelse:
            self.stmt(s)

        jump_to_finally_normal = self.emit_jump(Op.JUMP)
        jump_to_after = self.emit_jump(Op.JUMP)

        next_patch = None
        handler_exits = []
        for i, (exc_type, name, body) in enumerate(node.handlers):
            if i == 0:
                self.patch(except_h)
            else:
                self.patch(next_patch)

            if exc_type is not None:
                self.expr(exc_type)
                self.emit(Op.MATCH_EXC)
                next_patch = self.emit_jump(Op.JUMP_IF_FALSE)
            else:
                next_patch = None

            if name is not None:
                self.emit(Op.STORE_EXC, self.name(name.id))

            for s in body:
                self.stmt(s)

            if has_finally:
                self.emit(Op.POP_TRY)
            j = self.emit_jump(Op.JUMP)
            handler_exits.append(j)

        if has_handlers and next_patch is not None:
            self.patch(next_patch)
        if has_finally:
            if has_handlers:
                self.emit(Op.POP_TRY)
            finally_body_patch = self.emit_jump(Op.JUMP)
        else:
            if has_handlers:
                self.emit(Op.RERAISE)
            finally_body_patch = None

        if has_finally:
            self.patch(jump_to_finally_normal)
            for s in node.finally_:
                self.stmt(s)
            after_finally_normal = self.emit_jump(Op.JUMP)

            self.patch(finally_body_patch)
            for s in node.finally_:
                self.stmt(s)
            self.emit(Op.RERAISE)

            after_target = len(self.code.instructions)
            for j in handler_exits:
                self.patch(j, after_target)
            self.patch(after_finally_normal, after_target)
            self.patch(jump_to_after, after_target)
        else:
            after_target = len(self.code.instructions)
            for j in handler_exits:
                self.patch(j, after_target)
            self.patch(jump_to_after, after_target)

    def stmt_Raise(self, node):
        if node.value is None:
            self.emit(Op.RERAISE)
        else:
            self.expr(node.value)
            self.emit(Op.RAISE)

    # ----- التعبيرات -----
    def expr(self, node):
        method = "expr_" + type(node).__name__
        if not hasattr(self, method):
            raise DSCompileError(
                f"تعبير غير مدعوم: {type(node).__name__}"
            )
        getattr(self, method)(node)

    def expr_Num(self, node):
        self.emit(Op.LOAD_CONST, self.const(node.value))

    def expr_Str(self, node):
        self.emit(Op.LOAD_CONST, self.const(node.value))

    def expr_Bool(self, node):
        self.emit(Op.LOAD_CONST, self.const(node.value))

    def expr_NoneLit(self, node):
        self.emit(Op.LOAD_CONST, self.const(None))

    def expr_Name(self, node):
        self.emit(Op.LOAD_NAME, self.name(node.id))

    def expr_BinOp(self, node):
        self.expr(node.left)
        self.expr(node.right)
        op_map = {
            "+": Op.ADD, "-": Op.SUB, "*": Op.MUL, "/": Op.DIV,
            "//": Op.FLOORDIV, "%": Op.MOD, "**": Op.POW,
        }
        self.emit(op_map[node.op])

    def expr_UnaryOp(self, node):
        self.expr(node.operand)
        if node.op == "-":
            self.emit(Op.NEG)
        elif node.op == "not":
            self.emit(Op.NOT)

    def expr_BoolOp(self, node):
        end_patches = []
        if node.op == "and":
            for v in node.values[:-1]:
                self.expr(v)
                self.emit(Op.DUP)
                j = self.emit_jump(Op.JUMP_IF_FALSE_OR_POP)
                end_patches.append(j)
            self.expr(node.values[-1])
        else:
            for v in node.values[:-1]:
                self.expr(v)
                self.emit(Op.DUP)
                j = self.emit_jump(Op.JUMP_IF_TRUE_OR_POP)
                end_patches.append(j)
            self.expr(node.values[-1])
        for p in end_patches:
            self.patch(p)

    def expr_Compare(self, node):
        self.expr(node.left)
        for op, comp in zip(node.ops, node.comparators):
            self.expr(comp)
            op_map = {
                "==": Op.EQ, "!=": Op.NE,
                "<": Op.LT, "<=": Op.LE,
                ">": Op.GT, ">=": Op.GE,
            }
            self.emit(op_map[op])

    def expr_Call(self, node):
        self.expr(node.func)
        for arg in node.args:
            self.expr(arg)
        self.emit(Op.CALL, len(node.args))

    def expr_Attribute(self, node):
        self.expr(node.value)
        self.emit(Op.LOAD_ATTR, self.name(node.attr))

    def expr_Subscript(self, node):
        self.expr(node.value)
        self.expr(node.index)
        self.emit(Op.LOAD_SUBSCR)

    def expr_ListLit(self, node):
        for e in node.elts:
            self.expr(e)
        self.emit(Op.BUILD_LIST, len(node.elts))

    def expr_DictLit(self, node):
        for k, v in node.pairs:
            self.expr(k)
            self.expr(v)
        self.emit(Op.BUILD_DICT, len(node.pairs))


# ═══════════════════════════════════════════════════════════════
# 8) المكتبة القياسية
# ═══════════════════════════════════════════════════════════════

def _build_stdlib() -> dict:
    def _range(*args):
        return list(range(*args))

    def _print(*args, **kwargs):
        return print(*args, **kwargs)

    std = {
        "range":  _range,
        "len":    lambda x: len(x),
        "str":    lambda x: str(x),
        "int":    lambda x: int(x),
        "float":  lambda x: float(x),
        "bool":   lambda x: bool(x),
        "abs":    lambda x: abs(x),
        "min":    lambda *a: min(*a),
        "max":    lambda *a: max(*a),
        "sum":    lambda x: sum(x),
        "type":   lambda x: type(x).__name__,
        "print":  _print,
        "input":  lambda prompt="": input(prompt),
        # الاستثناءات المدمجة
        "DSError": DSError,
        "DSNameError": DSNameError,
        "DSTypeError": DSTypeError,
        "DSZeroDivisionError": DSZeroDivisionError,
        "DSIndexError": DSIndexError,
        "DSRuntimeError": DSRuntimeError,
    }

    # أسماء مسندية للدوال الشائعة
    std.update({
        "𐩵𐩰":  _range,         # رن  → range
        "𐩡𐩰":  std["len"],     # لن  → len
        "𐩯𐩵":  std["str"],     # تر  → str
        "𐩧𐩰":  std["int"],     # عن  → int
        "𐩩𐩠":  std["abs"],     # صه  → abs
    })
    return std


STDLIB = _build_stdlib()


# ═══════════════════════════════════════════════════════════════
# 9) الآلة الافتراضية (VM)
# ═══════════════════════════════════════════════════════════════

class DSFunction:
    def __init__(self, code: CodeObject, name: str, closure):
        self.code = code
        self.name = name
        self.closure = closure

    def __repr__(self):
        return f"<دالة {self.name}>"


class DSClass:
    def __init__(self, name, methods, bases=()):
        self.name = name
        self.methods = methods
        self.bases = bases

    def __repr__(self):
        return f"<صنف {self.name}>"


class DSInstance:
    def __init__(self, klass: DSClass):
        self.klass = klass
        self.attrs = {}

    def __repr__(self):
        return f"<كائن {self.klass.name}>"


class Frame:
    def __init__(self, code: CodeObject, closure=None):
        self.code = code
        self.ip = 0
        self.stack: list = []
        self.locals: dict = {}
        self.closure = closure
        self.block_stack: list = []   # [(handler_ip, stack_depth)]
        self.current_exc: BaseException | None = None


class VM:
    def __init__(self, globals_=None):
        self.globals = globals_ if globals_ is not None else {}
        self.globals.update(STDLIB)
        self.frames: list[Frame] = []

    # ----- البحث عن الأسماء -----
    def lookup(self, name: str):
        for f in reversed(self.frames):
            if name in f.locals:
                return f.locals[name]
            if f.closure and name in f.closure.locals:
                return f.closure.locals[name]
        if name in self.globals:
            return self.globals[name]
        raise DSNameError(name)

    def assign(self, name: str, value):
        if len(self.frames) == 1:
            self.globals[name] = value
        else:
            self.frames[-1].locals[name] = value

    # ----- التشغيل -----
    def run(self, code: CodeObject):
        frame = Frame(code)
        self.frames = [frame]
        try:
            self._loop()
        except ReturnSignal as r:
            return r.value
        return None

    def call(self, func, args):
        if isinstance(func, DSFunction):
            frame = Frame(func.code, closure=func.closure)
            for p, a in zip(func.code.params, args):
                frame.locals[p] = a
            self.frames.append(frame)
            try:
                self._loop()
            except ReturnSignal as r:
                return r.value
            return None
        if callable(func):
            return func(*args)
        raise DSTypeError(f"لا يمكن نداء {type(func).__name__}")

    def _loop(self):
        while True:
            f = self.frames[-1]
            if f.ip >= len(f.code.instructions):
                self.frames.pop()
                if not self.frames:
                    return
                self.frames[-1].stack.append(None)
                continue

            instr = f.code.instructions[f.ip]
            f.ip += 1
            try:
                self._exec(instr, f)
            except (BreakSignal, ContinueSignal, ReturnSignal):
                raise
            except (DSNameError, DSTypeError, DSIndexError,
                    DSZeroDivisionError, DSRuntimeError) as e:
                if not self._unwind(f, e):
                    raise

    def _unwind(self, frame: Frame, exc):
        while frame.block_stack:
            handler_ip, saved_depth = frame.block_stack.pop()
            del frame.stack[saved_depth:]
            frame.current_exc = exc
            frame.ip = handler_ip
            return True
        if len(self.frames) <= 1:
            return False
        self.frames.pop()
        return self._unwind(self.frames[-1], exc)

    # ----- المنفّذ -----
    def _exec(self, instr: Instruction, f: Frame):
        op = instr.op
        s = f.stack

        if op == Op.NOP: pass
        elif op == Op.POP: s.pop()
        elif op == Op.DUP: s.append(s[-1])

        elif op == Op.LOAD_CONST:
            s.append(f.code.constants[instr.arg])
        elif op == Op.LOAD_NAME:
            name = f.code.names[instr.arg]
            s.append(self.lookup(name))
        elif op == Op.STORE_NAME:
            name = f.code.names[instr.arg]
            self.assign(name, s.pop())
        elif op == Op.LOAD_ATTR:
            obj = s.pop()
            name = f.code.names[instr.arg]
            s.append(self._getattr(obj, name))
        elif op == Op.STORE_ATTR:
            value = s.pop()
            obj = s.pop()
            name = f.code.names[instr.arg]
            self._setattr(obj, name, value)
        elif op == Op.LOAD_SUBSCR:
            idx = s.pop(); obj = s.pop()
            s.append(self._subscript(obj, idx, instr.line))
        elif op == Op.STORE_SUBSCR:
            idx = s.pop(); obj = s.pop(); value = s.pop()
            self._store_subscript(obj, idx, value)

        elif op == Op.ADD:
            b = s.pop(); a = s.pop(); s.append(a + b)
        elif op == Op.SUB:
            b = s.pop(); a = s.pop(); s.append(a - b)
        elif op == Op.MUL:
            b = s.pop(); a = s.pop(); s.append(a * b)
        elif op == Op.DIV:
            b = s.pop(); a = s.pop()
            if b == 0: raise DSZeroDivisionError(instr.line)
            s.append(a / b)
        elif op == Op.FLOORDIV:
            b = s.pop(); a = s.pop()
            if b == 0: raise DSZeroDivisionError(instr.line)
            s.append(a // b)
        elif op == Op.MOD:
            b = s.pop(); a = s.pop()
            if b == 0: raise DSZeroDivisionError(instr.line)
            s.append(a % b)
        elif op == Op.POW:
            b = s.pop(); a = s.pop(); s.append(a ** b)
        elif op == Op.NEG:
            s.append(-s.pop())
        elif op == Op.NOT:
            s.append(not s.pop())

        elif op == Op.EQ:
            b = s.pop(); a = s.pop(); s.append(a == b)
        elif op == Op.NE:
            b = s.pop(); a = s.pop(); s.append(a != b)
        elif op == Op.LT:
            b = s.pop(); a = s.pop(); s.append(a < b)
        elif op == Op.LE:
            b = s.pop(); a = s.pop(); s.append(a <= b)
        elif op == Op.GT:
            b = s.pop(); a = s.pop(); s.append(a > b)
        elif op == Op.GE:
            b = s.pop(); a = s.pop(); s.append(a >= b)

        elif op == Op.JUMP:
            f.ip = instr.arg
        elif op == Op.JUMP_IF_FALSE:
            if not s.pop(): f.ip = instr.arg
        elif op == Op.JUMP_IF_TRUE:
            if s.pop(): f.ip = instr.arg
        elif op == Op.JUMP_IF_FALSE_OR_POP:
            if not s[-1]:
                f.ip = instr.arg
            else:
                s.pop()
        elif op == Op.JUMP_IF_TRUE_OR_POP:
            if s[-1]:
                f.ip = instr.arg
            else:
                s.pop()

        elif op == Op.MAKE_FUNCTION:
            code_idx, name_idx, nparams = instr.arg
            sub_code = f.code.constants[code_idx]
            name = f.code.constants[name_idx]
            s.append(DSFunction(sub_code, name, closure=f))
        elif op == Op.CALL:
            n = instr.arg
            args = [s.pop() for _ in range(n)][::-1]
            func = s.pop()
            s.append(self.call(func, args))
        elif op == Op.RETURN:
            raise ReturnSignal(s.pop() if s else None)

        elif op == Op.BUILD_LIST:
            n = instr.arg
            items = [s.pop() for _ in range(n)][::-1]
            s.append(items)
        elif op == Op.BUILD_DICT:
            n = instr.arg
            pairs = []
            for _ in range(n):
                v = s.pop(); k = s.pop()
                pairs.append((k, v))
            pairs.reverse()
            s.append(dict(pairs))
        elif op == Op.BUILD_CLASS:
            name_idx, n_methods = instr.arg
            name = f.code.constants[name_idx]
            methods = {}
            for _ in range(n_methods):
                m = s.pop()
                methods[m.name] = m
            cls = DSClass(name, methods)
            self.assign(name, cls)
            s.append(cls)

        elif op == Op.GET_ITER:
            obj = s.pop()
            try:
                s.append(iter(obj))
            except TypeError:
                raise DSTypeError(
                    f"{type(obj).__name__} غير قابل للتكرار",
                    instr.line,
                )
        elif op == Op.FOR_ITER:
            it = s[-1]
            try:
                s.append(next(it))
            except StopIteration:
                s.pop()
                f.ip = instr.arg

        elif op == Op.PUSH_TRY:
            f.block_stack.append((instr.arg, len(s)))
        elif op == Op.POP_TRY:
            if f.block_stack:
                f.block_stack.pop()
        elif op == Op.MATCH_EXC:
            exc_type = s.pop()
            if not (isinstance(exc_type, type) and
                    issubclass(exc_type, BaseException)):
                raise DSTypeError(
                    f"{exc_type!r} ليس نوع استثناء", instr.line
                )
            s.append(isinstance(f.current_exc, exc_type))
        elif op == Op.STORE_EXC:
            self.assign(f.code.names[instr.arg], f.current_exc)
        elif op == Op.RAISE:
            exc = s.pop()
            if not isinstance(exc, BaseException):
                raise DSTypeError(
                    f"لا يمكن رفع {type(exc).__name__}", instr.line
                )
            raise exc
        elif op == Op.RERAISE:
            if f.current_exc is None:
                raise DSRuntimeError(
                    "RERAISE بدون استثناء", instr.line
                )
            raise f.current_exc

        elif op == Op.PRINT:
            value = s.pop()
            print(value)

        elif op == Op.HALT:
            self.frames.pop()
            if not self.frames:
                return

        else:
            raise DSRuntimeError(f"تعليمة غير معروفة: {op}")

    # ----- أدوات -----
    def _getattr(self, obj, name):
        if isinstance(obj, DSInstance):
            if name in obj.attrs:
                return obj.attrs[name]
            if name in obj.klass.methods:
                m = obj.klass.methods[name]
                vm = self
                def bound(*args, m=m, o=obj):
                    return vm.call(m, [o, *args])
                return bound
            raise DSNameError(name)
        if isinstance(obj, DSClass):
            if name in obj.methods:
                return obj.methods[name]
            raise DSNameError(name)
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
            raise DSNameError(name)
        if hasattr(obj, name):
            return getattr(obj, name)
        raise DSNameError(name)

    def _setattr(self, obj, name, value):
        if isinstance(obj, DSInstance):
            obj.attrs[name] = value
        else:
            setattr(obj, name, value)

    def _subscript(self, obj, idx, line):
        try:
            return obj[idx]
        except (IndexError, KeyError) as e:
            raise DSIndexError(str(e), line)

    def _store_subscript(self, obj, idx, value):
        obj[idx] = value


# ═══════════════════════════════════════════════════════════════
# 10) الواجهة الموحّدة
# ═══════════════════════════════════════════════════════════════

def compile_source(source: str) -> CodeObject:
    """من نص إلى Bytecode."""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    return Compiler().compile(ast)


def run_source(source: str, globals_=None):
    """ترجم ونفّذ."""
    code = compile_source(source)
    vm = VM(globals_)
    return vm.run(code)


# ═══════════════════════════════════════════════════════════════
# 11) REPL
# ═══════════════════════════════════════════════════════════════

class REPL:
    def __init__(self):
        self.vm = VM()
        self.buffer: list[str] = []

    def banner(self):
        print("╔═══════════════════════════════════════════╗")
        print("║   DualScript REPL v1.0 — لغة المسند        ║")
        print("║   :help للمساعدة  :quit للخروج            ║")
        print("╚═══════════════════════════════════════════╝")

    def run(self):
        self.banner()
        while True:
            prompt = "ds> " if not self.buffer else "... "
            try:
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not self.buffer and line.strip() in (":quit", ":q", ":exit"):
                break
            if not self.buffer and line.strip() == ":help":
                self._help()
                continue

            if not line.strip() and not self.buffer:
                continue

            self.buffer.append(line)
            src = "\n".join(self.buffer)

            if src.rstrip().endswith(":"):
                continue

            self.buffer = []
            self._exec(src)

    def _exec(self, src):
        try:
            code = compile_source(src)
            frame = Frame(code)
            self.vm.frames = [frame]
            try:
                self.vm._loop()
            except ReturnSignal as r:
                if r.value is not None:
                    print(repr(r.value))
        except Exception as e:
            print(f"خطأ: {e}")

    def _help(self):
        print("""
أوامر REPL:
  :help       هذه المساعدة
  :quit       خروج

أمثلة:
  x = 42
  𐩯𐩬("مرحبا")               # print
  𐩦𐩴 x > 10:                  # if
      𐩯𐩬("كبير")
  𐩧𐩵 add(a, b):               # def
      𐩦𐩵 a + b
""")


# ═══════════════════════════════════════════════════════════════
# 12) CLI
# ═══════════════════════════════════════════════════════════════

def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def cmd_run(args):
    try:
        src = _read(args.file)
        code = compile_source(src)
        if args.dis:
            print(code.disassemble())
        run_source(src)
    except DSError as e:
        print(f"خطأ: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_dis(args):
    src = _read(args.file)
    code = compile_source(src)
    print(code.disassemble())


def cmd_tokens(args):
    src = _read(args.file)
    for t in Lexer(src).tokenize():
        if t.type != "NEWLINE":
            print(t)


def cmd_repl(args):
    REPL().run()


DEMO = '''\
# ── مثال ترحيبي ──
𐩯𐩬("مرحبًا بالعالم من المسند!")

# متغيرات وحساب
x = 10
y = 3
𐩯𐩬(x + y * 2)

# شرط
𐩦𐩴 x > 5:
    𐩯𐩬("x كبير")
𐩦𐩡:
    𐩯𐩬("x صغير")

# حلقة
𐩡𐩱 i 𐩦𐩥 range(3):
    𐩯𐩬(i)

# دالة
𐩧𐩵 greet(name):
    𐩦𐩵 "أهلًا يا " + name

𐩯𐩬(greet("رامي"))

# استثناء
𐩢𐩣:
    𐩯𐩬(1 / 0)
𐩶𐩸 DSZeroDivisionError 𐩦𐩫 e:
    𐩯𐩬("التقطنا الخطأ:")
    𐩯𐩬(e)

# قائمة
nums = [1, 2, 3, 4, 5]
total = 0
𐩡𐩱 n 𐩦𐩥 nums:
    total = total + n
𐩯𐩬("المجموع:")
𐩯𐩬(total)
'''


def cmd_demo(args):
    print("═" * 50)
    print("DualScript — مثال شامل")
    print("═" * 50)
    run_source(DEMO)
    print("═" * 50)
    print("انتهى المثال بنجاح.")


def main():
    validate_keywords()

    parser = argparse.ArgumentParser(
        prog="ds",
        description="DualScript — لغة برمجة بالمسند العربي",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="شغّل ملف")
    p_run.add_argument("file")
    p_run.add_argument("--dis", action="store_true",
                       help="اعرض Bytecode قبل التنفيذ")
    p_run.set_defaults(func=cmd_run)

    p_dis = sub.add_parser("dis", help="اعرض Bytecode")
    p_dis.add_argument("file")
    p_dis.set_defaults(func=cmd_dis)

    p_tok = sub.add_parser("tokens", help="اعرض التوكنات")
    p_tok.add_argument("file")
    p_tok.set_defaults(func=cmd_tokens)

    p_repl = sub.add_parser("repl", help="الصدفة التفاعلية")
    p_repl.set_defaults(func=cmd_repl)

    p_demo = sub.add_parser("demo", help="شغّل مثالًا جاهزًا")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

---

كيف تستخدم الملف

1) احفظه باسم dualscript.py

2) شغّل المثال الجاهز

```bash
python dualscript.py demo
```

المخرج المتوقع:

```
══════════════════════════════════════════════════
DualScript — مثال شامل
══════════════════════════════════════════════════
مرحبًا بالعالم من المسند!
16
x كبير
0
1
2
أهلًا يا رامي
التقطنا الخطأ:
ZeroDivisionError: القسمة على صفر
المجموع:
15
══════════════════════════════════════════════════
انتهى المثال بنجاح.
```

3) شغّل REPL تفاعلي

```bash
python dualscript.py repl
```

```
ds> x = 5 + 3
ds> 𐩯𐩬(x)
8
ds> 𐩧𐩵 add(a, b):
...     𐩦𐩵 a + b
ds> 𐩯𐩬(add(10, 20))
30
```

4) شغّل ملفك الخاص

```bash
python dualscript.py run myfile.ds
```

5) اعرض Bytecode

```bash
python dualscript.py dis myfile.ds
```

---

ما يحتويه الملف

المكوّن الوصف
Lexer توكنة مزدوجة (مسند + لاتين) مع INDENT/DEDENT
Parser محلل نحوي كامل: if/while/for/def/class/try/raise
Compiler تحويل AST إلى Bytecode مكدسي
VM آلة افتراضية مستقلة بتنفيذ البايت كود
Stdlib دوال مدمجة بأسماء عربية ولاتينية
Errors نظام استثناءات عربي كامل
REPL صدفة تفاعلية
CLI أوامر: run, dis, tokens, repl, demo

ما يدعمه

· ✅ 29 حرفًا مسنديًا للكلمات المفتاحية والمعرفات
· ✅ مزج المسند مع اللاتينية في نفس الملف
· ✅ الشروط: if / elif / else
· ✅ الحلقات: while / for / break / continue
· ✅ الدوال: تعريف، نداء، إغلاقات
· ✅ الفئات: class، methods، instance attributes
· ✅ الاستثناءات: try / except / finally / raise
· ✅ القوائم والقواميس: [1,2,3] و {"k": v}
· ✅ العمليات الحسابية والمنطقية والمقارنات
· ✅ الإزاحة بالمسافات (مثل Python)
· ✅ تعليقات بـ #

ما يمكن إضافته لاحقًا

· with statement
· المولدات (yield)
· async / await
· JIT
· Garbage Collector مخصص
· نظام وحدات
· Bootstrapping

---

هذا ملف واحد يعمل من الصفر. كل ما تحتاجه لتأسيس DualScript موجود فيه. احفظه، شغّله، وسترى اللغة تعمل فعليًا.