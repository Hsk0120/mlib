"""``mlib.cmds.getPlug`` のテスト。

- mlib.cmds の7入口(getNode・getPlug・createNode・ls・delete・duplicate・select)の仕様テスト(担当D)。
"""

import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.plugs import Plug


class _CmdsCase(unittest.TestCase):
    """一時名前空間・選択・Undo設定の保存と復元を共通にする。"""

    def setUp(self):
        """一時名前空間を作り、選択とUndo設定を保存する。"""
        self.undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.selection = cmds.ls(selection=True, long=True)
        self.ns = "mlibSpecDCmds_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を中身ごと削除し、選択とUndo設定を戻す。"""
        cmds.select(clear=True)
        if cmds.namespace(exists=self.ns):
            for node in cmds.ls(self.ns + ":*", long=True) or []:
                if cmds.objExists(node) and cmds.lockNode(node, query=True, lock=True)[0]:
                    cmds.lockNode(node, lock=False)
            cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        existing = [name for name in self.selection if cmds.objExists(name)]
        if existing:
            cmds.select(existing, replace=True)
        cmds.undoInfo(state=self.undo_state)

    def name(self, leaf):
        """一時名前空間内の名前を返す。"""
        return self.ns + ":" + leaf

    def transforms(self):
        """一時名前空間内のtransformの数を返す。"""
        return len(cmds.ls(self.ns + ":*", type="transform") or [])


class GetPlugSpecTest(_CmdsCase):
    """getPlugの入力・同一インスタンス・マルチアトリビュートの要素を固定する。"""

    def test_inputs_and_identity(self):
        """名前・MPlugから新しいPlug、既存Plugは同じインスタンスを返す。"""
        node = cmds.createNode("transform", name=self.name("node"))
        plug = mlib.getPlug(node + ".tx")
        self.assertIsInstance(plug, Plug)
        self.assertIs(mlib.getPlug(plug), plug)
        self.assertEqual(plug.getFullName(), mlib.getPlug(node + ".translateX").getFullName())
        mplug = om2.MSelectionList().add(node + ".ty").getPlug(0)
        self.assertEqual(mlib.getPlug(mplug).getFullName().split(".")[-1], "translateY")

    def test_multi_element_is_not_created(self):
        """未作成のマルチアトリビュートの要素も参照でき、参照取得だけでは要素を作らない。"""
        node = cmds.createNode("transform", name=self.name("node"))
        cmds.addAttr(node, longName="values", attributeType="double", multi=True)
        plug = mlib.getPlug(node + ".values[5]")
        self.assertIsInstance(plug, Plug)
        self.assertIsNone(cmds.getAttr(node + ".values", multiIndices=True))

    def test_errors(self):
        """空の名前・空のMPlugはValueError、未対応型はTypeError、解決できない名前はRuntimeError。"""
        node = cmds.createNode("transform", name=self.name("node"))
        with self.assertRaises(ValueError):
            mlib.getPlug("")
        with self.assertRaises(ValueError):
            mlib.getPlug(om2.MPlug())
        with self.assertRaises(TypeError):
            mlib.getPlug(5)
        with self.assertRaises(RuntimeError):
            mlib.getPlug(node + ".noSuchAttribute")
        with self.assertRaises(RuntimeError):
            mlib.getPlug(self.name("missing") + ".tx")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
