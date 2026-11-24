"""``mlib.nodes.nurbsSurface`` のテスト。

- 名前空間・選択・matchTransform の通常経路と、om2 へ置き換えた読み取りを cmds と突き合わせる。
- NurbsSurface・Transform・Vector・コンポーネント等のメソッド・引数の名前を確かめる。
- 形状のシェイプのメソッドと createNurbsPlane を確かめる。
"""

import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

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
        return sorted(name[len(root) :] for name in names)

    def nodes(self, root):
        """root 配下のノードを root からの相対名で返す。"""
        names = cmds.namespaceInfo(root, listOnlyDependencyNodes=True, recurse=True, absoluteName=True) or []
        return sorted(name[len(root) :] for name in names)


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
        transform = cmds.nurbsPlane(
            name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3, degree=3, axis=(0, 1, 0), constructionHistory=False
        )[0]
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
        """CV 数・形式・パラメーター範囲がアトリビュート・om2 と一致する。"""
        shape = self.surface()
        name = shape.getName(full=True)
        self.assertEqual(shape.getNumCVs(), (2 + 3, 3 + 3))
        self.assertEqual(shape.getForm(), (om2.MFnNurbsSurface.kOpen, om2.MFnNurbsSurface.kOpen))
        (u0, u1), (v0, v1) = shape.getParamRange()
        self.assertSequenceAlmostEqual((u0, u1), cmds.getAttr(name + ".minMaxRangeU")[0])
        self.assertSequenceAlmostEqual((v0, v1), cmds.getAttr(name + ".minMaxRangeV")[0])

    def test_cv_positions_match_cmds(self):
        """getPoints は cv[u][v] の順で、ローカルとワールドが pointPosition と一致する。"""
        shape = self.surface()
        name = shape.getName(full=True)
        count_u, count_v = shape.getNumCVs()
        local = shape.getPoints()
        world = shape.getPoints(ws=True)
        self.assertEqual(len(local), count_u * count_v)
        for u, v in ((0, 0), (1, 2), (count_u - 1, count_v - 1)):
            with self.subTest(u=u, v=v):
                index = u * count_v + v
                self.assertSequenceAlmostEqual(local[index], cmds.pointPosition(f"{name}.cv[{u}][{v}]", local=True))
                self.assertSequenceAlmostEqual(world[index], cmds.pointPosition(f"{name}.cv[{u}][{v}]", world=True))

    def test_set_cv_positions_undo_and_fast(self):
        """setPoints は全CVを書き、通常はUndo 1回で戻り、fast はUndoに残らない。ワールド指定も往復する。"""
        shape = self.surface()
        before = shape.getPoints()
        moved = [mlib.Vector(p) + mlib.Vector(0.0, 1.0, 0.0) for p in before]
        self.flushUndo()
        self.assertIsNone(shape.setPoints(moved))
        self.assertUndoesInOneStep(
            lambda: self.assertSequenceAlmostEqual(shape.getPoints()[3], before[3]), lambda: self.assertSequenceAlmostEqual(shape.getPoints()[3], moved[3])
        )
        world = shape.getPoints(worldSpace=True)
        shape.setPoints([mlib.Vector(p) + mlib.Vector(1.0, 0.0, 0.0) for p in world], worldSpace=True)
        self.assertSequenceAlmostEqual(shape.getPoints(ws=True)[5], mlib.Vector(world[5]) + mlib.Vector(1, 0, 0))
        self.flushUndo()
        shape.setPoints(before, fast=True)
        self.assertUndoEmpty()
        self.assertSequenceAlmostEqual(shape.getPoints()[7], before[7])

    def test_set_cv_positions_errors(self):
        """点の数・型・fast の型の誤りは例外で、CV は変わらない。履歴のある形状の fast は NotImplementedError。"""
        shape = self.surface()
        before = shape.getPoints()
        for points, flags, error in (
            (before[:-1], {}, ValueError),
            (["abc"] * len(before), {}, TypeError),
            (before, {"fast": 1}, TypeError),
            (before, {"worldSpace": True, "ws": True}, TypeError),
        ):
            with self.subTest(flags=flags, error=error):
                with self.assertRaises(error):
                    shape.setPoints(points, **flags)
                self.assertSequenceAlmostEqual(shape.getPoints()[4], before[4])
        transform = cmds.nurbsPlane(name=self.name("history#"), constructionHistory=True)[0]
        history = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        with self.assertRaises(NotImplementedError):
            history.setPoints(history.getPoints(), fast=True)

    def test_getCVs_single_index_and_uv(self):
        """getCVs は通し番号1つで SurfaceCV、[(u, v)] の並びで SurfaceCVs を返し、座標は pointPosition と一致する。"""
        shape = self.surface()
        name = shape.getName(full=True)
        _count_u, count_v = shape.getNumCVs()
        flat = 1 * count_v + 2
        cv = shape.getCVs(flat)
        self.assertIs(type(cv), mlib.SurfaceCV)
        self.assertEqual(cv.index, flat)
        self.assertSequenceAlmostEqual(tuple(cv.getPosition())[:3], cmds.pointPosition(f"{name}.cv[1][2]", local=True))
        pair = shape.getCVs([(1, 2)])
        self.assertIs(type(pair), mlib.SurfaceCVs)
        self.assertEqual(len(pair), 1)
        self.assertEqual(pair[0], cv)
        # (u, v) を並びに入れずに渡すと、通し番号 u と v の2つになる(変えていない動き)。
        both = shape.getCVs((1, 2))
        self.assertIs(type(both), mlib.SurfaceCVs)
        self.assertEqual([item.index for item in both], [1, 2])
        self.assertEqual(len(shape.getCVs()), len(shape.getPoints()))
        with self.assertRaises(TypeError):
            shape.getCVs(True)
        with self.assertRaises(IndexError):
            shape.getCVs(len(shape.getPoints()))

    def test_mirror_matches_cvs_mirror(self):
        """NurbsSurface.mirror は getCVs().mirror と同じ結果になり、軸・空間・pivot・indices を受ける。"""
        for label, args, kwargs, indices in (
            ("default", (), {}, None),
            ("y world pivot", ("y",), {"worldSpace": True, "pivot": (1.0, 2.0, 3.0)}, None),
            ("z ws", ("z",), {"ws": True}, None),
            ("indices flat", ("x",), {}, [0, 5, 7]),
            ("indices uv", ("x",), {}, [(1, 2), 3]),
            ("fast", ("x",), {"fast": True}, None),
        ):
            with self.subTest(label=label):
                direct = self.surface()
                through = self.surface()
                before = direct.getPoints()
                self.assertIsNone(direct.mirror(*args, indices=indices, **kwargs))
                through.getCVs(indices).mirror(*args, **kwargs)
                after = direct.getPoints()
                for actual, expected in zip(after, through.getPoints()):
                    self.assertSequenceAlmostEqual(actual, expected)
                self.assertNotEqual([tuple(p) for p in after], [tuple(p) for p in before])
                if indices is not None:
                    changed = {i for i, (a, b) in enumerate(zip(after, before)) if mlib.Vector(a).distanceTo(mlib.Vector(b)) > 1e-9}
                    self.assertLessEqual(changed, {item.index for item in direct.getCVs(indices)})
        # 既定(x・ローカル・原点)は、X の符号だけが反転する。
        shape = self.surface()
        before = shape.getPoints()
        shape.mirror()
        for actual, expected in zip(shape.getPoints(), before):
            self.assertSequenceAlmostEqual(actual, (-expected[0], expected[1], expected[2]))
        # 空の並びは何も変えない。
        shape.mirror(indices=[])
        for actual, expected in zip(shape.getPoints(), before):
            self.assertSequenceAlmostEqual(actual, (-expected[0], expected[1], expected[2]))

    def test_mirror_undo_and_fast(self):
        """mirror は Undo 1回(チャンク名 mlibNurbsSurfaceMirror)で戻り、fast=True は Undo に載らない。"""
        shape = self.surface()
        before = shape.getPoints()
        self.flushUndo()
        shape.mirror("x")
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "mlibNurbsSurfaceMirror")
        self.assertUndoesInOneStep(
            lambda: self.assertSequenceAlmostEqual(shape.getPoints()[0], before[0]),
            lambda: self.assertSequenceAlmostEqual(shape.getPoints()[0], (-before[0][0], before[0][1], before[0][2])),
        )
        self.flushUndo()
        shape.mirror("x", fast=True)
        self.assertUndoEmpty()
        self.assertSequenceAlmostEqual(shape.getPoints()[0], (-before[0][0], before[0][1], before[0][2]))

    def test_mirror_errors(self):
        """mirror の不正な入力は例外で CV を変えず、Transform.mirrorGeometry はサーフェスを今までどおり ValueError にする。"""
        shape = self.surface()
        before = shape.getPoints()
        for args, kwargs, error in (
            (("w",), {}, ValueError),
            ((None,), {}, TypeError),
            (("x",), {"fast": 1}, TypeError),
            (("x",), {"worldSpace": True, "ws": True}, TypeError),
            (("x",), {"pivot": (0, 0)}, ValueError),
            (("x",), {"indices": [len(before)]}, IndexError),
        ):
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    shape.mirror(*args, **kwargs)
                self.assertSequenceAlmostEqual(shape.getPoints()[4], before[4])
        with self.assertRaises(ValueError):
            shape.getTransform().mirrorGeometry()
        self.assertSequenceAlmostEqual(shape.getPoints()[4], before[4])
        transform = cmds.nurbsPlane(name=self.name("history#"), constructionHistory=True)[0]
        history = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        with self.assertRaises(NotImplementedError):
            history.mirror(fast=True)

    def test_closest_point_and_params_match_cmds(self):
        """最近点・(u, v) の位置・法線が closestPointOnSurface・pointOnSurface と一致する。"""
        shape = self.surface()
        name = shape.getName(full=True)
        found, u, v = shape.getClosestPoint((1.5, 9.0, 3.5), worldSpace=True)
        node = cmds.createNode("closestPointOnSurface", name=self.name("cpos#"))
        cmds.connectAttr(name + ".worldSpace[0]", node + ".inputSurface")
        cmds.setAttr(node + ".inPosition", 1.5, 9.0, 3.5)
        self.assertSequenceAlmostEqual(found, cmds.getAttr(node + ".result.position")[0], places=5)
        self.assertAlmostEqual(u, cmds.getAttr(node + ".result.parameterU"), places=5)
        self.assertAlmostEqual(v, cmds.getAttr(node + ".result.parameterV"), places=5)
        for space, flag in ((False, {}), (True, {"ws": True})):
            with self.subTest(worldSpace=space):
                point = shape.getAtParam(0.5, 1.0, **flag)
                # pointOnSurface はワールド座標を返す(transform は平行移動 (1, 2, 3) だけ)。
                expected = cmds.pointOnSurface(name, parameterU=0.5, parameterV=1.0, position=True)
                if not space:
                    expected = [value - offset for value, offset in zip(expected, (1, 2, 3))]
                self.assertSequenceAlmostEqual(point, expected, places=6)
                normal = shape.getAtParam(0.5, 1.0, what="normal", **flag)
                self.assertAlmostEqual(normal.length(), 1.0)
                self.assertSequenceAlmostEqual(normal, cmds.pointOnSurface(name, parameterU=0.5, parameterV=1.0, normalizedNormal=True), places=6)

    def test_param_errors_and_empty_shape(self):
        """範囲外・有限でないパラメーターは ValueError、数値以外は TypeError、形状データの無い曲面は RuntimeError。"""
        shape = self.surface()
        (u0, u1), (v0, _v1) = shape.getParamRange()
        for u, v, error in ((u1 + 1.0, v0, ValueError), (u0, float("nan"), ValueError), ("a", v0, TypeError)):
            with self.subTest(u=u, v=v):
                with self.assertRaises(error):
                    shape.getAtParam(u, v)
                with self.assertRaises(error):
                    shape.getAtParam(u, v, what="normal")
        with self.assertRaises(TypeError):
            shape.getClosestPoint((0, 0, 0), worldSpace=1)
        empty = mlib.createNode("nurbsSurface", name=self.name("empty#"))
        self.assertIsInstance(empty, mlib.NurbsSurface)
        for call in (empty.getNumCVs, empty.getParamRange, empty.getPoints):
            with self.subTest(call=call.__name__):
                with self.assertRaises(RuntimeError):
                    call()


