"""Mayaを起動せず、公開の関数・メソッドのすべてに、引数を網羅するテストの行があることを確かめる。

``inMaya/unit/<パッケージ>/test_<ソースのファイル名>_argumentSweep.py`` の表(``Method("名前", ...)``)を ast で読み、
``_tools/check_mlib_arguments.py`` が集める公開 def と突き合わせる。行が無い公開 def は、理由を書いた :data:`EXCLUDED` に
載っていなければ失敗にする(新しい公開メソッドを足したとき、引数のテストを書き忘れない)。

コンストラクターの行は ``Method("__init__", ..., function=クラス)`` と書く。同じファイルの中の、同じ名前のメソッド
(単数と複数形など)は、どれか1つに行があれば足りる。
"""

import ast
import collections
import fnmatch
import functools
import unittest
from pathlib import Path

import check_mlib_arguments as tool

_PACKAGE = Path(__file__).resolve().parents[2]
_UNIT = _PACKAGE / "__tests__" / "inMaya" / "unit"

#: 引数を網羅するテストの行を持たない公開 def と、その理由。キーは ``"パッケージ/ファイル.py:クラス.メソッド"``(fnmatch の形)。
EXCLUDED = {
    "common/progress.py:_ProgressLine.*": "progressBar が返す内部の表示クラス。progressBar の行と test_progress.py が確かめる",
    "common/progress.py:_MainProgressBar.*": "progressBar が返す内部の表示クラス。progressBar の行と test_progress.py が確かめる",
    "nodes/blendShape.py:_Directories.*": "ターゲットのフォルダーを読み書きする内部のクラス。BlendShape のフォルダーのメソッドの行が確かめる",
    "components/edge.py:_Topology.*": "エッジのループをたどる内部のクラス。Edge・Edges のメソッドの行が確かめる",
    "decorator.py:_UndoChunk.*": "undoChunk が返す内部のクラス。undoChunk の行が確かめる",
    "json/animationSnapshot.py:_LayerResolver.*": "アニメーションレイヤーを解決する内部のクラス。AnimationSnapshot.apply の行が確かめる",
    "util.py:_PointGrid.*": "近い点を探す内部のクラス。Mesh.getMirrorVertexMap などの行が確かめる",
}


def _source_key(function):
    return function.path.relative_to(_PACKAGE).as_posix()


def _sweep_file(function):
    """公開 def のテストを置くファイル(``unit/<パッケージ>/test_<ファイル名>_argumentSweep.py``)を返す。"""
    stem = function.path.stem
    # cmds の関数は1つずつファイルを持つが、テストは ``cmds/test_init_argumentSweep.py`` の1つの表にまとめてある。
    if stem == "__init__" or function.package == "cmds":
        stem = "init"
    return _UNIT / function.package / f"test_{stem}_argumentSweep.py"


@functools.lru_cache(maxsize=None)
def _rows(path):
    """テストのファイルにある ``Method("名前", ...)`` の名前の集まりを返す。ファイルが無ければ空。"""
    if not path.is_file():
        return frozenset()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "Method"):
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            names.add(node.args[0].value)
    # 表を名前の並びから作るファイルは、``SWEPT = ("名前", ...)`` に書いた名前も行として数える。
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SWEPT" for t in node.targets):
            names.update(item.value for item in ast.walk(node.value) if isinstance(item, ast.Constant) and isinstance(item.value, str))
    return frozenset(names)


def _excluded(key, used):
    for pattern, _reason in EXCLUDED.items():
        if fnmatch.fnmatchcase(key, pattern):
            used.add(pattern)
            return True
    return False


@functools.lru_cache(maxsize=None)
def find_uncovered():
    """行も除外も無い公開 def と、使われた除外のキーを返す。

    Returns:
        tuple[tuple[str, ...], frozenset[str]]: 行が無い公開 def の説明と、当てはまった除外のキー。
    """
    missing = collections.defaultdict(list)
    used = set()
    for function in tool.collect(_PACKAGE):
        method = function.owner.split(".")[-1]
        key = f"{_source_key(function)}:{function.owner}"
        if method in _rows(_sweep_file(function)):
            continue
        if _excluded(key, used):
            continue
        missing[_sweep_file(function).relative_to(_PACKAGE).as_posix()].append(function.owner)
    return tuple(f"{path}: {', '.join(owners)}" for path, owners in sorted(missing.items())), frozenset(used)


class ArgumentSweepCoverageTest(unittest.TestCase):
    """公開 def と、引数を網羅するテストの行の突き合わせ。"""

    def test_every_public_definition_has_a_row_or_a_reason(self):
        """公開の関数・メソッドは、網羅の表に行があるか、理由つきで除外してある。"""
        missing, _used = find_uncovered()
        self.assertEqual(list(missing), [], "引数を網羅するテストの行が無い公開def(行を足すか、EXCLUDED に理由を書く):\n" + "\n".join(missing))

    def test_exclusions_are_still_needed(self):
        """除外表の行は、どれも今ある公開 def に当てはまる。"""
        _missing, used = find_uncovered()
        self.assertEqual(sorted(set(EXCLUDED) - used), [])

    def test_exclusions_have_reasons(self):
        """除外には理由を書く。"""
        for key, reason in EXCLUDED.items():
            with self.subTest(key=key):
                self.assertTrue(reason.strip())

    def test_rows_are_read_from_method_calls_and_swept_names(self):
        """行の名前は ``Method("名前")`` と ``SWEPT`` から読む。"""
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test_sample_argumentSweep.py"
            path.write_text('SWEPT = ("alpha", "beta")\nMETHODS = (Method("gamma", None), table.Method("__init__", None, function=int))\n', encoding="utf-8")
            self.assertEqual(_rows(path), frozenset(("alpha", "beta", "gamma", "__init__")))
            self.assertEqual(_rows(Path(folder) / "missing.py"), frozenset())


if __name__ == "__main__":
    unittest.main()
