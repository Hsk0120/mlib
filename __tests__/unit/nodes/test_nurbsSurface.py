"""``mlib.nodes.nurbsSurface`` のテスト。

- 名前空間・選択・matchTransform の通常経路と、om2 へ置き換えた読み取りを cmds と突き合わせる。
- NurbsSurface・Transform・Vector・コンポーネント等のメソッド・引数の名前を確かめる。
- 形状のシェイプのメソッドと createNurbsPlane を確かめる。
"""

import inspect
import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common.namespace import Namespace
from mlib.common.selection import Selection
from support.namespaceCase import NamespaceCase


class _CommonCase(NamespaceCase):
    PREFIX = "mlibSpecCommonEdits_"

    def setUp(self):
        super().setUp()
        self.current = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.relative = cmds.namespace(query=True, relativeNames=True)
        self.selection = cmds.ls(selection=True, long=True)
        cmds.select(clear=True)

    def tearDown(self):
        cmds.namespace(relativeNames=self.relative)
        cmds.namespace(set=self.current if cmds.namespace(exists=self.current) else ":")
        if self.selection:
            cmds.select(self.selection, replace=True)
        else:
            cmds.select(clear=True)
        super().tearDown()

    def namespaces(self, root):
        """root 配下の名前空間を root からの相対名で返す。"""
        names = cmds.namespaceInfo(root, listOnlyNamespaces=True, recurse=True, absoluteName=True) or []
        return sorted(name[len(root):] for name in names)

    def nodes(self, root):
        """root 配下のノードを root からの相対名で返す。"""
        names = cmds.namespaceInfo(root, listOnlyDependencyNodes=True, recurse=True, absoluteName=True) or []
        return sorted(name[len(root):] for name in names)


class SurfaceBaseTest(unittest.TestCase):

    def test_base_follows_inherited_types(self):
        """Lambert・StandardSurface の基底は Maya の継承列に paintableShadingDependNode があるかで決まる。"""
        from mlib.nodes import Lambert, StandardSurface
        from mlib.nodes.paintableShadingDependNode import PaintableShadingDependNode
        from mlib.nodes.shadingDependNode import ShadingDependNode

        for cls, type_name in ((Lambert, "lambert"), (StandardSurface, "standardSurface")):
            with self.subTest(type_name=type_name):
                inherited = cmds.nodeType(type_name, isTypeName=True, inherited=True)
                base = PaintableShadingDependNode if "paintableShadingDependNode" in inherited else ShadingDependNode
                self.assertIs(cls.__bases__[0], base)


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibMethodAdd_"

    def surface(self):
        """2x3 スパン・3次の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3,
                                    degree=3, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def cube(self):
        """1辺2cm の polyCube を作り、(transform, shape) のラッパーを返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return mlib.getNode(transform), mlib.getNode(shape)