class _CaseShapeAdditions(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibShapeAdd_"

    def surface(self, scale=(1, 1, 1)):
        """幅4・長さ2(lengthRatio 0.5)の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=0.5, patchesU=2, patchesV=1, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        cmds.setAttr(transform + ".scale", *scale)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def curve(self, points, degree=3):
        """点列から NURBS カーブを作り、シェイプのラッパーを返す。"""
        transform = cmds.curve(name=self.name("curve#"), point=points, degree=degree)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def mesh(self):
        """polyPlane(2x2 分割)を作り、シェイプのラッパーを返す。"""
        transform = cmds.polyPlane(name=self.name("mesh#"), subdivisionsX=2, subdivisionsY=2, constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def assertDeletedRaises(self, node, calls):
        """ノードを削除し、各呼出しが RuntimeError になることを確かめる。"""
        cmds.delete(node.getName(full=True))
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(RuntimeError):
                    call(node)


class NurbsSurfaceFrameTest(_CaseShapeAdditions):
    """NurbsSurface の接線・マトリクス・面積。"""

    def test_tangents_match_point_on_surface(self):
        """接線は pointOnSurface の normalizedTangentU/V と一致し、非均等スケールのワールドでも向きが正しい。"""
        shape = self.surface(scale=(3, 1, 0.5))
        name = shape.getName(full=True)
        for flag in ({}, {"ws": True}, {"worldSpace": True}):
            with self.subTest(flag=flag):
                tangent_u, tangent_v = shape.getAtParam(0.3, 0.6, what="tangents", **flag)
                self.assertAlmostEqual(tangent_u.length(), 1.0)
                self.assertAlmostEqual(tangent_v.length(), 1.0)
                expected_u = cmds.pointOnSurface(name, parameterU=0.3, parameterV=0.6, normalizedTangentU=True)
                expected_v = cmds.pointOnSurface(name, parameterU=0.3, parameterV=0.6, normalizedTangentV=True)
                self.assertSequenceAlmostEqual(tangent_u, expected_u, places=6)
                self.assertSequenceAlmostEqual(tangent_v, expected_v, places=6)

    def test_matrix_at_param(self):
        """マトリクスの aim は U の接線、up は法線、位置は getAtParam(既定の what="point")と一致し、軸を変えられる。"""
        shape = self.surface()
        for flag in ({}, {"ws": True}):
            with self.subTest(flag=flag):
                matrix = shape.getAtParam(0.25, 0.5, what="matrix", **flag)
                tangent_u, _tangent_v = shape.getAtParam(0.25, 0.5, what="tangents", **flag)
                normal = shape.getAtParam(0.25, 0.5, what="normal", **flag)
                position = shape.getAtParam(0.25, 0.5, **flag)
                rows = [[matrix.getElement(row, column) for column in range(4)] for row in range(4)]
                self.assertSequenceAlmostEqual(rows[0][:3], tangent_u)
                self.assertSequenceAlmostEqual(rows[1][:3], normal)
                self.assertSequenceAlmostEqual(rows[3][:3], position)
                x, y, z = (om2.MVector(*row[:3]) for row in rows[:3])
                self.assertSequenceAlmostEqual(x ^ y, z)
        matrix = shape.getAtParam(0.25, 0.5, aimAxis="-z", upAxis="x", what="matrix")
        rows = [[matrix.getElement(row, column) for column in range(3)] for row in range(3)]
        self.assertSequenceAlmostEqual([-value for value in rows[2]], shape.getAtParam(0.25, 0.5, what="tangents")[0])
        self.assertSequenceAlmostEqual(rows[0], shape.getAtParam(0.25, 0.5, what="normal"))

    def test_area(self):
        """面積はローカルで幅×長さ、ワールドではスケールを掛けた値になる。"""
        shape = self.surface(scale=(3, 1, 2))
        self.assertAlmostEqual(shape.getArea(), 4 * 2, places=6)
        self.assertAlmostEqual(shape.getArea(ws=True), 4 * 2 * 3 * 2, places=5)
        self.assertAlmostEqual(shape.getArea(worldSpace=True), shape.getArea(ws=True))

    def test_errors(self):
        """不正な入力の例外型と、削除済みノードの RuntimeError。"""
        shape = self.surface()
        for kwargs, error in (
            ({"aimAxis": "x", "upAxis": "-x"}, ValueError),
            ({"aimAxis": "w"}, ValueError),
            ({"aimAxis": 1}, TypeError),
            ({"worldSpace": 1}, TypeError),
            ({"worldSpace": True, "ws": True}, TypeError),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(error):
                    shape.getAtParam(0.5, 0.5, what="matrix", **kwargs)
        # what の名前違いは ValueError、str 以外は TypeError。matrix 以外で aimAxis・upAxis、derivatives 以外で secondOrder=True は TypeError。
        for label, kwargs, error in (
            ("unknown what", {"what": "tangent"}, ValueError),
            ("what type", {"what": None}, TypeError),
            ("point+aimAxis", {"aimAxis": "x"}, TypeError),
            ("point+upAxis", {"upAxis": "y"}, TypeError),
            ("normal+aimAxis", {"what": "normal", "aimAxis": "z"}, TypeError),
            ("tangents+upAxis", {"what": "tangents", "upAxis": "z"}, TypeError),
            ("derivatives+aimAxis", {"what": "derivatives", "aimAxis": "x", "upAxis": "y"}, TypeError),
            ("point+secondOrder", {"secondOrder": True}, TypeError),
            ("matrix+secondOrder", {"what": "matrix", "secondOrder": True}, TypeError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    shape.getAtParam(0.5, 0.5, **kwargs)
        self.assertSequenceAlmostEqual(shape.getAtParam(0.5, 0.5, what="point"), shape.getAtParam(0.5, 0.5))
        for u, error in ((2.0, ValueError), ("a", TypeError), (float("inf"), ValueError)):
            with self.subTest(u=u):
                with self.assertRaises(error):
                    shape.getAtParam(u, 0.5, what="tangents")
        with self.assertRaises(TypeError):
            shape.getArea(worldSpace="yes")
        empty = mlib.createNode("nurbsSurface", name=self.name("empty#"))
        for call in (empty.getArea, lambda: empty.getAtParam(0, 0, what="tangents"), lambda: empty.getAtParam(0, 0, what="matrix")):
            with self.assertRaises(RuntimeError):
                call()
        self.assertDeletedRaises(
            shape, (lambda node: node.getArea(), lambda node: node.getAtParam(0, 0, what="tangents"), lambda node: node.getAtParam(0, 0, what="matrix"))
        )

    def collapsed_surface(self):
        """すべてのCVを原点へ集めた(形のつぶれた)NURBS平面を作る。"""
        shape = self.surface()
        cmds.xform(shape.getName(full=True) + ".cv[*]", translation=(0, 0, 0), worldSpace=True)
        return shape

    def test_collapsed_surface_tangents_and_matrix(self):
        """形のつぶれた曲面ではtangents・matrixがValueError(接線もフレームも決まらない)。"""
        shape = self.collapsed_surface()
        for what in ("tangents", "matrix"):
            with self.subTest(what=what):
                with self.assertRaises(ValueError):
                    shape.getAtParam(0.5, 0.5, what=what)

    def test_collapsed_surface_normal_raises_value_error(self):
        """形のつぶれた曲面のnormalはdocstringのとおりValueError。"""
        shape = self.collapsed_surface()
        with self.assertRaises(ValueError):
            shape.getAtParam(0.5, 0.5, what="normal")

    def test_set_points_world_space_with_singular_transform(self):
        """親のマトリクスが特異ならsetPoints(ws=True)はValueErrorで、CVは変わらない(fastでも同じ)。"""
        shape = self.surface()
        transform = shape.getParent().getName(full=True)
        cmds.setAttr(transform + ".offsetParentMatrix", [0.0] * 15 + [1.0], type="matrix")
        before = [tuple(point) for point in shape.mfn().cvPositions()]
        for kwargs in ({"ws": True}, {"worldSpace": True, "fast": True}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    shape.setPoints([(1, 1, 1)] * len(before), **kwargs)
                self.assertEqual([tuple(point) for point in shape.mfn().cvPositions()], before)

    def test_set_points_fast_rejects_locked_shape(self):
        """ロックしたシェイプへのsetPoints(fast=True)はRuntimeErrorで、CVは変わらない。"""
        shape = self.surface()
        name = shape.getName(full=True)
        before = [tuple(point) for point in shape.mfn().cvPositions()]
        cmds.lockNode(name, lock=True)
        try:
            for check in (False, True):
                with self.subTest(check=check):
                    with self.assertRaises(RuntimeError):
                        shape.setPoints([(1, 1, 1)] * len(before), fast=True, check=check)
        finally:
            cmds.lockNode(name, lock=False)
        self.assertEqual([tuple(point) for point in shape.mfn().cvPositions()], before)


if __name__ == "__main__":
    unittest.main()
