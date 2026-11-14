"""``util`` を Maya なしで確認する。

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
        name: sys.modules.get(name) for name in ("maya", "maya.api", "maya.api.OpenMaya", "maya.cmds", _PACKAGE, f"{_PACKAGE}.util", f"{_PACKAGE}.decorator")
    }
    try:
        maya = types.ModuleType("maya")
        api = types.ModuleType("maya.api")
        maya.api = api
        api.OpenMaya = types.ModuleType("maya.api.OpenMaya")
        maya.cmds = types.ModuleType("maya.cmds")
        sys.modules.update({"maya": maya, "maya.api": api, "maya.api.OpenMaya": api.OpenMaya, "maya.cmds": maya.cmds})
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


class FiniteTest(unittest.TestCase):
    """_finite・_finite_vector・_checked_tolerance は型違いをTypeError、値違いをValueErrorにする。"""

    def test_finite_converts_to_float(self):
        self.assertEqual(util._finite(3, "radius"), 3.0)
        self.assertIsInstance(util._finite(3, "radius"), float)

    def test_finite_rejects_bool_and_non_number(self):
        for value in (True, "1", None, [1]):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, r"^radius must be a number$"):
                    util._finite(value, "radius")

    def test_finite_rejects_inf_and_nan(self):
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, r"^radius must be finite$"):
                    util._finite(value, "radius")

    def test_finite_vector(self):
        self.assertEqual(util._finite_vector((1, 2, 3), 3, "pivot"), (1.0, 2.0, 3.0))
        self.assertEqual(util._finite_vector(iter([1, 2]), 2, "uv"), (1.0, 2.0))
        with self.assertRaisesRegex(TypeError, r"^pivot must be a sequence of 3 numbers$"):
            util._finite_vector(1, 3, "pivot")
        with self.assertRaisesRegex(ValueError, r"^pivot must have 3 components$"):
            util._finite_vector((1, 2), 3, "pivot")
        with self.assertRaisesRegex(TypeError, r"^pivot must be a number$"):
            util._finite_vector((1, "2", 3), 3, "pivot")
        with self.assertRaisesRegex(ValueError, r"^pivot must be finite$"):
            util._finite_vector((1, float("nan"), 3), 3, "pivot")

    def test_checked_tolerance(self):
        self.assertEqual(util._checked_tolerance(0), 0.0)
        self.assertEqual(util._checked_tolerance(1e-3, positive=True), 1e-3)
        with self.assertRaisesRegex(ValueError, r"^tolerance must be non-negative$"):
            util._checked_tolerance(-1)
        with self.assertRaisesRegex(ValueError, r"^tolerance must be positive$"):
            util._checked_tolerance(0, positive=True)
        with self.assertRaisesRegex(TypeError, r"^tolerance must be a number$"):
            util._checked_tolerance("0.1")
        with self.assertRaisesRegex(ValueError, r"^tolerance must be finite$"):
            util._checked_tolerance(float("inf"))


class UniqueOrderedTest(unittest.TestCase):
    """_unique_ordered は最初の出現順を保って重複を除く。"""

    def test_default_key(self):
        self.assertEqual(util._unique_ordered([3, 1, 3, 2, 1]), [3, 1, 2])
        self.assertEqual(util._unique_ordered(()), [])

    def test_custom_key_keeps_first(self):
        self.assertEqual(util._unique_ordered(["a", "B", "A", "b"], key=str.lower), ["a", "B"])


class WorldSpaceTest(unittest.TestCase):
    """_world_space はbool以外をTypeErrorで拒否する(ValueErrorから変更)。"""

    def test_accepts_bool(self):
        self.assertIs(util._world_space(True), True)
        self.assertIs(util._world_space(False), False)

    def test_rejects_non_bool_with_type_error(self):
        for value in (1, 0, None, "ws"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, r"^worldSpace \(ws\) must be a bool$"):
                    util._world_space(value)


class RethrowInitErrorTest(unittest.TestCase):
    """_rethrow_init_error は補助関数名をクラス名へ置き換え、元の例外を連鎖しない。"""

    def test_replaces_helper_name(self):
        class Vector:
            pass

        try:
            try:
                raise TypeError("_vector_keywords() got an unexpected keyword argument 'w'")
            except TypeError as error:
                util._rethrow_init_error(Vector, error)
        except TypeError as rethrown:
            self.assertEqual(str(rethrown), "Vector() got an unexpected keyword argument 'w'")
            self.assertTrue(rethrown.__suppress_context__)
        else:
            self.fail("TypeError was not raised")


class UnsetTest(unittest.TestCase):
    """_UNSET はutilだけが定義し、loggerは_NO_CAUSEを使う。"""

    def test_logger_has_no_unset(self):
        text = (_MLIB_ROOT / "logger.py").read_text(encoding="utf-8")
        self.assertNotIn("_UNSET", text)
        self.assertIn("_NO_CAUSE = object()", text)


if __name__ == "__main__":
    unittest.main()
