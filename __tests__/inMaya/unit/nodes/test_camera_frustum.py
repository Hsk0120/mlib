"""専門ノードの照会・更新をMaya標準APIと照合する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CameraFrustumTest(NamespaceCase):
    def test_projection_queries_match_openmaya(self):
        _, shape = cmds.camera(name=self.name("camera"))
        camera = mlib.Node(shape)
        cmds.setAttr(shape + ".overscan", 1.5)
        cmds.setAttr(shape + ".filmRollValue", 20)
        cmds.setAttr(shape + ".lensSqueezeRatio", 1.2)
        cmds.setAttr(shape + ".panZoomEnabled", True)
        cmds.setAttr(shape + ".horizontalPan", 0.1)
        cmds.setAttr(shape + ".zoom", 1.3)
        fn = camera.mfn()
        self.flushUndo()
        self.assertSequenceAlmostEqual(camera.getRenderingFrustum(1.7), fn.getRenderingFrustum(1.7))
        for overscan in (False, True):
            for squeeze in (False, True):
                for pan in (False, True):
                    self.assertSequenceAlmostEqual(
                        camera.getViewingFrustum(1.7, applyOverscan=overscan, applySqueeze=squeeze, applyPanZoom=pan),
                        fn.getViewingFrustum(1.7, overscan, squeeze, pan),
                    )
        self.assertSequenceAlmostEqual(camera.getPortFieldOfView(1920, 1080, unit="rad"), fn.getPortFieldOfView(1920, 1080))
        raw = fn.postProjectionMatrix()
        self.assertSequenceAlmostEqual(list(camera.getPostProjectionMatrix()), [raw.getElement(r, c) for r in range(4) for c in range(4)])
        self.assertUndoEmpty()
        with self.assertRaises(ValueError):
            camera.getViewingFrustum(0)
        with self.assertRaises(TypeError):
            camera.getPortFieldOfView(True, 100)
        with self.assertRaises(TypeError):
            camera.getViewingFrustum(1, applyOverscan=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
