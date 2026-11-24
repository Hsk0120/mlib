"""明示UV消去の形状・接続保持とUndo、更新前の拒否を検証する。"""

import sys
import tempfile
import unittest
from pathlib import Path

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class SurfaceClearUVDataTest(NamespaceCase):
    def make_surface(self, sphere=False):
        command = cmds.sphere if sphere else cmds.nurbsPlane
        shape = mlib.getNode(command(name=self.name("surface"), ch=False)[0]).getShape()
        patches = shape.mfn().numSpansInU * shape.mfn().numSpansInV
        shape.setUVData([(0, 0), (1, 0), (1, 1), (0, 1)], [4] * patches, [0, 1, 2, 3] * patches, fast=True)
        return shape

    def geometry(self, shape):
        fn = shape.mfn()
        return (
            cmds.ls(shape.getName(full=True), uuid=True),
            [tuple(p) for p in fn.cvPositions()],
            shape.getKnots(),
            fn.formInU,
            fn.formInV,
            fn.degreeInU,
            fn.degreeInV,
        )

    def test_clear_preserves_geometry_connection_and_undo_redo(self):
        for sphere in (False, True):
            with self.subTest(sphere=sphere):
                shape = self.make_surface(sphere)
                cmds.move(2, 3, 4, shape.getName(full=True) + ".cv[0][0]", absolute=True, objectSpace=True)
                sink = cmds.createNode("pointOnSurfaceInfo", name=self.name("sink"))
                cmds.connectAttr(shape.getName(full=True) + ".worldSpace[0]", sink + ".inputSurface")
                cmds.setAttr(sink + ".parameterU", 0.3)
                cmds.setAttr(sink + ".parameterV", 0.4)
                before = self.geometry(shape)
                uv_data = shape.getUVData()
                position = cmds.getAttr(sink + ".position")
                normal = cmds.getAttr(sink + ".normal")
                self.flushUndo()
                self.assertIsNone(shape.clearUVData())
                self.assertEqual(self.geometry(shape), before)
                self.assertEqual(cmds.getAttr(sink + ".position"), position)
                self.assertEqual(cmds.getAttr(sink + ".normal"), normal)
                self.assertTrue(cmds.isConnected(shape.getName(full=True) + ".worldSpace[0]", sink + ".inputSurface"))
                with self.assertRaises(RuntimeError):
                    shape.getUVData()
                cmds.undo()
                self.assertEqual(shape.getUVData(), uv_data)
                self.assertEqual(self.geometry(shape), before)
                cmds.redo()
                with self.assertRaises(RuntimeError):
                    shape.getUVData()
                self.assertEqual(self.geometry(shape), before)

    def test_no_uv_is_noop_and_can_set_new_smaller_uv_table(self):
        shape = self.make_surface()
        shape.clearUVData()
        self.flushUndo()
        self.assertIsNone(shape.clearUVData())
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        shape.setUVData([(0.25, 0.75)], [4], [0, 0, 0, 0], fast=True)
        self.assertEqual(shape.getUVData(), ([(0.25, 0.75)], [4], [0, 0, 0, 0]))

    def test_locked_and_connected_data_rejected_before_change(self):
        shape = self.make_surface()
        before = (self.geometry(shape), shape.getUVData())
        for attr in ("create", "controlPoints[0].xValue", "uvSet[0].uvSetPoints[0].uvSetPointsU"):
            with self.subTest(attr=attr):
                cmds.setAttr(shape.getName(full=True) + "." + attr, lock=True)
                with self.assertRaises(RuntimeError):
                    shape.clearUVData()
                cmds.setAttr(shape.getName(full=True) + "." + attr, lock=False)
                self.assertEqual((self.geometry(shape), shape.getUVData()), before)
        driver = cmds.createNode("addDoubleLinear", name=self.name("driver"))
        cmds.connectAttr(driver + ".output", shape.getName(full=True) + ".controlPoints[0].xValue")
        with self.assertRaises(RuntimeError):
            shape.clearUVData()
        self.assertEqual(shape.getUVData(), before[1])

    def test_instance_tags_multiple_sets_and_history_rejected(self):
        shape = self.make_surface()
        cmds.instance(shape.getName(full=True), name=self.name("instance"))
        with self.assertRaises(NotImplementedError):
            shape.clearUVData()
        tagged = self.make_surface()
        cmds.setAttr(tagged.getName(full=True) + ".componentTags[0].componentTagName", "keep", type="string")
        with self.assertRaises(NotImplementedError):
            tagged.clearUVData()
        multiple = self.make_surface()
        cmds.setAttr(multiple.getName(full=True) + ".uvSet[1].uvSetName", "second", type="string")
        with self.assertRaises(NotImplementedError):
            multiple.clearUVData()
        history = mlib.getNode(cmds.nurbsPlane(name=self.name("history"), ch=True)[0]).getShape()
        with self.assertRaises(NotImplementedError):
            history.clearUVData()

    def test_trim_rejected_without_losing_boundary(self):
        shape = self.make_surface()
        boundary = cmds.curveOnSurface(shape.getName(full=True), degree=1, positionUV=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)])
        cmds.trim(shape.getName(full=True), boundary, ch=False, replaceOriginal=True, locatorU=0.05, locatorV=0.05, selected=0)
        before = shape.getTrimBoundaryInfo()
        self.assertTrue(shape.mfn().isTrimmedSurface)
        with self.assertRaises(NotImplementedError):
            shape.clearUVData()
        self.assertEqual(shape.getTrimBoundaryInfo(), before)

    def test_saved_clear_and_reference_rejection(self):
        for file_type, suffix in (("mayaAscii", ".ma"), ("mayaBinary", ".mb")):
            with self.subTest(file_type=file_type), tempfile.TemporaryDirectory() as directory:
                shape = self.make_surface()
                uv_data = shape.getUVData()
                path = str(Path(directory) / ("surface" + suffix))
                cmds.select(shape.getParent().getName(full=True), replace=True)
                cmds.file(path, force=True, exportSelected=True, type=file_type)
                namespace = self.name("reference")
                nodes = cmds.file(path, reference=True, namespace=namespace, returnNewNodes=True)
                referenced = mlib.getNode(next(node for node in nodes if cmds.nodeType(node) == "nurbsSurface"))
                reference_node = cmds.referenceQuery(referenced.getName(full=True), referenceNode=True)
                try:
                    with self.assertRaises(NotImplementedError):
                        referenced.clearUVData()
                    self.assertEqual(referenced.getUVData(), uv_data)
                finally:
                    cmds.file(removeReference=True, referenceNode=reference_node)
                shape.clearUVData()
                cmds.select(shape.getParent().getName(full=True), replace=True)
                cmds.file(path, force=True, exportSelected=True, type=file_type)
                nodes = cmds.file(path, reference=True, namespace=namespace, returnNewNodes=True)
                referenced = mlib.getNode(next(node for node in nodes if cmds.nodeType(node) == "nurbsSurface"))
                reference_node = cmds.referenceQuery(referenced.getName(full=True), referenceNode=True)
                try:
                    with self.assertRaises(RuntimeError):
                        referenced.getUVData()
                    self.assertEqual(referenced.getKnots(), shape.getKnots())
                    self.assertEqual([tuple(p) for p in referenced.mfn().cvPositions()], [tuple(p) for p in shape.mfn().cvPositions()])
                finally:
                    cmds.file(removeReference=True, referenceNode=reference_node)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
