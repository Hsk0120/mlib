"""mlib・mlib_* のうち、ruff が見ない並び・入力検証・列挙を検査する。

空白・空行・改行位置・引用符・import の並び・未使用名・Maya の import 形式・文字コード・
pathlib への置換は ruff(``ruff.toml``・``_tools/format_mlib.bat``)が担当する。
このツールは次だけを見る。

- 定数・``__all__``・``if TYPE_CHECKING:`` の位置(L004〜L006)
- クラス内メンバーの並びと、対になる操作の隣接(L020〜L023)
- 公開入口の入力assert(L040)と、単純な列挙の確認候補(L041)
- 内部名と function set の取得・関数内importの理由コメント(L050〜L052)
- 例外の文言とUndoチャンク名・fastの受け取り(L060〜L064)
- docstringの見出し・Raisesの並び・固定文・用語・定数の説明、Args:と引数名の一致、残ったTODO(L070〜L077)
- Python 3.7(Maya 2022)で動く書き方と、propertyのgetter(L080・L081)

ast と tokenize だけを使うため通常の Python で実行でき、mlib や Maya を import しない。

--check     規則違反を一覧表示する(違反があれば終了コード1)。
--fix       クラス内メンバーの並び替えを書き込む(並べ替えた後の空行は ruff format が直す)。
--snapshot  各ファイルの関数本文・import束縛・モジュール文・コメントを JSON に保存する。
--compare   保存した JSON と現在のソースを比較し、差分があれば一覧表示して終了コード1。
--outline   クラスのメンバー構成(分類・行範囲)を表示する。
--fix-asserts TYPE  指定行の入力assertをTypeErrorまたはValueErrorへ変換する。
                   対象ファイル1つと --line 行番号を必ず指定する。
--template-docstrings  docstringが無いdefへ、署名と本文から組み立てたGoogle形式のテンプレートを
                   挿入する(対象ファイル1つを指定する)。書けない説明は TODO で残し、埋め忘れは
                   L077(情報)に出る。既存のdocstringは書き換えない。
"""

import argparse
import ast
import collections
import copy
import hashlib
import io
import json
import re
import sys
import tokenize
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ROOT = PACKAGE_ROOT.parent
DEFAULT_TARGETS = (PACKAGE_ROOT.name,)
EXCLUDED_DIRS = {"__tests__", "tests", "docs", "_docs", "_tools", "__pycache__", ".logs"}
MAYA_PACKAGES = {"maya", "maya.api"}
MAYA_SUBMODULES = {"cmds", "mel", "utils", "standalone", "OpenMaya", "OpenMayaAnim", "OpenMayaUI", "OpenMayaRender"}
CONSTANT_NAME = re.compile(r"^_?[A-Z][A-Z0-9_]*$")
# 例外の文言の言語を見分ける。英語の文は「英単語が空白や区切りを挟んで2つ以上続く」で判定する。
JAPANESE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
ENGLISH_PROSE = re.compile(r"[A-Za-z]{2,}[ ,:;]+[A-Za-z]{2,}")
PUBLIC_CONSTANT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
#: 使わない内部名の接頭辞と、代わりに使う名前。
BANNED_INTERNAL_PREFIXES = {
    "_as_": "変換・解決は _resolve_<対象>",
    "_coerce_": "変換・解決は _resolve_<対象>",
    "_validate_": "例外を送出する検証は _require_<条件>、値を返すなら _validated_*",
    "_check_": "例外を送出する検証は _require_<条件>、boolを返すなら _is_*/_has_*",
    "_fast_": "書込みの分岐は _<method>_fast / _<method>_cmds",
}
#: 使わない内部名の末尾(「直接更新」を表す _direct。「直接の子」のような普通の語は対象外)。
BANNED_INTERNAL_SUFFIXES = {"_direct": "書込みの分岐は _<method>_fast / _<method>_cmds"}
#: 既存の登録プロトコル名。接頭辞の規則より優先して維持する。
KEPT_INTERNAL_NAMES = frozenset({"_validate_inputs"})
#: 専用の取得メソッドがある function set(om2のクラス名 → 取得メソッド名)。
FUNCTION_SET_KINDS = {"MFnDependencyNode": "_dependency_fn", "MFnMesh": "_geometry_fn", "MFnNurbsCurve": "_geometry_fn", "MFnNurbsSurface": "_geometry_fn"}
FUNCTION_SET_GETTER = re.compile(r"^_\w*_fn$")
#: Undoチャンク名(mlib + クラス名 + メソッド名のPascalCase)。
UNDO_CHUNK_NAME = re.compile(r"^mlib[A-Z][A-Za-z0-9]*$")
#: docstringの ``Args:`` に書かなくてよい引数(第1引数と可変長)。
IMPLICIT_ARGUMENTS = frozenset({"self", "cls"})
#: docstringの見出しと、その規則上の順序。
DOCSTRING_SECTIONS = ["Args:", "Returns:", "Yields:", "Raises:", "Note:", "Examples:"]
#: Raisesに並べる例外型の順序。ここに無い型は順序を見ない。
RAISES_ORDER = ["TypeError", "ValueError", "IndexError", "RuntimeError", "NotImplementedError"]
#: fastの説明の固定文。
FIXED_FAST_TEXT = "fast (bool): TrueはUndoなしのOpenMaya更新。既定False。"
#: 値を返さない処理のReturnsの固定文。
FIXED_NO_RETURN_TEXT = "None: 値を返さない。"
#: 書き方が決まっている引数の説明。テンプレートではそのまま完成させる。
FIXED_ARGUMENT_TEXTS = {"fast": FIXED_FAST_TEXT, "ws": "ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。"}
#: 短縮名と元の名前。docstringでは元の名前の直後へ置く(署名ではキーワード専用のため後ろに来る)。
ARGUMENT_ALIASES = {"ws": "worldSpace"}
#: テンプレートの1行目。コロンを書かない(propertyのdocstringは1行目を型として読まれるため)。
TEMPLATE_SUMMARY = "TODO 概要を書く。"
#: テンプレートの埋め忘れを探す印。
TEMPLATE_MARK = "TODO"
#: docstringで使わない用語と、代わりに使う言葉。
BANNED_TERMS = {
    "インデックス": "「番号」を使う",
    "添字": "「番号」を使う",
    "配列": "list・doubleArray等のデータ型名か「マルチアトリビュート」を使う",
    "複合アトリビュート": "「コンパウンドアトリビュート」を使う",
}
#: 対応する最も古いPython(Maya 2022)。
PYTHON_FLOOR = (3, 7)
#: Python 3.8以降の自己文書化f-string。
SELF_DOCUMENTING_FSTRING = re.compile(r"""f(['"])[^'"]*=\}""")
#: Python 3.9以降の、組込み型そのものへ添字を付ける注釈。
BUILTIN_GENERICS = {"list", "dict", "set", "tuple", "frozenset", "type"}
#: propertyのgetterで呼ばない om2 のシーン照会。
OM2_SCENE_CALLS = {"MGlobal", "MSelectionList", "MDagPath", "MNamespace"}
ATTRIBUTE, INIT, SPECIAL, CLASS_PUBLIC, PROPERTY, PUBLIC, PRIVATE = range(7)
CATEGORY_LABELS = ("attribute", "init", "special", "classmethod", "property", "public", "private")
INIT_ORDER = {"__new__": 0, "__init__": 1, "__post_init__": 2}
OPERATORS = {"add", "sub", "mul", "matmul", "truediv", "floordiv", "mod", "divmod", "pow", "lshift", "rshift", "and", "xor", "or"}
DUNDER_FOLLOWERS = {
    "__ne__": (("__eq__",), 1),
    "__hash__": (("__eq__",), 2),
    "__str__": (("__repr__",), 1),
    "__setitem__": (("__getitem__",), 1),
    "__delitem__": (("__getitem__",), 2),
    "__deepcopy__": (("__copy__",), 1),
    "__exit__": (("__enter__",), 1),
    "__reduce_ex__": (("__reduce__",), 1),
}
PREFIX_PAIRS = (("disconnect", "connect"), ("unlock", "lock"), ("hide", "show"), ("remove", "add"))
INFORMATIONAL = {"L023", "L041", "L077"}
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
IMPORTS = (ast.Import, ast.ImportFrom)
FSTRING_START = getattr(tokenize, "FSTRING_START", -1)
FSTRING_END = getattr(tokenize, "FSTRING_END", -2)


