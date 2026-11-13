"""``mlib.plugs.multiPlug`` のテスト。

- mlib Node/DAG APIを検証するMaya内テスト。
- CompoundPlug・Double3Plug・MultiPlugの子・要素・値の約束を固定する。
"""

import math
import sys
import unittest
import uuid

from maya.api.OpenMaya import MSpace
import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib import plugs
from mlib.common import Namespace
from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Translate, Vector
from mlib.nodes import Node


class NodeApiTest(unittest.TestCase):
    """基本Node/DAG APIを検証する。"""

    namespace = ":mlibNodeApiTest"

    def setUp(self):
        self.created = []
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.namespace(add=self.namespace)

    def tearDown(self):
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)

    def create_transform(self, name):
        node = mlib.createNode(type="transform", name=name)
        self.created.append(node.getName())
        return node

    def test_multi_plug_next_available_set_and_remove_element(self):
        source = self.create_transform("mlibNodeApiMultiNextAvailSource")
        target = self.create_transform("mlibNodeApiMultiNextAvailTarget")
        multi_plug = target.addAttr("samples", attributeType="double", multi=True)

        self.assertEqual(multi_plug.getNextAvailable(vacant=True).getIndex(), 0)

        multi_plug[0].set(0)
        self.assertEqual(multi_plug.getNextAvailable(vacant=True).getIndex(), 1)
        self.assertEqual(multi_plug.getNextAvailable(start=5, vacant=True).getIndex(), 5)

        element = multi_plug[1].set(2)
        self.assertEqual(element.getLongName(), "samples")
        self.assertTrue(element.getFullName().endswith("[1]"))

        multi_plug.removeElement(1)
        self.assertNotIn(1, multi_plug.get())

        with self.assertRaises(IndexError):
            multi_plug.removeElement(99)

    def assert_channels(self, name, rotate, scale, places=9):
        for actual, expected in zip(cmds.getAttr(name + ".rotate")[0], rotate):
            self.assertAlmostEqual(actual, expected, places=places)
        for actual, expected in zip(cmds.getAttr(name + ".scale")[0], scale):
            self.assertAlmostEqual(actual, expected, places=places)

    def test_multi_plug_elements_returns_all_existing(self):
        target = self.create_transform("mlibNodeApiMultiElements")
        multi_plug = target.getPlug("worldMatrix")
        multi_plug.getElement(0)

        elements = multi_plug.getElements()
        self.assertEqual(len(elements), 1)
        self.assertTrue(elements[0].isMultiElement())


class _PlugSpecCase(unittest.TestCase):
    """専用の名前空間・Undo・単位を用意し、終了時に元へ戻す。"""

    def setUp(self):
        self.namespace = ":specBCompound_" + uuid.uuid4().hex
        self.before = set(cmds.ls(long=True) or [])
        cmds.namespace(add=self.namespace)
        self.undo_state = cmds.undoInfo(query=True, state=True)
        self.units = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True))
        cmds.undoInfo(state=True)
        cmds.currentUnit(linear="cm", angle="deg")
        self.node = self.make("transform")
        self.name = self.node.getFullName()

    def tearDown(self):
        cmds.currentUnit(linear=self.units[0], angle=self.units[1])
        for name in sorted(set(cmds.ls(long=True) or []) - self.before, key=len, reverse=True):
            if cmds.objExists(name):
                try:
                    cmds.lockNode(name, lock=False)
                    cmds.delete(name)
                except RuntimeError:
                    pass  # Mayaが自動で作る削除できないノードは残す。
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.undoInfo(state=self.undo_state)

    def make(self, kind="network"):
        """Mayaコマンドで作成したノードを取得する。"""
        return mlib.getNode(cmds.createNode(kind, name=self.namespace + ":n#", skipSelect=True))

    def indices(self, plug_name):
        """cmdsで既存の論理番号を取得する。"""
        return cmds.getAttr(plug_name, multiIndices=True) or []


