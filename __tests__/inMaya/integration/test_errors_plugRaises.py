"""Plug・MultiPlug の公開APIが docstring の Raises に書いた例外のうち、ほかのテストで確かめていないものを固定する。

- 無効な参照: 所有ノードの削除・動的アトリビュートの削除の後の照会・設定は RuntimeError。
  (``test_errors_plugs.py`` の表にある照会は除く)
- getRange(soft の有無): unit・timeUnit・uiUnits の型は TypeError。
- setRange(soft の有無): 値の型と、静的・数値以外のアトリビュートは TypeError。例外の後は定義が変わらない。
- MultiPlug.appendMessage: 論理番号が上限に達していれば IndexError で、接続を足さない。
- getNumConnectedChildren: コンパウンドでない Plug では 0 を返す。
- setIfChanged: check=True で NaN なら ValueError で、値を変えない。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.plugs.plug import MAX_LOGICAL_INDEX

#: 無効な Plug で RuntimeError になる照会・設定。(名前, Plug を受けて呼ぶ関数)。
_PLUG_CALLS = (
    ("isExactlyEqual", lambda plug, other: plug.isExactlyEqual(other)),
    ("isExactlyEqual(other)", lambda plug, other: other.isExactlyEqual(plug)),
    ("getNumConnectedChildren", lambda plug, other: plug.getNumConnectedChildren()),
    ("getAnimCurve(suitableType)", lambda plug, other: plug.getAnimCurve(suitableType=True)),
    ("getSetAttrCmds", lambda plug, other: plug.getSetAttrCmds()),
    ("getAttributeClass", lambda plug, other: plug.getAttributeClass()),
    ("getParent(all)", lambda plug, other: plug.getParent(all=True)),
    ("getDescendants", lambda plug, other: plug.getDescendants()),
    ("setFlags(keyable)", lambda plug, other: plug.setFlags(keyable=True)),
    ("setFlags(channelBox)", lambda plug, other: plug.setFlags(channelBox=True)),
    ("setFlags(leaf)", lambda plug, other: plug.setFlags(keyable=True, leaf=True)),
    ("getRange", lambda plug, other: plug.getRange()),
    ("setRange", lambda plug, other: plug.setRange(0.0, 1.0)),
    ("getRange(soft)", lambda plug, other: plug.getRange(soft=True)),
    ("setRange(soft)", lambda plug, other: plug.setRange(0.0, 1.0, soft=True)),
    ("isDefaultValue", lambda plug, other: plug.isDefaultValue()),
    ("isDirty", lambda plug, other: plug.isDirty()),
    ("setDirty", lambda plug, other: plug.setDirty()),
)

#: 無効な MultiPlug で RuntimeError になる照会。
_MULTI_CALLS = (
    ("getElementCount", lambda multi: multi.getElementCount()),
    ("getElementCount(evaluate)", lambda multi: multi.getElementCount(evaluate=True)),
    ("getElement(physical)", lambda multi: multi.getElement(0, physical=True)),
    ("getIndices(connected)", lambda multi: multi.getIndices(connected=True)),
)


class _PlugCase(NamespaceCase):
    """無効になった Plug と、範囲を持つ動的アトリビュートを作る補助。"""

    PREFIX = "mlibSpecPlugRaises_"
    UNLOCK_NODES = True

    def nodes(self):
        """シーン全体のノードの完全名の集合を返す。"""
        return set(cmds.ls(long=True) or [])

    def dead_node_plug(self):
        """所有ノードを削除した、範囲を持つ動的アトリビュートの Plug を返す。"""
        node = self.ranged()
        plug = mlib.getNode(node).getPlug("amount")
        cmds.delete(node)
        return plug

    def dead_attr_plug(self):
        """範囲を持つ動的アトリビュートを削除した Plug を返す(所有ノードは有効なまま)。"""
        node = self.ranged()
        plug = mlib.getNode(node).getPlug("amount")
        cmds.deleteAttr(node + ".amount")
        return plug

    def ranged(self):
        """最小0・最大10・ソフト最小1・ソフト最大9の動的アトリビュート amount を持つノードを作る。"""
        node = self.make("transform", "ranged#")
        cmds.addAttr(
            node, longName="amount", attributeType="double", minValue=0.0, maxValue=10.0, softMinValue=1.0, softMaxValue=9.0, defaultValue=5.0, keyable=True
        )
        return node

    def multi(self):
        """要素を2つ持つ plusMinusAverage を作り、(ノード名, input1D の MultiPlug) を返す。"""
        node = self.make("plusMinusAverage", "pma#")
        cmds.setAttr(node + ".input1D[0]", 1.0)
        cmds.setAttr(node + ".input1D[3]", 2.0)
        return node, mlib.getNode(node).getPlug("input1D")

    def limits(self, node, attribute="amount"):
        """attributeQuery で範囲の定義を読む(例外の後に変わっていないことの確認用)。"""
        return (
            cmds.attributeQuery(attribute, node=node, minimum=True),
            cmds.attributeQuery(attribute, node=node, maximum=True),
            cmds.attributeQuery(attribute, node=node, softMin=True),
            cmds.attributeQuery(attribute, node=node, softMax=True),
        )


class InvalidPlugTest(_PlugCase):
    """所有ノード・アトリビュートが無効な Plug の照会・設定は RuntimeError。"""

    def test_valid_calls(self):
        """正常系: 有効な Plug では同じ呼出しが例外にならない。"""
        node = self.ranged()
        plug = mlib.getNode(node).getPlug("amount")
        other = mlib.getNode(node).getPlug("translateX")
        compound = mlib.getNode(node).getPlug("translate")
        for name, call in _PLUG_CALLS:
            if name.startswith("isExactlyEqual") and not hasattr(om2.MPlug, "isExactlyEqual"):
                # API 2.0 に照会が無い版では、docstring のとおり NotImplementedError になる。
                with self.subTest(method=name, state="unsupported"):
                    with self.assertRaises(NotImplementedError):
                        call(plug, other)
                continue
            with self.subTest(method=name):
                call(plug, other)
        with self.subTest(method="getNumConnectedChildren", case="compound"):
            cmds.connectAttr(self.make("transform", "source#") + ".translateX", node + ".translateY")
            self.assertEqual(compound.getNumConnectedChildren(), 1)
        with self.subTest(method="getNumConnectedChildren", case="notCompound"):
            # コンパウンドでない Plug では、om2 の例外でなく 0 を返す。
            self.assertEqual(plug.getNumConnectedChildren(), 0)
            self.assertEqual(other.getNumConnectedChildren(), 0)

    def test_plug_calls(self):
        """削除済みノード・削除済み動的アトリビュートの Plug で、各呼出しが RuntimeError になり、ノードを増やさない。"""
        for label, factory in (("deletedNode", self.dead_node_plug), ("deletedAttribute", self.dead_attr_plug)):
            other = mlib.getNode(self.make("transform", "other#")).getPlug("translateX")
            for name, call in _PLUG_CALLS:
                with self.subTest(case=label, method=name):
                    plug = factory()
                    before = self.nodes()
                    with self.assertRaises(RuntimeError):
                        call(plug, other)
                    self.assertEqual(self.nodes(), before)

    def test_multi_calls(self):
        """所有ノードを削除した MultiPlug で、各照会が RuntimeError になる。"""
        for name, call in _MULTI_CALLS:
            node, multi = self.multi()
            with self.subTest(method=name, state="valid"):
                call(multi)
            cmds.delete(node)
            with self.subTest(method=name, state="deleted"):
                with self.assertRaises(RuntimeError):
                    call(multi)


class RangeArgumentTest(_PlugCase):
    """getRange・setRange(soft の有無)の引数の型の拒否。"""

    def test_get_range_type_errors(self):
        """unit・timeUnit が文字列・None 以外、uiUnits が bool 以外は TypeError。"""
        plug = mlib.getNode(self.ranged()).getPlug("amount")
        for soft in (False, True):
            with self.subTest(soft=soft, state="valid"):
                self.assertEqual(len(plug.getRange(soft=soft)), 2)
            for kwargs in ({"unit": 5}, {"timeUnit": 1.0}, {"uiUnits": "yes"}, {"uiUnits": 1}):
                with self.subTest(soft=soft, kwargs=kwargs):
                    with self.assertRaises(TypeError):
                        plug.getRange(soft=soft, **kwargs)

    def test_set_range_type_errors(self):
        """値の型の不正・静的アトリビュート・数値以外のアトリビュートは TypeError で、定義を変えない。"""
        node = self.ranged()
        cmds.addAttr(node, longName="label", dataType="string")
        cmds.addAttr(node, longName="flag", attributeType="bool")
        amount = mlib.getNode(node).getPlug("amount")
        before = self.limits(node)
        cases = (("amount", ("a", 1.0)), ("amount", (0.0, [1.0])), ("translateX", (0.0, 1.0)), ("label", (0.0, 1.0)))
        for soft in (False, True):
            for attribute, values in cases:
                with self.subTest(soft=soft, attribute=attribute, values=values):
                    plug = amount if attribute == "amount" else mlib.getNode(node).getPlug(attribute)
                    with self.assertRaises(TypeError):
                        plug.setRange(*values, soft=soft)
                    self.assertEqual(self.limits(node), before)
        for soft in (False, True):
            for kwargs in ({"unit": 5}, {"timeUnit": 1.0}):
                with self.subTest(soft=soft, kwargs=kwargs):
                    with self.assertRaises(TypeError):
                        amount.setRange(0.0, 1.0, soft=soft, **kwargs)
                    self.assertEqual(self.limits(node), before)


class SetIfChangedTest(_PlugCase):
    """setIfChanged の check=True の検査。"""

    def test_check_non_finite(self):
        """check=True で NaN・無限大は ValueError。通常・fast のどちらでも値は変わらない。"""
        for fast in (False, True):
            for value in (float("nan"), float("inf")):
                with self.subTest(fast=fast, value=value):
                    node = self.ranged()
                    plug = mlib.getNode(node).getPlug("amount")
                    with self.assertRaises(ValueError):
                        plug.setIfChanged(value, check=True, fast=fast)
                    self.assertEqual(cmds.getAttr(node + ".amount"), 5.0)


class AppendMessageLimitTest(_PlugCase):
    """MultiPlug.appendMessage の論理番号の上限。"""

    def test_index_limit(self):
        """最大の論理番号に要素があれば IndexError で、接続を足さない。"""
        holder = self.make("transform", "holder#")
        cmds.addAttr(holder, longName="links", attributeType="message", multi=True)
        source = self.make("transform", "source#")
        target = self.make("transform", "target#")
        cmds.connectAttr(source + ".message", f"{holder}.links[{MAX_LOGICAL_INDEX}]")
        multi = mlib.getNode(holder).getPlug("links")
        self.assertEqual(multi.getIndices(), [MAX_LOGICAL_INDEX])
        before = cmds.listConnections(holder + ".links", source=True, destination=False, plugs=True, connections=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(IndexError):
                    multi.appendMessage(target, fast=fast)
                self.assertEqual(cmds.listConnections(holder + ".links", source=True, destination=False, plugs=True, connections=True), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
