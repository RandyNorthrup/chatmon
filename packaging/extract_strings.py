"""Write chatmon/locale/chatmon.pot, the template every translation starts from, from the strings marked in
chatmon's modules (chatmon/i18n.py says how strings are marked).

usage: python packaging/extract_strings.py [--check]

--check writes nothing and exits 1 when the template isn't up to date; tests/test_i18n.py makes the same check, so
a string added without bringing the template up to date fails the tests.

It reads the code with the standard library's ast, without running it, and stops (exit 2, naming the file and line)
at a string that couldn't be translated:

- a marked call whose text isn't a plain string literal: an f-string, `"a" + b` or `"…".format()` inside it can't
  be looked up once translated. The one exception is `_(name)`, `_(obj.attr)` or `_(TABLE[key])`: a string marked
  with N_() where it's written, translated where it's shown;
- _() or ngettext() run while a module is imported (at its top level, in a class body, a default value or a
  decorator), before the language is chosen: N_() marks those, and _() translates them where they're shown;
- a function that uses _ as a throwaway name and calls _() as well, where _ is no longer the translation.

References name the file only, without line numbers, so the template changes when strings do, not whenever code
moves.
"""

from __future__ import annotations

import argparse
import ast
import re
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path("chatmon") / "locale" / "chatmon.pot"
MARKERS = {"_": 1, "N_": 1, "ngettext": 3}  # each marker's arguments; the strings are the first one or two
TRANSLATED_NOW = {"_", "ngettext"}  # the ones that translate when called, rather than only mark

HEADER = """\
# The words Chatmon shows, for translating. A translation is a copy of this file in this folder, named for its
# language (de.po, pt_BR.po), with each msgstr filled in and the Plural-Forms line set for the language. Leave a
# {name} placeholder as it is; the words around it can go in any order. Chatmon shows English wherever a msgstr
# is empty or marked fuzzy.
#
# packaging/extract_strings.py writes this file from the code: don't edit it by hand.
msgid ""
msgstr ""
"Project-Id-Version: Chatmon\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=INTEGER; plural=EXPRESSION;\\n"
"""


class ExtractError(Exception):
    """Strings that can't be translated as written, one "file:line: why" each."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass
class Message:
    msgid: str
    plural: str | None
    files: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)


@dataclass
class _Found:
    line: int
    column: int
    msgid: str
    plural: str | None
    comment: str | None


def _marker(call: ast.Call) -> str | None:
    """The marker a call is, `_("…")` or `i18n._("…")`, or None."""
    func = call.func
    if isinstance(func, ast.Name) and func.id in MARKERS:
        return func.id
    if isinstance(func, ast.Attribute) and func.attr in MARKERS and isinstance(func.value, ast.Name) and func.value.id == "i18n":
        return func.attr
    return None


def _translator_comment(lines: list[str], line: int) -> str | None:
    """The "# Translators: …" comment just above a line, joined into one, or None."""
    above: list[str] = []
    at = line - 2
    while at >= 0 and lines[at].strip().startswith("#"):
        above.insert(0, lines[at].strip().lstrip("#").strip())
        at -= 1
    for i, text in enumerate(above):
        if text.startswith("Translators:"):
            return " ".join(above[i:])
    return None


def _binds_underscore(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "_" and isinstance(node.ctx, (ast.Store, ast.Del))
    if isinstance(node, ast.arg):
        return node.arg == "_"
    if isinstance(node, ast.ExceptHandler):
        return node.name == "_"
    return False


def _defaults(args: ast.arguments) -> list[ast.AST]:
    return [*args.defaults, *(d for d in args.kw_defaults if d is not None)]


def _arguments(args: ast.arguments) -> list[ast.arg]:
    return [*args.posonlyargs, *args.args, *args.kwonlyargs, *(a for a in (args.vararg, args.kwarg) if a is not None)]


def _marked(node: ast.Call, marker: str, where: str, at_import: bool, lines: list[str]) -> tuple[_Found | None, list[str]]:
    """One marked call: the string it marks, when it can be translated, and what's wrong with it."""
    problems = []
    if marker in TRANSLATED_NOW and at_import:
        problems.append(f"{where}: {marker}() runs as the module is imported, before the language is chosen; mark it with N_() and translate it with _() where it's shown")
    texts = node.args[: 2 if marker == "ngettext" else 1]
    values = [t.value for t in texts if isinstance(t, ast.Constant) and isinstance(t.value, str)]
    if len(node.args) != MARKERS[marker] or node.keywords:
        problems.append(f"{where}: {marker}() takes {MARKERS[marker]} argument(s), with no keywords")
    elif marker == "_" and isinstance(texts[0], (ast.Name, ast.Attribute, ast.Subscript)):
        pass  # a string marked with N_() where it's written, translated here where it's shown
    elif len(values) != len(texts):
        problems.append(f"{where}: {marker}() needs plain string literals, so the text can be looked up once translated; put values in {{placeholders}} and .format() the result")
    elif not values[0]:
        problems.append(f"{where}: an empty string is gettext's header, not a message")
    else:
        plural = values[1] if marker == "ngettext" else None
        return _Found(node.lineno, node.col_offset, values[0], plural, _translator_comment(lines, node.lineno)), problems
    return None, problems