class NurbsSurfaceTest(_Case):
    """NurbsSurface の照会と CV の書込み。"""

    def test_counts_and_range(self):
        """CV 数・スパン数・次数・形式・パラメーター範囲がアトリビュート・om2 と一致する。"""
        shape = self.surface()
        name = shape.getFullName()
        self.assertEqual(shape.getNumSpans(), (cmds.getAttr(name + ".spansU"), cmds.getAttr(name + ".spansV")))
        self.assertEqual(shape.getDegree(), (cmds.getAttr(name + ".degreeU"), cmds.getAttr(name + ".degreeV")))
        self.assertEqual(shape.getNumCVs(), (2 + 3, 3 + 3))
        self.assertEqual(shape.getForm(), (om2.MFnNurbsSurface.kOpen, om2.MFnNurbsSurface.kOpen))
        (u0, u1), (v0, v1) = shape.getParamRange()
        self.assertSequenceAlmostEqual((u0, u1), cmds.getAttr(name + ".minMaxRangeU")[0])
        self.assertSequenceAlmostEqual((v0, v1), cmds.getAttr(name + ".minMaxRangeV")[0])

    def test_cv_positions_match_cmds(self):
        """getCvPositions は cv[u][v] の順で、ローカルとワールドが pointPosition と一致する。"""
        shape = self.surface()
        name = shape.getFullName()
        count_u, count_v = shape.getNumCVs()
        local = shape.getCvPositions()
        world = shape.getCvPositions(ws=True)
        self.assertEqual(len(local), count_u * count_v)
        for u, v in ((0, 0), (1, 2), (count_u - 1, count_v - 1)):
            with self.subTest(u=u, v=v):
                index = u * count_v + v
                self.assertSequenceAlmostEqual(local[index], cmds.pointPosition(f"{name}.cv[{u}][{v}]", local=True))
                self.assertSequenceAlmostEqual(world[index], cmds.pointPosition(f"{name}.cv[{u}][{v}]", world=True))

    def test_set_cv_positions_undo_and_fast(self):
        """setCvPositions は全CVを書き、通常はUndo 1回で戻り、fast はUndoに残らない。ワールド指定も往復する。"""
        shape = self.surface()
        before = shape.getCvPositions()
        moved = [mlib.Vector(p) + mlib.Vector(0.0, 1.0, 0.0) for p in before]
        self.flushUndo()
        self.assertIs(shape.setCvPositions(moved), shape)
        self.assertUndoesInOneStep(
            lambda: self.assertSequenceAlmostEqual(shape.getCvPositions()[3], before[3]),
            lambda: self.assertSequenceAlmostEqual(shape.getCvPositions()[3], moved[3]))
        world = shape.getCvPositions(worldSpace=True)
        shape.setCvPositions([mlib.Vector(p) + mlib.Vector(1.0, 0.0, 0.0) for p in world], worldSpace=True)
        self.assertSequenceAlmostEqual(shape.getCvPositions(ws=True)[5], mlib.Vector(world[5]) + mlib.Vector(1, 0, 0))
        self.flushUndo()
        shape.setCvPositions(before, fast=True)
        self.assertUndoEmpty()
        self.assertSequenceAlmostEqual(shape.getCvPositions()[7], before[7])

    def test_set_cv_positions_errors(self):
        """点の数・型・fast の型の誤りは例外で、CV は変わらない。履歴のある形状の fast は NotImplementedError。"""
        shape = self.surface()
        before = shape.getCvPositions()
        for points, flags, error in ((before[:-1], {}, ValueError), (["abc"] * len(before), {}, TypeError),
                                     (before, {"fast": 1}, TypeError), (before, {"worldSpace": True, "ws": True},
                                                                         TypeError)):
            with self.subTest(flags=flags, error=error):
                with self.assertRaises(error):
                    shape.setCvPositions(points, **flags)
                self.assertSequenceAlmostEqual(shape.getCvPositions()[4], before[4])
        transform = cmds.nurbsPlane(name=self.name("history#"), constructionHistory=True)[0]
        history = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        with self.assertRaises(NotImplementedError):
            history.setCvPositions(history.getCvPositions(), fast=True)

    def test_closest_point_and_params_match_cmds(self):
        """最近点・(u, v) の位置・法線が closestPointOnSurface・pointOnSurface と一致する。"""
        shape = self.surface()
        name = shape.getFullName()
        found, u, v = shape.getClosestPoint((1.5, 9.0, 3.5), worldSpace=True)
        node = cmds.createNode("closestPointOnSurface", name=self.name("cpos#"))
        cmds.connectAttr(name + ".worldSpace[0]", node + ".inputSurface")
        cmds.setAttr(node + ".inPosition", 1.5, 9.0, 3.5)
        self.assertSequenceAlmostEqual(found, cmds.getAttr(node + ".result.position")[0], places=5)
        self.assertAlmostEqual(u, cmds.getAttr(node + ".result.parameterU"), places=5)
        self.assertAlmostEqual(v, cmds.getAttr(node + ".result.parameterV"), places=5)
        for space, flag in ((False, {}), (True, {"ws": True})):
            with self.subTest(worldSpace=space):
                point = shape.getPointAtParam(0.5, 1.0, **flag)
                # pointOnSurface はワールド座標を返す(transform は平行移動 (1, 2, 3) だけ)。
                expected = cmds.pointOnSurface(name, parameterU=0.5, parameterV=1.0, position=True)
                if not space:
                    expected = [value - offset for value, offset in zip(expected, (1, 2, 3))]
                self.assertSequenceAlmostEqual(point, expected, places=6)
                normal = shape.getNormalAtParam(0.5, 1.0, **flag)
                self.assertAlmostEqual(normal.length(), 1.0)
                self.assertSequenceAlmostEqual(
                    normal, cmds.pointOnSurface(name, parameterU=0.5, parameterV=1.0, normalizedNormal=True), places=6)

    def test_param_errors_and_empty_shape(self):
        """範囲外・有限でないパラメーターは ValueError、数値以外は TypeError、形状データの無い曲面は RuntimeError。"""
        shape = self.surface()
        (u0, u1), (v0, v1) = shape.getParamRange()
        for u, v, error in ((u1 + 1.0, v0, ValueError), (u0, float("nan"), ValueError), ("a", v0, TypeError)):
            with self.subTest(u=u, v=v):
                with self.assertRaises(error):
                    shape.getPointAtParam(u, v)
                with self.assertRaises(error):
                    shape.getNormalAtParam(u, v)
        with self.assertRaises(TypeError):
            shape.getClosestPoint((0, 0, 0), worldSpace=1)
        empty = mlib.createNode("nurbsSurface", name=self.name("empty#"))
        self.assertIsInstance(empty, mlib.NurbsSurface)
        for call in (empty.getNumCVs, empty.getParamRange, empty.getCvPositions):
            with self.subTest(call=call.__name__):
                with self.assertRaises(RuntimeError):
                    call()


