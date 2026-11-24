"""複数形の ``Plugs`` の、比較・連結・並べ替え・転送の誤りと、無効なアトリビュートの拒否のテスト。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class _PlugsCase(NamespaceCase):
    """数値のマルチアトリビュートを持つtransformを作る。"""

    PREFIX = "mlibPlugsCollection_"

    def setUp(self):
        super().setUp()
        self.node = self.make("transform", "node#")
        cmds.addAttr(self.node, longName="numbers", shortName="numbers", attributeType="double", multi=True)
        cmds.setAttr(self.node + ".numbers[3]", 1.0)


class PlugsOperatorTest(_PlugsCase):
    """比較・連結・並べ替え。"""

    def test_unsupported_operands(self):
        """Plugs・list・tuple以外との比較はFalse、左辺がlist・tuple以外の + はTypeError。"""
        plugs = mlib.Plugs([self.node + ".tx", self.node + ".ty"])
        self.assertFalse(plugs == 5)
        self.assertTrue(plugs != "tx")
        with self.assertRaises(TypeError):
            5 + plugs
        joined = [self.node + ".tz"] + plugs  # noqa: RUF005 list + Plugs の __radd__ を確かめる
        self.assertIsInstance(joined, mlib.Plugs)
        self.assertEqual(joined.getNames(full=True), [cmds.ls(self.node + "." + name)[0] for name in ("translateZ", "translateX", "translateY")])

    def test_sort(self):
        """keyが呼び出せなければTypeErrorで順を変えない。sortは値を返さない。"""
        plugs = mlib.Plugs([self.node + ".ty", self.node + ".tx"])
        before = plugs.getNames()
        with self.assertRaises(TypeError):
            plugs.sort(key=5)
        with self.assertRaises(TypeError):
            plugs.sort(reverse=1)
        self.assertEqual(plugs.getNames(), before)
        self.assertIsNone(plugs.sort())
        self.assertEqual(plugs.getNames(), sorted(before))


class PlugsForwardTest(_PlugsCase):
    """各要素のメソッドへの転送。"""

    def test_mixed_types(self):
        """一部の要素だけが持つメソッドは、どの要素も呼ぶ前にTypeError。全要素が持てば同じ順のリストを返す。"""
        plugs = mlib.Plugs([self.node + ".tx", self.node + ".numbers"])
        with self.assertRaises(TypeError):
            plugs.getIndices()
        with self.assertRaises(AttributeError):
            plugs.notMethod
        self.assertEqual(plugs.isMulti(), [False, True])
        self.assertEqual(plugs.isMulti(), [cmds.attributeQuery(name, node=self.node, multi=True) for name in ("translateX", "numbers")])


class PlugsInvalidItemTest(_PlugsCase):
    """無効なアトリビュートの拒否。"""

    def test_deleted_attribute(self):
        """削除したアトリビュートのPlugは、作るときもappendでもRuntimeErrorで、コレクションを変えない。"""
        cmds.addAttr(self.node, longName="extraValue", shortName="extraValue", attributeType="double")
        removed = mlib.getPlug(self.node + ".extraValue")
        cmds.deleteAttr(self.node + ".extraValue")
        with self.assertRaises(RuntimeError):
            mlib.Plugs([self.node + ".tx", removed])
        plugs = mlib.Plugs([self.node + ".tx"])
        with self.assertRaises(RuntimeError):
            plugs.append(removed)
        with self.assertRaises(RuntimeError):
            plugs.insert(0, removed)
        self.assertEqual(len(plugs), 1)


class ConnectElementTest(_PlugsCase):
    """マルチアトリビュートの要素への接続。"""

    def test_skip_existing_next_available(self):
        """skipExistingとnextAvailableでは、同じ接続が無ければ空いた要素へつなぎ、あればその要素を返す。"""
        cmds.addAttr(self.node, longName="sourceValue", shortName="sourceValue", attributeType="double")
        plug = mlib.getPlug(self.node + ".numbers")
        first = plug.connect(self.node + ".sourceValue", nextAvailable=True, skipExisting=True)
        self.assertEqual(first.getIndex(), 0)
        second = plug.connect(self.node + ".sourceValue", nextAvailable=True, skipExisting=True)
        self.assertEqual(second, first)
        self.assertEqual(cmds.listConnections(self.node + ".numbers", source=True, destination=False, plugs=True), [cmds.ls(self.node)[0] + ".sourceValue"])

    def test_connect_with_undo_disabled(self):
        """Undoが無効でも、値を持つ要素へつなげる(cmdsで接続を読める)。"""
        element = mlib.getPlug(self.node + ".numbers[3]")
        cmds.undoInfo(state=False)
        try:
            element.connect(self.node + ".tx")
        finally:
            cmds.undoInfo(state=True)
        self.assertEqual(cmds.listConnections(self.node + ".numbers[3]", source=True, destination=False, plugs=True), [cmds.ls(self.node)[0] + ".translateX"])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
