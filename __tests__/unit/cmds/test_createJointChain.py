"""``mlib.cmds.createJointChain`` のテスト。

- リグ・スキン向けの API の契約を固定する。
"""

import json
import math
import os
import shutil
import tempfile
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.cmds.createJointChain import createJointChain
from mlib.nodes import Joint, Mesh, SkinCluster
from support.namespaceCase import NamespaceCase


def _distance(first, second):
    """2点の距離(Python 3.7 には math.dist が無いため)。"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _world_points(name):
    selection = om2.MSelectionList()
    selection.add(name)
    path = selection.getDagPath(0)
    path.extendToShape()
    return [(p.x, p.y, p.z) for p in om2.MFnMesh(path).getPoints(om2.MSpace.kObject)]


class _RigCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, offset=(0, 0, 0)):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        cmds.move(offset[0], offset[1], offset[2], self.mesh)
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True, maximumInfluences=3)[0])
        cmds.select(clear=True)
        return self.skin


class CreateJointChainTest(NamespaceCase):

    def axes(self, joint):
        matrix = cmds.xform(joint.getFullName(), query=True, matrix=True, worldSpace=True)
        return [matrix[0:3], matrix[4:7], matrix[8:11]]

    def test_default_axes(self):
        """x を次の点へ、y を up へ向け、rotate は0。最後は1つ前と同じ向き。Undo 1回。"""
        points = [(0, 0, 0), (4, 0, -1), (8, 0, 0)]
        names = [self.name(n) for n in ("a", "b", "c")]
        self.flushUndo()
        joints = createJointChain(points, names=names)
        self.assertEqual([j.getName() for j in joints], [n for n in names])
        for joint, point in zip(joints, points):
            self.assertSequenceAlmostEqual(cmds.xform(joint.getFullName(), query=True, translation=True, worldSpace=True),
                                           point, places=6)
            self.assertSequenceAlmostEqual(cmds.getAttr(joint.getFullName() + ".rotate")[0], (0, 0, 0))
        for index in range(2):
            aim = om2.MVector(*points[index + 1]) - om2.MVector(*points[index])
            x_axis, y_axis, z_axis = self.axes(joints[index])
            self.assertSequenceAlmostEqual(x_axis, list(aim.normal()), places=6)
            self.assertSequenceAlmostEqual(y_axis, (0, 1, 0), places=6)
        self.assertSequenceAlmostEqual(sum(self.axes(joints[2]), []), sum(self.axes(joints[1]), []), places=6)
        self.assertEqual(joints[1].getParent().getUuid(), joints[0].getUuid())
        self.assertTrue(cmds.isConnected(names[0] + ".scale", names[1] + ".inverseScale"))
        cmds.undo()
        self.assertFalse(cmds.ls(names))
        self.assertUndoEmpty()

    def test_axes_and_parent(self):
        """-y を向け z を up に、親(回転・移動した transform)の下でもワールドの位置・向きが合う。"""
        parent = cmds.createNode("transform", name=self.name("grp"), skipSelect=True)
        cmds.setAttr(parent + ".translate", 1, 2, 3)
        cmds.setAttr(parent + ".rotate", 10, 20, 30)
        points = [(0, 5, 0), (0, 0, 0)]
        joints = createJointChain(points, aimAxis="-y", upAxis="z", up=(0, 0, 1), parent=parent)
        self.assertEqual(joints[0].getParent().getUuid(), mlib.getNode(parent).getUuid())
        x_axis, y_axis, z_axis = self.axes(joints[0])
        self.assertSequenceAlmostEqual(y_axis, (0, 1, 0), places=6)
        self.assertSequenceAlmostEqual(z_axis, (0, 0, 1), places=6)
        self.assertSequenceAlmostEqual(x_axis, (1, 0, 0), places=6)
        self.assertSequenceAlmostEqual(cmds.xform(joints[1].getFullName(), query=True, translation=True, worldSpace=True),
                                       (0, 0, 0), places=6)

    def test_errors(self):
        transform = cmds.createNode("joint", name=self.name("j"), skipSelect=True)
        cases = (
            (ValueError, lambda: createJointChain([(0, 0, 0)])),
            (ValueError, lambda: createJointChain([(0, 0, 0), (0, 0, 0)])),
            (TypeError, lambda: createJointChain([(0, 0, "a"), (1, 0, 0)])),
            (TypeError, lambda: createJointChain("abc")),
            (ValueError, lambda: createJointChain([(0, 0, 0), (1, 0, 0)], aimAxis="w")),
            (TypeError, lambda: createJointChain([(0, 0, 0), (1, 0, 0)], aimAxis=0)),
            (ValueError, lambda: createJointChain([(0, 0, 0), (1, 0, 0)], aimAxis="x", upAxis="-x")),
            (ValueError, lambda: createJointChain([(0, 0, 0), (1, 0, 0)], up=(1, 0, 0))),
            (ValueError, lambda: createJointChain([(0, 0, 0), (1, 0, 0)], up=(0, 0, 0))),
            (ValueError, lambda: createJointChain([(0, 0, 0), (1, 0, 0)], names=["a"])),
            (TypeError, lambda: createJointChain([(0, 0, 0), (1, 0, 0)], names=["a", 1])),
            (TypeError, lambda: createJointChain([(0, 0, 0), (1, 0, 0)], parent=cmds.createNode("network", name=self.name("n"), skipSelect=True))),
        )
        before = set(cmds.ls(type="joint"))
        for error, call in cases:
            with self.subTest(error=error.__name__):
                self.assertRaises(error, call)
        self.assertEqual(set(cmds.ls(type="joint")), before)
        self.assertTrue(cmds.objExists(transform))


if __name__ == "__main__":
    unittest.main()
