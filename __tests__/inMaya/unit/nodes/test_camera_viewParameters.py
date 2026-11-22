"""Maya標準の照会と、既存の取得対象との違いを検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CameraViewParametersTest(NamespaceCase):
    def test_flags_and_aspect_match_native_without_edit(self):
        _transform, name = cmds.camera(name=self.ns + ":camera")
        camera = mlib.getNode(name)
        cmds.setAttr(name + ".overscan", 1.5)
        cmds.setAttr(name + ".lensSqueezeRatio", 1.3)
        cmds.setAttr(name + ".panZoomEnabled", True)
        cmds.setAttr(name + ".horizontalPan", 0.1)
        fn = om2.MFnCamera(camera.mpath())
        undo_name = cmds.undoInfo(query=True, undoName=True)
        for aspect in (1.0, 1.777):
            for overscan in (False, True):
                for squeeze in (False, True):
                    for pan in (False, True):
                        expected = fn.getViewParameters(aspect, overscan, squeeze, pan)
                        actual = camera.getViewParameters(aspect, applyOverscan=overscan, applySqueeze=squeeze, applyPanZoom=pan)
                        self.assertEqual(actual, tuple(expected))
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
        for value in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                camera.getViewParameters(value)
        with self.assertRaises(TypeError):
            camera.getViewParameters(1, applyPanZoom=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