class Unsupported(Exception):
    """自動整形の対象外にするクラス構成。"""


class Violation:
    """検出した規則違反(またはスキップの通知)。"""

    def __init__(self, path, line, code, message):
        self.path = path
        self.line = line
        self.code = code
        self.message = message

    def __str__(self):
        return f"{relative(self.path)}:{self.line}: {self.code} {self.message}"


class Source:
    """1ファイル分のテキスト・AST・トークン情報。"""

    def __init__(self, path, text):
        self.path = path
        self.lines = text.split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        self.tree = ast.parse(text, filename=str(path))
        self.string_lines = set()
        self.comment_lines = {}
        self.tokens = []
        fstring_starts = []
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            self.tokens.append(tok)
            if tok.type == tokenize.STRING:
                self.string_lines.update(range(tok.start[0] + 1, tok.end[0] + 1))
            elif tok.type == FSTRING_START:
                fstring_starts.append(tok.start[0])
            elif tok.type == FSTRING_END and fstring_starts:
                self.string_lines.update(range(fstring_starts.pop() + 1, tok.end[0] + 1))
            elif tok.type == tokenize.COMMENT and tok.line[: tok.start[1]].strip() == "":
                self.comment_lines[tok.start[0]] = tok.start[1]

    def is_blank(self, lineno):
        return lineno not in self.string_lines and self.lines[lineno - 1].strip() == ""

    def is_comment(self, lineno):
        return lineno in self.comment_lines

    def blank_count(self, line_numbers):
        return sum(1 for n in line_numbers if self.is_blank(n))

    def leading_comment_top(self, start, indent):
        """start 行の直上に空行を挟まず続く、indent 以下の字下げのコメント行の先頭行番号。"""
        line = start
        while line > 1 and self.is_comment(line - 1) and self.comment_lines[line - 1] <= indent:
            line -= 1
        return line

    def header_end(self, node):
        """def/class ヘッダーを閉じるコロンがある行番号を返す。"""
        depth = 0
        for tok in self.tokens:
            if tok.start[0] < node.lineno or (tok.start[0] == node.lineno and tok.start[1] < node.col_offset):
                continue
            if tok.type != tokenize.OP:
                continue
            if tok.string in "([{":
                depth += 1
            elif tok.string in ")]}":
                depth -= 1
            elif tok.string == ":" and depth == 0:
                return tok.start[0]
        return node.lineno


def relative(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def iter_files(targets):
    for target in targets:
        path = Path(target)
        if path.is_file():
            yield path
            continue
        for file in sorted(path.rglob("*.py")):
            if EXCLUDED_DIRS.isdisjoint(file.relative_to(path).parts[:-1]):
                yield file


def read_source(path):
    """テキストと、書き戻し用の改行コード・BOM の有無を返す。"""
    data = path.read_bytes()
    bom = data.startswith(b"\xef\xbb\xbf")
    text = data[3:].decode("utf-8") if bom else data.decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n"), eol, bom


def write_source(path, text, eol, bom):
    data = text.replace("\n", eol).encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)


def load(path):
    text, eol, bom = read_source(path)
    return Source(path, text), eol, bom


def node_start(node):
    decorators = getattr(node, "decorator_list", None) or []
    return min([node.lineno] + [d.lineno for d in decorators])


def is_docstring(node):
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def is_type_checking(node):
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")


def decorator_name(node):
    if isinstance(node, ast.Call):
        node = node.func
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def names_in(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


# ---------------------------------------------------------------- class members


class Member:
    """クラス本体の1文と、その分類・行範囲。"""

    def __init__(self, node):
        self.node = node
        self.indent = node.col_offset
        self.start = node_start(node)
        self.end = node.end_lineno
        self.name = getattr(node, "name", None)
        self.category = ATTRIBUTE
        self.subkey = 0
        self.attach_to = None  # 付随先の定義名、または Member(属性 docstring)
        self.decorators = [decorator_name(d) for d in getattr(node, "decorator_list", [])]


def is_type_declaration_block(stmt):
    """TYPE_CHECKING直下の、値を代入しない単純名の注釈宣言だけを許可する。"""
    if not is_type_checking(stmt) or stmt.orelse:
        return False
    test = stmt.test
    if isinstance(test, ast.Attribute) and not (isinstance(test.value, ast.Name) and test.value.id == "typing"):
        return False
    return all(isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.value is None for item in stmt.body)


def classify_members(cls):
    """クラス本体を Member の列に分類する。整形できない構成は Unsupported を送出する。"""
    body = list(cls.body)
    if body and is_docstring(body[0]):
        body = body[1:]
    def_names = {stmt.name for stmt in body if isinstance(stmt, FUNCTIONS)}
    members = []
    seen = set()
    for stmt in body:
        member = Member(stmt)
        if isinstance(stmt, FUNCTIONS):
            name = stmt.name
            decos = member.decorators
            accessor = any(d.endswith((".setter", ".deleter", ".getter")) for d in decos)
            property_like = accessor or any(d in ("property", "cached_property") or d.endswith(".cached_property") for d in decos)
            if accessor:
                if name not in seen:
                    raise Unsupported(f"property {name} の getter が先に定義されていない")
                member.category = PROPERTY
                member.attach_to = name
            else:
                if name in seen:
                    raise Unsupported(f"同名メンバー {name} が複数ある")
                if property_like:
                    member.category = PROPERTY
                elif name in INIT_ORDER:
                    member.category, member.subkey = INIT, INIT_ORDER[name]
                elif name.startswith("__") and name.endswith("__"):
                    member.category = SPECIAL
                elif name.startswith("_"):
                    member.category = PRIVATE
                elif "staticmethod" in decos or "classmethod" in decos:
                    member.category = CLASS_PUBLIC
                else:
                    member.category = PUBLIC
            referenced = set()
            for deco in stmt.decorator_list:
                referenced |= names_in(deco)
            for default in stmt.args.defaults + [d for d in stmt.args.kw_defaults if d is not None]:
                referenced |= names_in(default)
            if (referenced - {name}) & def_names:
                raise Unsupported(f"{name} のデコレータ・既定値がクラス内の定義を参照する")
            seen.add(name)
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            value = stmt.value
            signature_target = targets[0] if len(targets) == 1 else None
            if (
                isinstance(signature_target, ast.Attribute)
                and signature_target.attr == "__signature__"
                and isinstance(signature_target.value, ast.Name)
                and signature_target.value.id in def_names
            ):
                name = signature_target.value.id
                if name not in seen:
                    raise Unsupported(f"メソッド {name} の署名が定義より先にある")
                member.attach_to = name
                member.name = name + ".__signature__"
            elif isinstance(value, ast.Name) and value.id in def_names and len(targets) == 1 and isinstance(targets[0], ast.Name):
                member.attach_to = value.id
                member.name = targets[0].id
            elif value is not None and names_in(value) & def_names:
                raise Unsupported("クラス属性がメソッドを参照する")
            elif len(targets) == 1 and isinstance(targets[0], ast.Name):
                member.name = targets[0].id
        elif is_docstring(stmt) and members and isinstance(members[-1].node, (ast.Assign, ast.AnnAssign)):
            member.attach_to = members[-1]
        elif is_type_declaration_block(stmt):
            pass
        elif isinstance(stmt, ast.Pass) or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)):
            pass
        else:
            raise Unsupported(f"クラス直下に {type(stmt).__name__} がある")
        members.append(member)
    return members


