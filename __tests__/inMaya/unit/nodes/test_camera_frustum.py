"""専門ノードの照会・更新をMaya標準APIと照合する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
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
        self.assertSequenceAlmostEqual(camera.getFrustum(1.7, kind="rendering"), fn.getRenderingFrustum(1.7))
        for overscan in (False, True):
            for squeeze in (False, True):
                for pan in (False, True):
                    self.assertSequenceAlmostEqual(
                        camera.getFrustum(1.7, applyOverscan=overscan, applySqueeze=squeeze, applyPanZoom=pan),
                        fn.getViewingFrustum(1.7, overscan, squeeze, pan),
                    )
        self.assertSequenceAlmostEqual(camera.getFieldOfView(port=(1920, 1080), unit="rad"), fn.getPortFieldOfView(1920, 1080))
        raw = fn.postProjectionMatrix()
        self.assertSequenceAlmostEqual(list(camera.getProjectionMatrix(kind="post")), [raw.getElement(r, c) for r in range(4) for c in range(4)])
        self.assertUndoEmpty()
        with self.assertRaises(ValueError):
            camera.getFrustum(0)
        with self.assertRaises(TypeError):
            camera.getFieldOfView(port=(True, 100))
        with self.assertRaises(TypeError):
            camera.getFrustum(1, applyOverscan=1)

    def test_merged_arguments(self):
        """kind・post・port の指定と、同時に指定できない組み合わせ・名前違いの例外型。"""
        _, shape = cmds.camera(name=self.name("camera"))
        camera = mlib.Node(shape)
        fn = camera.mfn()
        self.flushUndo()
        self.assertSequenceAlmostEqual(camera.getFrustum(1.7, kind="viewing"), camera.getFrustum(1.7))
        self.assertSequenceAlmostEqual(camera.getFrustum(1.7, kind="rendering", applyOverscan=False), fn.getRenderingFrustum(1.7))
        for flag in ("applyOverscan", "applySqueeze", "applyPanZoom"):
            with self.subTest(flag=flag):
                with self.assertRaises(TypeError):
                    camera.getFrustum(1.7, kind="rendering", **{flag: True})
        with self.assertRaises(ValueError):
            camera.getFrustum(1.7, kind="film")
        with self.assertRaises(TypeError):
            camera.getFrustum(1.7, kind=None)
        with self.assertRaises(TypeError):
            camera.getFrustum(1.7, "rendering")
        raw = fn.projectionMatrix()
        self.assertSequenceAlmostEqual(list(camera.getProjectionMatrix(kind="projection")), [raw.getElement(r, c) for r in range(4) for c in range(4)])
        self.assertIsInstance(camera.getProjectionMatrix(kind="post"), mlib.Matrix)
        with self.assertRaises(TypeError):
            camera.getProjectionMatrix(kind=1)
        with self.assertRaises(ValueError):
            camera.getProjectionMatrix(kind="pre")
        with self.assertRaises(TypeError):
            camera.getProjectionMatrix("post")
        radians = fn.getPortFieldOfView(640, 480)
        self.assertSequenceAlmostEqual(camera.getFieldOfView(port=(640, 480)), [om2.MAngle(value).asDegrees() for value in radians], places=6)
        self.assertSequenceAlmostEqual(camera.getFieldOfView(port=[640, 480], unit="rad"), radians)
        for port, error in (
            ((1.5, 100), TypeError),
            ((100, "a"), TypeError),
            (100, TypeError),
            ((100,), TypeError),
            ((100, 100, 100), TypeError),
            ("ab", TypeError),
            ((0, 100), ValueError),
            ((100, -1), ValueError),
        ):
            with self.subTest(port=port):
                with self.assertRaises(error):
                    camera.getFieldOfView(port=port)
        with self.assertRaises(TypeError):
            camera.getFieldOfView((640, 480))
        self.assertUndoEmpty()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
