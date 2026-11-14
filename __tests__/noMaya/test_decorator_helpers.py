"""``decorator`` を Maya なしで確認する。

- Maya不要で、util・decoratorの共通ヘルパー(入力検証・別名選択)の約束を固定する。
"""

import importlib.util
import sys
import types
import unittest
from pathlib import Path

_MLIB_ROOT = Path(__file__).resolve().parents[2]


_PACKAGE = "_mlib_static_helpers"


def _load(relative, name, package=None):
    """mlibのソースファイルを、仮パッケージ配下のモジュールとして読み込む。

    Args:
        relative (str): mlibからの相対パス。
        name (str): モジュール名(パッケージ名を含む)。
        package (str | None): 相対importの基準にするパッケージ名。

    Returns:
        module: 読み込んだモジュール。
    """
    spec = importlib.util.spec_from_file_location(name, str(_MLIB_ROOT / relative))
    module = importlib.util.module_from_spec(spec)
    if package is not None:
        module.__package__ = package
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_helpers():
    """util・decoratorを読み込み、(util, decorator)を返す。"""
    saved = {
        name: sys.modules.get(name)
        for name in ("maya", "maya.api", "maya.api.OpenMaya", "maya.cmds", "maya.mel", _PACKAGE, f"{_PACKAGE}.util", f"{_PACKAGE}.decorator")
    }
    try:
        maya = types.ModuleType("maya")
        api = types.ModuleType("maya.api")
        maya.api = api
        api.OpenMaya = types.ModuleType("maya.api.OpenMaya")
        maya.cmds = types.ModuleType("maya.cmds")
        maya.mel = types.ModuleType("maya.mel")
        sys.modules.update({"maya": maya, "maya.api": api, "maya.api.OpenMaya": api.OpenMaya, "maya.cmds": maya.cmds, "maya.mel": maya.mel})
        package = types.ModuleType(_PACKAGE)
        package.__path__ = [str(_MLIB_ROOT)]
        sys.modules[_PACKAGE] = package
        util = _load("util.py", f"{_PACKAGE}.util", _PACKAGE)
        decorator = _load("decorator.py", f"{_PACKAGE}.decorator", _PACKAGE)
        return util, decorator
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


util, decorator = _load_helpers()


_UNSET = util._UNSET


class RequireBoolTest(unittest.TestCase):
    """_require_bool はboolだけを通し、文言は ``<name> must be a bool``。"""

    def test_accepts_bool_and_returns_it(self):
        self.assertIs(decorator._require_bool(True, "fast"), True)
        self.assertIs(decorator._require_bool(False, "fast"), False)

    def test_rejects_non_bool_with_type_error(self):
        for value in (0, 1, None, "True", 1.0):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, r"^fastはboolで指定してください$"):
                    decorator._require_bool(value, "fast")


class PickAliasTest(unittest.TestCase):
    """_pick_alias は長短の別名から1つを選び、競合・必須欠落を_ArgumentError(TypeError)にする。"""

    def test_returns_long_or_short(self):
        self.assertEqual(decorator._pick_alias("a", _UNSET, "worldSpace", "ws"), "a")
        self.assertEqual(decorator._pick_alias(_UNSET, "b", "worldSpace", "ws"), "b")

    def test_default_when_both_unset(self):
        self.assertIs(decorator._pick_alias(_UNSET, _UNSET, "worldSpace", "ws", default=False), False)
        self.assertIsNone(decorator._pick_alias(_UNSET, _UNSET, "worldSpace", "ws", default=None))

    def test_conflict_is_argument_error_long_then_short(self):
        with self.assertRaisesRegex(util._ArgumentError, r"^'worldSpace'と'ws'は同時に指定できません$"):
            decorator._pick_alias(True, False, "worldSpace", "ws")

    def test_missing_required_is_argument_error(self):
        with self.assertRaisesRegex(util._ArgumentError, r"^必須の引数がありません: 'attributes'$"):
            decorator._pick_alias(_UNSET, _UNSET, "attributes", "attrs")

    def test_argument_error_is_type_error(self):
        self.assertTrue(issubclass(util._ArgumentError, TypeError))


class MergeFlagsTest(unittest.TestCase):
    """_merge_flags は指定したフラグだけを長名で辞書へ詰め、同じ辞書を返す。"""

    def test_merges_only_given_flags(self):
        kwargs = {}
        result = decorator._merge_flags(kwargs, [("new", _UNSET, "name", "n"), (_UNSET, True, "skipSelect", "ss"), (_UNSET, _UNSET, "parent", "p")])
        self.assertIs(result, kwargs)
        self.assertEqual(kwargs, {"name": "new", "skipSelect": True})

    def test_conflict_is_argument_error(self):
        with self.assertRaisesRegex(util._ArgumentError, r"^'name'と'n'は同時に指定できません$"):
            decorator._merge_flags({}, [("a", "b", "name", "n")])


if __name__ == "__main__":
    unittest.main()