def follower_anchors(name):
    """対になる先行メンバーの候補名と、先行メンバーの直後での順位を返す。対にならなければ None。"""
    if name in DUNDER_FOLLOWERS:
        return DUNDER_FOLLOWERS[name]
    match = re.match(r"^__([ri])(\w+)__$", name)
    if match and match.group(2) in OPERATORS:
        return ((f"__{match.group(2)}__",), 1 if match.group(1) == "r" else 2)
    match = re.match(r"^set([A-Z].*)?$", name)
    if match:
        rest = match.group(1) or ""
        candidates = ["get" + rest, "is" + rest, "has" + rest]
        if rest:
            candidates.append(rest[0].lower() + rest[1:])
        return (tuple(candidates), 1)
    for prefix, anchor in PREFIX_PAIRS:
        match = re.match(rf"^{prefix}([A-Z].*)?$", name)
        if not match:
            continue
        rest = match.group(1) or ""
        candidates = [anchor + rest]
        if prefix == "disconnect" and rest:
            candidates.append(anchor)
        return (tuple(candidates), 1)
    return None


def primary_indices(members):
    return [i for i, m in enumerate(members) if m.attach_to is None]


def resolve_pairs(members):
    """直後に続けるべき先行メンバーを持つメンバーを {index: (anchor_index, rank)} で返す。"""
    index_of = {}
    for index in primary_indices(members):
        if members[index].name is not None:
            index_of.setdefault(members[index].name, index)
    pairs = {}
    for index in primary_indices(members):
        member = members[index]
        if member.name is None or member.category == ATTRIBUTE:
            continue
        found = follower_anchors(member.name)
        if found is None:
            continue
        candidates, rank = found
        for candidate in candidates:
            anchor = index_of.get(candidate)
            if anchor is not None and anchor != index and members[anchor].category == member.category:
                pairs[index] = (anchor, rank)
                break
    return pairs


def ordered_indices(members):
    """規則に沿ったメンバー順(付随メンバーを除く index の列)を返す。"""
    primary = sorted(primary_indices(members), key=lambda i: (members[i].category, members[i].subkey, i))
    pairs = resolve_pairs(members)
    followers = collections.defaultdict(list)
    for index, (anchor, rank) in pairs.items():
        followers[anchor].append((rank, index))
    emitted = set()
    result = []

    def emit(index):
        if index in emitted:
            return
        emitted.add(index)
        result.append(index)
        for _, follower in sorted(followers.get(index, ())):
            emit(follower)

    for index in primary:
        if index not in pairs:
            emit(index)
    for index in primary:
        emit(index)
    return result


def attached_indices(members):
    """付随メンバーを、付随先 index ごとにまとめる。"""
    attached = collections.defaultdict(list)
    by_name = {}
    for index in primary_indices(members):
        if members[index].name is not None:
            by_name.setdefault(members[index].name, index)
    # 判定省略入口に付随する署名・別名も、元の入口に結び付ける。
    for index, member in enumerate(members):
        if member.name is not None:
            by_name.setdefault(member.name, index)
    for index, member in enumerate(members):
        if member.attach_to is None:
            continue
        target = members.index(member.attach_to) if isinstance(member.attach_to, Member) else by_name[member.attach_to]
        attached[target].append(index)
    return attached


def attachment_groups(members):
    """先行定義と付随メンバーを、依存先が必ず先になる一塊へまとめる。"""
    attached = attached_indices(members)
    groups = {}
    visited = set()

    def collect(index, result):
        if index in visited:
            raise Unsupported("付随メンバーの依存が循環している")
        visited.add(index)
        result.append(index)
        for follower in attached[index]:
            collect(follower, result)

    for index in primary_indices(members):
        group = []
        collect(index, group)
        groups[index] = group
    if len(visited) != len(members):
        raise Unsupported("付随メンバーの依存先を解決できない")
    return groups


def member_blocks(src, cls, members):
    """各メンバーの行テキスト(付随コメント込み)を返す。"""
    docstring = cls.body[0] if cls.body and is_docstring(cls.body[0]) else None
    prev_end = docstring.end_lineno if docstring is not None else src.header_end(cls)
    blocks = []
    for member in members:
        top = src.leading_comment_top(member.start, member.indent)
        trailing = []
        floating = []
        for n in range(prev_end + 1, top):
            if src.is_blank(n):
                floating.append("")
            elif src.comment_lines.get(n, 0) > member.indent and blocks:
                trailing.append(src.lines[n - 1])
            else:
                floating.append(src.lines[n - 1])
        if blocks:
            blocks[-1].extend(trailing)
        while floating and floating[0] == "":
            floating.pop(0)
        while floating and floating[-1] == "":
            floating.pop()
        blocks.append(floating + [src.lines[n - 1] for n in range(top, member.end + 1)])
        prev_end = member.end
    return blocks


def reorder_class(src, cls):
    """クラス本体を規則順に並べ替えた置換 (start, end_exclusive, lines) を返す。"""
    members = classify_members(cls)
    if not members:
        return None
    blocks = member_blocks(src, cls, members)
    groups = attachment_groups(members)
    docstring = cls.body[0] if cls.body and is_docstring(cls.body[0]) else None
    start = node_start(cls)
    header_end = docstring.end_lineno if docstring is not None else src.header_end(cls)
    out = [src.lines[n - 1] for n in range(start, header_end + 1)]
    if docstring is not None:
        out.append("")
    previous = None
    for position, index in enumerate(ordered_indices(members)):
        member = members[index]
        if position:
            if previous.category == ATTRIBUTE and member.category == ATTRIBUTE:
                # 連続する属性(dataclass のフィールドなど)は元の空行数を保ち、離れていた属性は詰める。
                adjacent = members.index(previous) + 1 == index or (members.index(previous) + 2 == index and members[index - 1].attach_to is previous)
                gap = range(members[index - 1].end + 1, src.leading_comment_top(member.start, member.indent))
                out.extend([""] * (src.blank_count(gap) if adjacent else 0))
            else:
                out.append("")
        for offset, extra in enumerate(groups[index]):
            if offset and not is_docstring(members[extra].node):
                out.append("")
            out.extend(blocks[extra])
        previous = member
    return (start, cls.end_lineno + 1, out)


def apply_replacements(lines, reps):
    """(start, end_exclusive, new_lines) を 1-based 行番号で後ろから適用する。"""
    reps = sorted(reps, key=lambda rep: (rep[0], rep[1]), reverse=True)
    last_start = None
    for start, end, new_lines in reps:
        if last_start is not None and end > last_start:
            raise RuntimeError(f"置換範囲が重なっている: {start}-{end} と {last_start}")
        last_start = start
        lines[start - 1 : end - 1] = list(new_lines)
    return lines


def rebuild(path, lines):
    while lines and lines[-1].strip() == "":
        lines.pop()
    return Source(path, "\n".join(lines) + "\n")


def classes_by_depth(tree):
    """ClassDef を、外側を囲む ClassDef の数(深さ)ごとにまとめた dict を返す。

    同じ深さのクラスは互いを含まないため、1回の置換でまとめて並べ替えられる。
    check_classes と同じく、関数内に定義したクラスも対象にする。
    """
    depths = collections.defaultdict(list)

    def visit(node, depth):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                depths[depth].append(child)
                visit(child, depth + 1)
            else:
                visit(child, depth)

    visit(tree, 0)
    return depths


def fix_text(path, text):
    """クラス内メンバーを並べ替えたテキストを返す。空行・空白は ruff format が直す。"""
    src = Source(path, text)
    depth = 0
    while True:
        # 外側のクラスから順に並べ替える。並べ替えで行番号が変わるため、深さごとに解析し直す。
        classes = classes_by_depth(src.tree).get(depth)
        if not classes:
            break
        reps = []
        for node in classes:
            try:
                rep = reorder_class(src, node)
            except Unsupported:
                rep = None
            if rep is not None:
                reps.append(rep)
        if reps:
            src = rebuild(path, apply_replacements(src.lines, reps))
        depth += 1
    return "\n".join(src.lines) + "\n"


