"""mlib本体をわざと少し書き換え(ミューテーション)、テストがその変化に気づくかを確かめる。

テストが行を通っていても、結果を確かめていなければ、書き換えても失敗しない(書き換えが「生き残る」)。
生き残った書き換えは、テストの確かめ方が弱い場所を示す。標準ライブラリだけを使う。

使い方(mlibのフォルダーで実行する。``py`` はPython 3.8以上):

    py -3 _tools/measure_mlib_mutations.py --only nodes/joint.py --limit 30
    py -3 _tools/measure_mlib_mutations.py --only nodes core --limit 10 --workers 6

手順:

1. どのテストのファイルがどの行を通るかを、``measure_mlib_coverage.py --by-test`` で調べる(``--coverage`` で既にある結果を使える)。
2. 対象のファイルの、テストが通る行から書き換えを作る。1つのファイルからは ``--limit`` 個まで、行が偏らないように選ぶ。
   書き換えの種類: 比較の向き(``==``↔``!=``・``<``↔``>=`` など)、``in``↔``not in``、``is``↔``is not``、
   ``and``↔``or``、``not`` を外す、``True``↔``False``、整数に1を足す、``raise`` 文を ``pass`` にする、``return 値`` を ``return None`` にする。
3. mlibを作業用のフォルダーへ写し(``_tools/.temp/mutations/<出力先の名前>/``)、``--workers`` 個のmayapyで手分けして、
   書き換えを1つずつ当てて ``mlib.reload()`` し、その行を通るテストのファイルのうち近いもの(``--max-tests`` 個まで)を実行する。
   テストが1つでも失敗すれば「見つけた」、全部成功すれば「生き残った」。

結果は ``__tests__/_output/mutations/<日時>/`` に置く。``summary.txt`` に見つけた割合、``survived.md`` に生き残った書き換えを並べる。
"""

import argparse
import ast
import datetime
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "__tests__"
TOOLS_DIR = ROOT / "_tools"
EXCLUDED_FOLDERS = ("__tests__", "_tools", "_docs")
_COMPARE_SWAPS = {
    ast.Eq: "!=",
    ast.NotEq: "==",
    ast.Lt: ">=",
    ast.GtE: "<",
    ast.Gt: "<=",
    ast.LtE: ">",
    ast.In: "not in",
    ast.NotIn: "in",
    ast.Is: "is not",
    ast.IsNot: "is",
}


# --- Mayaの中で動く部分(Python 3.7でも動く書き方にする) ---


def _worker(job_path):
    """mayapyの中で、書き換えを1つずつ当ててテストを実行し、結果をJSONで書く。

    Args:
        job_path (Path): 書き換えの一覧と、写したmlibの場所を書いたJSON。

    Returns:
        int: 終了コード。
    """
    import importlib
    import runpy

    job = json.loads(job_path.read_text(encoding="utf-8"))
    copy_root = Path(job["root"])
    import maya.standalone

    maya.standalone.initialize(name="python")
    sys.path[:0] = [str(copy_root.parent), str(copy_root / "__tests__"), str(copy_root / "_tools")]
    mlib = importlib.import_module("mlib")
    namespace = runpy.run_path(str(copy_root / "__tests__" / "runAll.py"))
    run_all = namespace["run_all"]
    run_all.__globals__["LOG_DIR"] = job_path.parent
    results = []
    for mutant in job["mutants"]:
        path = copy_root / mutant["file"]
        original = path.read_text(encoding="utf-8")
        started = time.time()
        try:
            path.write_text(mutant["source"], encoding="utf-8")
            try:
                mlib.reload()
                suite = run_all(names=mutant["tests"], suite="all")
                killed = bool(suite.get("failed"))
                reason = ", ".join(suite.get("failed") or [])
            except Exception as error:  # noqa: BLE001 書き換えたコードの失敗はすべて「見つけた」に数える
                killed, reason = True, f"{type(error).__name__}: {error}"[:200]
        finally:
            path.write_text(original, encoding="utf-8")
            # 書き換えたモジュール(再読み込みの処理そのものを含む)を、元のソースで読み直してから全体を読み直す。
            module_name = "mlib." + mutant["file"][:-3].replace("/", ".")
            module_name = module_name[: -len(".__init__")] if module_name.endswith(".__init__") else module_name
            try:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                mlib.reload()
            except Exception:  # noqa: BLE001 元に戻せなかったときは、次の書き換えの結果で分かる
                pass
        results.append(dict(mutant, source=None, killed=killed, reason=reason, seconds=round(time.time() - started, 1)))
        (job_path.parent / (job_path.stem + "_result.json")).write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    try:
        mlib.reload()
    finally:
        maya.standalone.uninitialize()
    return 0


# --- 手元のPythonで動く部分 ---


