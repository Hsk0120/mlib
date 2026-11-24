"""mlibのMayaのテストを実行しながら、mlib本体のどの行が実行されたかを数える。

テストの書き漏れ(一度も通っていない分岐)を見つけるための道具。標準ライブラリの ``sys.settrace`` だけを使い、
追加のパッケージは要らない。テストは ``__tests__/runMaya.py`` と同じ隔離した設定のmayapyで実行する。

使い方(mlibのフォルダーで実行する。``py`` はPython 3.8以上):

    py -3 _tools/measure_mlib_coverage.py                       # Maya 2027で全部のテスト
    py -3 _tools/measure_mlib_coverage.py --versions 2022 2027  # 版ごとに測り、合わせた結果も出す
    py -3 _tools/measure_mlib_coverage.py --tests test_joint.py --only nodes/joint.py

結果は ``__tests__/_output/coverage/<日時>/`` に置く(Gitの対象外)。

- ``summary.txt``: パッケージごとの、実行された行の数と割合。版ごとと、全部の版を合わせた値。
- ``gaps/<パッケージ>.md``: 全部の版を合わせても実行されなかった行を、関数ごとに並べたもの。
- ``<版>/hits.json``: 版ごとの実行された行(合わせ直すときの元)。

数えるのは、docstringを除いた実行される行(Pythonがコンパイルした行の表)。分岐の両側を通ったかは数えない。
テストの中で深い再帰などが起きるとトレースが外れることがあるので、テストのファイルごととテストごとに付け直し、
ファイルの終わりで外れていたものは ``summary.txt`` に書く。
"""

import argparse
import ast
import contextlib
import datetime
import importlib.util
import json
import os
import runpy
import subprocess
import sys
import threading
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "__tests__"
EXCLUDED_FOLDERS = ("__tests__", "_tools", "_docs")


