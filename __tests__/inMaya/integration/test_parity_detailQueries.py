"""ノード・Plug・形状の詳細照会をMaya標準と比較する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class DetailQueryTest(NamespaceCase):
    def test_plug_and_dag(self):
        node = mlib.getNode(cmds.createNode("transform", name=self.ns + ":node"))
        other = mlib.getNode(cmds.createNode("transform", name=self.ns + ":other"))
        node.getPlug("tx").connect(other.getPlug("tx"))
        plug = other.getPlug("translate")
        self.assertEqual(plug.getNumConnectedChildren(), 1)
        self.assertEqual(plug.isIndexMatters(), om2.MFnAttribute(plug.mplug().attribute()).indexMatters)
        if hasattr(om2.MPlug, "isExactlyEqual"):
            self.assertTrue(plug.isExactlyEqual(plug))
            self.assertFalse(plug.isExactlyEqual(node.getPlug("translate")))
        else:
            with self.assertRaises(NotImplementedError):
                plug.isExactlyEqual(plug)
        with self.assertRaises(TypeError):
            plug.isExactlyEqual(None)
        self.assertEqual(node.isInModel(), node.mfn().inModel)
        self.assertFalse(node.isInUnderworld())
        self.assertEqual(node.affectsAnimation(), om2.MFnDependencyNode(node.mnode()).affectsAnimation())

    def test_uncreated_element_is_not_existing(self):
        node = mlib.getNode(cmds.createNode("plusMinusAverage", name=self.ns + ":sum"))
        element = node.getPlug("input3D")[13]
        self.assertTrue(element.isValid())
        self.assertFalse(element.isExisting())
        self.assertFalse(element.getChildren()[0].isExisting())
        self.assertEqual(node.getPlug("input3D").getIndices(), [])
        element.set((1, 2, 3))
        self.assertTrue(element.isExisting())
        self.assertTrue(element.getChildren()[0].isExisting())

    def test_container_connections(self):
        node = mlib.getNode(cmds.createNode("transform", name=self.ns + ":member"))
        external = mlib.getNode(cmds.createNode("transform", name=self.ns + ":external"))
        box = mlib.getNode(cmds.container(name=self.ns + ":box", addNode=[node.getFullName()]))
        node.getPlug("tx").connect(external.getPlug("tx"))
        self.assertEqual(node.getContainer(), box)
        self.assertIsNone(external.getContainer())
        self.assertEqual(list(box.getExternalConnections()), [external.getPlug("tx")])

    def test_camera(self):
        camera = mlib.getNode(cmds.camera(name=self.ns + ":camera")[1])
        second = mlib.getNode(cmds.camera(name=self.ns + ":second")[1])
        fn = camera.mfn()
        self.assertAlmostEqual(camera.getAspectRatio(), fn.aspectRatio())
        limits = camera.getParameterLimits()
        self.assertEqual(limits["aspectRatio"], tuple(fn.getAspectRatioLimits()))
        for lo, hi in limits.values():
            self.assertLess(lo, hi)
        self.assertEqual(tuple(camera.getCenterOfInterestPoint(ws=False)), tuple(fn.centerOfInterestPoint(om2.MSpace.kObject))[:3])
        self.assertEqual(camera.hasSamePerspective(second), fn.hasSamePerspective(second.mpath()))
        with self.assertRaises(TypeError):
            camera.hasSamePerspective(None)

    def test_surface_point(self):
        transform = mlib.getNode(cmds.nurbsPlane(name=self.ns + ":surface", constructionHistory=False)[0])
        surface = transform.getShape()
        self.assertTrue(surface.isPointOnSurface((0, 0, 0)))
        self.assertFalse(surface.isPointOnSurface((0, 0, 5)))
        cmds.setAttr(transform.getFullName() + ".translateZ", 10)
        self.assertTrue(surface.isPointOnSurface((0, 0, 10), ws=True))
        self.assertFalse(surface.isPointOnSurface((0, 0, 10)))
        with self.assertRaises(ValueError):
            surface.isPointOnSurface((0, 0, 0), tolerance=-1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
