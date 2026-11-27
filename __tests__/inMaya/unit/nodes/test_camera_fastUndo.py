"""``mlib.nodes.camera`` の fast 専用の視点の編集が、Undo に載らないことを cmds と突き合わせて確かめる。

setView・copyViewFrom・setPoint は fast=True 専用。呼んだ後の Undo キューが空で、cmds.undo() でも値が戻らない。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class CameraFastUndoTest(NamespaceCase):
    """視点の編集の後で Undo しても、カメラの値は編集後のまま。"""

    PREFIX = "mlibSpecCameraFastUndo_"

    def camera(self, text="camera"):
        return mlib.getNode(cmds.camera(name=self.name(text))[1])

    def world_translation(self, camera):
        return cmds.xform(camera.getParent().getName(full=True), query=True, worldSpace=True, translation=True)

    def assertUndoKeeps(self, read):
        """Undo キューが空で、cmds.undo() の後も read() の値が変わらないことを確かめる。

        キューが空のままでは cmds.undo() が例外になるので、別のノードへの setAttr を1つ積んでから Undo する。
        """
        self.assertUndoEmpty()
        after = read()
        marker = self.make("transform", "marker#")
        cmds.setAttr(marker + ".translateX", 1)
        cmds.undo()
        self.assertEqual(cmds.getAttr(marker + ".translateX"), 0)
        self.assertSequenceAlmostEqual(read(), after, places=6)
        self.flushUndo()

    def test_set_view_is_not_undone(self):
        """setView(fast=True) は視点と画角を書き、Undo に載らない。"""
        camera = self.camera()
        name = camera.getName(full=True)
        self.flushUndo()
        camera.setView((1, 2, 3), (0, 0, -1), (0, 1, 0), 50, 1.5, fast=True)
        self.assertSequenceAlmostEqual(self.world_translation(camera), (1, 2, 3), places=6)

        def read():
            return [*self.world_translation(camera), cmds.camera(name, query=True, horizontalFieldOfView=True)]

        self.assertAlmostEqual(read()[3], 50, places=4)
        self.assertUndoKeeps(read)

    def test_copy_view_from_is_not_undone(self):
        """copyViewFrom(fast=True) は別のカメラの視点を写し、Undo に載らない。"""
        source = self.camera("source")
        cmds.xform(source.getParent().getName(full=True), worldSpace=True, translation=(4, 5, 6))
        target = self.camera("target")
        self.flushUndo()
        target.copyViewFrom(source, fast=True)
        self.assertSequenceAlmostEqual(self.world_translation(target), (4, 5, 6), places=6)
        self.assertUndoKeeps(lambda: self.world_translation(target))

    def test_set_point_is_not_undone(self):
        """setPoint(fast=True) は視点を動かし、Undo に載らない。注視点の変更も同じ。"""
        camera = self.camera()
        self.flushUndo()
        camera.setPoint((3, 4, 5), fast=True, worldSpace=True)
        self.assertSequenceAlmostEqual(self.world_translation(camera), (3, 4, 5), places=6)
        self.assertUndoKeeps(lambda: self.world_translation(camera))
        camera.setPoint((0, 0, -10), kind="centerOfInterest", fast=True, worldSpace=True)
        self.assertUndoKeeps(lambda: list(camera.getPoint(kind="centerOfInterest", worldSpace=True)))
        self.assertSequenceAlmostEqual(camera.getPoint(kind="centerOfInterest", worldSpace=True), (0, 0, -10), places=5)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
