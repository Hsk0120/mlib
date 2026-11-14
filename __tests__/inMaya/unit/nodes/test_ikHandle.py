"""``mlib.nodes.ikHandle`` のテスト。

- Joint・Joints・IkHandle の参照の少ない公開APIの約束を固定する(担当C)。
- Transform・DagNode・Joint・IkHandle のメソッドと createGroup を確かめる。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import IkHandle, Joint, Node


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecJointChain_"
    CLEAR_SELECTION = True

    def chain(self, *items):
        """(名前, 位置) の並びで、選択を使わずに親子の joint を作る。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(text), position=position) for text, position in items]
        cmds.select(clear=True)
        return names


class IkHandleTest(_SpecCase):
    """IkHandle.getEndJoint・getJoints。"""

    def setUp(self):
        super().setUp()
        self.j1, self.j2, self.j3 = self.chain(("j1", (0, 0, 0)), ("j2", (1, 0, 1)), ("j3", (2, 0, 0)))
        self.handle = cmds.ikHandle(startJoint=self.j1, endEffector=self.j3, name=self.name("ik"))[0]
        self.node = Node(self.handle)

    def test_end_joint_and_joints(self):
        """getJoints は jointList(末端を含まない)、includeTip=True で末端を足す。"""
        self.assertIs(type(self.node), IkHandle)
        self.assertEqual(self.node.getEndJoint(), Joint(self.j3))
        self.assertEqual(self.node.getJoints(), [Joint(self.j1), Joint(self.j2)])
        self.assertEqual(self.node.getJoints(includeTip=True), [Joint(self.j1), Joint(self.j2), Joint(self.j3)])
        self.assertTrue(all(type(item) is Joint for item in self.node.getJoints(True)))

    def test_disconnected_effector(self):
        """effector の translate の入力が無ければ getEndJoint は None、getJoints は末端を足さない。"""
        effector = cmds.listConnections(self.handle + ".endEffector")[0]
        cmds.disconnectAttr(self.j3 + ".translateX", effector + ".translateX")
        self.assertIsNone(self.node.getEndJoint())
        self.assertEqual(self.node.getJoints(includeTip=True), [Joint(self.j1), Joint(self.j2)])

    def test_deleted_handle(self):
        """削除済みのハンドルの getJoints は RuntimeError。"""
        cmds.delete(self.handle)
        with self.assertRaisesRegex(RuntimeError, "無効なIkHandleのため"):
            self.node.getJoints()


class _Case(NamespaceCase):
    """ノードを作る補助。"""

    PREFIX = "mlibDagAdd_"

    def transform(self, text="node#", parent=None):
        """transform を作り、ラッパーを返す。"""
        return mlib.getNode(cmds.ls(self.make("transform", text, parent), long=True)[0])

    def chain(self):
        """3つの joint の連鎖を作り、名前のリストを返す。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(f"j{i}"), position=position) for i, position in enumerate(((0, 0, 0), (0, 2, 1), (0, 4, 0)))]
        cmds.select(clear=True)
        return [cmds.ls(name, long=True)[0] for name in names]

    def assertRaisesNoChange(self, error, read, call):
        """call が error を送出し、read の値を変えないことを確かめる。"""
        before = read()
        with self.assertRaises(error):
            call()
        self.assertEqual(read(), before)


class IkHandleDagAdditionsTest(_Case):
    """getSolver・setSolver・snapToEffector。"""

    def setUp(self):
        super().setUp()
        if not cmds.ls(type="ikSCsolver"):
            # 最初のソルバーノードは Undo で消えないため、Undo の確認の前に作っておく。
            cmds.createNode("ikSCsolver", name="ikSCsolver")
        self.joints = self.chain()
        self.handle = mlib.createIkHandle(self.joints[0], self.joints[2], solver="ikRPsolver", name=self.name("ikh#"))

    def test_solver(self):
        handle = self.handle
        self.assertEqual(handle.getSolver(), "ikRPsolver")
        self.assertEqual(handle.getSolver(), cmds.ikHandle(handle.getFullName(), query=True, solver=True))
        self.flushUndo()
        self.assertIs(handle.setSolver("ikSCsolver"), handle)
        self.assertEqual(handle.getSolver(), "ikSCsolver")
        self.assertUndoesInOneStep(lambda: self.assertEqual(handle.getSolver(), "ikRPsolver"), lambda: None)
        handle.setSolver("ikSpringSolver")
        self.assertEqual(handle.getSolver(), "ikSpringSolver")
        for value, error in ((None, TypeError), ("ikSplineSolver", ValueError), ("bogus", ValueError)):
            with self.subTest(value=value):
                self.assertRaisesNoChange(error, handle.getSolver, lambda: handle.setSolver(value))
        source = cmds.listConnections(handle.getFullName() + ".ikSolver", plugs=True)[0]
        cmds.disconnectAttr(source, handle.getFullName() + ".ikSolver")
        self.assertIsNone(handle.getSolver())

    def test_spline_handle_is_rejected(self):
        cmds.select(clear=True)
        joints = [cmds.joint(name=self.name(f"s{i}"), position=(0, i, 0)) for i in range(3)]
        cmds.select(clear=True)
        spline = mlib.createIkHandle(joints[0], joints[2], solver="ikSplineSolver", name=self.name("spl#"))
        self.assertEqual(spline.getSolver(), "ikSplineSolver")
        self.assertRaisesNoChange(ValueError, spline.getSolver, lambda: spline.setSolver("ikRPsolver"))

    def test_snap_to_effector(self):
        """届かない位置のハンドルをエフェクターの位置へ移す。Undo 1回。"""
        handle = self.handle
        name = handle.getFullName()
        cmds.setAttr(name + ".snapEnable", False)
        cmds.setAttr(name + ".t", 10, 10, 10)
        effector = handle.getEffector().getFullName()
        self.flushUndo()
        self.assertIs(handle.snapToEffector(), handle)
        self.assertSequenceAlmostEqual(
            cmds.xform(name, query=True, rotatePivot=True, worldSpace=True), cmds.xform(effector, query=True, rotatePivot=True, worldSpace=True), places=5
        )
        self.assertUndoesInOneStep(lambda: self.assertSequenceAlmostEqual(cmds.getAttr(name + ".t")[0], (10, 10, 10)), lambda: None)
        cmds.delete(name)
        for call in (handle.getSolver, lambda: handle.setSolver("ikSCsolver"), handle.snapToEffector):
            with self.assertRaises(RuntimeError):
                call()


if __name__ == "__main__":
    unittest.main()