# ---------------------------------------------------------------- check


def check_type_checking(src, violations):
    """``if TYPE_CHECKING:`` ブロックの後ろに通常のimportを置いていないか調べる。

    ruff の E402 は条件分岐の後のimportを許すため、この位置だけはここで見る。
    """
    seen = False
    for stmt in src.tree.body:
        if is_type_checking(stmt):
            seen = True
        elif isinstance(stmt, IMPORTS) and seen:
            violations.append(Violation(src.path, stmt.lineno, "L006", "if TYPE_CHECKING: ブロックを import群の後に置く"))
            seen = False


def is_assembled_all(stmt):
    """``__all__`` を文字列の並びではなく、他の名前から組み立てているかを返す。

    ルートの ``__init__.py`` は公開名を集めてから ``__all__`` を作るため、位置を問わない。
    各パッケージの ``__all__ = ["A", "B"]`` は従来どおり定義の前に置く。
    """
    value = stmt.value
    if not isinstance(value, (ast.List, ast.Tuple)):
        return True
    return not all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.elts)


def check_module(src, violations):
    body = src.tree.body
    first_def = next((i for i, stmt in enumerate(body) if isinstance(stmt, DEFINITIONS)), None)
    if first_def is None:
        return
    defined = set()
    index = first_def
    while index < len(body):
        stmt = body[index]
        if isinstance(stmt, DEFINITIONS):
            defined.add(stmt.name)
            index += 1
            continue
        # 連続した代入をひとまとまりとして扱い、先行定義に依存する値を含む並びは後置を許す。
        block = []
        while index < len(body) and isinstance(body[index], (ast.Assign, ast.AnnAssign)):
            block.append(body[index])
            index += 1
        if not block:
            index += 1
            continue
        if any(item.value is not None and names_in(item.value) & defined for item in block):
            continue
        for item in block:
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            if any(CONSTANT_NAME.match(name) for name in names):
                violations.append(Violation(src.path, item.lineno, "L004", "定数 {} を関数・クラス定義の前に置く".format(", ".join(names))))
            elif "__all__" in names and not is_assembled_all(item):
                violations.append(Violation(src.path, item.lineno, "L005", "__all__ を関数・クラス定義の前に置く"))


def check_classes(src, violations):
    for cls in ast.walk(src.tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        try:
            members = classify_members(cls)
            attachments = attachment_groups(members)
        except Unsupported as error:
            violations.append(Violation(src.path, cls.lineno, "L023", f"クラス {cls.name} の並び検査をスキップ({error})"))
            continue
        primary = primary_indices(members)
        highest = (-1, 0)
        highest_name = None
        out_of_order = []
        for index in primary:
            member = members[index]
            rank = (member.category, member.subkey)
            if rank < highest:
                out_of_order.append(f"{member.name} ({CATEGORY_LABELS[member.category]}) を {highest_name} ({CATEGORY_LABELS[highest[0]]}) より前に置く")
            elif rank > highest:
                highest, highest_name = rank, member.name
        if out_of_order:
            violations.append(Violation(src.path, cls.lineno, "L020", f"クラス {cls.name}: メンバー順の違反 {len(out_of_order)}件(例: {out_of_order[0]})"))
        groups = collections.defaultdict(list)
        for index, (anchor, _) in resolve_pairs(members).items():
            groups[anchor].append(index)
        for anchor, followers in sorted(groups.items()):
            positions = sorted(primary.index(i) for i in [anchor] + followers)
            if positions[0] != primary.index(anchor) or positions != list(range(positions[0], positions[0] + len(positions))):
                violations.append(
                    Violation(
                        src.path,
                        members[anchor].start,
                        "L021",
                        "クラス {}: {} を {} の直後に置く".format(cls.name, ", ".join(members[i].name for i in followers), members[anchor].name),
                    )
                )
        for anchor, group in attachments.items():
            for offset, index in enumerate(group[1:], 1):
                if index != anchor + offset:
                    violations.append(
                        Violation(src.path, members[index].start, "L022", f"クラス {cls.name}: {members[index].name} を {members[anchor].name} の直後に置く")
                    )


def ast_position(src, node, end=False):
    """ASTのUTF-8バイト位置を、tokenizeと同じ文字位置へ変換する。"""
    line = node.end_lineno if end else node.lineno
    offset = node.end_col_offset if end else node.col_offset
    column = len(src.lines[line - 1].encode("utf-8")[:offset].decode("utf-8"))
    return line, column


def public_input_asserts(src):
    """公開入口の冒頭で引数に直接触れるassertを、入力検証の候補として返す。

    テスト、内部関数、self/clsだけの確認、処理開始後のassertは対象外。
    任意の関数内データフローや、入力検証と内部整合性の完全な判別は行わない。
    """
    if src.path.name.startswith("test_") or src.path.name.startswith("_") and src.path.name != "__init__.py" or {"__tests__", "tests"} & set(src.path.parts):
        return []
    result = []

    def visit(body):
        for item in body:
            if isinstance(item, ast.ClassDef) and not item.name.startswith("_"):
                visit(item.body)
            elif isinstance(item, FUNCTIONS) and (not item.name.startswith("_") or item.name in {"__init__", "__new__"}):
                args = item.args
                inputs = {arg.arg for arg in args.posonlyargs + args.args + args.kwonlyargs}
                inputs.update(arg.arg for arg in (args.vararg, args.kwarg) if arg is not None)
                inputs -= {"self", "cls"}
                for stmt in item.body:
                    if is_docstring(stmt):
                        continue
                    if not isinstance(stmt, ast.Assert):
                        break
                    if names_in(stmt.test) & inputs:
                        result.append(stmt)

    visit(src.tree.body)
    return result


def rewrite_input_asserts(src, line_numbers, error_type):
    """選んだ入力assertだけを変換し、行の共有・コメント等は書換え前に拒否する。"""
    if error_type not in {"TypeError", "ValueError"}:
        raise ValueError("例外型はTypeErrorまたはValueErrorを指定してください")
    for node in ast.walk(src.tree):
        if (
            (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == error_type)
            or (isinstance(node, ast.arg) and node.arg == error_type)
            or (isinstance(node, DEFINITIONS) and node.name == error_type)
            or (isinstance(node, IMPORTS) and any((alias.asname or alias.name.split(".")[0]) == error_type for alias in node.names))
        ):
            raise ValueError("選択した例外名がソース内で再定義されているため、手動で修正してください")
    candidates = {node.lineno: node for node in public_input_asserts(src)}
    if not line_numbers or any(line not in candidates for line in line_numbers):
        raise ValueError("--lineにはL040で報告された入力assertの行を指定してください")
    reps = []
    for line in sorted(set(line_numbers)):
        node = candidates[line]
        _, column = ast_position(src, node)
        _, end_column = ast_position(src, node, end=True)
        indent = src.lines[line - 1][:column]
        if indent.strip() or src.lines[node.end_lineno - 1][end_column:].strip():
            raise ValueError("他の文・行末コメントと同じ行のassertは手動で修正してください")
        if any(tok.type == tokenize.COMMENT and line <= tok.start[0] <= node.end_lineno for tok in src.tokens):
            raise ValueError("コメントを含むassertは手動で修正してください")
        test = ast.unparse(node.test)
        message = ast.unparse(node.msg) if node.msg is not None else ""
        reps.append((line, node.end_lineno + 1, [indent + "if not (" + test + "):", indent + "    raise " + error_type + "(" + message + ")"]))
    text = "\n".join(apply_replacements(list(src.lines), reps)) + "\n"
    ast.parse(text, filename=str(src.path))
    return text


def check_simple_enumeration(src, violations):
    """要素を読む単純なrange(len(name))を、enumerate検討候補として表示する。"""
    for loop in ast.walk(src.tree):
        if not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Name):
            continue
        outer = loop.iter
        if not (isinstance(outer, ast.Call) and isinstance(outer.func, ast.Name) and outer.func.id == "range" and len(outer.args) == 1 and not outer.keywords):
            continue
        inner = outer.args[0]
        if not (
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "len"
            and len(inner.args) == 1
            and not inner.keywords
            and isinstance(inner.args[0], ast.Name)
        ):
            continue
        sequence = inner.args[0].id
        reads = False
        unsafe = False
        for stmt in loop.body:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == sequence:
                    if not isinstance(node.ctx, ast.Load) or not isinstance(node.slice, ast.Name) or node.slice.id != loop.target.id:
                        unsafe = True
                    else:
                        reads = True
                if isinstance(node, ast.Name) and node.id in {sequence, loop.target.id} and isinstance(node.ctx, (ast.Store, ast.Del)):
                    unsafe = True
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == sequence
                ):
                    unsafe = True
        if reads and not unsafe:
            violations.append(Violation(src.path, loop.lineno, "L041", f"確認候補: {sequence}の番号と要素はenumerateで取得できるか確認する(自動修正なし)"))