def _offsets(source):
    """行の番号(1から)と列から、文字列の位置を求める表を作る。

    Args:
        source (str): ソース。

    Returns:
        list[int]: 各行の先頭の位置。
    """
    starts = [0]
    for line in source.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    return starts


def _mutations(source):
    """ソースから書き換えの候補を作る。

    Args:
        source (str): 対象のファイルのソース。

    Returns:
        list[dict]: ``line``(行)・``label``(説明)・``start``/``end``(置き換える範囲)・``text``(置き換える文字)。
    """
    tree = ast.parse(source)
    starts = _offsets(source)

    def position(line, column):
        return starts[line - 1] + column

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _COMPARE_SWAPS:
            left_end = position(node.left.end_lineno, node.left.end_col_offset)
            right = node.comparators[0]
            right_start = position(right.lineno, right.col_offset)
            between = source[left_end:right_start]
            new = _COMPARE_SWAPS[type(node.ops[0])]
            candidates.append({"line": node.lineno, "label": f"比較 {between.strip()} → {new}", "start": left_end, "end": right_start, "text": f" {new} "})
        elif isinstance(node, ast.BoolOp) and len(node.values) == 2:
            left, right = node.values
            start = position(left.end_lineno, left.end_col_offset)
            end = position(right.lineno, right.col_offset)
            between = source[start:end]
            new = "or" if isinstance(node.op, ast.And) else "and"
            if between.strip() in ("and", "or"):
                candidates.append({"line": node.lineno, "label": f"{between.strip()} → {new}", "start": start, "end": end, "text": f" {new} "})
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            start = position(node.lineno, node.col_offset)
            end = position(node.operand.lineno, node.operand.col_offset)
            candidates.append({"line": node.lineno, "label": "not を外す", "start": start, "end": end, "text": ""})
        elif isinstance(node, ast.Constant) and id(node) not in docstrings:
            start = position(node.lineno, node.col_offset)
            end = position(node.end_lineno, node.end_col_offset)
            if isinstance(node.value, bool):
                candidates.append({"line": node.lineno, "label": f"{node.value} → {not node.value}", "start": start, "end": end, "text": str(not node.value)})
            elif isinstance(node.value, int) and source[start:end].isdigit():
                candidates.append({"line": node.lineno, "label": f"{node.value} → {node.value + 1}", "start": start, "end": end, "text": str(node.value + 1)})
        elif isinstance(node, ast.Raise) and node.exc is not None:
            start = position(node.lineno, node.col_offset)
            end = position(node.end_lineno, node.end_col_offset)
            candidates.append({"line": node.lineno, "label": "raise を pass にする", "start": start, "end": end, "text": "pass"})
        elif isinstance(node, ast.Return) and node.value is not None and not (isinstance(node.value, ast.Constant) and node.value.value is None):
            start = position(node.value.lineno, node.value.col_offset)
            end = position(node.value.end_lineno, node.value.end_col_offset)
            candidates.append({"line": node.lineno, "label": "return 値 → return None", "start": start, "end": end, "text": "None"})
    return candidates


def _function_bodies(source):
    """関数の定義の行(デコレーター・引数の既定値の行)から、その関数の本体の行を引く表を作る。

    既定値を書き換えた行は、モジュールを最初に読み込んだテストでしか実行されないので、
    その関数を実際に呼ぶテスト(本体の行を通るテスト)から選ぶために使う。

    Args:
        source (str): ソース。

    Returns:
        dict[int, tuple[int, ...]]: 定義の行と、本体の行。
    """
    table = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = tuple(range(node.body[0].lineno, node.end_lineno + 1))
            for line in range(min([node.lineno] + [decorator.lineno for decorator in node.decorator_list]), node.body[0].lineno):
                table[line] = body
    return table


def _load_coverage(directory):
    """``measure_mlib_coverage.py --by-test`` の結果から、ファイルの行ごとに通るテストのファイルを集める。

    Args:
        directory (Path): 結果のフォルダー。版のフォルダーの ``hits.json`` を読む。

    Returns:
        dict[tuple[str, int], set[str]]: (normcaseしたパス, 行)と、その行を通るテストのファイル(``inMaya/`` からの相対パス)。
    """
    by_line = {}
    for hits in directory.glob("*/hits.json"):
        data = json.loads(hits.read_text(encoding="utf-8"))
        for test, files in data.get("byTest", {}).items():
            name = test.split("inMaya/", 1)[-1]
            for filename, lines in files.items():
                key = os.path.normcase(filename)
                for line in lines:
                    by_line.setdefault((key, line), set()).add(name)
    return by_line


