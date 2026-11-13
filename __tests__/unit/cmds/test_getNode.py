"""``mlib.cmds.getNode`` のテスト。

- mlib.cmds の7入口(getNode・getPlug・createNode・ls・delete・duplicate・select)の仕様テスト(担当D)。
"""

import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.components import Vertex, Vertices
from mlib.nodes import Joints, Node, Nodes, SkinClusters
from mlib.plugs import Plug, Plugs


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


class GetNodeSpecTest(_CmdsCase):
    """getNodeの入力解決・型選択・例外を固定する。"""

    def test_wrapper_type_follows_registry_and_new_reference(self):
        """ラッパー型は登録表(祖先型を含む)で選び、呼ぶたびに同じノードの新しい参照を作る。"""
        joint = cmds.createNode("joint", name=self.name("joint"))
        network = cmds.createNode("network", name=self.name("network"))
        for name in (joint, network):
            node = mlib.getNode(name)
            self.assertIs(type(node), Node._registry.wrapper_class(cmds.nodeType(name)))
        first = mlib.getNode(joint)
        second = mlib.getNode(first)
        self.assertIsNot(first, second)
        self.assertEqual(first, second)
        self.assertEqual(type(first).__name__, "Joint")

    def test_owner_resolution_from_plug_component_and_api(self):
        """Plug・MPlugは所有ノード、Componentは所有シェイプ、API参照は対象ノードへ解決する。"""
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        shape = cmds.listRelatives(cube, shapes=True, fullPath=True)[0]
        selection = om2.MSelectionList().add(cube).add(cube + ".tx")
        self.assertEqual(mlib.getNode(cube + ".tx").getFullName(), "|" + cube)
        self.assertEqual(mlib.getNode(mlib.getPlug(cube + ".tx")).getFullName(), "|" + cube)
        self.assertEqual(mlib.getNode(selection.getPlug(1)).getFullName(), "|" + cube)
        self.assertEqual(mlib.getNode(selection.getDagPath(0)).getFullName(), "|" + cube)
        self.assertEqual(mlib.getNode(selection.getDependNode(0)).getFullName(), "|" + cube)
        vertex = Vertex(mlib.getNode(shape), 0)
        self.assertEqual(mlib.getNode(vertex).getFullName(), shape)
        self.assertEqual(mlib.getNode(Vertices(mlib.getNode(shape), [0, 1])).getFullName(), shape)

    def test_errors(self):
        """存在しない・複数一致・削除済みはRuntimeError、未対応型はTypeError、削除済みアトリビュートはValueError。"""
        cmds.createNode("transform", name=self.name("a1"))
        cmds.createNode("transform", name=self.name("a2"))
        with self.assertRaises(RuntimeError):
            mlib.getNode(self.name("missing"))
        with self.assertRaises(RuntimeError):
            mlib.getNode(self.name("a*"))
        with self.assertRaises(TypeError):
            mlib.getNode(5)
        node = mlib.getNode(self.name("a1"))
        cmds.addAttr(self.name("a1"), longName="extra", attributeType="double")
        plug = mlib.getPlug(self.name("a1") + ".extra")
        cmds.deleteAttr(self.name("a1") + ".extra")
        with self.assertRaises(ValueError):
            mlib.getNode(plug)
        cmds.delete(self.name("a1"))
        with self.assertRaises(RuntimeError):
            mlib.getNode(node)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