# ---------------------------------------------------------------- 内部名・function set・関数内import


def class_methods(tree):
    """(ClassDef, その直下のdef) を列挙する。入れ子のクラスも対象にする。"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, FUNCTIONS):
                yield node, item


def called_names(node):
    """node の中で呼ばれている名前(``f()`` の f、``a.f()`` の f)を列挙する。"""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call):
            yield getattr(inner.func, "id", None) or getattr(inner.func, "attr", None) or "", inner


def check_internal_names(src, violations):
    """内部名の接頭辞が規則どおりかを調べる。

    検証は ``_require_*``、bool を返す判定は ``_is_*``/``_has_*``、検査済みの値を返すものは
    ``_validated_*``、書込みの分岐は ``_<method>_fast``/``_<method>_cmds`` に揃える。
    既存の登録プロトコル名(``Nodes._validate_inputs`` 等)は維持するため除く。
    """
    for node in ast.walk(src.tree):
        if not isinstance(node, FUNCTIONS) or node.name in KEPT_INTERNAL_NAMES:
            continue
        for prefix, reason in BANNED_INTERNAL_PREFIXES.items():
            if node.name.startswith(prefix):
                violations.append(Violation(src.path, node.lineno, "L050", f"内部名 {node.name}: {prefix}* は使わない({reason})"))
                break
        for suffix, reason in BANNED_INTERNAL_SUFFIXES.items():
            if node.name.endswith(suffix):
                violations.append(Violation(src.path, node.lineno, "L050", f"内部名 {node.name}: *{suffix} は使わない({reason})"))
                break


def check_function_sets(src, violations):
    """専用の取得メソッドがある function set を直接作っていないかを調べる。

    ``om2.MFnDependencyNode(self.mnode())`` のように、自身から専用の取得メソッドで得られる
    function set だけを対象にする(``_dependency_fn`` は ``Node``、``_geometry_fn`` は各Shapeが持つ)。
    他のノードを指す引数と、取得メソッドの定義自体(``mfn``・``_<kind>_fn``)は対象外。
    """
    for _, node in class_methods(src.tree):
        if node.name == "mfn" or FUNCTION_SET_GETTER.match(node.name):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Attribute):
                continue
            getter = FUNCTION_SET_KINDS.get(inner.func.attr)
            if getter is None or getattr(inner.func.value, "id", "") != "om2" or not inner.args:
                continue
            source = inner.args[0]
            if not (isinstance(source, ast.Call) and getattr(source.func, "attr", "") in {"mnode", "mpath"}):
                continue
            if getattr(getattr(source.func, "value", None), "id", "") == "self":
                violations.append(Violation(src.path, inner.lineno, "L051", f"function setは self.{getter}() で取得する(om2.{inner.func.attr} の直書き)"))


def check_inner_imports(src, violations):
    """関数内 import の直前に、理由のコメントがあるかを調べる。

    連続した import の群は先頭の1つにコメントがあればよい。モジュール直下の import は対象外。
    """
    for node in ast.walk(src.tree):
        if not isinstance(node, FUNCTIONS):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, IMPORTS):
                continue
            above = src.lines[inner.lineno - 2].strip() if inner.lineno >= 2 else ""
            if above.startswith(("#", "import ", "from ")):
                continue
            violations.append(Violation(src.path, inner.lineno, "L052", "関数内importの直前に、必要な理由の短いコメントを置く"))


# ---------------------------------------------------------------- 例外・ログ・fast


def check_raise_messages(src, violations):
    """例外の文言が日本語の f-string 1つで書かれているかを調べる。

    引数名・型名・パスだけの文言(``f"{name}: {error}"`` など)は対象にせず、
    英語の文(英単語が空白で2つ以上続く)になっていて日本語を含まないものを報告する。
    """
    for node in ast.walk(src.tree):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call) or not node.exc.args:
            continue
        message = node.exc.args[0]
        if isinstance(message, ast.BinOp) and isinstance(message.op, ast.Add):
            violations.append(Violation(src.path, node.lineno, "L061", "例外の文言は f-string 1つで書く(+ での連結は使わない)"))
        text = " ".join(part.value for part in ast.walk(message) if isinstance(part, ast.Constant) and isinstance(part.value, str))
        if ENGLISH_PROSE.search(text) and not JAPANESE.search(text):
            violations.append(Violation(src.path, node.lineno, "L060", "例外の文言は日本語で書く(引数名・型名などの識別子は英字のまま)"))


def check_notify_and_raise(src, violations):
    """同じ関数で logger.error と raise を併せていないかを調べる。"""
    for node in ast.walk(src.tree):
        if not isinstance(node, FUNCTIONS):
            continue
        notifies = [inner for name, inner in called_names(node) if name == "error" and getattr(getattr(inner.func, "value", None), "id", "") == "logger"]
        if notifies and any(isinstance(inner, ast.Raise) for inner in ast.walk(node)):
            violations.append(Violation(src.path, notifies[0].lineno, "L062", "例外を送出する処理で logger.error を重ねない(通知は利用側の入口)"))


def check_undo_chunk_names(src, violations):
    """Undoチャンク名が ``mlib<Class><Method>`` の形かを調べる。"""
    for node in ast.walk(src.tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
        if name not in {"_edit_context", "undoChunk", "undoTransaction"}:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str) and not UNDO_CHUNK_NAME.match(first.value):
            violations.append(
                Violation(src.path, node.lineno, "L063", f"Undoチャンク名 {first.value!r} は mlib<Class><Method> の形にする(短縮・ドット・_ は使わない)")
            )


def check_fast_argument(src, violations):
    """fast を受ける公開メソッドが、検証も転送もしていないかを調べる。

    ``_require_bool(fast, "fast")``・``_edit_context(..., fast)``・内側への ``fast`` の受け渡しの
    どれも無い場合、指定が黙って無視されるため報告する。
    """
    for cls, node in class_methods(src.tree):
        if node.name.startswith("_") or not any(arg.arg == "fast" for arg in node.args.kwonlyargs):
            continue
        for _, inner in called_names(node):
            if any(getattr(arg, "id", "") == "fast" for arg in inner.args):
                break
            if any(keyword.arg == "fast" and getattr(keyword.value, "id", "") == "fast" for keyword in inner.keywords):
                break
        else:
            violations.append(Violation(src.path, node.lineno, "L064", f"{cls.name}.{node.name}: fast を検証も転送もしていない"))


# ---------------------------------------------------------------- docstring・定数


def docstring_sections(doc):
    """docstring に現れた見出しを、出現順に返す。"""
    return [line.strip() for line in doc.splitlines() if line.strip() in DOCSTRING_SECTIONS]


def docstring_entries(doc, section):
    """``Raises:`` のような見出しの直下に並ぶ ``名前:`` の名前を順に返す。"""
    names = []
    inside = False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped == section:
            inside = True
            continue
        if not inside:
            continue
        if stripped in DOCSTRING_SECTIONS:
            break
        match = re.match(r"^([A-Za-z_][\w.]*)\s*(\([^)]*\))?:", stripped)
        if match:
            names.append(match.group(1))
    return names


def docstring_arguments(doc):
    """``Args:`` に並ぶ引数名を順に返す。見出しが無ければNoneを返す。

    ``name (type):``・型を省いた ``name:``・型が次の行へ折り返したものを読み、``*args``・
    ``**kwargs`` の ``*`` は外す。説明の折り返しを名前と読み違えないよう、最初の項目と同じ
    深さの行だけを見る。
    """
    names = None
    depth = None
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped == "Args:":
            names = []
            continue
        if names is None:
            continue
        if stripped in DOCSTRING_SECTIONS:
            break
        indent = len(line) - len(line.lstrip())
        if depth is not None and indent != depth:
            continue
        match = re.match(r"^\*{0,2}([A-Za-z_]\w*)\s*[(:]", stripped)
        if match:
            names.append(match.group(1))
            depth = indent
    return names


def check_docstring_arguments(node, doc):
    """``Args:`` の名前と並びが ``def`` の引数と合っているかを調べ、違いの説明を返す。

    位置引数は署名と同じ順に書く。キーワード専用引数(``fast``・短縮名等)の順は問わない。
    短縮名は元の名前の直後へ置くため、署名の並びとは変わる。``self``・``cls`` と
    ``*args``・``**kwargs`` は、書いても省いても求めない。

    Args:
        node (ast.FunctionDef | ast.AsyncFunctionDef): 対象のdef。
        doc (str): そのdocstring。

    Returns:
        str | None: 違いの説明。合っていればNone。
    """
    documented = docstring_arguments(doc)
    if documented is None:
        return None
    arguments = node.args
    positional = [arg.arg for arg in arguments.posonlyargs + arguments.args if arg.arg not in IMPLICIT_ARGUMENTS]
    declared = positional + [arg.arg for arg in arguments.kwonlyargs]
    allowed = IMPLICIT_ARGUMENTS | {arg.arg for arg in (arguments.vararg, arguments.kwarg) if arg}
    unknown = [name for name in documented if name not in declared and name not in allowed]
    undocumented = [name for name in declared if name not in documented]
    if unknown or undocumented:
        detail = []
        if unknown:
            detail.append("引数に無い: " + ", ".join(unknown))
        if undocumented:
            detail.append("Args:に無い: " + ", ".join(undocumented))
        return " / ".join(detail)
    written = [name for name in documented if name in positional]
    if written != [name for name in positional if name in documented]:
        return "位置引数の順: {}(署名は {})".format(" → ".join(written), " → ".join(positional))
    return None


def own_statements(node):
    """``def`` 自身の本文を、入れ子の def・class の中へ入らずに辿る。"""
    stack = list(node.body)
    while stack:
        current = stack.pop()
        yield current
        if not isinstance(current, DEFINITIONS):
            stack.extend(ast.iter_child_nodes(current))


def raised_types(statements):
    """``raise`` 文の例外型名を、Raisesの規則の順(規則外は名前順)で返す。"""
    names = []
    for statement in statements:
        if not isinstance(statement, ast.Raise) or statement.exc is None:
            continue
        exception = statement.exc.func if isinstance(statement.exc, ast.Call) else statement.exc
        name = getattr(exception, "id", "") or getattr(exception, "attr", "")
        if name and name not in names:
            names.append(name)
    return [name for name in RAISES_ORDER if name in names] + sorted(name for name in names if name not in RAISES_ORDER)


def docstring_template(node):
    """``def`` の署名と本文から、Google形式のdocstringの行を組み立てて返す。

    署名から引数の名前と並び、本文から ``Returns``・``Yields``・``Raises`` を決める。``fast``・``ws``・
    値を返さない ``Returns`` は固定文でそのまま完成させ、書けない説明だけを :data:`TEMPLATE_MARK` にする。
    その印は型として読まれない形(引数は型を省き、戻り値はコロンを書かない)にして、スタブ生成と
    Sphinxのビルドが止まらないようにする。

    Args:
        node (ast.FunctionDef | ast.AsyncFunctionDef): 対象のdef。

    Returns:
        list[str]: docstringの各行。インデントと引用符は付けない。
    """
    arguments = node.args
    ordered = [arg.arg for arg in arguments.posonlyargs + arguments.args + arguments.kwonlyargs if arg.arg not in IMPLICIT_ARGUMENTS]
    for short, long in ARGUMENT_ALIASES.items():
        if short in ordered and long in ordered:
            ordered.remove(short)
            ordered.insert(ordered.index(long) + 1, short)
    ordered += [f"*{arguments.vararg.arg}"] if arguments.vararg else []
    ordered += [f"**{arguments.kwarg.arg}"] if arguments.kwarg else []
    lines = [TEMPLATE_SUMMARY]
    if ordered:
        lines += ["", "Args:"]
        lines += ["    " + FIXED_ARGUMENT_TEXTS.get(name, f"{name}: {TEMPLATE_MARK}。") for name in ordered]
    statements = list(own_statements(node))
    if any(isinstance(statement, (ast.Yield, ast.YieldFrom)) for statement in statements):
        lines += ["", "Yields:", "    " + TEMPLATE_MARK]
    elif any(isinstance(statement, ast.Return) and statement.value is not None for statement in statements):
        lines += ["", "Returns:", "    " + TEMPLATE_MARK]
    else:
        lines += ["", "Returns:", "    " + FIXED_NO_RETURN_TEXT]
    raised = raised_types(statements)
    if raised:
        lines += ["", "Raises:"]
        lines += [f"    {name}: {TEMPLATE_MARK}。" for name in raised]
    return lines


def insert_docstring_templates(src):
    """docstringが無い ``def`` へテンプレートを入れたテキストと、入れた場所を返す。

    既存のdocstringは書き換えない。本文を同じ行に書いた ``def`` は、挿入すると壊れるため対象にしない。

    Args:
        src (Source): 対象のファイル。

    Returns:
        tuple[str, list[tuple[str, int]]]: 挿入後のテキストと、(def名, 行番号)の一覧。
    """
    targets = []
    for node in ast.walk(src.tree):
        if not isinstance(node, FUNCTIONS) or ast.get_docstring(node):
            continue
        first = node.body[0]
        if first.lineno != node.lineno:
            targets.append((first.lineno, first.col_offset, node))
    lines = list(src.lines)
    inserted = []
    # 行番号がずれないよう、後ろの def から順に入れる。
    for lineno, column, node in sorted(targets, key=lambda target: target[0], reverse=True):
        indent = " " * column
        body = docstring_template(node)
        block = [f'{indent}"""{body[0]}'] + [indent + line if line else "" for line in body[1:]] + [f'{indent}"""']
        lines[lineno - 1 : lineno - 1] = block
        inserted.append((node.name, lineno))
    return "\n".join(lines) + "\n", list(reversed(inserted))


def check_docstring_todo(src, violations):
    """テンプレートの ``TODO`` が残っているdocstringを、情報として報告する。"""
    for node in [src.tree] + [node for node in ast.walk(src.tree) if isinstance(node, DEFINITIONS)]:
        doc = ast.get_docstring(node)
        if doc and TEMPLATE_MARK in doc:
            name = getattr(node, "name", src.path.stem)
            violations.append(Violation(src.path, node.body[0].lineno, "L077", f"{name}: docstringの{TEMPLATE_MARK}が残っている"))


def check_docstring_argument_names(src, violations):
    """``Args:`` の名前と並びを、内部の def・``__init__`` も含めて調べる。

    docstringは型スタブにも出るため、公開・非公開を問わず署名と一致させる。
    """
    for node in ast.walk(src.tree):
        if not isinstance(node, FUNCTIONS):
            continue
        doc = ast.get_docstring(node)
        if not doc:
            continue
        detail = check_docstring_arguments(node, doc)
        if detail:
            violations.append(Violation(src.path, node.lineno, "L076", f"{node.name}: {detail}"))


def check_docstrings(src, violations):
    """公開 def の docstring の見出し順・Raisesの並び・1行目・固定文・用語を調べる。"""
    for node in ast.walk(src.tree):
        if not isinstance(node, FUNCTIONS) or node.name.startswith("_"):
            continue
        doc = ast.get_docstring(node)
        if not doc:
            continue
        sections = docstring_sections(doc)
        if sections != sorted(sections, key=DOCSTRING_SECTIONS.index):
            violations.append(Violation(src.path, node.lineno, "L070", f"docstringの見出しの順: {' → '.join(sections)}"))
        raised = [name for name in docstring_entries(doc, "Raises:") if name in RAISES_ORDER]
        if raised != sorted(raised, key=RAISES_ORDER.index):
            violations.append(Violation(src.path, node.lineno, "L071", f"Raisesの並び: {' → '.join(raised)}(規則は {' → '.join(RAISES_ORDER)})"))
        summary = doc.splitlines()[0].rstrip()
        if summary and not summary.endswith("。"):
            violations.append(Violation(src.path, node.lineno, "L072", "docstringの1行目は動詞文「〜する。」で終える"))
        if any(arg.arg == "fast" for arg in node.args.kwonlyargs) and "fast (bool)" in doc and FIXED_FAST_TEXT not in doc:
            violations.append(Violation(src.path, node.lineno, "L073", f"fastの説明は固定文にする: {FIXED_FAST_TEXT}"))
        for word, replacement in BANNED_TERMS.items():
            if word in doc:
                violations.append(Violation(src.path, node.lineno, "L074", f"用語「{word}」は使わない({replacement})"))


def check_module_constants(src, violations):
    """公開のモジュール定数に説明があるかを調べる。

    直前の ``#:`` コメント、または代入の直後の文字列(``\"\"\"str: ...\"\"\"``)のどちらかを認める。
    """
    body = src.tree.body
    for index, node in enumerate(body):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        if not PUBLIC_CONSTANT_NAME.match(name):
            continue
        above = src.lines[node.lineno - 2].strip() if node.lineno >= 2 else ""
        following = body[index + 1] if index + 1 < len(body) else None
        if above.startswith("#:") or is_docstring(following):
            continue
        violations.append(Violation(src.path, node.lineno, "L075", f"公開定数 {name} の説明を #: か直後の文字列で書く"))


# ---------------------------------------------------------------- Python版・property


def check_python_version(src, violations):
    """Python 3.7(Maya 2022)で動く書き方かを調べる。

    構文は ``ast.parse(feature_version=(3, 7))`` で判定し、構文としては通る新しい書き方
    (``f"{x=}"``・``list[int]`` や ``X | Y`` の注釈)を続けて調べる。
    """
    text = "\n".join(src.lines) + "\n"
    try:
        ast.parse(text, filename=str(src.path), feature_version=PYTHON_FLOOR)
    except SyntaxError as error:
        violations.append(Violation(src.path, error.lineno or 1, "L080", f"Python {PYTHON_FLOOR[0]}.{PYTHON_FLOOR[1]} で動かない: {error.msg}"))
    except TypeError:  # feature_version を持たない古いPython。構文の判定は省く。
        pass
    for number, line in enumerate(src.lines, 1):
        if SELF_DOCUMENTING_FSTRING.search(line):
            violations.append(Violation(src.path, number, "L080", 'f"{値=}" はPython 3.8以降の書き方'))
    for annotation, lineno in annotations_in(src.tree):
        for inner in ast.walk(annotation):
            if isinstance(inner, ast.Subscript) and getattr(inner.value, "id", "") in BUILTIN_GENERICS:
                violations.append(Violation(src.path, lineno, "L080", f"注釈の {ast.unparse(inner.value)}[...] はPython 3.9以降(typing を使うか文字列にする)"))
            elif isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.BitOr):
                violations.append(Violation(src.path, lineno, "L080", "注釈の X | Y はPython 3.10以降(typing.Union を使うか文字列にする)"))


def annotations_in(tree):
    """(型注釈のAST, 行番号) を列挙する。文字列の注釈は実行時に評価されないため除く。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and node.annotation is not None:
            yield node.annotation, node.lineno
        elif isinstance(node, FUNCTIONS):
            args = node.args
            for arg in args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]:
                if arg is not None and arg.annotation is not None:
                    yield arg.annotation, arg.lineno
            if node.returns is not None:
                yield node.returns, node.lineno