class _CaseShapeAdditions(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibShapeAdd_"

    def surface(self, scale=(1, 1, 1)):
        """幅4・長さ2(lengthRatio 0.5)の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=0.5, patchesU=2, patchesV=1,
                                    axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        cmds.setAttr(transform + ".scale", *scale)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def curve(self, points, degree=3):
        """点列から NURBS カーブを作り、シェイプのラッパーを返す。"""
        transform = cmds.curve(name=self.name("curve#"), point=points, degree=degree)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def mesh(self):
        """polyPlane(2x2 分割)を作り、シェイプのラッパーを返す。"""
        transform = cmds.polyPlane(name=self.name("mesh#"), subdivisionsX=2, subdivisionsY=2,
                                   constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def assertDeletedRaises(self, node, calls):
        """ノードを削除し、各呼出しが RuntimeError になることを確かめる。"""
        cmds.delete(node.getFullName())
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(RuntimeError):
                    call(node)


class NurbsSurfaceFrameTest(_CaseShapeAdditions):
    """NurbsSurface の接線・マトリクス・面積。"""

    def test_tangents_match_point_on_surface(self):
        """接線は pointOnSurface の normalizedTangentU/V と一致し、非均等スケールのワールドでも向きが正しい。"""
        shape = self.surface(scale=(3, 1, 0.5))
        name = shape.getFullName()
        for flag in ({}, {"ws": True}, {"worldSpace": True}):
            with self.subTest(flag=flag):
                tangent_u, tangent_v = shape.getTangentsAtParam(0.3, 0.6, **flag)
                self.assertAlmostEqual(tangent_u.length(), 1.0)
                self.assertAlmostEqual(tangent_v.length(), 1.0)
                expected_u = cmds.pointOnSurface(name, parameterU=0.3, parameterV=0.6, normalizedTangentU=True)
                expected_v = cmds.pointOnSurface(name, parameterU=0.3, parameterV=0.6, normalizedTangentV=True)
                self.assertSequenceAlmostEqual(tangent_u, expected_u, places=6)
                self.assertSequenceAlmostEqual(tangent_v, expected_v, places=6)

    def test_matrix_at_param(self):
        """マトリクスの aim は U の接線、up は法線、位置は getPointAtParam と一致し、軸を変えられる。"""
        shape = self.surface()
        for flag in ({}, {"ws": True}):
            with self.subTest(flag=flag):
                matrix = shape.getMatrixAtParam(0.25, 0.5, **flag)
                tangent_u, _tangent_v = shape.getTangentsAtParam(0.25, 0.5, **flag)
                normal = shape.getNormalAtParam(0.25, 0.5, **flag)
                position = shape.getPointAtParam(0.25, 0.5, **flag)
                rows = [[matrix.getElement(row, column) for column in range(4)] for row in range(4)]
                self.assertSequenceAlmostEqual(rows[0][:3], tangent_u)
                self.assertSequenceAlmostEqual(rows[1][:3], normal)
                self.assertSequenceAlmostEqual(rows[3][:3], position)
                x, y, z = (om2.MVector(*row[:3]) for row in rows[:3])
                self.assertSequenceAlmostEqual(x ^ y, z)
        matrix = shape.getMatrixAtParam(0.25, 0.5, aimAxis="-z", upAxis="x")
        rows = [[matrix.getElement(row, column) for column in range(3)] for row in range(3)]
        self.assertSequenceAlmostEqual([-value for value in rows[2]], shape.getTangentsAtParam(0.25, 0.5)[0])
        self.assertSequenceAlmostEqual(rows[0], shape.getNormalAtParam(0.25, 0.5))

    def test_area(self):
        """面積はローカルで幅×長さ、ワールドではスケールを掛けた値になる。"""
        shape = self.surface(scale=(3, 1, 2))
        self.assertAlmostEqual(shape.getArea(), 4 * 2, places=6)
        self.assertAlmostEqual(shape.getArea(ws=True), 4 * 2 * 3 * 2, places=5)
        self.assertAlmostEqual(shape.getArea(worldSpace=True), shape.getArea(ws=True))

    def test_errors(self):
        """不正な入力の例外型と、削除済みノードの RuntimeError。"""
        shape = self.surface()
        for kwargs, error in (({"aimAxis": "x", "upAxis": "-x"}, ValueError), ({"aimAxis": "w"}, ValueError),
                              ({"aimAxis": 1}, TypeError), ({"worldSpace": 1}, TypeError),
                              ({"worldSpace": True, "ws": True}, TypeError)):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(error):
                    shape.getMatrixAtParam(0.5, 0.5, **kwargs)
        for u, error in ((2.0, ValueError), ("a", TypeError), (float("inf"), ValueError)):
            with self.subTest(u=u):
                with self.assertRaises(error):
                    shape.getTangentsAtParam(u, 0.5)
        with self.assertRaises(TypeError):
            shape.getArea(worldSpace="yes")
        empty = mlib.createNode("nurbsSurface", name=self.name("empty#"))
        for call in (empty.getArea, lambda: empty.getTangentsAtParam(0, 0), lambda: empty.getMatrixAtParam(0, 0)):
            with self.assertRaises(RuntimeError):
                call()
        self.assertDeletedRaises(shape, (lambda node: node.getArea(), lambda node: node.getTangentsAtParam(0, 0),
                                         lambda node: node.getMatrixAtParam(0, 0)))


if __name__ == "__main__":
    unittest.main()
