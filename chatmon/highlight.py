"""Code in the bubbles, coloured: keywords, strings, comments and numbers.

A small highlighter, not a parser: for each code block (richtext.is_code) it knows the keywords and comment
marks of a handful of languages by the fence's name, and falls back to marks most languages share. Its
colours come from the bubble's style and are made to read on the code block's panel (4.5:1), with the
keywords in the style's link colour so each style's code looks like it belongs to it.

Qt draws a highlighter's formats over the text without storing them, so copying, `toPlainText` and
`toMarkdown` see the code as it was written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument, QTextFormat

from . import richtext, styles

_PY = "and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case None True False self"
_JS = "async await break case catch class const continue debugger default delete do else export extends finally for from function if import in instanceof let new of return static super switch this throw try typeof var void while with yield null undefined true false interface type enum implements readonly"
_C = "auto break case catch char class const continue default delete do double else enum extern final float for goto if inline int long namespace new nullptr override private protected public return short signed sizeof static struct switch template this throw try typedef union unsigned using virtual void volatile while bool true false null var val fun let in is package import"
_RUST = "as async await break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while"
_GO = "break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var nil true false"
_SHELL = "if then else elif fi case esac for while until do done in function select time return exit export local readonly unset set echo cd"
_SQL = "select from where and or not insert into values update set delete create table index drop alter join left right inner outer on group by order having limit as distinct null is in like between union all case when then else end primary key"
_DATA = "true false null yes no on off"

# name: (keywords, line comment marks, block comments, triple-quoted strings)
LANGUAGES: dict[str, tuple[frozenset[str], tuple[str, ...], bool, bool]] = {
    "python": (frozenset(_PY.split()), ("#",), False, True),
    "js": (frozenset(_JS.split()), ("//",), True, False),
    "c": (frozenset(_C.split()), ("//",), True, False),
    "rust": (frozenset(_RUST.split()), ("//",), True, False),
    "go": (frozenset(_GO.split()), ("//",), True, False),
    "shell": (frozenset(_SHELL.split()), ("#",), False, False),
    "sql": (frozenset(_SQL.split()) | frozenset(_SQL.upper().split()), ("--",), True, False),
    "data": (frozenset(_DATA.split()), ("#",), False, False),
}
ALIASES = {
    "py": "python", "python3": "python", "pyi": "python",
    "javascript": "js", "jsx": "js", "ts": "js", "tsx": "js", "typescript": "js", "mjs": "js", "json5": "js",
    "cpp": "c", "c++": "c", "h": "c", "hpp": "c", "cc": "c", "cs": "c", "csharp": "c", "java": "c", "kotlin": "c", "kt": "c", "swift": "c",
    "rs": "rust", "golang": "go",
    "sh": "shell", "bash": "shell", "zsh": "shell", "console": "shell", "shell-session": "shell", "powershell": "shell", "ps1": "shell", "fish": "shell",
    "yaml": "data", "yml": "data", "toml": "data", "ini": "data", "json": "data",
}
# Unknown or unnamed: keywords most languages share, and both comment marks (# only where a word can't be).
ANY = (frozenset("if else elif for while return def function class import from const let var true false null None True False".split()), ("#", "//"), True, False)

_NUMBER = re.compile(r"\b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?)\b")
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Block states, carried from one line of a code block to the next.
INSIDE_COMMENT, INSIDE_SINGLE, INSIDE_DOUBLE = 1, 2, 3


@dataclass(frozen=True)
class CodeColours:
    keyword: QColor
    string: QColor
    number: QColor
    comment: QColor


# Hues to start from, by the panel's lightness; each ends up made to read on the panel.
_ON_DARK = {"string": ("#a5e075", "#7fdbca", "#e6d27a"), "number": ("#f5b971", "#d7a8ff", "#ff9e9e")}
_ON_LIGHT = {"string": ("#2e7d32", "#00796b", "#7a5b00"), "number": ("#a14a00", "#7b1fa2", "#b71c1c")}


def code_colours(c: styles.Colours) -> CodeColours:
    """The style's code colours: keywords in its link colour, strings and numbers in hues that stand apart
    from it, comments faded toward the panel; every one 4.5:1 on the code panel."""
    panel = c.code_fill
    hues = _ON_DARK if styles.luminance(panel) < 0.2 else _ON_LIGHT
    keyword = styles.readable(c.link, panel)

    def apart(choices: tuple[str, ...]) -> QColor:
        for name in choices:  # the first whose hue isn't the keywords'
            colour = QColor(name)
            if keyword.hslHue() < 0 or abs((colour.hslHue() - keyword.hslHue() + 180) % 360 - 180) >= 40:
                return styles.readable(colour, panel)
        return styles.readable(QColor(choices[0]), panel)

    return CodeColours(keyword, apart(hues["string"]), apart(hues["number"]), styles.readable(styles.blend(c.body, panel, 150), panel))


def language(block) -> tuple[frozenset[str], tuple[str, ...], bool, bool]:
    name = block.blockFormat().stringProperty(QTextFormat.Property.BlockCodeLanguage).strip().lower()
    return LANGUAGES.get(ALIASES.get(name, name), ANY)


class CodeHighlighter(QSyntaxHighlighter):
    """Colours the code blocks of one document; everything else is left as it is."""

    def __init__(self, doc: QTextDocument, colours: CodeColours):
        super().__init__(doc)
        self._formats: dict[str, QTextCharFormat] = {}
        self.set_colours(colours)

    def set_colours(self, colours: CodeColours) -> None:
        self.colours = colours
        for kind in ("keyword", "string", "number", "comment"):
            f = QTextCharFormat()
            f.setForeground(getattr(colours, kind))
            if kind == "keyword":
                f.setFontWeight(QFont.Weight.DemiBold)
            if kind == "comment":
                f.setFontItalic(True)
            self._formats[kind] = f
        self.rehighlight()

    def highlightBlock(self, text: str | None) -> None:
        text = text or ""
        block = self.currentBlock()
        if not richtext.is_code(block):
            self.setCurrentBlockState(-1)
            return
        keywords, comments, block_comments, triple = language(block)
        state = self.previousBlockState()
        i, n = 0, len(text)
        # Carried over from the line before: inside a /* comment */ or a triple-quoted string.
        if state in (INSIDE_COMMENT, INSIDE_SINGLE, INSIDE_DOUBLE):
            close = {INSIDE_COMMENT: "*/", INSIDE_SINGLE: "'''", INSIDE_DOUBLE: '"""'}[state]
            end = text.find(close)
            kind = "comment" if state == INSIDE_COMMENT else "string"
            if end < 0:
                self.setFormat(0, n, self._formats[kind])
                self.setCurrentBlockState(state)
                return
            i = end + len(close)
            self.setFormat(0, i, self._formats[kind])
        self.setCurrentBlockState(0)
        while i < n:
            ch = text[i]
            if block_comments and text.startswith("/*", i):
                end = text.find("*/", i + 2)
                if end < 0:
                    self.setFormat(i, n - i, self._formats["comment"])
                    self.setCurrentBlockState(INSIDE_COMMENT)
                    return
                self.setFormat(i, end + 2 - i, self._formats["comment"])
                i = end + 2
                continue
            mark = next((m for m in comments if text.startswith(m, i)), None)
            if mark and (mark != "#" or comments != ANY[1] or i == 0 or text[i - 1].isspace()):
                self.setFormat(i, n - i, self._formats["comment"])
                return
            if triple and text.startswith(("'''", '"""'), i):
                quote = text[i : i + 3]
                end = text.find(quote, i + 3)
                if end < 0:
                    self.setFormat(i, n - i, self._formats["string"])
                    self.setCurrentBlockState(INSIDE_SINGLE if quote == "'''" else INSIDE_DOUBLE)
                    return
                self.setFormat(i, end + 3 - i, self._formats["string"])
                i = end + 3
                continue
            if ch in "\"'`":
                j = i + 1
                while j < n and text[j] != ch:
                    j += 2 if text[j] == "\\" else 1
                j = min(j + 1, n)
                self.setFormat(i, j - i, self._formats["string"])
                i = j
                continue
            word = _WORD.match(text, i)
            if word:
                if word.group() in keywords:
                    self.setFormat(i, word.end() - i, self._formats["keyword"])
                i = word.end()
                continue
            number = _NUMBER.match(text, i)
            if number and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
                self.setFormat(i, number.end() - i, self._formats["number"])
                i = number.end()
                continue
            i += 1