def _closest_tests(relative, tests, limit):
    """行を通るテストのファイルから、書き換えたファイルに近いものを ``limit`` 個まで選ぶ。

    近い順は、同じ名前のテスト(``nodes/joint.py`` なら ``test_joint*.py``)、同じパッケージの ``unit`` のテスト、それ以外。
    多くのテストが通る行(モジュールの読み込みなど)で、全部を流して時間がかかりすぎるのを防ぐ。

    Args:
        relative (str): 書き換えたファイルの、mlibからの相対パス。
        tests (set[str]): その行を通るテストのファイル。
        limit (int): 選ぶ最大の数。

    Returns:
        list[str]: 選んだテストのファイル。
    """
    stem = Path(relative).stem
    package = relative.split("/")[0] if "/" in relative else "root"

    def rank(test):
        name = Path(test).name
        if name == f"test_{stem}.py" or name.startswith(f"test_{stem}_"):
            return (0, test)
        if test.startswith(f"unit/{package}/"):
            return (1, test)
        return (2, test)

    return sorted(tests, key=rank)[:limit]


def _copy_mlib(target):
    """mlibを作業用のフォルダーへ写す。テストの出力・文書・仮想環境は写さない。

    Args:
        target (Path): 写す先(``<target>/mlib`` に置く)。

    Returns:
        Path: 写したmlibのフォルダー。
    """
    destination = target / "mlib"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(ROOT, destination, ignore=shutil.ignore_patterns(".git", ".venv", ".mayapy-site", ".temp", "_output", "_docs", "__pycache__", "*.pyi"))
    return destination


