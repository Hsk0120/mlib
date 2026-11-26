"""引数を網羅するテストの、Mayaを使わない部分(``support/argumentTable.py``)を確かめる。

- docstring の Args・Raises の読み取り、型の分類、段1の候補・段2の違う型の値、段3の組の生成と上限。
"""

import math
import unittest

from support import argumentTable as table

_DOC = """位置を書く。

Args:
    value (Iterable[float] | float): 値。
        2行目の説明。
    worldSpace (bool): ワールドか。
    ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
    at (int): 基準。
    unit (str): ``"deg"``・``"rad"`` のどちらか。
    name (str | None): 名前。
    parent (Transform | str | None): 親。
    plug (Plug | str): 相手。

Returns:
    None: 返さない。

Raises:
    TypeError: 型が違う場合。
    ValueError: 値が違う場合。
        続きの行 RuntimeError: は数えない。
    MissingAttributeError: 無い場合。
"""


def _sample(value, worldSpace=False, ws=None, at=2, *, unit="deg", name=None, parent=None, plug=None, **kwargs):
    """``_DOC`` のシグネチャだけを持つ関数。"""


_sample.__doc__ = _DOC


class _Error(Exception):
    """独自の例外の親。"""


class MissingAttributeError(_Error):
    """Raises に書いた独自の型。"""


class DocstringTest(unittest.TestCase):
    """docstring の読み取り。"""

    def test_args_and_raises(self):
        docs = table.argDocs(_DOC)
        self.assertEqual(list(docs), ["value", "worldSpace", "ws", "at", "unit", "name", "parent", "plug"])
        self.assertEqual(docs["value"][0], "Iterable[float] | float")
        self.assertIn("2行目の説明", docs["value"][1])
        self.assertEqual(table.raisesNames(_DOC), {"TypeError", "ValueError", "MissingAttributeError"})

    def test_documented_error_follows_the_class_hierarchy(self):
        self.assertTrue(table.isDocumented(MissingAttributeError("x"), {"MissingAttributeError"}))
        self.assertTrue(table.isDocumented(MissingAttributeError("x"), {"_Error"}))
        self.assertFalse(table.isDocumented(KeyError("x"), {"TypeError", "ValueError"}))

    def test_kinds_choices_and_alias(self):
        self.assertEqual(table.kindsOf("Iterable[float] | float"), ["sequence", "float"])
        self.assertEqual(table.kindsOf("str", '``"deg"``・``"rad"``'), ["choice"])
        self.assertEqual(table.kindsOf("Transform | str | None"), ["node", "str", "none"])
        self.assertEqual(table.kindsOf("Plug | str"), ["plug", "str"])
        self.assertEqual(table.kindsOf("dict[str, int] | None"), ["sequence", "none"])
        self.assertEqual(table.choices('``"deg"``・``"rad"``・``"deg"``'), ["deg", "rad"])
        self.assertEqual(table.aliasOf("worldSpaceの短縮名。"), "worldSpace")
        self.assertIsNone(table.aliasOf("名前。"))


class CandidateTest(unittest.TestCase):
    """段1の候補と段2の違う型の値。"""

    def setUp(self):
        self.params = {param.name: param for param in table.parameters(_sample)}

    def test_parameters_skip_variadic_and_named(self):
        self.assertNotIn("kwargs", self.params)
        self.assertEqual([param.name for param in table.parameters(_sample, skip=("plug",))][-1], "parent")

    def test_candidates(self):
        self.assertEqual(self.params["worldSpace"].candidates(), [False, True])
        self.assertEqual(self.params["at"].candidates(), [2, 0, 1, -1, 100])
        self.assertEqual(self.params["unit"].candidates(), ["deg", "rad"])
        self.assertEqual(self.params["name"].candidates(), [None])
        self.assertEqual(self.params["at"].candidates((7,), replace=True), [7])
        self.assertEqual(self.params["ws"].alias, "worldSpace")

    def test_true_and_one_stay_separate(self):
        self.assertEqual(self.params["at"].candidates((True, 1)), [2, True, 1, 0, -1, 100])

    def test_invalid_values(self):
        labels = {name: [repr(value) for value in param.invalidValues()] for name, param in self.params.items()}
        self.assertEqual(labels["worldSpace"], ["1", "'yes'"])
        self.assertEqual(labels["at"], ["'a'", "nan", "inf"])
        self.assertEqual(labels["unit"], ["1.5", repr(table.INVALID_CHOICE)])
        missing = repr(table.MISSING_NAME)
        self.assertEqual(labels["parent"], ["1.5", "<削除済みのノード>", missing])
        self.assertEqual(labels["plug"], ["1.5", "<削除済みのPlug>", missing])
        self.assertIn("'a'", labels["value"])
        self.assertTrue(labels["value"][-1].startswith("<object"))


class SameTest(unittest.TestCase):
    """値の比較。"""

    def test_same(self):
        self.assertTrue(table.same([1.0, (2.0, "a")], (1.0000000001, [2, "a"])))
        self.assertFalse(table.same(True, 1))
        self.assertTrue(table.same(float("nan"), math.nan))
        self.assertFalse(table.same((1.0, 2.0), (1.0, 2.0, 3.0)))
        self.assertTrue(table.same((1.0, 2.0, 3.0, 1.0), (1.0, 2.0, 3.0)))
        self.assertFalse(table.same(1.0, 1.001))


class PairTest(unittest.TestCase):
    """段3の組。"""

    def test_all_pairs_without_limit(self):
        combos, cut = table.pairs({"a": [True, False], "b": [True, False], "c": [1, 2, 3]}, limit=100)
        self.assertEqual(cut, 0)
        self.assertEqual(len(combos), 4 + 6 + 6)
        self.assertIn({"a": False, "c": 3}, combos)
        self.assertEqual(len({table.label(combo) for combo in combos}), len(combos))

    def test_limit_takes_every_pair_in_turn(self):
        combos, cut = table.pairs({"a": [1, 2, 3], "b": [1, 2, 3], "c": [1, 2, 3]}, limit=6)
        self.assertEqual(cut, 27 - 6)
        self.assertEqual(sorted(tuple(sorted(combo)) for combo in combos[:3]), [("a", "b"), ("a", "c"), ("b", "c")])

    def test_empty_candidates_are_left_out(self):
        combos, cut = table.pairs({"a": [1, 2], "b": []})
        self.assertEqual((combos, cut), ([], 0))


class MethodTest(unittest.TestCase):
    """表の1行。"""

    def test_known_conflicts_and_writes(self):
        method = table.Method(
            "setX", None, conflicts=(("worldSpace", "ws"), lambda kwargs: kwargs.get("relative") is True and "at" in kwargs), known={"invalid:at=*": "理由"}
        )
        self.assertTrue(method.writes)
        self.assertFalse(table.Method("getX", None).writes)
        self.assertEqual(method.isKnown("invalid:at=nan"), "理由")
        self.assertIsNone(method.isKnown("values:at=1"))
        self.assertTrue(method.conflicting({"worldSpace": False, "ws": True}))
        self.assertTrue(method.conflicting({"relative": True, "at": 1}))
        self.assertFalse(method.conflicting({"relative": False, "at": 1}))


if __name__ == "__main__":
    unittest.main()
