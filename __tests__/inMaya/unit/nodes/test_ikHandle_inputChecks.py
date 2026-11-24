"""``mlib.nodes.ikHandle`` の setChain・snapToEffector・getJoints の、拒否と接続が無い場合のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import IkHandle, Joint


class _Case(NamespaceCase):
    """このテストファイルの名前空間の先頭と、SCソルバーのIKの作成。"""

    PREFIX = "mlibSpecIkHandleInput_"
    CLEAR_SELECTION = True

    def chain(self, prefix, parent=None):
        """3つのジョイントのチェーンとSCソルバーのIKを作って (ジョイント名, ハンドル名, エフェクター名) を返す。"""
        cmds.select(clear=True)
        if parent is not None:
            cmds.select(parent, replace=True)
        names = [cmds.joint(name=self.name(f"{prefix}{index}"), position=(index, 0, index % 2)) for index in range(3)]
        cmds.select(clear=True)
        handle, effector = cmds.ikHandle(startJoint=names[0], endEffector=names[2], solver="ikSCsolver", name=self.name(prefix + "Ik"))
        return names, handle, effector


class IkHandleInputTest(_Case):
    """IkHandleの拒否する状態。"""

    def test_set_chain_locked_plug(self):
        """startJointがロックされているとRuntimeErrorで、チェーンは変わらない。"""
        joints, handle, _ = self.chain("a")
        node = mlib.getNode(handle)
        self.assertIs(type(node), IkHandle)
        cmds.setAttr(handle + ".startJoint", lock=True)
        try:
            with self.assertRaises(RuntimeError):
                node.setChain(joints[1], joints[2])
        finally:
            cmds.setAttr(handle + ".startJoint", lock=False)
        self.assertEqual(cmds.ls(cmds.ikHandle(handle, query=True, startJoint=True), long=True), cmds.ls(joints[0], long=True))

    def test_set_chain_instanced(self):
        """インスタンスのチェーンはNotImplementedError。"""
        group = self.make(text="group")
        joints, handle, _ = self.chain("b", parent=group)
        cmds.instance(group, name=self.name("groupCopy"))
        with self.assertRaises(NotImplementedError):
            mlib.getNode(handle).setChain(joints[0], joints[1])

    def test_without_effector(self):
        """エフェクターの接続を外すと、getJoints(end=True)はNone、snapToEffectorはRuntimeError。"""
        joints, handle, effector = self.chain("c")
        node = mlib.getNode(handle)
        self.assertEqual(node.getJoints(end=True), Joint(joints[2]))
        source = cmds.listConnections(effector + ".translateX", source=True, destination=False, plugs=True)
        cmds.disconnectAttr(source[0], effector + ".translateX")
        self.assertIsNone(node.getJoints(end=True))
        plug = cmds.listConnections(handle + ".endEffector", source=True, destination=False, plugs=True)[0]
        cmds.disconnectAttr(plug, handle + ".endEffector")
        self.assertIsNone(node.getJoints(end=True))
        before = cmds.getAttr(handle + ".translate")[0]
        with self.assertRaises(RuntimeError):
            node.snapToEffector()
        self.assertEqual(cmds.getAttr(handle + ".translate")[0], before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
