"""Plugの公開メソッドが、無効な対象・誤った入力でdocstringの例外を出すことと、fastの分岐を確かめる。

期待値は maya.cmds で読み直して比べる。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.plugs.plug import MissingAttributeError, Plugs


def _mplug(name):
    """名前からMPlugを取得する。"""
    selection = om2.MSelectionList()
    selection.add(name)
    return selection.getPlug(0)


class _Case(NamespaceCase):
    """名前空間に transform を1つ作る。"""

    PREFIX = "mlibPlugInvalid_"

    def setUp(self):
        super().setUp()
        self.path = self.make("transform", "node")
        self.node = mlib.getNode(self.path)

    def deleted_plug(self, attribute="translateX"):
        """削除したノードのPlugを返す。"""
        name = self.make("transform", "gone#")
        plug = mlib.getNode(name).getPlug(attribute)
        cmds.delete(name)
        return plug


class InvalidPlugTest(_Case):
    """ノードが削除されたPlugの操作は RuntimeError にする。"""

    def test_queries_and_key_edits_raise_runtime_error(self):
        plug = self.deleted_plug()
        calls = {
            "isNewAttribute": plug.isNewAttribute,
            "removeKey": plug.removeKey,
            "moveKey": lambda: plug.moveKey(timeOffset=1),
            "setKeyTangent": lambda: plug.setKeyTangent(inTangentType="linear"),
            "setDirty": plug.setDirty,
        }
        for label, call in calls.items():
            with self.subTest(method=label), self.assertRaises(RuntimeError):
                call()

    @unittest.expectedFailure  # findings2/plugs-core-cmds.md 1: 削除済みのPlugのevaluateがValueErrorになる。
    def test_evaluate_on_deleted_plug_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            self.deleted_plug().evaluate()

    def test_deleted_attribute_mplug_is_rejected(self):
        """deleteAttrで消したアトリビュートのMPlugからは、Plugを作らない。"""
        cmds.addAttr(self.path, longName="zzGone", attributeType="double")
        mplug = _mplug(self.path + ".zzGone")
        cmds.deleteAttr(self.path + ".zzGone")
        self.assertFalse(cmds.attributeQuery("zzGone", node=self.path, exists=True))
        # getPlugのdocstringに書いていない例外(findings2/plugs-core-cmds.md 5)。型が決まるまで両方を受ける。
        with self.assertRaises((RuntimeError, ValueError)):
            mlib.getPlug(mplug)
        with self.assertRaises(RuntimeError):
            self.node.getPlug("translateX").isConnected(mplug)


class ArgumentTest(_Case):
    """引数の型・値の誤り。"""

    def test_get_name_rejects_non_bool_full(self):
        plug = self.node.getPlug("tx")
        self.assertEqual(plug.getName(full=True), self.path + ".translateX")
        for value in (1, None, "yes"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    plug.getName(full=value)
                with self.assertRaises(TypeError):
                    Plugs([plug]).getNames(full=value)

    def test_set_if_changed_rejects_non_finite_and_non_scalar(self):
        plug = self.node.getPlug("tx")
        for value in (math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                plug.setIfChanged(value, check=True)
        with self.assertRaises(TypeError):
            self.node.getPlug("translate").setIfChanged((1.0, 2.0, 3.0))
        self.assertEqual(cmds.getAttr(self.path + ".translate"), [(0.0, 0.0, 0.0)])

    def test_set_enum_names_on_static_attribute_is_refused_by_maya(self):
        before = cmds.attributeQuery("rotateOrder", node=self.path, listEnum=True)
        with self.assertRaises(RuntimeError):
            self.node.getPlug("rotateOrder").setEnumNames(["a", "b"])
        self.assertEqual(cmds.attributeQuery("rotateOrder", node=self.path, listEnum=True), before)

    def test_missing_attribute_names_raise_attribute_error(self):
        plug = self.node.getPlug("tx")
        missing = self.path + ".zzNoSuch"
        adder = mlib.createNode("addDoubleLinear", name=self.name("adl"))
        calls = {
            "isConnected": lambda: plug.isConnected(missing),
            "connect": lambda: plug.connect(missing),
            "disconnect": lambda: plug.disconnect(missing),
            "connectTo": lambda: plug.connectTo(missing),
            "insertInput": lambda: plug.insertInput(adder, "zzNoSuch", "output"),
        }
        for label, call in calls.items():
            with self.subTest(method=label):
                with self.assertRaises(AttributeError) as caught:
                    call()
                self.assertIsInstance(caught.exception, MissingAttributeError)
        self.assertEqual(cmds.listConnections(self.path, source=True, destination=False) or [], [])

    def test_ambiguous_name_is_not_resolved_to_one_plug(self):
        first = self.make("transform", "groupA")
        second = self.make("transform", "groupB")
        self.make("transform", "dup", parent=first)
        self.make("transform", "dup", parent=second)
        self.assertEqual(len(cmds.ls(self.name("dup") + ".tx")), 2)
        with self.assertRaises(RuntimeError) as caught:
            mlib.getPlug(self.name("dup") + ".tx")
        self.assertNotIsInstance(caught.exception, MissingAttributeError)
        with self.assertRaises(MissingAttributeError):
            mlib.getPlug(self.name("dup") + ".zzNoSuch")


class StateTest(_Case):
    """Undoに載らない操作と、ペアで返す接続の照会。"""

    def test_set_dirty_records_no_undo(self):
        """setDirtyはUndoに載らないので、直後のUndoはその前のsetを戻す。"""
        plug = self.node.getPlug("tx")
        plug.set(2.0)
        plug.setDirty()
        self.assertEqual(cmds.getAttr(self.path + ".tx"), 2.0)
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.path + ".tx"), 0.0)

    def test_get_connections_with_connections_flag_returns_pairs(self):
        plug = self.node.getPlug("tx")
        self.assertEqual(list(plug.getConnections(connections=True)), [])
        cmds.connectAttr(self.path + ".ty", self.path + ".tx")
        pairs = list(plug.getConnections(connections=True))
        expected = cmds.listConnections(self.path + ".tx", connections=True, plugs=True, source=True, destination=False)
        self.assertEqual(len(pairs), 1)
        self.assertEqual([str(item) for item in pairs[0]], [cmds.ls(name)[0] for name in expected])


class FastBranchTest(_Case):
    """fastの書き込みで、単位付きの既定値と、無いエイリアスの解除。"""

    def test_set_default_fast_matches_normal_for_unit_attributes(self):
        for kind, value in (("doubleLinear", 2.5), ("doubleAngle", 90.0)):
            with self.subTest(kind=kind):
                normal = "zzN" + kind
                fast = "zzF" + kind
                cmds.addAttr(self.path, longName=normal, attributeType=kind)
                cmds.addAttr(self.path, longName=fast, attributeType=kind)
                self.node.getPlug(normal).setDefault(value)
                self.flushUndo()
                self.node.getPlug(fast).setDefault(value, fast=True)
                self.assertUndoEmpty()
                self.assertAlmostEqual(
                    cmds.addAttr(self.path + "." + fast, query=True, defaultValue=True), cmds.addAttr(self.path + "." + normal, query=True, defaultValue=True)
                )

    def test_set_alias_fast_without_alias_does_nothing(self):
        self.flushUndo()
        self.node.getPlug("tx").setAlias(None, fast=True)
        self.assertUndoEmpty()
        self.assertIsNone(cmds.aliasAttr(self.path, query=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