def scan(source: str, name: str) -> tuple[list[_Found], list[str]]:
    """The marked strings in one module's source, and the problems found in it."""
    tree = ast.parse(source, filename=name)
    lines = source.splitlines()
    found: list[_Found] = []
    problems: list[str] = []
    # Each scope: its own nodes, whether it runs as the module is imported, and the names it takes as arguments.
    scopes: list[tuple[list[ast.AST], bool, list[ast.arg]]] = [(list(tree.body), True, [])]
    while scopes:
        body, at_import, arguments = scopes.pop()
        binds = any(a.arg == "_" for a in arguments)
        translated_here: list[int] = []
        stack = list(body)
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stack.extend([*node.decorator_list, *_defaults(node.args)])  # run where the function is defined
                scopes.append((list(node.body), False, _arguments(node.args)))
                continue
            if isinstance(node, ast.Lambda):
                stack.extend(_defaults(node.args))
                scopes.append(([node.body], False, _arguments(node.args)))
                continue
            if isinstance(node, ast.ClassDef):
                stack.extend([*node.decorator_list, *node.bases, *(k.value for k in node.keywords)])
                scopes.append((list(node.body), at_import, []))
                continue
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                scopes.append((list(ast.iter_child_nodes(node)), at_import, []))  # its loop names are its own
                continue
            binds = binds or _binds_underscore(node)
            if isinstance(node, ast.Call):
                marker = _marker(node)
                if marker is not None:
                    if marker == "_" and isinstance(node.func, ast.Name):
                        translated_here.append(node.lineno)
                    marked, wrong = _marked(node, marker, f"{name}:{node.lineno}", at_import, lines)
                    problems.extend(wrong)
                    if marked is not None:
                        found.append(marked)
            stack.extend(ast.iter_child_nodes(node))
        if binds and translated_here:
            problems.append(f"{name}:{min(translated_here)}: this function uses _ as a name of its own and calls _() too; give the throwaway another name")
    found.sort(key=lambda f: (f.line, f.column))
    return found, problems


def _flags(message: Message) -> list[str]:
    texts = [message.msgid] + ([message.plural] if message.plural else [])
    try:
        named = any(n is not None for t in texts for _l, n, _s, _c in string.Formatter().parse(t))
    except ValueError:
        named = False
    return ["python-brace-format"] if named else []


_ESCAPED = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r", "\a": "\\a", "\b": "\\b", "\f": "\\f", "\v": "\\v"}


def _quote(text: str) -> str:
    return '"' + "".join(_ESCAPED.get(c, c) for c in text) + '"'


def _field(keyword: str, text: str) -> list[str]:
    """A msgid or msgstr: on one line, or split after each line break as gettext's own tools write it."""
    parts = re.findall(r"[^\n]*\n|[^\n]+", text)
    if len(parts) <= 1:
        return [f"{keyword} {_quote(text)}"]
    return [f'{keyword} ""', *(_quote(p) for p in parts)]


def messages(root: Path = ROOT) -> list[Message]:
    """Every marked string in chatmon/'s modules, each once, in the order first met (file by file)."""
    found: dict[str, Message] = {}  # by msgid: gettext keys a message by its English singular alone
    problems: list[str] = []
    for path in sorted((root / "chatmon").glob("*.py")):
        rel = path.relative_to(root).as_posix()
        strings, trouble = scan(path.read_text(encoding="utf-8"), rel)
        problems.extend(trouble)
        for s in strings:
            message = found.setdefault(s.msgid, Message(s.msgid, s.plural))
            if message.plural != s.plural:
                problems.append(f"{rel}:{s.line}: {s.msgid!r} is marked with two different plurals (or with and without one); gettext needs the same each time")
                continue
            if rel not in message.files:
                message.files.append(rel)
            if s.comment and s.comment not in message.comments:
                message.comments.append(s.comment)
    if problems:
        raise ExtractError(problems)
    return list(found.values())


def template(root: Path = ROOT) -> str:
    """The text of chatmon.pot, as it should be for the code under `root`."""
    out = [HEADER.rstrip("\n")]
    for m in messages(root):
        out.append("")
        out.extend(f"#. {c}" for c in m.comments)
        out.append("#: " + " ".join(m.files))
        flags = _flags(m)
        if flags:
            out.append("#, " + ", ".join(flags))
        out.extend(_field("msgid", m.msgid))
        if m.plural is None:
            out.append('msgstr ""')
        else:
            out.extend(_field("msgid_plural", m.plural))
            out.extend(['msgstr[0] ""', 'msgstr[1] ""'])
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 if the template isn't up to date")
    args = parser.parse_args(argv)
    try:
        text = template(ROOT)
    except (ExtractError, SyntaxError) as exc:
        print(f"extract_strings: {exc}", file=sys.stderr)
        return 2
    target = ROOT / TEMPLATE
    current = target.read_text(encoding="utf-8") if target.is_file() else None
    if args.check:
        if current != text:
            print(f"{TEMPLATE.as_posix()} is out of date: run python packaging/extract_strings.py", file=sys.stderr)
            return 1
        return 0
    if current != text:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {TEMPLATE.as_posix()} ({len(messages(ROOT))} strings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