class MultiPlugSpecTest(_PlugSpecCase):
    """疎な論理番号、要素の作成と削除、messageのマルチアトリビュートへの追加。"""

    def setUp(self):
        super().setUp()
        self.net = self.make("network")
        self.net_name = self.net.getFullName()
        cmds.addAttr(self.net_name, longName="vals", attributeType="double", multi=True)
        self.array = self.net.getPlug("vals")

    def test_empty_multi(self):
        """空のマルチアトリビュートはget={}、getIndices=[]、反復しない。"""
        self.assertIs(type(self.array), plugs.MultiPlug)
        self.assertEqual(self.array.get(), {})
        self.assertEqual(self.array.getIndices(), [])
        self.assertEqual(self.array.getElements(), [])
        self.assertEqual(list(self.array), [])
        self.assertEqual(self.array.getSourceNodes(), {})
        self.assertTrue(self.array.isMulti())
        self.assertFalse(self.array.isMultiElement())

    def test_reference_does_not_create_but_set_does(self):
        """参照だけでは要素を作らず、setが作る。番号は詰めずにキーへ残る。"""
        element = self.array[5]
        self.assertEqual(element.getFullName(), self.net_name + ".vals[5]")
        self.assertTrue(element.isMultiElement())
        self.assertEqual(self.indices(self.net_name + ".vals"), [])
        element.set(1.5)
        self.array[2].set(0.5, fast=True)
        self.assertEqual(self.array.getIndices(), [2, 5])
        self.assertEqual(self.indices(self.net_name + ".vals"), [2, 5])
        self.assertEqual(self.array.get(), {2: 0.5, 5: 1.5})
        self.assertEqual([p.getFullName() for p in self.array],
                         [self.net_name + ".vals[2]", self.net_name + ".vals[5]"])

    def test_get_of_missing_element_creates_it(self):
        """未作成の要素のget()は要素を作る(cmds.getAttrと同じ)。"""
        self.assertEqual(self.array[9].get(), 0.0)
        self.assertEqual(self.array.getIndices(), [9])

    def test_logical_index_validation(self):
        """論理番号は0〜2147483647の整数。範囲外はIndexError、整数以外・boolはTypeError。"""
        self.assertEqual(self.array[2147483647].getFullName(), self.net_name + ".vals[2147483647]")
        for bad, error in ((-1, IndexError), (2147483648, IndexError), (1.0, TypeError), (True, TypeError),
                           (slice(0, 2), TypeError), ("0", TypeError)):
            with self.subTest(bad=bad):
                with self.assertRaises(error):
                    self.array[bad]

    def test_get_element(self):
        """getElementは欠番も参照を返し(multi[index]と同じ)、要素を作らない。"""
        self.array[3].set(1.0)
        self.assertEqual(self.array.getElement(3).get(), 1.0)
        self.assertEqual(self.array.getElement(index=3).getFullName(), self.net_name + ".vals[3]")
        self.assertEqual(self.array.getElement(4), self.array[4])
        self.assertNotIn(4, self.array)
        with self.assertRaises(TypeError):
            self.array.getElement()
        with self.assertRaises(TypeError):
            self.array.getElement(True)
        self.assertEqual(self.indices(self.net_name + ".vals"), [3])

    def test_get_next_available_index(self):
        """getNextAvailable(vacant=True)は既存番号に無い最初の番号。負数は0から。要素を作らない。"""
        self.array[0].set(1)
        self.array[1].set(1)
        self.array[3].set(1)
        self.assertEqual(self.array.getNextAvailable(vacant=True).getIndex(), 2)
        self.assertEqual(self.array.getNextAvailable(3, vacant=True).getIndex(), 4)
        self.assertEqual(self.array.getNextAvailable(10, vacant=True).getIndex(), 10)
        self.assertEqual(self.array.getNextAvailable(-1, vacant=True).getIndex(), 2)
        self.assertEqual(self.indices(self.net_name + ".vals"), [0, 1, 3])

    def test_get_next_available_for_connections(self):
        """getNextAvailableは入力接続とロックを避ける。既定は最後の接続要素の次から探す。"""
        source = self.make("transform").getFullName()
        self.assertEqual(self.array.getNextAvailable().getIndex(), 0)
        cmds.connectAttr(source + ".tx", self.net_name + ".vals[2]")
        self.assertEqual(self.array.getNextAvailable().getIndex(), 3)
        self.assertEqual(self.array.getNextAvailable(0).getIndex(), 0)
        cmds.setAttr(self.net_name + ".vals[0]", 1.0)
        cmds.setAttr(self.net_name + ".vals[0]", lock=True)
        self.assertEqual(self.array.getNextAvailable(0).getIndex(), 1)
        self.assertEqual(self.array.getNextAvailable(0, checkLocked=False).getIndex(), 0)
        element = self.array.getNextAvailable()
        self.assertEqual(element.getFullName(), self.net_name + ".vals[3]")
        with self.assertRaises(AttributeError):
            self.array[2].getNextAvailable()
        cmds.setAttr(self.net_name + ".vals", lock=True)
        with self.assertRaises(RuntimeError):
            self.array.getNextAvailable()

    def test_remove_element_undo_and_fast(self):
        """removeElementは接続ごと要素を消して自身を返し、1回のUndoで戻る。fastは記録しない。"""
        source = self.make("transform").getFullName()
        self.array[0].set(1.0)
        cmds.connectAttr(source + ".tx", self.net_name + ".vals[1]")
        self.array[2].set(3.0)
        cmds.flushUndo()
        self.assertIs(self.array.removeElement(1), self.array)
        self.assertEqual(self.array.getIndices(), [0, 2])
        self.assertFalse(cmds.listConnections(source + ".tx", source=False, destination=True))
        cmds.undo()
        self.assertEqual(self.array.getIndices(), [0, 1, 2])
        self.assertTrue(cmds.isConnected(source + ".tx", self.net_name + ".vals[1]"))
        cmds.flushUndo()
        self.array.removeElement(index=0, fast=True)
        self.assertEqual(self.array.getIndices(), [1, 2])
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        with self.assertRaises(IndexError):
            self.array.removeElement(0)
        with self.assertRaises(TypeError):
            self.array.removeElement()
        with self.assertRaises(TypeError):
            self.array.removeElement("1")
        with self.assertRaises(TypeError):
            self.array.removeElement(1, fast=1)

    def test_multi_level_set_and_reset_rejected(self):
        """マルチアトリビュート全体のset・resetはsafeでもTypeError。"""
        with self.assertRaises(TypeError):
            self.array.set({0: 1})
        with self.assertRaises(TypeError):
            self.array.set({0: 1}, safe=True)
        with self.assertRaises(TypeError):
            self.array.set({0: 1}, fast=1)
        with self.assertRaises(TypeError):
            self.array.reset()
        self.assertEqual(self.array.getIndices(), [])

    def test_ui_units_per_element(self):
        """角度のマルチアトリビュートのgetはuiUnitsを各要素へ渡す。"""
        cmds.addAttr(self.net_name, longName="angles", attributeType="doubleAngle", multi=True)
        angles = self.net.getPlug("angles")
        angles[0].set(180)
        angles[3].set(90, uiUnits=True)
        result = angles.get()
        self.assertAlmostEqual(result[0], 180)
        self.assertAlmostEqual(result[3], 90)
        self.assertAlmostEqual(angles.get(unit="rad")[0], math.pi)
        self.assertEqual(sorted(angles.get(uiUnits=True).items()), [(0, 180.0), (3, 90.0)])
        with self.assertRaises(TypeError):
            angles.get(uiUnits=1)

    def test_compound_elements(self):
        """コンパウンドアトリビュートであるマルチアトリビュートの要素はCompoundPlugで、子の番号は要素ごとに独立する。"""
        cmds.addAttr(self.net_name, longName="items", attributeType="compound", numberOfChildren=2, multi=True)
        cmds.addAttr(self.net_name, longName="ia", attributeType="double", parent="items")
        cmds.addAttr(self.net_name, longName="ib", attributeType="double", parent="items")
        items = self.net.getPlug("items")
        self.assertIs(type(items[1]), plugs.CompoundPlug)
        items[1].set((1, 2))
        items[4]["ib"].set(5)
        self.assertEqual(items.get(), {1: (1.0, 2.0), 4: (0.0, 5.0)})
        child = items[4]["ib"]
        self.assertEqual(child.getFullName(), self.net_name + ".items[4].ib")
        self.assertEqual(child.getParent().getFullName(), self.net_name + ".items[4]")
        self.assertTrue(child.getParent().isMultiElement())

    def test_world_space_multi_includes_instances(self):
        """worldMatrixはインスタンス番号の要素を評価前から含む。"""
        world = self.node.getPlug("worldMatrix")
        self.assertEqual(world.getIndices(), [0])
        cmds.instance(self.name)
        self.assertEqual(world.getIndices(), [0, 1])
        self.assertEqual(sorted(world.get()), [0, 1])
        self.assertTrue(world.getElement(1).getFullName().endswith(".worldMatrix[1]"))

    def test_source_nodes_keep_holes(self):
        """getSourceNodesは接続のある要素の番号と入力元ノードを返す。"""
        source = self.make("transform")
        cmds.connectAttr(source.getFullName() + ".tx", self.net_name + ".vals[4]")
        self.array[1].set(1.0)
        self.assertEqual(self.array.getSourceNodes(), {4: source})

    def test_append_message(self):
        """appendMessageは最大番号の次へ追加し、穴を再利用しない。通常はUndo、fastは記録なし。"""
        cmds.addAttr(self.net_name, longName="links", attributeType="message", multi=True)
        links = self.net.getPlug("links")
        target = self.make("transform")
        self.assertEqual(links.appendMessage(target), 0)
        self.assertEqual(links.appendMessage(target.getFullName()), 1)
        self.assertEqual(links.getSourceNodes(), {0: target, 1: target})
        links.removeElement(0)
        self.assertEqual(links.appendMessage(target), 2)
        self.assertEqual(links.getIndices(), [1, 2])
        cmds.flushUndo()
        self.assertEqual(links.appendMessage(target), 3)
        cmds.undo()
        self.assertEqual(links.getIndices(), [1, 2])
        cmds.flushUndo()
        self.assertEqual(links.appendMessage(target, fast=True), 3)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertTrue(cmds.isConnected(target.getFullName() + ".message", self.net_name + ".links[3]"))
        with self.assertRaises(TypeError):
            self.array.appendMessage(target)
        with self.assertRaises(RuntimeError):
            links.appendMessage(self.namespace + ":missing")
        with self.assertRaises(TypeError):
            links.appendMessage(target, fast=1)
        with self.assertRaises(RuntimeError):
            links.get()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
