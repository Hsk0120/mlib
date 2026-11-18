"""フィルムゲートの距離・単位・pan/zoomを検証する。"""

import math
import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CameraFilmFrustumTest(NamespaceCase):
    def test_distance_units_and_offsets(self):
        _, shape = cmds.camera(name=self.name("camera"))
        camera = mlib.getNode(shape)
        cmds.setAttr(shape + ".horizontalFilmOffset", 0.4)
        cmds.setAttr(shape + ".verticalFilmOffset", -0.1)
        cmds.currentUnit(linear="cm")
        baseline = camera.getFilmFrustum(10)
        self.assertAlmostEqual(baseline[0], 20 * math.tan(camera.mfn().horizontalFieldOfView() / 2))
        self.assertSequenceAlmostEqual(baseline[2:], [0.4, -0.1])
        cmds.currentUnit(linear="m")
        self.assertSequenceAlmostEqual(camera.getFilmFrustum(10), baseline)
        twice = camera.getFilmFrustum(20)
        self.assertSequenceAlmostEqual(twice[:2], [v * 2 for v in baseline[:2]])
        self.assertSequenceAlmostEqual(twice[2:], baseline[2:])
        cmds.setAttr(shape + ".panZoomEnabled", True)
        cmds.setAttr(shape + ".horizontalPan", 0.2)
        cmds.setAttr(shape + ".zoom", 0.5)
        self.flushUndo()
        zoomed = camera.getFilmFrustum(10, applyPanZoom=True)
        self.assertSequenceAlmostEqual(zoomed, camera.mfn().getFilmFrustum(10, True))
        self.assertSequenceAlmostEqual(zoomed[:2], [v * 0.5 for v in baseline[:2]])
        self.assertAlmostEqual(zoomed[2], 0.6)
        self.assertUndoEmpty()

    def test_ortho_and_invalid_input(self):
        _, shape = cmds.camera(name=self.name("camera"), orthographic=True)
        camera = mlib.getNode(shape)
        self.assertEqual(camera.getFilmFrustum(10), camera.getFilmFrustum(20))
        for distance in (0, -1, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                camera.getFilmFrustum(distance)
        for distance in (None, "10", True):
            with self.assertRaises(TypeError):
                camera.getFilmFrustum(distance)
        with self.assertRaises(TypeError):
            camera.getFilmFrustum(10, applyPanZoom=1)
        cmds.delete(shape)
        with self.assertRaises(RuntimeError):
            camera.getFilmFrustum(10)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
