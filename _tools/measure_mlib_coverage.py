"""mlibのMayaのテストを実行しながら、テストがmlib本体のどこをどう確かめているかを数える。

テストの書き漏れを見つけるための道具。標準ライブラリの ``sys.settrace`` だけを使い、追加のパッケージは要らない。
テストは ``__tests__/runMaya.py`` と同じ隔離した設定のmayapyで実行する。

使い方(mlibのフォルダーで実行する。``py`` はPython 3.8以上):

    py -3 _tools/measure_mlib_coverage.py                       # Maya 2027で全部のテスト
    py -3 _tools/measure_mlib_coverage.py --versions 2022 2027  # 版ごとに測り、合わせた結果も出す
    py -3 _tools/measure_mlib_coverage.py --tests test_joint.py --only nodes/joint.py

結果は ``__tests__/_output/coverage/<日時>/`` に置く(Gitの対象外)。

- ``summary.txt``: パッケージごとの、実行された行・両側を通った分岐の割合と、観点の抜けの数。版ごとと、全部の版を合わせた値。
- ``gaps/<パッケージ>.md``: 全部の版を合わせても実行されなかった行を、関数ごとに並べたもの。
- ``branches/<パッケージ>.md``: 片側しか通っていない分岐(``if``・``for``・``while``)。
- ``viewpoints/<パッケージ>.md``: 公開メソッドごとの、テストで確かめていない観点(下を参照)。
- ``<版>/hits.json``: 版ごとの記録(合わせ直すときの元)。``--by-test`` のときはテストのファイルごとの実行された行も入る。

観点は、テストのコードから直接呼んだ(mlibの別の公開メソッドの中からではない)呼び出しだけで数える。

- 引数: キーワード専用の引数で、既定がboolのものは、TrueとFalseの両方で呼んだか。
- 例外: docstringの ``Raises:`` に書いた型(その派生を含む)が、そのメソッドから実際に出たか。``with`` の中で出た例外も数える。
- Undo: 書き換えるメソッド(``fast`` を持つか、名前が ``set``・``add`` などで始まる。数学型と、複数形のlistと同じ操作は除く)の後で、同じテストが ``cmds.undo`` を呼んだか。
- fastのUndoなし: ``fast=True`` で呼んだ後で、同じテストが ``cmds.undoInfo(undoQueueEmpty=True)`` で確かめたか。
- 突き合わせ: 呼んだ後で、同じテストが ``cmds`` の問い合わせ(``getAttr``・``query=True`` など)を呼んだか、OpenMayaを使ったか。
- 複数形: ``Nodes`` などの複数形から転送して呼んだか(情報として表示するだけ)。

数える行は、docstringを除いた実行される行(Pythonがコンパイルした行の表)。分岐は、条件の行から本体へ進んだか(成り立つ側)と、
本体以外へ進んだか(成り立たない側)を見る。``and``・``or`` の途中は数えない。
テストの中で深い再帰などが起きるとトレースが外れることがあるので、テストのファイルごととテストごとに付け直し、
ファイルの終わりで外れていたものは ``summary.txt`` に書く。
"""

import argparse
import ast
import contextlib
import datetime
import functools
import importlib.util
import inspect
import json
import os
import re
import runpy
import subprocess
import sys
import threading
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "__tests__"
EXCLUDED_FOLDERS = ("__tests__", "_tools", "_docs")
#: 突き合わせとして数える、テストからのcmdsの読み取り(``query=True`` の呼び出しも数える)。
QUERY_COMMANDS = frozenset(
    (
        "getAttr",
        "ls",
        "listRelatives",
        "listConnections",
        "listAttr",
        "listHistory",
        "pointPosition",
        "polyEvaluate",
        "polyInfo",
        "objExists",
        "nodeType",
        "attributeQuery",
        "connectionInfo",
        "isConnected",
        "keyframe",
        "polyListComponentConversion",
        "filterExpand",
        "referenceQuery",
        "namespaceInfo",
        "getPanel",
    )
)
#: 名前がこれで始まるメソッドは、シーンを書き換えるものとして Undo を確かめる対象にする。
#: ファイルの読み書き(load・save・import・export・open など)は Undo に記録されないので入れない。
WRITE_PREFIXES = (
    "set",
    "add",
    "remove",
    "delete",
    "connect",
    "disconnect",
    "create",
    "rename",
    "reset",
    "mirror",
    "apply",
    "lock",
    "unlock",
    "freeze",
    "bake",
    "bind",
    "unbind",
    "insert",
    "move",
    "copy",
    "transfer",
    "prune",
    "normalize",
    "smooth",
    "reverse",
    "rebuild",
    "assign",
    "clear",
    "compact",
    "duplicate",
    "publish",
    "unpublish",
    "replace",
    "extrude",
    "swap",
    "toggle",
    "merge",
    "reorder",
    "scale",
    "flip",
    "match",
    "regenerate",
    "invert",
    "redistribute",
    "round",
    "cut",
    "paste",
    "shift",
    "snap",
    "orient",
    "parent",
    "group",
    "combine",
    "split",
)