def _load_run_maya():
    """``__tests__/runMaya.py`` を読み込み、mayapyの場所と隔離した環境の作り方を借りる。

    Returns:
        module: runMayaのモジュール。
    """
    spec = importlib.util.spec_from_file_location("_mlib_run_maya", TESTS_DIR / "runMaya.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Mayaの中で動く部分(Python 3.7でも動く書き方にする) ---


def _worker(output, selected_tests, suite):
    """mayapyの中でテストを実行し、mlib本体の実行された行を ``output`` へJSONで書く。

    Args:
        output (Path): 書き出すJSONのパス。
        selected_tests (list[str] | None): 実行するテストのファイル名。Noneなら全部。
        suite (str): ``unit``・``integration``・``all``。

    Returns:
        int: 終了コード。テストが失敗しても、実行された行は書き出す。
    """
    prefix = os.path.normcase(str(ROOT)) + os.sep
    skipped = tuple(os.path.normcase(str(ROOT / name)) + os.sep for name in EXCLUDED_FOLDERS)
    hits = {}
    wanted = {}
    lost = []

    def local(frame, event, _arg):
        if event == "line":
            hits.setdefault(frame.f_code.co_filename, set()).add(frame.f_lineno)
        return local

    def global_trace(frame, _event, _arg):
        filename = frame.f_code.co_filename
        result = wanted.get(filename)
        if result is None:
            normalized = os.path.normcase(filename)
            result = normalized.startswith(prefix) and not normalized.startswith(skipped) and normalized.endswith(".py")
            wanted[filename] = result
        if not result:
            return None
        hits.setdefault(filename, set()).add(frame.f_lineno)
        return local

    import maya.standalone

    maya.standalone.initialize(name="python")
    sys.path[:0] = [str(ROOT.parent), str(TESTS_DIR), str(ROOT / "_tools")]
    namespace = runpy.run_path(str(TESTS_DIR / "runAll.py"))
    run_all = namespace["run_all"]
    run_all.__globals__["LOG_DIR"] = output.parent
    real_runpy = run_all.__globals__["runpy"]

    class _Rearm:
        """テストのファイルを実行するたびに、トレースを付け直す。"""

        @staticmethod
        def run_path(path, *args, **kwargs):
            sys.settrace(global_trace)
            threading.settrace(global_trace)
            try:
                return real_runpy.run_path(path, *args, **kwargs)
            finally:
                if sys.gettrace() is None:
                    lost.append(str(path))

    run_all.__globals__["runpy"] = _Rearm
    # 1つのファイルの途中で外れても、次のテストから数え直せるように、テストごとにも付け直す。
    import unittest

    original_run = unittest.TestCase.run

    def run_with_trace(self, *args, **kwargs):
        if sys.gettrace() is None:
            sys.settrace(global_trace)
        return original_run(self, *args, **kwargs)

    unittest.TestCase.run = run_with_trace
    result = {}
    try:
        result = run_all(names=selected_tests, suite=suite)
    except AssertionError as error:
        # 失敗したテストがあっても、実行された行は書き出す。
        result = {"error": str(error)}
    finally:
        sys.settrace(None)
        threading.settrace(None)
    data = {"hits": {name: sorted(lines) for name, lines in hits.items()}, "failed": result.get("failed"), "error": result.get("error"), "lost": lost}
    output.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with contextlib.suppress(RuntimeError):
        maya.standalone.uninitialize()
    return 0 if not result.get("failed") and not result.get("error") else 1


# --- 手元のPythonで動く部分 ---


def _run_version(run_maya, version, directory, selected_tests, suite):
    """1つの版のmayapyで、このファイルを ``--worker`` として実行する。

    Args:
        run_maya (module): runMayaのモジュール。
        version (str): Mayaの版。
        directory (Path): この版の作業フォルダー(まだ無いこと)。
        selected_tests (list[str] | None): 実行するテストのファイル名。
        suite (str): テストの範囲。

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


def _report(results, directory, only):
    """版ごとと、合わせた結果の割合を書き出し、合わせても実行されなかった行を並べる。

    Args:
        results (dict[str, dict]): 版と、その版の結果。
        directory (Path): 書き出す先。
        only (tuple[str, ...]): 数える相対パスの先頭。

    Returns:
        str: summary.txtの内容。
    """
    by_version = {version: {os.path.normcase(name): set(lines) for name, lines in data["hits"].items()} for version, data in results.items()}
    versions = sorted(by_version)
    columns = [*versions, "all"] if len(versions) > 1 else versions
    totals = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    gaps = defaultdict(list)
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
        missed = sorted(lines - hit_sets["all"])
        if not missed:
            continue
        source_lines = source.splitlines()
        owner = _owner_of(tree)
        grouped = defaultdict(list)
        for line in missed:
            grouped[owner(line)].append(line)
        covered = len(lines) - len(missed)
        gaps[package].append(f"\n## {relative}  ({covered}/{len(lines)})")
        for name, numbers in grouped.items():
            items = "; ".join(f"L{number} `{source_lines[number - 1].strip()[:90]}`" for number in numbers[:12])
            gaps[package].append(f"- {name}: {items}" + (" …" if len(numbers) > 12 else ""))
    header = "package\t" + "\t".join(columns)
    rows = [header]
    grand = defaultdict(lambda: [0, 0])
    for package in sorted(totals):
        cells = []
        for column in columns:
            covered, total = totals[package][column]
            grand[column][0] += covered
            grand[column][1] += total
            cells.append(f"{covered}/{total} {covered / total:.1%}" if total else "-")
        rows.append(package + "\t" + "\t".join(cells))
    rows.append("ALL\t" + "\t".join(f"{grand[c][0]}/{grand[c][1]} {grand[c][0] / grand[c][1]:.1%}" if grand[c][1] else "-" for c in columns))
    for version, data in sorted(results.items()):
        if data.get("failed") or data.get("error"):
            rows.append(f"[NG] Maya {version}: 失敗したテストがあります: {data.get('failed') or data.get('error')}")
        if data.get("lost"):
            rows.append(f"[注意] Maya {version}: 途中でトレースが外れたテストのファイル(数え漏れがあり得る): {', '.join(data['lost'])}")
    summary = "\n".join(rows) + "\n"
    (directory / "summary.txt").write_text(summary, encoding="utf-8")
    gap_dir = directory / "gaps"
    gap_dir.mkdir(exist_ok=True)
    for package in sorted(totals):
        covered, total = totals[package][columns[-1]]
        body = "\n".join(gaps[package]) if gaps[package] else "\n実行されなかった行はありません。"
        (gap_dir / f"{package}.md").write_text(f"# {package} 実行されなかった行 ({covered}/{total})\n{body}\n", encoding="utf-8")
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
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return _worker(args.worker, args.tests, args.suite)
    if sys.version_info < (3, 8):
        print("[NG] 結果をまとめる側はPython 3.8以上で実行してください(py -3)")
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005 フォルダー名に使う手元の時刻
    directory = (args.output or TESTS_DIR / "_output" / "coverage" / stamp).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    run_maya = _load_run_maya()
    results = {}
    for version in args.versions:
        data = _run_version(run_maya, version, directory / version, args.tests, args.suite)
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