def main():
    """引数を読み、書き換えを作って手分けして確かめ、結果をまとめる。

    Returns:
        int: 終了コード。0は最後まで確かめられた場合。
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="+", default=[], help="書き換えるファイル。mlibからの相対パスの先頭(例: nodes/joint.py core)")
    parser.add_argument("--limit", type=int, default=20, help="1つのファイルから作る書き換えの最大数(既定: 20)")
    parser.add_argument("--workers", type=int, default=4, help="同時に動かすmayapyの数(既定: 4)")
    parser.add_argument("--version", default="2027", help="使うMayaの版(既定: 2027)")
    parser.add_argument("--coverage", type=Path, help="measure_mlib_coverage.py --by-test の結果のフォルダー。省くと先に測る")
    parser.add_argument("--max-tests", type=int, default=8, help="1つの書き換えで流すテストのファイルの最大数(既定: 8。近いものから選ぶ)")
    parser.add_argument("--lines", nargs="+", type=int, default=[], help="書き換える行(--only のファイルの行番号)。省くと全部の行から選ぶ")
    parser.add_argument("--skip-done", type=Path, help="前の結果のフォルダー。そこで確かめ終えた書き換えは飛ばす(途中で止まったときの続き)")
    parser.add_argument("--seed", type=int, default=0, help="書き換えを選ぶ乱数の種(既定: 0)")
    parser.add_argument("--output", type=Path, help="書き出す先(既定: __tests__/_output/mutations/<日時>)")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return _worker(args.worker)
    if not args.only:
        parser.error("--only で書き換えるファイルを指定してください")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005 フォルダー名に使う手元の時刻
    directory = (args.output or TESTS_DIR / "_output" / "mutations" / stamp).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    coverage = args.coverage
    if coverage is None:
        coverage = directory / "coverage"
        print("テストのファイルごとに通る行を測っています")
        command = [sys.executable, str(TOOLS_DIR / "measure_mlib_coverage.py"), "--by-test", "--versions", args.version, "--output", str(coverage)]
        subprocess.call(command, cwd=str(ROOT), stdout=subprocess.DEVNULL)
    by_line = _load_coverage(coverage)
    if not by_line:
        print(f"[NG] テストのファイルごとの記録がありません: {coverage}(--by-test で測った結果を指定してください)")
        return 1
    generator = random.Random(args.seed)
    mutants = []
    only = tuple(args.only)
    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(EXCLUDED_FOLDERS) or ".venv" in relative or not relative.startswith(only):
            continue
        source = path.read_text(encoding="utf-8")
        key = os.path.normcase(str(path))
        bodies = _function_bodies(source)
        tests_of = {}
        for item in _mutations(source):
            lines = bodies.get(item["line"], (item["line"],))
            found = set().union(*(by_line.get((key, line), set()) for line in lines))
            if found:
                tests_of[item["line"]] = found
        usable = [item for item in _mutations(source) if item["line"] in tests_of and (not args.lines or item["line"] in args.lines)]
        generator.shuffle(usable)
        chosen, used_lines = [], set()
        # 行が偏らないよう、まず1行に1つずつ選び、足りなければ残りから足す。
        for item in usable:
            if len(chosen) < args.limit and item["line"] not in used_lines:
                chosen.append(item)
                used_lines.add(item["line"])
        for item in usable:
            if len(chosen) < args.limit and item not in chosen:
                chosen.append(item)
        for item in chosen:
            mutated = source[: item["start"]] + item["text"] + source[item["end"] :]
            try:
                ast.parse(mutated)
            except SyntaxError:
                continue
            tests = _closest_tests(relative, tests_of[item["line"]], args.max_tests)
            text = source.splitlines()[item["line"] - 1].strip()
            mutants.append({"file": relative, "line": item["line"], "label": item["label"], "code": text[:120], "tests": tests, "source": mutated})
    if args.skip_done:
        done = set()
        for result in args.skip_done.glob("worker*/job*_result.json"):
            done.update((item["file"], item["line"], item["label"]) for item in json.loads(result.read_text(encoding="utf-8")))
        mutants = [item for item in mutants if (item["file"], item["line"], item["label"]) not in done]
        print(f"前の結果で確かめ終えた書き換えを飛ばします: {len(done)}個")
    if not mutants:
        print("[NG] 書き換えを作れませんでした(--only と、テストが通る行を確かめてください)")
        return 1
    print(f"書き換え: {len(mutants)}個、mayapy {args.workers}個で確かめます")
    spec = importlib.util.spec_from_file_location("_mlib_run_maya", TESTS_DIR / "runMaya.py")
    run_maya = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_maya)
    executable = run_maya.maya_executable(args.version, Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Autodesk")
    work_root = TOOLS_DIR / ".temp" / "mutations" / directory.name
    count = max(1, args.workers)
    collected = [[] for _ in range(count)]

    def run_slot(index):
        """1つのmayapyで割り当てを確かめる。Mayaが落ちたら、その書き換えを「見つけた」として残りを続ける。"""
        remaining = mutants[index::count]
        work = directory / f"worker{index}"
        work.mkdir(exist_ok=True)
        copy_root = _copy_mlib(work_root / f"w{index}")
        round_number = 0
        while remaining:
            job = work / f"job{round_number}.json"
            job.write_text(json.dumps({"root": str(copy_root), "mutants": remaining}, ensure_ascii=False), encoding="utf-8")
            maya_dir = work / f"maya{round_number}"
            maya_dir.mkdir()
            env = run_maya.isolated_environment(executable, maya_dir)
            env["PYTHONPATH"] = str(copy_root.parent)
            command = [str(executable), str(Path(__file__).resolve()), "--worker", str(job)]
            with (work / f"console{round_number}.log").open("w", encoding="utf-8") as console:
                subprocess.call(command, cwd=str(copy_root), env=env, stdout=console, stderr=subprocess.STDOUT)
            result_path = work / f"job{round_number}_result.json"
            done = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else []
            collected[index].extend(done)
            remaining = remaining[len(done) :]
            if remaining:
                # 書き換えたままMayaが落ちたので、写しを元に戻し、その書き換えは見つけたものとして数える。
                crashed = remaining.pop(0)
                shutil.copyfile(ROOT / crashed["file"], copy_root / crashed["file"])
                collected[index].append(dict(crashed, source=None, killed=True, reason="Mayaが異常終了した", seconds=None))
            round_number += 1

    threads = [threading.Thread(target=run_slot, args=(index,)) for index in range(count) if mutants[index::count]]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    results = [item for items in collected for item in items]
    killed = [item for item in results if item["killed"]]
    survived = sorted((item for item in results if not item["killed"]), key=lambda item: (item["file"], item["line"]))
    by_file = {}
    for item in results:
        counts = by_file.setdefault(item["file"], [0, 0])
        counts[0] += int(item["killed"])
        counts[1] += 1
    rows = ["file\tkilled/total"] + [f"{name}\t{done}/{total}" for name, (done, total) in sorted(by_file.items())]
    total = len(results)
    rows.append(f"ALL\t{len(killed)}/{total} {len(killed) / total:.1%}" if total else "ALL\t-")
    if total < len(mutants):
        rows.append(f"[NG] 確かめ終わらなかった書き換えがあります: {len(mutants) - total}個(worker*/console*.log を確かめてください)")
    summary = "\n".join(rows) + "\n"
    (directory / "summary.txt").write_text(summary, encoding="utf-8")
    lines = ["# 生き残った書き換え(テストが気づかなかったもの)", ""]
    lines.extend(
        f"- {item['file']}:{item['line']} {item['label']} — `{item['code']}`(テスト: {', '.join(item['tests'][:4])}{' ほか' if len(item['tests']) > 4 else ''})"
        for item in survived
    )
    (directory / "survived.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    shutil.rmtree(work_root, ignore_errors=True)
    print(summary)
    print(f"結果: {directory}")
    ok = total == len(mutants)
    print("[OK] 確かめ終えました。" if ok else "[NG] 確かめ終わらなかった書き換えがあります。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