#: 複数形がPythonのlistと同じに持つ操作。集まりの中身だけを変え、シーンは書き換えない。
LIST_METHODS = frozenset(("append", "extend", "insert", "remove", "pop", "index", "count", "clear", "reverse", "sort", "copy"))


def _load_run_maya():
    """``__tests__/runMaya.py`` を読み込み、mayapyの場所と隔離した環境の作り方を借りる。

    Returns:
        module: runMayaのモジュール。
    """
    spec = importlib.util.spec_from_file_location("_mlib_run_maya", TESTS_DIR / "runMaya.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _public_definitions():
    """mlib本体の公開の関数とメソッドを、構文木から集める。

    公開なのは、名前が ``_`` で始まらないモジュール直下の関数と、名前が ``_`` で始まらないクラスのメソッド。

    Returns:
        dict[tuple[str, int], tuple[str, ast.FunctionDef]]: (normcaseしたパス, defか先頭のデコレーターの行)と、
            (``相対パス:Class.method`` の名前, 定義)。
    """
    result = {}
    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(EXCLUDED_FOLDERS) or ".venv" in relative:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        key_path = os.path.normcase(str(path))
        owners = [("", node) for node in tree.body]
        owners += [(node.name + ".", child) for node in tree.body if isinstance(node, ast.ClassDef) and not node.name.startswith("_") for child in node.body]
        for prefix, node in owners:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            name = f"{relative}:{prefix}{node.name}"
            for line in [node.lineno] + [decorator.lineno for decorator in node.decorator_list]:
                result[(key_path, line)] = (name, node)
    return result


# --- Mayaの中で動く部分(Python 3.7でも動く書き方にする) ---


def _exception_names(kind):
    """例外の型と、その継承元の名前を返す(``MissingAttributeError`` なら ``AttributeError`` も)。

    Args:
        kind (type): 例外の型。

    Returns:
        set[str]: 型の名前。``object``・``BaseException``・``Exception`` は除く。
    """
    return {base.__name__ for base in kind.__mro__ if base not in (object, BaseException, Exception)}


class _Recorder:
    """テストを実行している間の、行・分岐・公開メソッドの呼び出しの記録。"""

    def __init__(self, by_test):
        """記録する入れ物を用意する。

        Args:
            by_test (bool): Trueなら、テストのファイルごとの実行された行も記録する。
        """
        self.prefix = os.path.normcase(str(ROOT)) + os.sep
        self.skipped = tuple(os.path.normcase(str(ROOT / name)) + os.sep for name in EXCLUDED_FOLDERS)
        self.tests_prefix = os.path.normcase(str(TESTS_DIR)) + os.sep
        self.public = {key: value[0] for key, value in _public_definitions().items()}
        self.public_names = {value: value.rsplit(".", 1)[-1].rsplit(":", 1)[-1] for value in self.public.values()}
        self.hits = {}
        self.arcs = {}
        self.wanted = {}
        self.is_test_file = {}
        self.last = {}
        self.stack = []
        self.external = {}
        self.pending = {}
        self.views = {}
        self.test_calls = []
        self.by_test = {} if by_test else None
        self.current_file = None
        self.lost = []

    def wants(self, filename):
        """記録の対象のファイル(mlib本体の .py)かを返す。

        Args:
            filename (str): コードのファイル名。

        Returns:
            bool: 対象ならTrue。
        """
        result = self.wanted.get(filename)
        if result is None:
            normalized = os.path.normcase(filename)
            result = normalized.startswith(self.prefix) and not normalized.startswith(self.skipped) and normalized.endswith(".py")
            self.wanted[filename] = result
        return result

    def from_tests(self, filename):
        """テストのコードのファイルかを返す。

        Args:
            filename (str): コードのファイル名。

        Returns:
            bool: ``__tests__`` の中ならTrue。
        """
        result = self.is_test_file.get(filename)
        if result is None:
            result = os.path.normcase(filename).startswith(self.tests_prefix)
            self.is_test_file[filename] = result
        return result

    def add_line(self, frame, line):
        """実行された行と、前の行からの移り(分岐)を記録する。

        Args:
            frame (frame): 実行中のフレーム。
            line (int): 行の番号。負の数は関数の出入り。
        """
        filename = frame.f_code.co_filename
        previous = self.last.get(id(frame))
        if previous is not None:
            self.arcs.setdefault(filename, set()).add((previous, line))
        if line > 0:
            self.last[id(frame)] = line
            self.hits.setdefault(filename, set()).add(line)
            if self.by_test is not None and self.current_file is not None:
                self.by_test.setdefault(self.current_file, {}).setdefault(filename, set()).add(line)

    def record_call(self, frame, key):
        """テストのコードから直接呼ばれた公開メソッドの、引数と呼び方を記録する。

        Args:
            frame (frame): 呼ばれたメソッドのフレーム。
            key (str): 公開メソッドの名前。
        """
        view = self.views.setdefault(key, {"calls": 0, "flags": set(), "raised": set(), "undo": False, "fastUndo": False, "parity": False, "plural": False})
        view["calls"] += 1
        code = frame.f_code
        values = frame.f_locals
        for name in code.co_varnames[: code.co_argcount + code.co_kwonlyargcount]:
            if name in ("self", "cls") or name not in values:
                continue
            value = values[name]
            if isinstance(value, bool) or value is None:
                view["flags"].add(f"{name}={value!r}")
        caller = frame.f_back
        for _ in range(8):
            if caller is None:
                break
            if caller.f_code.co_name in ("forward", "_forward", "callEach") and self.wants(caller.f_code.co_filename):
                view["plural"] = True
                break
            caller = caller.f_back
        self.external[id(frame)] = key
        self.test_calls.append((key, values.get("fast") is True))

    def global_trace(self, frame, event, _arg):
        """呼び出しごとにPythonが呼ぶ関数。対象のファイルの関数だけを細かく追う。

        Args:
            frame (frame): 呼ばれたフレーム。
            event (str): ``"call"``。

        Returns:
            Callable | None: そのフレームを追う関数。対象外ならNone。
        """
        if event != "call":
            return None
        if self.from_tests(frame.f_code.co_filename):
            return self.test_trace
        if not self.wants(frame.f_code.co_filename):
            return None
        code = frame.f_code
        self.last[id(frame)] = -code.co_firstlineno
        self.hits.setdefault(code.co_filename, set()).add(frame.f_lineno)
        key = self.public.get((os.path.normcase(code.co_filename), code.co_firstlineno))
        if key is not None and self.public_names.get(key) == code.co_name:
            external = not self.stack or self.stack[-1][1] == "callEach"
            self.stack.append((id(frame), code.co_name))
            if external:
                self.record_call(frame, key)
        return self.local_trace

    def test_trace(self, _frame, event, arg):
        """テストのコードのフレームで、届いた例外を、最初に通った公開メソッドの例外として数える。

        Args:
            _frame (frame): テストのフレーム。
            event (str): イベントの種類。``"exception"`` だけを見る。
            arg (object): 例外のときは (型, 値, トレースバック)。

        Returns:
            Callable: 自身。続けて追う。
        """
        if event == "exception":
            traceback = arg[2].tb_next if arg[2] is not None else None
            while traceback is not None:
                code = traceback.tb_frame.f_code
                key = self.public.get((os.path.normcase(code.co_filename), code.co_firstlineno))
                if key is not None and self.public_names.get(key) == code.co_name:
                    if key in self.views:
                        self.views[key]["raised"].update(_exception_names(arg[0]))
                    break
                traceback = traceback.tb_next
        return self.test_trace

    def local_trace(self, frame, event, arg):
        """対象の関数の中の、行・例外・戻りごとにPythonが呼ぶ関数。

        Args:
            frame (frame): 実行中のフレーム。
            event (str): ``"line"``・``"exception"``・``"return"`` など。
            arg (object): 例外のときは (型, 値, トレースバック)。

        Returns:
            Callable: 自身。続けて追う。
        """
        frame_id = id(frame)
        if event == "line":
            self.add_line(frame, frame.f_lineno)
            self.pending.pop(frame_id, None)
        elif event == "exception":
            if frame_id in self.external:
                self.pending[frame_id] = _exception_names(arg[0])
        elif event == "return":
            self.add_line(frame, -frame.f_code.co_firstlineno)
            self.last.pop(frame_id, None)
            if self.stack and self.stack[-1][0] == frame_id:
                self.stack.pop()
            key = self.external.pop(frame_id, None)
            raised = self.pending.pop(frame_id, None)
            if key is not None and raised is not None:
                self.views[key]["raised"].update(raised)
        return self.local_trace

    def on_command(self, name, kwargs):
        """テストのコードがcmdsを呼んだときに、それまでに呼んだメソッドの観点を記録する。

        Args:
            name (str): cmdsの関数名。
            kwargs (dict): キーワード引数。
        """
        if name == "undo":
            for key, _ in self.test_calls:
                self.views[key]["undo"] = True
        elif name == "undoInfo" and (kwargs.get("undoQueueEmpty") or kwargs.get("uqe")):
            for key, fast in self.test_calls:
                if fast:
                    self.views[key]["fastUndo"] = True
        if name in QUERY_COMMANDS or kwargs.get("query") or kwargs.get("q"):
            for key, _ in self.test_calls:
                self.views[key]["parity"] = True

    def wrap_commands(self):
        """maya.cmdsの関数を包み、テストのコードからの呼び出しを :meth:`on_command` へ知らせる。"""
        import maya.cmds as cmds

        def make(name, function):
            @functools.wraps(function)
            def wrapper(*args, **kwargs):
                if self.from_tests(sys._getframe(1).f_code.co_filename):
                    self.on_command(name, kwargs)
                return function(*args, **kwargs)

            return wrapper

        for name in dir(cmds):
            function = getattr(cmds, name)
            if not name.startswith("_") and callable(function):
                setattr(cmds, name, make(name, function))

    def start(self):
        """トレースを付ける。"""
        sys.settrace(self.global_trace)
        threading.settrace(self.global_trace)

    def to_data(self):
        """書き出す形にする。

        Returns:
            dict: JSONにできる記録。
        """
        views = {}
        for key, view in self.views.items():
            views[key] = dict(view, flags=sorted(view["flags"]), raised=sorted(view["raised"]))
        data = {
            "hits": {name: sorted(lines) for name, lines in self.hits.items()},
            "arcs": {name: sorted(pairs) for name, pairs in self.arcs.items()},
            "views": views,
            "lost": self.lost,
        }
        if self.by_test is not None:
            data["byTest"] = {test: {name: sorted(lines) for name, lines in files.items()} for test, files in self.by_test.items()}
        return data


def _worker(output, selected_tests, suite, by_test):
    """mayapyの中でテストを実行し、記録を ``output`` へJSONで書く。

    Args:
        output (Path): 書き出すJSONのパス。
        selected_tests (list[str] | None): 実行するテストのファイル名。Noneなら全部。
        suite (str): ``unit``・``integration``・``all``。
        by_test (bool): Trueなら、テストのファイルごとの実行された行も書く。

    Returns:
        int: 終了コード。テストが失敗しても、記録は書き出す。
    """
    import maya.standalone

    maya.standalone.initialize(name="python")
    recorder = _Recorder(by_test)
    recorder.wrap_commands()
    sys.path[:0] = [str(ROOT.parent), str(TESTS_DIR), str(ROOT / "_tools")]
    namespace = runpy.run_path(str(TESTS_DIR / "runAll.py"))
    run_all = namespace["run_all"]
    run_all.__globals__["LOG_DIR"] = output.parent
    real_runpy = run_all.__globals__["runpy"]

    class _Rearm:
        """テストのファイルを実行するたびに、トレースを付け直す。"""

        @staticmethod
        def run_path(path, *args, **kwargs):
            recorder.current_file = Path(path).resolve().relative_to(TESTS_DIR).as_posix()
            recorder.start()
            try:
                return real_runpy.run_path(path, *args, **kwargs)
            finally:
                if sys.gettrace() is None:
                    recorder.lost.append(str(path))

    run_all.__globals__["runpy"] = _Rearm
    # 1つのファイルの途中で外れても、次のテストから数え直せるように、テストごとにも付け直す。
    # 観点の記録は、テストごとに呼んだメソッドを数え直す。
    import unittest

    original_run = unittest.TestCase.run

    def run_with_trace(self, *args, **kwargs):
        if sys.gettrace() is None:
            sys.settrace(recorder.global_trace)
        recorder.test_calls = []
        try:
            source = inspect.getsource(getattr(type(self), self._testMethodName))
        except (AttributeError, OSError, TypeError):
            source = ""
        try:
            return original_run(self, *args, **kwargs)
        finally:
            if "om2." in source or "OpenMaya" in source:
                for key, _ in recorder.test_calls:
                    recorder.views[key]["parity"] = True
            recorder.test_calls = []

    unittest.TestCase.run = run_with_trace
    result = {}
    try:
        result = run_all(names=selected_tests, suite=suite)
    except AssertionError as error:
        # 失敗したテストがあっても、記録は書き出す。
        result = {"error": str(error)}
    finally:
        sys.settrace(None)
        threading.settrace(None)
    data = recorder.to_data()
    data.update(failed=result.get("failed"), error=result.get("error"))
    output.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with contextlib.suppress(RuntimeError):
        maya.standalone.uninitialize()
    return 0 if not result.get("failed") and not result.get("error") else 1


# --- 手元のPythonで動く部分 ---


def _run_version(run_maya, version, directory, selected_tests, suite, by_test):
    """1つの版のmayapyで、このファイルを ``--worker`` として実行する。

    Args:
        run_maya (module): runMayaのモジュール。
        version (str): Mayaの版。
        directory (Path): この版の作業フォルダー(まだ無いこと)。
        selected_tests (list[str] | None): 実行するテストのファイル名。
        suite (str): テストの範囲。
        by_test (bool): Trueなら、テストのファイルごとの実行された行も記録する。

    Returns:
        dict | None: 書き出された結果。mayapyが無いか、結果を書けなかったときはNone。
    """
    install_root = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Autodesk"
    executable = run_maya.maya_executable(version, install_root)
    if not executable.is_file():
        print(f"[NG] Maya {version}: mayapyが見つかりません: {executable}")
        return None
    directory.mkdir(parents=True)
    output = directory / "hits.json"
    command = [str(executable), str(Path(__file__).resolve()), "--worker", str(output), "--suite", suite]
    if by_test:
        command.append("--by-test")
    if selected_tests:
        command += ["--tests", *selected_tests]
    print(f"Maya {version}: 実行中")
    with (directory / "console.log").open("w", encoding="utf-8") as console:
        subprocess.call(command, cwd=str(ROOT), env=run_maya.isolated_environment(executable, directory), stdout=console, stderr=subprocess.STDOUT)
    if not output.is_file():
        print(f"[NG] Maya {version}: 結果を書き出せませんでした({directory / 'console.log'} を確かめてください)")
        return None
    return json.loads(output.read_text(encoding="utf-8"))


def _source_files(only):
    """数える対象のmlib本体の .py を返す。

    Args:
        only (tuple[str, ...]): mlibからの相対パスの先頭。空なら全部。

    Returns:
        list[tuple[str, Path]]: (相対パス, パス)。
    """
    files = []
    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(EXCLUDED_FOLDERS) or ".venv" in relative or (only and not relative.startswith(only)):
            continue
        files.append((relative, path))
    return files


def _executable_lines(source, path):
    """実行される行の番号の集まりを返す。docstringの行は除く。

    Args:
        source (str): ソースの文字列。
        path (Path): ソースのパス。

    Returns:
        tuple[set[int], ast.Module]: 行の番号と、構文木。
    """
    lines = set()
    stack = [compile(source, str(path), "exec")]
    while stack:
        code = stack.pop()
        lines.update(line for _, _, line in code.co_lines() if line)
        stack.extend(const for const in code.co_consts if hasattr(const, "co_code"))
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                lines.difference_update(range(first.lineno, first.end_lineno + 1))
    return lines, tree


def _owner_of(tree):
    """行の番号から、その行を含むいちばん内側の関数名を返す関数を作る。

    Args:
        tree (ast.Module): 構文木。

    Returns:
        Callable[[int], str]: 行の番号を受け取り、``Class.method`` の形の名前を返す関数。
    """
    spans = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                if not isinstance(child, ast.ClassDef):
                    spans.append((child.lineno, child.end_lineno, name))
                visit(child, name + ".")
            else:
                visit(child, prefix)

    visit(tree, "")

    def owner(line):
        best, name = None, "<module>"
        for start, end, label in spans:
            if start <= line <= end and (best is None or start > best):
                best, name = start, label
        return name

    return owner


def _branches(tree, arcs, hits):
    """``if``・``for``・``while`` のうち、通った側を調べる。

    条件の行(複数行の条件ならそのすべて)から本体の最初の行へ移ったら「成り立つ側」、
    条件の行から、条件の行でも本体の最初の行でもない行(関数を出るのを含む)へ移ったら「成り立たない側」を通ったとする。
    条件の行が一度も実行されていない分岐と、本体が条件と同じ行にある分岐・``TYPE_CHECKING`` の分岐は数えない。

    Args:
        tree (ast.Module): 構文木。
        arcs (set[tuple[int, int]]): 実行された (前の行, 次の行)。負の数は関数の出入り。
        hits (set[int]): 実行された行。

    Returns:
        list[tuple[int, str, bool, bool]]: (条件の行, 種類, 成り立つ側を通ったか, 成り立たない側を通ったか)。
    """
    by_start = defaultdict(set)
    for start, end in arcs:
        by_start[start].add(end)
    result = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)):
            test = node.test
            if (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or isinstance(test, ast.Constant):
                continue
            test_lines = set(range(test.lineno, test.end_lineno + 1)) | {node.lineno}
            kind = "while" if isinstance(node, ast.While) else "if"
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            test_lines = set(range(node.lineno, node.iter.end_lineno + 1))
            kind = "for"
        else:
            continue
        body = node.body[0]
        body_first = min([body.lineno] + [decorator.lineno for decorator in getattr(body, "decorator_list", [])])
        body_lines = set(range(body_first, body.end_lineno + 1))
        if body_first in test_lines or not test_lines & hits:
            continue
        targets = set().union(*(by_start[line] for line in test_lines))
        taken = bool(targets & body_lines)
        skipped = any(target not in body_lines and target not in test_lines for target in targets)
        result.append((node.lineno, kind, taken, skipped))
    return result


def _raises(node):
    """docstringの ``Raises:`` に書いた例外の型の名前を集める。

    Args:
        node (ast.FunctionDef): 定義。

    Returns:
        set[str]: 例外の型の名前。
    """
    doc = ast.get_docstring(node) or ""
    names = set()
    inside = False
    for line in doc.splitlines():
        stripped = line.strip()
        if re.match(r"^(Args|Returns|Yields|Raises|Examples|Note|Notes|Warning|See Also|Attributes):$", stripped):
            inside = stripped == "Raises:"
            continue
        if inside:
            match = re.match(r"^([A-Z]\w*(?:Error|Exception|Exit))\s*:", stripped)
            if match:
                names.add(match.group(1))
    return names


def _bool_keywords(node):
    """キーワード専用の引数のうち、既定がboolのものの名前を返す。

    Args:
        node (ast.FunctionDef): 定義。

    Returns:
        list[str]: 引数の名前。
    """
    names = []
    for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        if isinstance(default, ast.Constant) and isinstance(default.value, bool):
            names.append(argument.arg)
    return names


def _viewpoint_gaps(name, node, view):
    """1つの公開メソッドの、テストで確かめていない観点を並べる。

    Args:
        name (str): ``相対パス:Class.method`` の名前。
        node (ast.FunctionDef): 定義。
        view (dict | None): 合わせた記録。一度も呼ばれていなければNone。

    Returns:
        list[str]: 抜けている観点の説明。抜けが無ければ空。
    """
    # プロパティ(と、そのsetter)は値を返すだけなので、観点を数えない。
    if any("property" in ast.dump(decorator) or "setter" in ast.dump(decorator) for decorator in node.decorator_list):
        return []
    if view is None:
        return ["テストから直接呼んでいない"]
    gaps = []
    flags = set(view["flags"])
    missing = [f"{keyword}={value}" for keyword in _bool_keywords(node) for value in (True, False) if f"{keyword}={value}" not in flags]
    if missing:
        gaps.append("引数: " + ", ".join(missing))
    raises = sorted(_raises(node) - set(view["raised"]))
    if raises:
        gaps.append("例外: " + ", ".join(raises))
    method = name.rsplit(".", 1)[-1].rsplit(":", 1)[-1]
    has_fast = "fast" in [argument.arg for argument in node.args.kwonlyargs]
    changes_scene = not name.startswith("maths/") and method not in LIST_METHODS
    if changes_scene and (has_fast or method.startswith(WRITE_PREFIXES)) and not view["undo"]:
        gaps.append("Undo")
    if has_fast and not view["fastUndo"]:
        gaps.append("fastのUndoなし")
    if not view["parity"]:
        gaps.append("突き合わせ")
    return gaps


def _merge_views(results):
    """版ごとの観点の記録を合わせる。

    Args:
        results (dict[str, dict]): 版と、その版の結果。

    Returns:
        dict[str, dict]: 公開メソッドの名前と、合わせた記録。
    """
    merged = {}
    for data in results.values():
        for key, view in data.get("views", {}).items():
            target = merged.setdefault(key, {"calls": 0, "flags": set(), "raised": set(), "undo": False, "fastUndo": False, "parity": False, "plural": False})
            target["calls"] += view["calls"]
            target["flags"].update(view["flags"])
            target["raised"].update(view["raised"])
            for flag in ("undo", "fastUndo", "parity", "plural"):
                target[flag] = target[flag] or view[flag]
    return merged


def _report(results, directory, only):
    """版ごとと、合わせた結果を書き出す。

    Args:
        results (dict[str, dict]): 版と、その版の結果。
        directory (Path): 書き出す先。
        only (tuple[str, ...]): 数える相対パスの先頭。

    Returns:
        str: summary.txtの内容。
    """
    by_version = {version: {os.path.normcase(name): set(lines) for name, lines in data["hits"].items()} for version, data in results.items()}
    arcs_all = defaultdict(set)
    for data in results.values():
        for name, pairs in data.get("arcs", {}).items():
            arcs_all[os.path.normcase(name)].update(tuple(pair) for pair in pairs)
    views = _merge_views(results)
    definitions = {}
    for name, node in _public_definitions().values():
        definitions[name] = node
    versions = sorted(by_version)
    columns = [*versions, "all"] if len(versions) > 1 else versions
    totals = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    branch_totals = defaultdict(lambda: [0, 0])
    view_totals = defaultdict(lambda: defaultdict(int))
    gaps = defaultdict(list)
    branch_gaps = defaultdict(list)
    view_gaps = defaultdict(list)
    for relative, path in _source_files(only):
        source = path.read_text(encoding="utf-8")
        lines, tree = _executable_lines(source, path)
        key = os.path.normcase(str(path))
        hit_sets = {version: by_version[version].get(key, set()) for version in versions}
        hit_sets["all"] = set().union(*hit_sets.values())
        package = relative.split("/")[0] if "/" in relative else "root"
        for column in columns:
            totals[package][column][0] += len(lines & hit_sets[column])
            totals[package][column][1] += len(lines)
        source_lines = source.splitlines()
        owner = _owner_of(tree)
        missed = sorted(lines - hit_sets["all"])
        if missed:
            grouped = defaultdict(list)
            for line in missed:
                grouped[owner(line)].append(line)
            gaps[package].append(f"\n## {relative}  ({len(lines) - len(missed)}/{len(lines)})")
            for name, numbers in grouped.items():
                items = "; ".join(f"L{number} `{source_lines[number - 1].strip()[:90]}`" for number in numbers[:12])
                gaps[package].append(f"- {name}: {items}" + (" …" if len(numbers) > 12 else ""))
        half = []
        for line, kind, taken, skipped in sorted(_branches(tree, arcs_all.get(key, set()), hit_sets["all"])):
            branch_totals[package][1] += 2
            branch_totals[package][0] += int(taken) + int(skipped)
            if not (taken and skipped):
                side = "成り立つ側" if not taken else ("一度も回らない側" if kind == "for" else "成り立たない側")
                half.append(f"- {owner(line)}: L{line} `{source_lines[line - 1].strip()[:90]}` — {side}を通っていない")
        if half:
            branch_gaps[package].append(f"\n## {relative}")
            branch_gaps[package].extend(half)
        rows = []
        for name, node in sorted(((n, d) for n, d in definitions.items() if n.startswith(relative + ":")), key=lambda item: item[1].lineno):
            found = _viewpoint_gaps(name, node, views.get(name))
            view_totals[package]["methods"] += 1
            for item in found:
                view_totals[package][item.split(":")[0]] += 1
            if found:
                plural = " (複数形から呼んだ)" if views.get(name, {}).get("plural") else ""
                rows.append(f"- {name.split(':', 1)[1]} (L{node.lineno}){plural}: " + " / ".join(found))
        if rows:
            view_gaps[package].append(f"\n## {relative}")
            view_gaps[package].extend(rows)
    header = "package\t" + "\t".join(f"lines {column}" for column in columns) + "\tbranches(all)"
    lines_out = [header]
    grand = defaultdict(lambda: [0, 0])
    grand_branch = [0, 0]
    for package in sorted(totals):
        cells = []
        for column in columns:
            covered, total = totals[package][column]
            grand[column][0] += covered
            grand[column][1] += total
            cells.append(f"{covered}/{total} {covered / total:.1%}" if total else "-")
        covered, total = branch_totals[package]
        grand_branch[0] += covered
        grand_branch[1] += total
        cells.append(f"{covered}/{total} {covered / total:.1%}" if total else "-")
        lines_out.append(package + "\t" + "\t".join(cells))
    cells = [f"{grand[c][0]}/{grand[c][1]} {grand[c][0] / grand[c][1]:.1%}" if grand[c][1] else "-" for c in columns]
    cells.append(f"{grand_branch[0]}/{grand_branch[1]} {grand_branch[0] / grand_branch[1]:.1%}" if grand_branch[1] else "-")
    lines_out.append("ALL\t" + "\t".join(cells))
    lines_out.append("")
    labels = ("テストから直接呼んでいない", "引数", "例外", "Undo", "fastのUndoなし", "突き合わせ")
    lines_out.append("観点の抜け\tmethods\t" + "\t".join(labels))
    for package in sorted(view_totals):
        counts = view_totals[package]
        lines_out.append(f"{package}\t{counts['methods']}\t" + "\t".join(str(counts[label]) for label in labels))
    for version, data in sorted(results.items()):
        if data.get("failed") or data.get("error"):
            lines_out.append(f"[NG] Maya {version}: 失敗したテストがあります: {data.get('failed') or data.get('error')}")
        if data.get("lost"):
            lines_out.append(f"[注意] Maya {version}: 途中でトレースが外れたテストのファイル(数え漏れがあり得る): {', '.join(data['lost'])}")
    summary = "\n".join(lines_out) + "\n"
    (directory / "summary.txt").write_text(summary, encoding="utf-8")
    for folder, collected, title, empty in (
        ("gaps", gaps, "実行されなかった行", "実行されなかった行はありません。"),
        ("branches", branch_gaps, "片側しか通っていない分岐", "片側しか通っていない分岐はありません。"),
        ("viewpoints", view_gaps, "テストで確かめていない観点", "抜けている観点はありません。"),
    ):
        target = directory / folder
        target.mkdir(exist_ok=True)
        for package in sorted(totals):
            body = "\n".join(collected[package]) if collected[package] else "\n" + empty
            (target / f"{package}.md").write_text(f"# {package} {title}\n{body}\n", encoding="utf-8")
    return summary


def main():
    """引数を読み、版ごとにテストを実行して結果をまとめる。

    Returns:
        int: 終了コード。0は全部の版で結果を書けてテストも成功、1はそれ以外。
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--versions", nargs="+", default=["2027"], help="測るMayaの版(既定: 2027)")
    parser.add_argument("--tests", nargs="+", help="実行するテストのファイル。runMaya.pyの--testsと同じ書き方")
    parser.add_argument("--suite", choices=("unit", "integration", "all"), default="all", help="テストの範囲(既定: all)")
    parser.add_argument("--only", nargs="+", default=[], help="数えるファイル。mlibからの相対パスの先頭(例: nodes/joint.py core)")
    parser.add_argument("--output", type=Path, help="書き出す先(既定: __tests__/_output/coverage/<日時>)")
    parser.add_argument("--by-test", action="store_true", help="テストのファイルごとの実行された行も記録する(hits.jsonが大きくなる)")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return _worker(args.worker, args.tests, args.suite, args.by_test)
    if sys.version_info < (3, 8):
        print("[NG] 結果をまとめる側はPython 3.8以上で実行してください(py -3)")
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005 フォルダー名に使う手元の時刻
    directory = (args.output or TESTS_DIR / "_output" / "coverage" / stamp).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    run_maya = _load_run_maya()
    results = {}
    for version in args.versions:
        data = _run_version(run_maya, version, directory / version, args.tests, args.suite, args.by_test)
        if data is not None:
            results[version] = data
    if not results:
        print("[NG] どの版でも結果を書き出せませんでした")
        return 1
    print(_report(results, directory, tuple(args.only)))
    print(f"結果: {directory}")
    ok = len(results) == len(args.versions) and not any(data.get("failed") or data.get("error") for data in results.values())
    print("[OK] 測り終えました。" if ok else "[NG] 測れなかった版か、失敗したテストがあります。上の表の下を確かめてください。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
