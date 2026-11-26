"""引数を網羅するテストの、Mayaを使わない部分(``support/argumentTable.py``)を確かめる。

- docstring の Args・Raises の読み取り、型の分類、段1の候補・段2の違う型の値、段3の組の生成と上限。
- known の型紙・関数・版、可変長の引数、Lazy の作り直し(並びの中・ほかの引数を受け取るもの)、可変長の引数を展開した呼び出し。
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


class KnownTest(unittest.TestCase):
    """known の型紙・関数・版。"""

    def test_bracket_is_also_literal(self):
        method = table.Method("setX", None, known={"invalid:members=[<root>, <j1>]": "理由", "values:at=[[](0,)]": "古い書き方"})
        self.assertEqual(method.isKnown("invalid:members=[<root>, <j1>]"), "理由")
        self.assertEqual(method.isKnown("values:at=[(0,)]"), "古い書き方")
        self.assertIsNone(method.isKnown("invalid:members=r"))
        self.assertTrue(table.matchLabel("pairs:value=a,b", "pairs:value=a,[!f]*"))
        self.assertFalse(table.matchLabel("pairs:value=a,f", "pairs:value=a,[!f]*"))
        self.assertTrue(table.matchLabel("invalid:normals=[(1.0, 2.0)]", "invalid:normals=[(1.0, 2.0)*"))

    def test_function_and_version(self):
        method = table.Method(
            "setX",
            None,
            known={(lambda stage, kwargs: stage == "pairs" and kwargs.get("time") == 1): "関数", "values:*": table.Known("2022だけ", versions=(2022,))},
        )
        self.assertEqual(method.isKnown("pairs:time=1", {"time": 1}), "関数")
        self.assertIsNone(method.isKnown("values:time=1", {"time": 1}, version=2027))
        self.assertEqual(method.isKnown("values:time=1", {"time": 1}, version=2022), "2022だけ")
        self.assertTrue(method.hasVersionedKnown(2027))
        self.assertFalse(method.hasVersionedKnown(2022))

    def test_test_name(self):
        self.assertEqual(table.Method("getWeights", None, variant="vertex").testName, "getWeights_vertex")
        self.assertEqual(table.Method("getWeights", None).testName, "getWeights")


def _variadic(weight, *targets, fast=False, **flags):
    """可変長の引数を持つ関数。

    Args:
        weight (float): ウェイト。
        *targets (Node | str): 対象。
        fast (bool): 速く書くか。
        **flags (object): そのほかのフラグ。
    """
    return weight, targets, fast, flags


class VariadicTest(unittest.TestCase):
    """可変長の引数。"""

    def test_parameters_include_variadic_only_when_asked(self):
        self.assertEqual([param.name for param in table.parameters(_variadic)], ["weight", "fast"])
        params = {param.name: param for param in table.parameters(_variadic, include=("*", "flags"))}
        self.assertEqual(params["targets"].variadic, "*")
        self.assertEqual(params["flags"].variadic, "**")
        self.assertEqual(params["targets"].kinds, ["node", "str"])
        self.assertEqual(params["targets"].candidates((("a", "b"),)), [("a", "b")])
        self.assertTrue(all(isinstance(value, tuple) and len(value) == 1 for value in params["targets"].invalidValues()))
        self.assertEqual(params["flags"].invalidValues(), [])
        method = table.Method("setX", None, values={"*": (("a",),), "flags": ({"q": 1},)})
        self.assertEqual(method.valuesFor(params["targets"]), (("a",),))
        self.assertEqual(method.valuesFor(params["flags"]), ({"q": 1},))
        self.assertTrue(method.mentions("targets", "*"))
        self.assertFalse(method.mentions("other", "**"))

    def test_invoke_spreads_variadic(self):
        self.assertEqual(table.invoke(_variadic, {"weight": 0.5, "targets": ("a", "b"), "fast": True}), (0.5, ("a", "b"), True, {}))
        self.assertEqual(table.invoke(_variadic, {"weight": 1.0, "flags": {"time": 2}}), (1.0, (), False, {"time": 2}))
        self.assertEqual(table.invoke(_variadic, {"targets": ["c"], "weight": 2.0}), (2.0, ("c",), False, {}))


class _Case:
    """Lazy に渡すテストケースの代わり。"""

    def name(self, text):
        return "ns:" + text


class ResolveTest(unittest.TestCase):
    """Lazy の作り直し。"""

    def test_nested_and_argument_lazy(self):
        node = table.Lazy(lambda case: case.name("a"), "<a>")
        count = table.Lazy(lambda case, kwargs: len(kwargs["colors"]), "<数>", args=True)
        resolved = table.resolve({"colors": [node, (node, 1)], "options": {"x": node}, "count": count, "plain": 3}, _Case())
        self.assertEqual(resolved, {"colors": ["ns:a", ("ns:a", 1)], "options": {"x": "ns:a"}, "count": 2, "plain": 3})
        self.assertEqual(list(resolved), ["colors", "options", "count", "plain"])
        points = ((0, 0, 0), (1, 0, 0))
        self.assertIs(table.resolve({"points": points}, _Case())["points"], points)

    def test_any_kind_accepts_everything(self):
        self.assertEqual(table.kindsOf("object", "書き込む値。"), ["any"])
        self.assertEqual(table.kindsOf("object", "親のノード。"), ["node"])
        self.assertEqual(table.Parameter("value", None, "object", "書き込む値。").invalidValues(), [])

    def test_error_state_matches_by_type_or_name(self):
        self.assertTrue(table.ErrorState("削除済み", None, RuntimeError).matches(RuntimeError("x")))
        self.assertTrue(table.ErrorState("削除済み", None, ("_Error", ValueError)).matches(MissingAttributeError("x")))
        self.assertFalse(table.ErrorState("削除済み", None, ValueError).matches(TypeError("x")))


if __name__ == "__main__":
    unittest.main()
