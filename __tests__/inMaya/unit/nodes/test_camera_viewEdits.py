"""カメラの画角とフィルム開口の編集を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CameraEditTest(NamespaceCase):
    def camera(self):
        return mlib.getNode(cmds.camera(name=self.name("camera"))[1])

    def test_world_view(self):
        for linear in ("cm", "m"):
            cmds.currentUnit(linear=linear)
            camera = self.camera()
            group = cmds.group(empty=True, name=self.name("parent"))
            cmds.setAttr(group + ".translate", 2, 3, 4)
            cmds.setAttr(group + ".rotate", 12, 23, 34)
            cmds.parent(camera.getParent().getFullName(), group)
            camera.setUpDirection((1, 0, 0))
            self.assertAlmostEqual(camera.getUpDirection() * camera.getViewDirection(), 0, places=5)
        cmds.currentUnit(linear="cm")

    def test_field_of_view_undo(self):
        camera = self.camera()
        for vertical in (False, True):
            before = camera.getFieldOfView()
            cmds.flushUndo()
            camera.setFieldOfView(40, vertical=vertical)
            after = camera.getFieldOfView()
            self.assertAlmostEqual(after[int(vertical)], 40)
            cmds.undo()
            for a, b in zip(camera.getFieldOfView(), before):
                self.assertAlmostEqual(a, b)
            cmds.redo()
            for a, b in zip(camera.getFieldOfView(), after):
                self.assertAlmostEqual(a, b)
        camera.setFieldOfView(1, unit="rad")
        self.assertAlmostEqual(camera.getFieldOfView(unit="rad")[0], 1)

    def test_aspect_ratio_undo(self):
        camera = self.camera()
        before = camera.getAspectRatio()
        cmds.flushUndo()
        camera.setAspectRatio(2)
        self.assertAlmostEqual(camera.getAspectRatio(), 2)
        cmds.undo()
        self.assertAlmostEqual(camera.getAspectRatio(), before)
        cmds.redo()
        self.assertAlmostEqual(camera.getAspectRatio(), 2)

    def test_focus_distance_undo(self):
        camera = self.camera()
        for method, index, value in [(camera.setNearFocusDistance, 0, 3), (camera.setFarFocusDistance, 1, 9)]:
            before = camera.getDepthOfFieldRange()
            cmds.flushUndo()
            method(value)
            after = camera.getDepthOfFieldRange()
            self.assertAlmostEqual(after[index], value)
            cmds.undo()
            for a, b in zip(camera.getDepthOfFieldRange(), before):
                self.assertAlmostEqual(a, b)
            cmds.redo()
            for a, b in zip(camera.getDepthOfFieldRange(), after):
                self.assertAlmostEqual(a, b)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
