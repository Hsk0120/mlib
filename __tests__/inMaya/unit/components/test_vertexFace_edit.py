"""``mlib.components.vertexFace`` の書き込み(法線・色)と接線のテスト。

- ``setNormal`` の値・ロックの切り替え・ws・fast・check を、polyNormalPerVertex の照会と突き合わせ、Undo1回で戻ることを確かめる。
- ``setColor``・``removeColor`` を polyColorPerVertex の照会と突き合わせ、Undo・fast を確かめる。
- ``getTangent`` を ``MFnMesh.getFaceVertexTangent``・``getFaceVertexBinormal`` と突き合わせる。
- 複数形 ``VertexFaces`` から転送した書き込みが、要素ごとの戻り値のリストを返し、Undo1回で戻ること。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import VertexFace, VertexFaces
from mlib.maths import Vector


class _Case(NamespaceCase):
    """履歴なしの立方体を作る準備。"""

    PREFIX = "mlibVertexFaceEdit_"

    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        self.mesh = mlib.getNode(cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0])
        self.item = VertexFace(self.mesh, (2, 0))
        self.label = self.item.getName(full=True)

    def cmds_normal(self):
        """polyNormalPerVertexで照会した法線と、ロックの状態を返す。"""
        normal = cmds.polyNormalPerVertex(self.label, query=True, xyz=True)
        frozen = cmds.polyNormalPerVertex(self.label, query=True, freezeNormal=True)[0]
        return normal, frozen

    def assertVectorAlmostEqual(self, actual, expected, places=5):
        self.assertSequenceAlmostEqual(list(actual), list(expected), places=places)


class SetNormalTest(_Case):
    """VertexFace.setNormal。"""

    def test_normal_matches_cmds_and_undo(self):
        """法線を正規化して書いてロックし、Undo1回で元の法線・ロックなしへ戻り、redoでまた変わる。"""
        before = self.item.getNormal()
        self.flushUndo()
        self.assertIsNone(self.item.setNormal((1.0, 1.0, 0.0)))
        expected = (math.sqrt(0.5), math.sqrt(0.5), 0.0)

        def after():
            normal, frozen = self.cmds_normal()
            self.assertVectorAlmostEqual(normal, expected)
            self.assertTrue(frozen)
            self.assertVectorAlmostEqual(self.item.getNormal(), expected)

        def original():
            self.assertVectorAlmostEqual(self.item.getNormal(), before)
            self.assertFalse(self.cmds_normal()[1])

        self.assertUndoesInOneStep(original, after)
        cmds.redo()
        after()

    def test_lock_toggle_without_value(self):
        """normalを省いたlocked=Falseはロックを外して計算し直し、locked=Trueは今の値でロックする。"""
        before = self.item.getNormal()
        self.item.setNormal((0.0, 1.0, 0.0))
        self.flushUndo()
        self.item.setNormal(locked=False)
        self.assertFalse(self.cmds_normal()[1])
        self.assertVectorAlmostEqual(self.item.getNormal(), before)
        cmds.undo()
        self.assertTrue(self.cmds_normal()[1])
        cmds.redo()
        self.item.setNormal(locked=True)
        normal, frozen = self.cmds_normal()
        self.assertTrue(frozen)
        self.assertVectorAlmostEqual(normal, before)

    def test_world_space_and_short_name(self):
        """ws=TrueとworldSpace=Trueは同じで、Transformの回転を戻したオブジェクト空間の値を書く。"""
        cmds.setAttr(self.cube + ".rotateZ", 90)
        for flags in ({"ws": True}, {"worldSpace": True}):
            with self.subTest(flags=flags):
                self.item.setNormal((0.0, 1.0, 0.0), **flags)
                self.assertVectorAlmostEqual(self.item.getNormal(), (1.0, 0.0, 0.0))
                self.assertVectorAlmostEqual(self.item.getNormal(ws=True), (0.0, 1.0, 0.0))
                self.assertVectorAlmostEqual(self.cmds_normal()[0], (1.0, 0.0, 0.0))
                self.item.setNormal(locked=False)

    def test_fast_is_not_recorded(self):
        """fast=TrueはUndoに載らず、polyNormalPerVertexの照会でも同じ値になる。"""
        self.flushUndo()
        self.item.setNormal((0.0, 0.0, 1.0), fast=True)
        self.assertUndoEmpty()
        self.assertVectorAlmostEqual(self.cmds_normal()[0], (0.0, 0.0, 1.0))
        self.assertVectorAlmostEqual(self.item.getNormal(), (0.0, 0.0, 1.0))

    def test_check_rejects_non_finite(self):
        """check=TrueはNaNを書く前にValueErrorにし、法線を変えない。"""
        before = self.item.getNormal()
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(ValueError):
                    self.item.setNormal((float("nan"), 0.0, 0.0), fast=fast, check=True)
                self.assertVectorAlmostEqual(self.item.getNormal(), before)


class ColorTest(_Case):
    """VertexFace.setColor・removeColor。"""

    def test_set_and_remove_match_cmds_and_undo(self):
        """setColorはpolyColorPerVertexと同じ色になり、removeColorはNoneへ戻す。どちらもUndo1回で戻る。"""
        self.assertIsNone(self.item.getColor())
        self.flushUndo()
        self.assertIsNone(self.item.setColor((1.0, 0.5, 0.0)))
        self.assertUndoesInOneStep(
            lambda: self.assertIsNone(self.item.getColor()),
            lambda: self.assertVectorAlmostEqual(cmds.polyColorPerVertex(self.label, query=True, rgb=True), (1.0, 0.5, 0.0)),
        )
        cmds.redo()
        self.assertVectorAlmostEqual(self.item.getColor(), (1.0, 0.5, 0.0, 1.0))
        self.flushUndo()
        self.assertIsNone(self.item.removeColor())
        self.assertUndoesInOneStep(
            lambda: self.assertVectorAlmostEqual(self.item.getColor(), (1.0, 0.5, 0.0, 1.0)), lambda: self.assertIsNone(self.item.getColor())
        )

    def test_fast_is_not_recorded(self):
        """fast=TrueのsetColor・removeColorはUndoに載らない。RGBAのAも書く。"""
        self.flushUndo()
        self.item.setColor((0.0, 0.0, 1.0, 0.5), fast=True)
        self.assertUndoEmpty()
        self.assertVectorAlmostEqual(self.item.getColor(), (0.0, 0.0, 1.0, 0.5))
        self.assertAlmostEqual(cmds.polyColorPerVertex(self.label, query=True, alpha=True)[0], 0.5, places=5)
        self.item.removeColor(fast=True)
        self.assertUndoEmpty()
        self.assertIsNone(self.item.getColor())

    def test_collection_forwarding(self):
        """VertexFacesのsetColorは要素ごとのNoneのリストを返し、Undo1回で全部戻る。"""
        items = VertexFaces(self.mesh, [(2, 0), (3, 0)])
        self.flushUndo()
        self.assertEqual(items.setColor((0.0, 1.0, 0.0)), [None, None])
        self.assertUndoesInOneStep(
            lambda: self.assertEqual(items.getColor(), [None, None]),
            lambda: self.assertEqual([tuple(round(v, 5) for v in color) for color in items.getColor()], [(0.0, 1.0, 0.0, 1.0)] * 2),
        )


class TangentTest(_Case):
    """VertexFace.getTangent。"""

    def test_tangent_and_binormal_match_om2(self):
        """接線・従法線はMFnMeshの同じ照会と一致し、wsはTransformの回転を含む。"""
        cmds.setAttr(self.cube + ".rotateY", 30)
        vertex, face = self.item.getMultiIndex()
        path = om2.MSelectionList().add(self.mesh.getName(full=True)).getDagPath(0)
        fn = om2.MFnMesh(path)
        for space, flags in ((om2.MSpace.kObject, {}), (om2.MSpace.kWorld, {"ws": True}), (om2.MSpace.kWorld, {"worldSpace": True})):
            with self.subTest(flags=flags):
                tangent = self.item.getTangent(**flags)
                self.assertIs(type(tangent), Vector)
                self.assertVectorAlmostEqual(tangent, fn.getFaceVertexTangent(face, vertex, space).normal())
                binormal = self.item.getTangent(binormal=True, **flags)
                self.assertVectorAlmostEqual(binormal, fn.getFaceVertexBinormal(face, vertex, space).normal())
        with self.assertRaises(TypeError):
            self.item.getTangent(binormal=1)
        with self.assertRaises(TypeError):
            self.item.getTangent(True, ws=True)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