def check_property_getters(src, violations):
    """property の getter が Maya へ問い合わせていないかを調べる。

    保持する値はプロパティ、Maya へ問い合わせる操作はメソッドという規則の検査。
    cmds・mel の呼出しと、function set・選択・グローバルの om2 呼出しを対象にする。
    """
    for node in ast.walk(src.tree):
        if not isinstance(node, FUNCTIONS):
            continue
        if "property" not in {decorator_name(d) for d in node.decorator_list}:
            continue
        for _, inner in called_names(node):
            func = inner.func
            root = func
            while isinstance(root, ast.Attribute):
                root = root.value
            module = getattr(root, "id", "")
            attribute = getattr(func, "attr", "")
            if module in {"cmds", "mel"} or (module == "om2" and (attribute.startswith("MFn") or attribute in OM2_SCENE_CALLS)):
                violations.append(Violation(src.path, inner.lineno, "L081", f"propertyのgetterでMayaへ問い合わせない({module}.{attribute} はメソッドで行う)"))
                break


def check_source(src):
    violations = []
    check_type_checking(src, violations)
    check_module(src, violations)
    check_classes(src, violations)
    for node in public_input_asserts(src):
        violations.append(Violation(src.path, node.lineno, "L040", "入力検証候補: assertを型付きraiseへ変更する。内部整合性なら用途を個別確認する"))
    check_simple_enumeration(src, violations)
    check_internal_names(src, violations)
    check_function_sets(src, violations)
    check_inner_imports(src, violations)
    check_raise_messages(src, violations)
    check_notify_and_raise(src, violations)
    check_undo_chunk_names(src, violations)
    check_fast_argument(src, violations)
    check_docstrings(src, violations)
    check_docstring_argument_names(src, violations)
    check_docstring_todo(src, violations)
    check_module_constants(src, violations)
    check_python_version(src, violations)
    check_property_getters(src, violations)
    violations.sort(key=lambda v: v.line)
    return violations


