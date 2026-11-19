"""新しい編集入口の更新前拒否と版別の照会を検証する。"""

import sys
import unittest

import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class GuardTest(NamespaceCase):
    def test_hik_name(self):
        joint = mlib.createNode("joint", name=self.name("joint"))
        if hasattr(oma2, "MFnIkJoint"):
            try:
                expected = oma2.MFnIkJoint(joint.mpath()).hikJointName()
            except RuntimeError:
                with self.assertRaises(RuntimeError):
                    joint.getHikJointName()
            else:
                self.assertEqual(joint.getHikJointName(), expected)
        else:
            with self.assertRaises(NotImplementedError):
                joint.getHikJointName()

    def test_swap_guards(self):
        a = mlib.createNode("network", name=self.name("a"))
        b = mlib.createNode("network", name=self.name("b"))
        with self.assertRaises(ValueError):
            a.swapConnections(a)
        b.addAttr("extra", attributeType="double")
        cmds.flushUndo()
        with self.assertRaises(NotImplementedError):
            a.swapConnections(b)
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))
        self.assertTrue(b.hasAttr("extra"))

    def test_ik_rejects_rp(self):
        cmds.select(clear=True)
        a = cmds.joint(name=self.name("a"))
        b = cmds.joint(name=self.name("b"), position=(2, 1, 0))
        end = cmds.joint(name=self.name("end"), position=(4, 0, 0))
        handle = mlib.getNode(cmds.ikHandle(startJoint=a, endEffector=end, solver="ikRPsolver")[0])
        before = handle.getPlug("startJoint").getSource()
        cmds.flushUndo()
        with self.assertRaises(NotImplementedError):
            handle.setChain(b, end)
        self.assertEqual(handle.getPlug("startJoint").getSource(), before)
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))

    def test_surface_rejects_uv_and_lock(self):
        surface = mlib.getNode(cmds.nurbsPlane(name=self.name("surface"), constructionHistory=False)[0]).getShape()
        before = surface.getKnots()
        cmds.lockNode(surface.getFullName(), lock=True)
        cmds.flushUndo()
        with self.assertRaises(RuntimeError):
            surface.setKnots(*before)
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))
        cmds.lockNode(surface.getFullName(), lock=False)
        fn = surface.mfn()
        fn.setUVs([0.0, 1.0, 1.0, 0.0], [0.0, 0.0, 1.0, 1.0])
        fn.assignUVs([4], [0, 1, 2, 3])
        cmds.flushUndo()
        with self.assertRaises(NotImplementedError):
            surface.setKnots(*before)
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))
        self.assertEqual(surface.getKnots(), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
