"""ターゲット形状の再生成・接続・Undoと未対応条件の事前拒否を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class BlendShapeRegenerateTest(NamespaceCase):
    @staticmethod
    def delete_if_exists(name):
        if cmds.objExists(name):
            cmds.delete(name)

    def setup_blend(self, full_weight=1.0):
        base = cmds.polyCube(name=self.name("base"), constructionHistory=False)[0]
        target = self.make_target(base, "target", 2)
        blend = mlib.Node(cmds.blendShape(base, name=self.name("blend"))[0])
        blend.addTarget(target, index=3, fullWeight=full_weight)
        return blend, base, target

    def make_target(self, base, text, height):
        target = cmds.duplicate(base, name=self.name(text))[0]
        cmds.move(0, height, 0, target + ".vtx[0]", relative=True)
        return target

    def input_path(self, blend, base=0, item=6000):
        return f"{blend.getName(full=True)}.inputTarget[{base}].inputTargetGroup[3].inputTargetItem[{item}].inputGeomTarget"

    def track_created(self, meshes):
        for mesh in meshes:
            parent = cmds.listRelatives(mesh.getName(full=True), parent=True, fullPath=True)[0]
            self.addCleanup(self.delete_if_exists, parent)

    def test_generate_keeps_selection_and_edit_mode_and_undo(self):
        blend, base, target = self.setup_blend()
        cmds.delete(target)
        blend.targetEdit(3)
        cmds.select(base)
        selected = cmds.ls(selection=True, long=True)
        self.flushUndo()
        meshes = blend.regenerateTarget(3)
        self.track_created(meshes)
        self.assertIsInstance(meshes, mlib.Nodes)
        self.assertEqual(len(meshes), 1)
        mesh = meshes[0]
        self.assertIsInstance(mesh, mlib.Mesh)
        self.assertEqual(cmds.ls(selection=True, long=True), selected)
        self.assertEqual(cmds.getAttr(blend.getName(full=True) + ".inputTarget[0].sculptTargetIndex"), 3)
        self.assertAlmostEqual(cmds.pointPosition(mesh.getName(full=True) + ".vtx[0]", local=True)[1], 1.5)
        self.assertEqual(blend.getPlug(self.input_path(blend).split(".", 1)[1]).getConnections(input=True).getNode(), mesh)
        name = mesh.getName(full=True)
        cmds.undo()
        self.assertFalse(cmds.objExists(name))
        self.assertFalse(cmds.listConnections(self.input_path(blend), source=True, destination=False))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        cmds.redo()
        self.assertTrue(cmds.objExists(name))
        self.assertEqual(cmds.ls(selection=True, long=True), selected)

    def test_existing_shape_returns_same_mesh_without_undo(self):
        blend, _base, target = self.setup_blend()
        existing = mlib.getNode(target).getShape()
        self.flushUndo()
        self.assertEqual(list(blend.regenerateTarget(3)), [existing])
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_inbetween_recreates_its_own_shape(self):
        blend, base, _target = self.setup_blend()
        between = self.make_target(base, "between", 0.75)
        blend.addTarget(between, inBetween=3, fullWeight=0.5)
        cmds.delete(between)
        self.flushUndo()
        meshes = blend.regenerateTarget(3, fullWeight=0.5)
        self.track_created(meshes)
        self.assertAlmostEqual(cmds.pointPosition(meshes[0].getName(full=True) + ".vtx[0]", local=True)[1], 0.25)
        self.assertTrue(cmds.listConnections(self.input_path(blend, item=5500), source=True, destination=False))
        cmds.undo()
        self.assertFalse(cmds.listConnections(self.input_path(blend, item=5500), source=True, destination=False))
        cmds.redo()
        self.assertTrue(cmds.listConnections(self.input_path(blend, item=5500), source=True, destination=False))

    def test_multiple_bases_return_existing_and_generated_in_base_order(self):
        blend, base, target = self.setup_blend()
        second = cmds.polyCube(name=self.name("second"), constructionHistory=False)[0]
        second_target = self.make_target(second, "secondTarget", 4)
        blend.addBaseGeometry(second)
        blend.addTarget(second_target, base=second, index=3)
        cmds.delete(second_target)
        cmds.select(base)
        selected = cmds.ls(selection=True, long=True)
        self.flushUndo()
        meshes = blend.regenerateTarget(3)
        self.track_created([meshes[1]])
        self.assertEqual(meshes[0], mlib.getNode(target).getShape())
        self.assertAlmostEqual(cmds.pointPosition(meshes[1].getName(full=True) + ".vtx[0]", local=True)[1], 3.5)
        self.assertEqual(cmds.ls(selection=True, long=True), selected)
        cmds.undo()
        self.assertTrue(cmds.listConnections(self.input_path(blend), source=True, destination=False))
        self.assertFalse(cmds.listConnections(self.input_path(blend, base=1), source=True, destination=False))
        cmds.redo()
        self.assertTrue(cmds.listConnections(self.input_path(blend, base=1), source=True, destination=False))

    def test_all_bases_are_checked_before_creation(self):
        blend, base, target = self.setup_blend()
        second = cmds.polyCube(name=self.name("second"), constructionHistory=False)[0]
        second_target = self.make_target(second, "secondTarget", 4)
        blend.addBaseGeometry(second)
        blend.addTarget(second_target, base=second, index=3)
        cmds.delete(target, second_target)
        path = self.input_path(blend, base=1)
        cmds.setAttr(path, lock=True)
        try:
            self.flushUndo()
            with self.assertRaises(RuntimeError):
                blend.regenerateTarget(3)
            self.assertFalse(cmds.listConnections(self.input_path(blend), source=True, destination=False))
            self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        finally:
            cmds.setAttr(path, lock=False)
        between = self.make_target(base, "between", 0.75)
        blend.addTarget(between, inBetween=3, fullWeight=0.5, base=base)
        cmds.delete(between)
        with self.assertRaises(ValueError):
            blend.regenerateTarget(3, fullWeight=0.5)
        self.assertFalse(cmds.listConnections(self.input_path(blend, item=5500), source=True, destination=False))

    def test_unsupported_full_weight_is_rejected_without_native_call(self):
        blend, _base, target = self.setup_blend(full_weight=2)
        cmds.delete(target)
        self.flushUndo()
        for full_weight in (2, 0, -1, 1):
            with self.subTest(full_weight=full_weight), self.assertRaises(NotImplementedError):
                blend.regenerateTarget(3, fullWeight=full_weight)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        for value in (True, "bad"):
            with self.assertRaises(TypeError):
                blend.regenerateTarget(3, fullWeight=value)
        with self.assertRaises(ValueError):
            blend.regenerateTarget(3, fullWeight=float("nan"))

    def test_post_deformation_mode_is_rejected(self):
        blend, _base, target = self.setup_blend()
        cmds.delete(target)
        cmds.setAttr(blend.getName(full=True) + ".inputTarget[0].inputTargetGroup[3].postDeformersMode", 1)
        self.flushUndo()
        with self.assertRaises(NotImplementedError):
            blend.regenerateTarget(3)
        self.assertFalse(cmds.listConnections(self.input_path(blend), source=True, destination=False))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_target_missing_from_one_base_is_rejected(self):
        blend, _base, target = self.setup_blend()
        second = cmds.polyCube(name=self.name("second"), constructionHistory=False)[0]
        blend.addBaseGeometry(second)
        cmds.delete(target)
        self.flushUndo()
        with self.assertRaises(ValueError):
            blend.regenerateTarget(3)
        self.assertFalse(cmds.listConnections(self.input_path(blend), source=True, destination=False))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