# ---------------------------------------------------------------- snapshot / compare


def digest(node):
    return hashlib.sha1(ast.dump(node).encode("utf-8")).hexdigest()[:16]


def import_bindings(stmt):
    """import が束縛する名前と参照先を、import 形式の違いを吸収した文字列で返す。"""
    bindings = []
    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            if alias.asname:
                bindings.append(f"{alias.asname}<-{alias.name}")
            else:
                bindings.append("{}<-import {}".format(alias.name.split(".")[0], alias.name))
        return bindings
    module = "." * stmt.level + (stmt.module or "")
    for alias in stmt.names:
        if not stmt.level and stmt.module in MAYA_PACKAGES and alias.name in MAYA_SUBMODULES:
            bindings.append(f"{alias.asname or alias.name}<-{stmt.module}.{alias.name}")
        else:
            bindings.append(f"{alias.asname or alias.name}<-{module}:{alias.name}")
    return bindings


def snapshot_source(src):
    functions = collections.defaultdict(list)
    classes = {}
    imports = []
    statements = []

    def visit_class(cls, prefix):
        header = copy.copy(cls)
        header.body = [ast.Pass()]
        qualname = prefix + cls.name
        classes[qualname] = {"header": digest(header), "members": sorted(digest(stmt) for stmt in cls.body)}
        for stmt in cls.body:
            if isinstance(stmt, FUNCTIONS):
                functions[qualname + "." + stmt.name].append(digest(stmt))
            elif isinstance(stmt, ast.ClassDef):
                visit_class(stmt, qualname + ".")

    for stmt in src.tree.body:
        if isinstance(stmt, IMPORTS):
            imports.extend(import_bindings(stmt))
        elif isinstance(stmt, FUNCTIONS):
            functions[stmt.name].append(digest(stmt))
        elif isinstance(stmt, ast.ClassDef):
            visit_class(stmt, "")
        else:
            statements.append(ast.dump(stmt))
    return {
        "functions": {name: sorted(values) for name, values in functions.items()},
        "classes": classes,
        "imports": sorted(imports),
        "statements": sorted(statements),
        "comments": sorted(tok.string for tok in src.tokens if tok.type == tokenize.COMMENT),
    }


