"""``mlib.cmds.createNurbsPlane`` のテスト。

- 形状のシェイプのメソッドと createNurbsPlane を確かめる。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibShapeAdd_"

    def surface(self, scale=(1, 1, 1)):
        """幅4・長さ2(lengthRatio 0.5)の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=0.5, patchesU=2, patchesV=1, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        cmds.setAttr(transform + ".scale", *scale)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def curve(self, points, degree=3):
        """点列から NURBS カーブを作り、シェイプのラッパーを返す。"""
        transform = cmds.curve(name=self.name("curve#"), point=points, degree=degree)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def mesh(self):
        """polyPlane(2x2 分割)を作り、シェイプのラッパーを返す。"""
        transform = cmds.polyPlane(name=self.name("mesh#"), subdivisionsX=2, subdivisionsY=2, constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def assertDeletedRaises(self, node, calls):
        """ノードを削除し、各呼出しが RuntimeError になることを確かめる。"""
        cmds.delete(node.getFullName())
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(RuntimeError):
                    call(node)


class CreateNurbsPlaneTest(_Case):
    """mlib.createNurbsPlane。"""

    def test_create_and_undo(self):
        """nurbsPlane と同じ形状を作り、短縮名も受け、Undo 1回で消える。"""
        self.flushUndo()
        shape = mlib.createNurbsPlane(width=4.0, lengthRatio=0.25, patchesU=4, patchesV=2, name=self.name("ribbon"))
        self.assertIsInstance(shape, mlib.NurbsSurface)
        transform = shape.getTransform().getFullName()
        self.assertEqual(shape.getFullName().rsplit("|", 1)[-1], self.name("ribbonShape").rsplit("|", 1)[-1])
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(transform)), lambda: self.assertTrue(cmds.objExists(transform)))
        shape = mlib.createNurbsPlane(w=4.0, lr=0.25, u=4, v=2, d=1, ax=(0, 0, 1), n=self.name("short"))
        self.assertEqual(shape.getNumSpans(), (4, 2))
        self.assertEqual(shape.getDegree(), (1, 1))
        self.assertAlmostEqual(shape.getArea(), 4.0 * 1.0, places=6)
        self.assertAlmostEqual(abs(shape.getNormalAtParam(0.5, 0.5).z), 1.0)
        self.assertFalse(cmds.listConnections(shape.getFullName() + ".create"))
        default = mlib.createNurbsPlane(name=self.name("default"))
        self.assertAlmostEqual(abs(default.getNormalAtParam(0.5, 0.5).y), 1.0)
        self.assertAlmostEqual(default.getArea(), 1.0, places=6)
        parent = self.make("transform", "parent#")
        child = mlib.createNurbsPlane(name=self.name("child"), parent=parent)
        self.assertEqual(child.getTransform().getParent().getFullName(), cmds.ls(parent, long=True)[0])

    def test_units_and_errors(self):
        """幅は UI 単位によらず cm で、不正な入力は例外になりノードを残さない。"""
        cmds.currentUnit(linear="m")
        shape = mlib.createNurbsPlane(width=2.0, name=self.name("cm"))
        cmds.currentUnit(linear="cm")
        self.assertAlmostEqual(shape.getArea(), 4.0, places=6)
        before = set(cmds.ls(self.ns + ":*"))
        cases = (
            ({"width": 0}, ValueError),
            ({"lengthRatio": float("nan")}, ValueError),
            ({"patchesU": 0}, ValueError),
            ({"patchesV": 1.5}, TypeError),
            ({"axis": (0, 0, 0)}, ValueError),
            ({"degree": 2}, ValueError),
            ({"degree": True}, TypeError),
            ({"width": 1, "w": 1}, TypeError),
            ({"name": "a|b"}, ValueError),
            ({"parent": self.name("missing")}, Exception),
        )
        for kwargs, error in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(error):
                    mlib.createNurbsPlane(**kwargs)
        self.assertEqual(set(cmds.ls(self.ns + ":*")), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
