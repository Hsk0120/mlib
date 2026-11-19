"""被写界深度の再計算と距離の取得を検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CameraDepthOfFieldTest(NamespaceCase):
    def test_range_matches_native_and_does_not_change_inputs(self):
        name = cmds.camera(name=self.ns + ":camera")[1]
        camera = mlib.getNode(name)
        cmds.setAttr(name + ".focusDistance", 100)
        cmds.setAttr(name + ".fStop", 8)
        before = [cmds.getAttr(name + "." + attr) for attr in ("focusDistance", "fStop", "focalLength")]
        undo_name = cmds.undoInfo(query=True, undoName=True)
        actual = camera.getDepthOfFieldRange()
        fn = om2.MFnCamera(camera.mpath())
        fn.computeDepthOfField()
        self.assertEqual(actual, (fn.nearFocusDistance, fn.farFocusDistance))
        self.assertEqual([cmds.getAttr(name + "." + attr) for attr in ("focusDistance", "fStop", "focalLength")], before)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
        cmds.currentUnit(linear="m")
        self.assertEqual(camera.getDepthOfFieldRange(), actual)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