def compare_snapshots(before, after):
    """差分の説明文の一覧を返す。"""
    messages = []
    for name in sorted(set(before["functions"]) | set(after["functions"])):
        old = before["functions"].get(name)
        new = after["functions"].get(name)
        if old is None:
            messages.append(f"関数が追加: {name}")
        elif new is None:
            messages.append(f"関数が削除: {name}")
        elif old != new:
            messages.append(f"関数の内容が変化: {name}")
    for name in sorted(set(before["classes"]) | set(after["classes"])):
        old = before["classes"].get(name)
        new = after["classes"].get(name)
        if old is None or new is None:
            messages.append("クラスの{}: {}".format("追加" if old is None else "削除", name))
            continue
        if old["header"] != new["header"]:
            messages.append(f"クラス宣言が変化: {name}")
        if old["members"] != new["members"]:
            messages.append("クラス直下の文が変化: {} ({} -> {} 件)".format(name, len(old["members"]), len(new["members"])))
    for label, key in (("import束縛", "imports"), ("モジュール文", "statements"), ("コメント", "comments")):
        old = collections.Counter(before[key])
        new = collections.Counter(after[key])
        for item in sorted((old - new).elements()):
            messages.append(f"{label}が削除: {item[:160]}")
        for item in sorted((new - old).elements()):
            messages.append(f"{label}が追加: {item[:160]}")
    return messages


# ---------------------------------------------------------------- outline / main


def outline(src):
    lines = []
    for cls in ast.walk(src.tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        lines.append(f"class {cls.name} (L{cls.lineno}-{cls.end_lineno})")
        try:
            members = classify_members(cls)
        except Unsupported as error:
            lines.append(f"  (skip: {error})")
            continue
        for member in members:
            label = CATEGORY_LABELS[member.category] if member.attach_to is None else "attached"
            decos = " ".join("@" + d for d in member.decorators)
            lines.append(f"  L{member.start:>5}-{member.end:<5} {label:<10} {member.name or type(member.node).__name__} {decos}".rstrip())
    return lines


def package_of(path):
    parts = relative(path).split("/")
    if parts[:2] == ["maya", "inhouse"]:
        return "/".join(parts[2:4]) if len(parts) > 4 else parts[2]
    return parts[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="対象のファイル・ディレクトリ(既定: このテストを含むmlib)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="規則違反を一覧表示する")
    mode.add_argument("--fix", action="store_true", help="クラス内メンバーの並び替えを書き込む")
    mode.add_argument("--snapshot", metavar="JSON", help="構造の要約を保存する")
    mode.add_argument("--compare", metavar="JSON", help="保存した要約と比較する")
    mode.add_argument("--outline", action="store_true", help="クラスのメンバー構成を表示する")
    mode.add_argument("--fix-asserts", choices=("TypeError", "ValueError"), help="選んだ入力assertを、指定した例外型のraiseへ変換する")
    mode.add_argument("--template-docstrings", action="store_true", help="docstringが無いdefへGoogle形式のテンプレートを挿入する")
    parser.add_argument("--line", action="append", type=int, dest="assert_lines", help="--fix-assertsで修正するL040の行番号(繰り返し指定可)")
    args = parser.parse_args(argv)
    if args.assert_lines and not args.fix_asserts:
        parser.error("--lineは--fix-assertsと組み合わせて指定してください")
    if args.fix_asserts:
        if len(args.paths) != 1 or not Path(args.paths[0]).is_file() or not args.assert_lines:
            parser.error("--fix-assertsには対象ファイル1つと--lineを指定してください")
        path = Path(args.paths[0]).resolve()
        source, eol, bom = load(path)
        try:
            fixed = rewrite_input_asserts(source, args.assert_lines, args.fix_asserts)
        except ValueError as error:
            print(f"修正中止: {error}", file=sys.stderr)
            return 1
        write_source(path, fixed, eol, bom)
        print(f"直した入力assert: {relative(path)} ({args.fix_asserts})")
        return 0
    if args.template_docstrings:
        if len(args.paths) != 1 or not Path(args.paths[0]).is_file():
            parser.error("--template-docstringsには対象ファイル1つを指定してください")
        path = Path(args.paths[0]).resolve()
        src, eol, bom = load(path)
        text, inserted = insert_docstring_templates(src)
        if not inserted:
            print(f"docstringが無いdefはありません: {relative(path)}")
            return 0
        write_source(path, text, eol, bom)
        print(f"入れたdocstringの雛形: {relative(path)} ({len(inserted)})")
        for name, lineno in inserted:
            print(f"  {lineno}: {name}")
        print(f"{TEMPLATE_MARK} を書き換えてから、_tools/format_mlib.bat で整形・検査してください(残りはL077に出ます)。")
        return 0
    targets = [Path(p).resolve() for p in args.paths] if args.paths else [PACKAGE_ROOT]
    files = list(iter_files(targets))
    if args.check:
        violations = []
        for path in files:
            violations.extend(check_source(load(path)[0]))
        for violation in violations:
            print(violation)
        counted = [v for v in violations if v.code not in INFORMATIONAL]
        per_code = collections.Counter(v.code for v in violations)
        per_package = collections.Counter(package_of(v.path) for v in counted)
        print(f"files: {len(files)}  violations: {len(counted)}  informational: {len(violations) - len(counted)}")
        print("by code: " + ", ".join(f"{code}={count}" for code, count in sorted(per_code.items())))
        print("by package: " + ", ".join(f"{name}={count}" for name, count in sorted(per_package.items())))
        return 1 if counted else 0
    if args.fix:
        changed = []
        for path in files:
            text, eol, bom = read_source(path)
            fixed = fix_text(path, text)
            if fixed != text:
                ast.parse(fixed, filename=str(path))
                write_source(path, fixed, eol, bom)
                changed.append(path)
        for path in changed:
            print(f"fixed: {relative(path)}")
        print(f"changed {len(changed)} / {len(files)} files")
        return 0
    if args.snapshot:
        data = {"files": {relative(path): snapshot_source(load(path)[0]) for path in files}}
        output = Path(args.snapshot)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print(f"snapshot: {len(files)} files -> {output}")
        return 0
    if args.compare:
        before = json.loads(Path(args.compare).read_text(encoding="utf-8"))["files"]
        after = {relative(path): snapshot_source(load(path)[0]) for path in files}
        prefixes = tuple(relative(t) + "/" for t in targets if t.is_dir())
        differences = 0
        for name in sorted(set(before) | set(after)):
            if name not in after:
                if name.startswith(prefixes):
                    print(f"{name}: ファイルが無い")
                    differences += 1
                continue
            if name not in before:
                print(f"{name}: 要約に無いファイル")
                differences += 1
                continue
            messages = compare_snapshots(before[name], after[name])
            for message in messages:
                print(f"{name}: {message}")
            differences += len(messages)
        print(f"compared {len(after)} files, {differences} differences")
        return 1 if differences else 0
    for path in files:
        print(f"== {relative(path)}")
        for line in outline(load(path)[0]):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
