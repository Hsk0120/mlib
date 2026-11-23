"""ループ変数の改名・例外の絞り込み・三項演算子への書き換えなど、中身だけを整えた関数の動きを固定する。

公開APIを通して、書き換えの前と同じ結果になることを確かめる。対象は次のとおり。

- ``SkinCluster`` の周期カーブのCV番号の写し(``getWeights``・``setWeights``)、インフルエンスを外すときの
  移し先のたどり方(``removeInfluences``)、cmdsでの書込みの行と列の位置(``setWeights``)。
- ``Edges.getLoop`` のたどる順。
- 入力を変換してから使う箇所(om2の型・``__index__`` を持つ値・名前の文字列など)。
- 例外を絞った ``maths.matrix._reinit_is_safe``・``Transform._channel_equals``。
- 三項演算子・``contextlib.suppress`` にした ``jointOrient`` の読み取り・クリースの判定・トレースバックを省く処理。
- 名前を変えたキャッシュが ``mlib.reload()`` の後も使われること、``Double3Plug`` の値の型の対応表。
- まだテストの無い ``mlib.json.file._current_fps``・``ValidationReport._add_skipped``・``ValidationReport.warn`` の文言。
"""

import copy
import math
import os
import sys
import unittest
from unittest import mock

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.utils as maya_utils

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib import logger
from mlib.common.selection import Selection
from mlib.components.cv import CV
from mlib.components.surfaceCV import SurfaceCVs
from mlib.json import ValidationReport
from mlib.json import file as json_file
from mlib.json._animCurveData import _transform_keys
from mlib.maths import matrix as matrix_module
from mlib.nodes import Nodes
from mlib.nodes.blendShape import _weight_item
from mlib.nodes.node import _is_writable


class _IndexLike:
    """``operator.index`` で整数になるが、intではない値。"""

    def __init__(self, value):
        self.value = value

    def __index__(self):
        return self.value


class _Case(NamespaceCase):
    PREFIX = "mlibCompatRefactor_"


class SkinClusterPeriodicCvTest(_Case):
    """周期カーブのCV番号を独立CVへ写す処理(``_cv_indices``)。"""

    def setUp(self):
        super().setUp()
        # sections=8・次数3の円は、CVが11個で独立CVが8個(番号8・9・10は0・1・2と重なる)。
        self.curve = cmds.circle(name=self.name("circle"), constructionHistory=False, sections=8)[0]
        self.joints = [self.make("joint", "joint#") for _ in range(2)]
        cmds.setAttr(self.joints[1] + ".tx", 3)
        name = cmds.skinCluster(self.joints, self.curve, toSelectedBones=True, normalizeWeights=0, name=self.name("skin"))[0]
        self.skin = mlib.getNode(name)
        self.shape = mlib.getNode(self.curve).getShape()
        rows = [[index / 10.0, 1.0 - index / 10.0] for index in range(8)]
        self.skin.setWeights(self.joints, rows, rows=True)

    def test_duplicate_cv_numbers_read_the_independent_cv(self):
        """重なるCVの番号・CV参照・名前は、独立CVの行を読む。指定した順を保つ。"""
        # Mayaは周期カーブのcv[8]以降の名前をcv[7]へ丸めるため、名前は独立CVの番号で確かめる。
        cases = (([8], [0]), ([9], [1]), ([10, 0], [2, 0]), ([CV(self.shape, 9)], [1]), (self.shape.getFullName() + ".cv[2]", [2]))
        for vertices, expected in cases:
            with self.subTest(vertices=str(vertices)):
                self.assertEqual(
                    self.skin.getWeights(self.joints, vertices=vertices, rows=True), self.skin.getWeights(self.joints, vertices=expected, rows=True)
                )

    def test_duplicate_cv_number_writes_the_independent_cv(self):
        """重なるCVの番号へ書くと、独立CVの要素へ書かれる。"""
        self.skin.setWeights(self.joints, [[0.3, 0.7]], vertices=[9], rows=True)
        self.assertSequenceAlmostEqual(cmds.getAttr(f"{self.skin}.weightList[1].weights[*]"), [0.3, 0.7])
        self.assertSequenceAlmostEqual(self.skin.getWeights(self.joints, vertices=[1]), [0.3, 0.7])

    def test_errors_name_the_folded_or_given_number(self):
        """写した後に重なればValueError(写した後の番号)、範囲外はIndexError(指定した番号)。値は変えない。"""
        before = self.skin.getWeights(self.joints, rows=True)
        cases = (
            ([1, 9], ValueError, "CVが複数回指定されています: 1"),
            ([10, 2], ValueError, "CVが複数回指定されています: 2"),
            ([11], IndexError, "CV番号が範囲外です: 11"),
            ([-1], IndexError, "CV番号が範囲外です: -1"),
        )
        for vertices, error, message in cases:
            with self.subTest(vertices=vertices):
                with self.assertRaises(error) as context:
                    self.skin.setWeights(self.joints, [0.5, 0.5], vertices=vertices, broadcast=True)
                self.assertIn(message, str(context.exception))
                self.assertEqual(self.skin.getWeights(self.joints, rows=True), before)


class SkinClusterWeightWriteTest(_Case):
    """インフルエンスを外すときの移し先と、cmdsでの書込みの位置。"""

    def setUp(self):
        super().setUp()
        self.mesh = cmds.polyPlane(name=self.name("plane"), subdivisionsX=3, subdivisionsY=1, constructionHistory=False)[0]
        self.joints = []
        parent = None
        for index in range(4):
            joint = self.make("joint", f"j{index}", parent=parent)
            cmds.setAttr(joint + ".tx", 0.0 if parent is None else 0.3)
            self.joints.append(joint)
            parent = joint
        name = cmds.skinCluster(self.joints, self.mesh, toSelectedBones=True, normalizeWeights=0, name=self.name("skin"))[0]
        self.skin = mlib.getNode(name)
        self.count = cmds.polyEvaluate(self.mesh, vertex=True)
        self.rows = [[0.1 + 0.01 * v, 0.2, 0.3 - 0.01 * v, 0.4] for v in range(self.count)]
        self.skin.setWeights(self.joints, self.rows, rows=True)

    def test_removing_parent_and_child_follows_the_chain(self):
        """j1・j3を外すと、j3はj2へ、j1はj0へ移る(外すj1をたどらず、残る祖先へ直接足す)。"""
        self.skin.removeInfluences([self.joints[3], self.joints[1]])
        self.assertEqual([node.getName() for node in self.skin.getInfluences()], [mlib.getNode(j).getName() for j in (self.joints[0], self.joints[2])])
        after = self.skin.getWeights([self.joints[0], self.joints[2]], rows=True)
        for row, original in zip(after, self.rows):
            self.assertAlmostEqual(row[0], original[0] + original[1], places=6)
            self.assertAlmostEqual(row[1], original[2] + original[3], places=6)

    def test_removing_a_chain_of_three_moves_to_the_root(self):
        """j1・j2・j3を外すと、j3→j2→j1とたどって、すべてj0へ集まる。"""
        self.skin.removeInfluences(self.joints[1:])
        for value, original in zip(self.skin.getWeights([self.joints[0]]), self.rows):
            self.assertAlmostEqual(value, sum(original), places=6)

    def test_columns_follow_the_given_influence_order(self):
        """インフルエンスの順を入れ替えても、各値は対応する行・列の要素へ書かれる。"""
        order = [self.joints[2], self.joints[0], self.joints[3], self.joints[1]]
        logical = [self.skin.getInfluenceIndex(joint) for joint in order]
        rows = [[0.01 * v + 0.1 * c for c in range(4)] for v in (1, 3)]
        self.skin.setWeights(order, rows, vertices=[1, 3], rows=True)
        for vertex, row in zip((1, 3), rows):
            for index, value in zip(logical, row):
                with self.subTest(vertex=vertex, index=index):
                    self.assertAlmostEqual(cmds.getAttr(f"{self.skin}.weightList[{vertex}].weights[{index}]"), value, places=6)

    def test_locked_element_in_a_range_writes_up_to_it(self):
        """範囲の書込みがロックで拒否されると、要素ごとに書き直して、ロックの手前まで書く。"""
        prefix = f"{self.skin}.weightList[2].weights"
        cmds.setAttr(prefix + "[2]", lock=True)
        try:
            with self.assertRaises(RuntimeError):
                self.skin.setWeights(self.joints, [[0.9, 0.8, 0.7, 0.6]], vertices=[2], rows=True)
            values = [cmds.getAttr(f"{prefix}[{index}]") for index in range(4)]
            self.assertSequenceAlmostEqual(values[:2], [0.9, 0.8], places=6)
            self.assertSequenceAlmostEqual(values[2:], self.rows[2][2:], places=6)
        finally:
            cmds.setAttr(prefix + "[2]", lock=False)


class EdgeLoopOrderTest(_Case):
    """``Edges.getLoop`` が、始めのエッジから両方向へ順にたどること。"""

    def assertLoopOrder(self, mesh, edge, loop):
        fn = om2.MFnMesh(mesh.mpath())
        self.assertEqual(loop[0], edge)
        self.assertEqual(len(loop), len(set(loop)))
        first, second = fn.getEdgeVertices(edge)
        position = 1
        # 1つ目の頂点の側へ、つながった順に並ぶ。
        current, pivot = edge, first
        while position < len(loop) and pivot in fn.getEdgeVertices(loop[position]):
            start, end = fn.getEdgeVertices(loop[position])
            current, pivot = loop[position], (end if start == pivot else start)
            position += 1
        # 残りは2つ目の頂点の側へ、つながった順に並ぶ。
        current, pivot = edge, second
        while position < len(loop):
            self.assertIn(pivot, fn.getEdgeVertices(loop[position]), msg=f"{current}の次の{loop[position]}がつながっていません")
            start, end = fn.getEdgeVertices(loop[position])
            current, pivot = loop[position], (end if start == pivot else start)
            position += 1

    def test_loop_is_walked_in_both_directions(self):
        plane = cmds.polyPlane(name=self.name("p"), subdivisionsX=5, subdivisionsY=4, constructionHistory=False)[0]
        cylinder = cmds.polyCylinder(name=self.name("c"), subdivisionsAxis=8, subdivisionsHeight=3, constructionHistory=False)[0]
        for name in (plane, cylinder):
            mesh = mlib.getNode(name).getShape()
            for edge in range(0, mesh.getNumEdges(), 2):
                with self.subTest(mesh=name, edge=edge):
                    loop = list(mesh.getEdge(edge).getLoop().indices)
                    self.assertEqual(sorted(loop), sorted(set(cmds.polySelect(name, edgeLoop=edge, noSelection=True) or [])))
                    self.assertLoopOrder(mesh, edge, loop)


class ConvertedInputTest(_Case):
    """入力を変換してから使う箇所が、変換の必要な入力でも同じ結果になること。"""

    def test_mesh_set_points_accepts_om2_points_and_vectors(self):
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        mesh = mlib.getNode(cube).getShape()
        points = [(float(i), 1.0, 2.0) for i in range(8)]
        given = [om2.MPoint(*points[0]), om2.MVector(*points[1]), om2.MFloatPoint(*points[2]), list(points[3]), *points[4:]]
        for fast in (False, True):
            with self.subTest(fast=fast):
                mesh.setPoints(given, fast=fast)
                actual = om2.MFnMesh(mesh.mpath()).getPoints()
                for point, expected in zip(actual, points):
                    self.assertSequenceAlmostEqual((point.x, point.y, point.z), expected, places=6)
        before = [tuple(p) for p in om2.MFnMesh(mesh.mpath()).getPoints()]
        for value in (om2.MPoint(), om2.MVector(), om2.MFloatPoint(), "points", [(0, 0, 0)] * 7 + ["abc"]):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypeError):
                    mesh.setPoints(value)
                self.assertEqual([tuple(p) for p in om2.MFnMesh(mesh.mpath()).getPoints()], before)

    def test_periodic_cv_fast_write_folds_the_index(self):
        """周期カーブの重なるCVへのfastの書込みは、対応する独立CVへ書く(通常と同じ)。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                curve = cmds.circle(name=self.name("circle#"), constructionHistory=False, sections=8)[0]
                shape = mlib.getNode(curve).getShape()
                CV(shape, 9).setPosition((5.0, 6.0, 7.0), fast=fast)
                self.assertSequenceAlmostEqual(CV(shape, 1).getPosition(), (5.0, 6.0, 7.0), places=6)
                self.assertSequenceAlmostEqual(CV(shape, 9).getPosition(), (5.0, 6.0, 7.0), places=6)

    def test_uvs_set_u_keeps_v(self):
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        uvs = mlib.getNode(cube).getShape().getUVs([2, 3])
        before = [tuple(row) for row in uvs.getPosition()]
        uvs.setPosition([0.1, 0.9], axis="u", each=True)
        after = [tuple(row) for row in uvs.getPosition()]
        self.assertSequenceAlmostEqual([row[0] for row in after], [0.1, 0.9], places=6)
        self.assertSequenceAlmostEqual([row[1] for row in after], [row[1] for row in before], places=6)

    def test_surface_cv_numbers_accept_index_like_values(self):
        """``(u, v)`` の各番号は ``__index__`` を持つ値でもよい。boolはTypeError、負の数はIndexError。"""
        plane = cmds.nurbsPlane(name=self.name("plane"), constructionHistory=False, patchesU=2, patchesV=2)[0]
        shape = mlib.getNode(plane).getShape()
        expected = SurfaceCVs(shape, [(1, 2), 3])
        self.assertEqual(SurfaceCVs(shape, [(_IndexLike(1), _IndexLike(2)), _IndexLike(3)]).indices, expected.indices)
        for value, error in (([(True, 0)], TypeError), ([(0, -1)], IndexError), ([(0, 1.5)], TypeError)):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    SurfaceCVs(shape, value)

    def test_selection_splits_complete_and_listed_components(self):
        """完全な(complete)コンポーネントは番号0から、番号を並べたものはgetElements()の順に分ける。"""
        plane = cmds.polyPlane(name=self.name("p"), subdivisionsX=2, subdivisionsY=2, constructionHistory=False)[0]
        mesh = mlib.getNode(plane).getShape()
        for complete in (True, False):
            with self.subTest(complete=complete):
                fn = om2.MFnSingleIndexedComponent()
                component = fn.create(om2.MFn.kMeshVertComponent)
                if complete:
                    fn.setCompleteData(9)
                    expected = list(range(9))
                else:
                    fn.addElements([5, 2, 7])
                    expected = list(fn.getElements())
                selection = om2.MSelectionList()
                selection.add((mesh.mpath(), component))
                items = list(Selection(selection))
                self.assertEqual([item.index for item in items], expected)

    def test_fast_enum_fields_match_cmds(self):
        """fastのenumの項目(``名前=値`` と続き番号)は、cmds.addAttrと同じ値になる。"""
        node = mlib.getNode(self.make())
        text = "a=3:b:c=10:d"
        node.addAttr("fastEnum", at="enum", en=text, fast=True)
        cmds.addAttr(node.getFullName(), longName="cmdsEnum", attributeType="enum", enumName=text)
        self.assertEqual(
            cmds.attributeQuery("fastEnum", node=node.getFullName(), listEnum=True), cmds.attributeQuery("cmdsEnum", node=node.getFullName(), listEnum=True)
        )

    def test_vector_children_count_must_match_the_type(self):
        """double3にnumberOfChildrenの3以外を渡すとValueError(アトリビュートは足さない)。3はそのまま足す。"""
        node = mlib.getNode(self.make())
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(ValueError):
                    node.addAttr(f"bad{int(fast)}", at="double3", nc=2, fast=fast)
                self.assertFalse(cmds.attributeQuery(f"bad{int(fast)}", node=node.getFullName(), exists=True))
                node.addAttr(f"good{int(fast)}", at="double3", nc=3, fast=fast)
                self.assertEqual(cmds.attributeQuery(f"good{int(fast)}", node=node.getFullName(), numberOfChildren=True), [3])

    def test_deformer_weights_accept_vertex_objects(self):
        """setDeformerWeightsのverticesは、Vertex・Vertices・番号を混ぜてもよい。"""
        cube = cmds.polyCube(name=self.name("cube"))[0]
        cluster = mlib.getNode(cmds.cluster(cube, name=self.name("cl"))[0])
        mesh = mlib.getNode(cube).getShape()
        cluster.setDeformerWeights([0.25, 0.5], vertices=[mesh.getVertex(5), 2])
        values = cluster.getDeformerWeights()
        self.assertAlmostEqual(values[5], 0.25, places=6)
        self.assertAlmostEqual(values[2], 0.5, places=6)
        cluster.setDeformerWeights([0.75, 0.125], vertices=mesh.getVertices([1, 6]))
        values = cluster.getDeformerWeights()
        self.assertAlmostEqual(values[1], 0.75, places=6)
        self.assertAlmostEqual(values[6], 0.125, places=6)
        before = cluster.getDeformerWeights()
        with self.assertRaises(ValueError):
            cluster.setDeformerWeights([0.1, 0.2], vertices=[mesh.getVertex(4), 4])
        self.assertEqual(cluster.getDeformerWeights(), before)

    def test_plug_path_indices_are_read_as_numbers(self):
        """名前の中の番号(先頭の0を含む)を数として読む。"""
        node = mlib.getNode(self.make("plusMinusAverage", "pma"))
        cases = (("input1D[007]", "input1D[7]"), ("input3D[2].input3Dx", "input3D[2].input3Dx"), ("i3[12].i3y", "input3D[12].input3Dy"))
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(str(mlib.getPlug(node.getFullName() + "." + text)), node.getFullName() + "." + expected)

    def test_default_tangents_of_fast_set_key(self):
        """fastで新しいキーを打つと、Mayaの既定の接線になる。fastで使えない型(fixed・入力側のstep)はautoにする。

        Mayaは既定の接線にfixedや入力側のstepを設定できないため、その場合は既定の接線の照会の結果を差し替えて確かめる。
        """
        saved = cmds.keyTangent(query=True, g=True, inTangentType=True, outTangentType=True)
        query = cmds.keyTangent
        cases = (
            (("linear", "step"), False, ("linear", "step")),
            (("clamped", "spline"), False, ("clamped", "spline")),
            (("fixed", "fixed"), True, ("auto", "auto")),
            (("step", "linear"), True, ("auto", "linear")),
            (("stepnext", "stepnext"), True, ("auto", "stepnext")),
        )
        try:
            for index, (settings, replaced, expected) in enumerate(cases):
                with self.subTest(settings=settings):
                    curve = mlib.getNode(self.make("animCurveTL", f"curve{index}"))
                    if replaced:

                        def fake(*args, _settings=settings, **kwargs):
                            if kwargs.get("g") and kwargs.get("query"):
                                return list(_settings)
                            return query(*args, **kwargs)

                        with mock.patch.object(cmds, "keyTangent", side_effect=fake):
                            curve.setKey(1.0, 2.0, fast=True)
                    else:
                        cmds.keyTangent(g=True, inTangentType=settings[0], outTangentType=settings[1])
                        curve.setKey(1.0, 2.0, fast=True)
                    actual = (
                        cmds.keyTangent(curve.getFullName(), query=True, index=(0, 0), inTangentType=True)[0],
                        cmds.keyTangent(curve.getFullName(), query=True, index=(0, 0), outTangentType=True)[0],
                    )
                    self.assertEqual(actual, expected)
        finally:
            cmds.keyTangent(g=True, inTangentType=saved[0], outTangentType=saved[1])

    def test_transform_keys_does_not_change_the_input(self):
        keys = [{"input": 2.0, "value": 3.0, "inAngle": 0.0, "inWeight": 1.0, "outAngle": 0.0, "outWeight": 1.0}]
        saved = copy.deepcopy(keys)
        result = _transform_keys(keys, scale=2.0, offset=1.0, value_scale=0.5)
        self.assertEqual(keys, saved)
        self.assertIsNot(result[0], keys[0])
        self.assertEqual((result[0]["input"], result[0]["value"]), (5.0, 1.5))

    def test_blend_shape_item_index_is_int(self):
        for weight, expected in ((1.0, 6000), (0.5, 5500), (-5, 0), (0.001, 5001)):
            with self.subTest(weight=weight):
                item = _weight_item(weight)
                self.assertIs(type(item), int)
                self.assertEqual(item, expected)

    def test_surface_params_and_derivatives(self):
        """整数のパラメーターも受け、微分はVectorのtupleで返す。接線は長さ1でワールドのマトリクスを掛ける。"""
        plane = cmds.nurbsPlane(name=self.name("plane"), constructionHistory=False, patchesU=2, patchesV=2, width=4)[0]
        cmds.xform(plane, rotation=(30, 45, 0), scale=(2, 1, 3))
        shape = mlib.getNode(plane).getShape()
        fn = om2.MFnNurbsSurface(shape.mpath())
        self.assertSequenceAlmostEqual(shape.getPointAtParam(1, 0), list(fn.getPointAtParam(1.0, 0.0, om2.MSpace.kObject))[:3], places=6)
        for second, count in ((False, 3), (True, 6)):
            with self.subTest(secondOrder=second):
                values = shape.getDerivativesAtParam(1, 0, secondOrder=second)
                self.assertIs(type(values), tuple)
                self.assertEqual(len(values), count)
                self.assertTrue(all(isinstance(value, mlib.Vector) for value in values))
        matrix = shape.mpath().inclusiveMatrix()
        for derivative, actual in zip(fn.tangents(0.5, 0.25, om2.MSpace.kObject), shape.getTangentsAtParam(0.5, 0.25, ws=True)):
            expected = (om2.MVector(derivative) * matrix).normal()
            self.assertSequenceAlmostEqual(actual, expected, places=6)
        curve = cmds.curve(name=self.name("curve"), degree=3, point=[(0, 0, 0), (1, 1, 0), (2, -1, 0), (3, 0, 0)])
        values = mlib.getNode(curve).getShape().getDerivativesAtParam(0.5, secondOrder=True)
        self.assertIs(type(values), tuple)
        self.assertEqual(len(values), 3)
        self.assertTrue(all(isinstance(value, mlib.Vector) for value in values))

    def test_limits_keep_the_other_side(self):
        """片側だけのリミット(Noneの側)は、今の値を保つ。並びはlistでもよい。"""
        node = mlib.getNode(self.make())
        node.setLimits(translateX=(-1.0, 2.0))
        node.setLimits(translateX=[None, 4.0])
        self.assertEqual(cmds.transformLimits(node.getFullName(), query=True, translationX=True), [-1.0, 4.0])
        self.assertEqual(cmds.transformLimits(node.getFullName(), query=True, enableTranslationX=True), [False, True])
        with self.assertRaises(TypeError):
            node.setLimits(translateX="0:1")


class NarrowedExceptionTest(_Case):
    """``except Exception`` を絞った所と、三項演算子・suppressにした所。"""

    def test_matrix_reinit_flag_matches_api_version(self):
        self.assertEqual(matrix_module._reinit_is_safe(), om2.MGlobal.apiVersion() >= 20240000)

    def test_channel_equals_returns_false_for_unreadable(self):
        """読めないアトリビュートはFalse(書込みへ委ねる)。同じ値はTrue、違う値はFalse。"""
        node = mlib.getNode(self.make())
        cmds.setAttr(node.getFullName() + ".translate", 1, 2, 3)
        self.assertTrue(node._channel_equals("translate", (1.0, 2.0, 3.0)))
        self.assertFalse(node._channel_equals("translate", (1.0, 2.0, 4.0)))
        self.assertFalse(node._channel_equals("translate", (1.0, 2.0)))
        for name in ("noSuchAttribute", "jointOrient"):
            with self.subTest(name=name):
                self.assertFalse(node._channel_equals(name, (0.0, 0.0, 0.0)))

    def test_joint_orient_on_a_non_joint_is_read_through_the_plug(self):
        """joint以外でjointOrientを読むときは、Plugから(rad)読む。jointは組み込みの読み取りで読む。"""
        node = mlib.getNode(self.make())
        cmds.addAttr(node.getFullName(), longName="jointOrient", attributeType="double3")
        for axis in "XYZ":
            cmds.addAttr(node.getFullName(), longName="jointOrient" + axis, attributeType="doubleAngle", parent="jointOrient")
        cmds.setAttr(node.getFullName() + ".jointOrient", 10, 20, 30)
        expected = om2.MEulerRotation(math.radians(10), math.radians(20), math.radians(30)).asQuaternion()
        self.assertSameRotation(node._component_quaternion("jointOrient"), expected)
        joint = mlib.getNode(self.make("joint", "joint"))
        cmds.setAttr(joint.getFullName() + ".jointOrient", 10, 20, 30)
        self.assertSameRotation(joint._component_quaternion("jointOrient"), expected)
        self.assertSameRotation(joint.getQuaternion(r=False, jo=True), expected)

    def test_set_matrix_round_trip_with_and_without_pivots(self):
        """ピボットの有無で式を分けた所: setMatrixの後のローカルのマトリクスが指定と同じ。"""
        target = mlib.Matrix(translate=(1, 2, 3), rotate=mlib.EulerRotate(0.3, -0.2, 0.5), scale=(1.5, 0.5, 2.0))
        # jointのrotatePivotは、setMatrixの後のマトリクスが指定と合わない(書換え前からの動き。報告済み)ため入れない。
        for kind, pivots in (("transform", False), ("transform", True), ("joint", False), ("joint", True)):
            with self.subTest(kind=kind, pivots=pivots):
                node = mlib.getNode(self.make(kind, kind + "#"))
                if pivots:
                    if kind == "transform":
                        cmds.setAttr(node.getFullName() + ".rotatePivot", 0.5, -1.0, 2.0)
                    cmds.setAttr(node.getFullName() + ".scalePivot", 1.0, 0.25, 0.0)
                    cmds.setAttr(node.getFullName() + ".rotateAxis", 15, 0, 30)
                if kind == "joint":
                    cmds.setAttr(node.getFullName() + ".jointOrient", 5, 10, 20)
                node.setMatrix(target)
                self.assertSequenceAlmostEqual(list(node.getMatrix()), list(target), places=6)

    def test_mesh_crease_is_rejected_and_plain_mesh_is_not(self):
        """クリース(エッジ・頂点のどちらか)があればValueErrorで何も変えない。無いメッシュは並べ替える。"""
        for crease in ("edge", "vertex", None):
            with self.subTest(crease=crease):
                reference, target = self._permuted_cubes()
                fn = om2.MFnMesh(target.mpath())
                if crease == "edge":
                    fn.setCreaseEdges([0], [1.0])
                elif crease == "vertex":
                    fn.setCreaseVertices([0], [1.0])
                before = [tuple(point) for point in fn.getPoints()]
                if crease is None:
                    target.reorderVertices(reference, match="position")
                    self.assertEqual(list(om2.MFnMesh(target.mpath()).getVertices()[1]), list(om2.MFnMesh(reference.mpath()).getVertices()[1]))
                    continue
                with self.assertRaises(ValueError) as context:
                    target.reorderVertices(reference, match="position")
                self.assertIn("クリース", str(context.exception))
                self.assertEqual([tuple(point) for point in om2.MFnMesh(target.mpath()).getPoints()], before)

    def _permuted_cubes(self):
        """頂点の番号だけを入れ替えた2つの立方体(基準と対象)を作る。"""
        cube = cmds.polyCube(name=self.name("reference#"), constructionHistory=False)[0]
        reference = mlib.getNode(cube).getShape()
        source = om2.MFnMesh(reference.mpath())
        permutation = [3, 6, 0, 7, 1, 5, 2, 4]
        points = source.getPoints()
        target_points = om2.MPointArray(points)
        for old, new in enumerate(permutation):
            target_points[new] = points[old]
        counts, connects = source.getVertices()
        transform = om2.MFnMesh().create(target_points, counts, [permutation[v] for v in connects])
        name = cmds.rename(om2.MFnDagNode(transform).fullPathName(), self.name("target#"))
        return reference, mlib.getNode(name).getShape()

    def test_failed_traceback_trim_keeps_maya_display(self):
        """トレースバックを省く処理が失敗しても、省かずにMayaの表示を作る。"""
        saved = os.environ.pop(logger.FULL_TRACEBACK_ENV, None)
        try:
            try:
                mlib.getNode(self.name("missing"))
            except RuntimeError:
                kind, error, trace = sys.exc_info()
            with mock.patch.object(logger, "_trimmed_traceback", side_effect=ValueError("injected")):
                text = maya_utils.formatGuiException(kind, error, trace, 2)
            self.assertIn("ノードが見つかりません", text)
            self.assertIn("getNode.py", text)
        finally:
            if saved is not None:
                os.environ[logger.FULL_TRACEBACK_ENV] = saved

    def test_writable_check_of_multi_elements(self):
        """マルチアトリビュートの要素は、全体がロックされていれば書き込めない。"""
        node = self.make("plusMinusAverage", "pma")
        cmds.setAttr(node + ".input1D[2]", 1.0)
        element = mlib.getPlug(node + ".input1D[2]").mplug()
        self.assertTrue(_is_writable(element))
        cmds.setAttr(node + ".input1D", lock=True)
        try:
            self.assertFalse(_is_writable(element))
        finally:
            cmds.setAttr(node + ".input1D", lock=False)

    def test_not_unique_message_suggests_the_first_match(self):
        """一意でない名前の例外は、表示した最初の一致をフルパスの例に挙げる。"""
        groups = [self.make(text=f"grp{index}") for index in range(2)]
        for group in groups:
            self.make(text="dup", parent=group)
        with self.assertRaises(RuntimeError) as context:
            mlib.getNode(self.name("dup"))
        message = str(context.exception)
        shown = message.split("(", 1)[1].split(", ", 1)[0]
        self.assertTrue(shown.startswith("'|"))
        self.assertIn(f"{shown}のようなフルパスを使うか", message)


class WrapAndCacheTest(_Case):
    """``Nodes._wrap`` の型の選び方と、名前を変えたキャッシュ。"""

    def test_nodes_wrap_picks_the_plural_class(self):
        joints = [mlib.getNode(self.make("joint", "j#")) for _ in range(2)]
        transform = mlib.getNode(self.make())
        mesh = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        skin = mlib.getNode(cmds.skinCluster([j.getFullName() for j in joints], mesh, toSelectedBones=True, name=self.name("skin"))[0])
        cases = (
            (Nodes, joints, mlib.Joints, True),
            (Nodes, [skin], mlib.SkinClusters, True),
            (Nodes, [joints[0], transform], mlib.Nodes, False),
            (Nodes, [], mlib.Nodes, False),
            (mlib.Joints, joints, mlib.Joints, False),
        )
        for cls, items, expected, promoted in cases:
            with self.subTest(cls=cls.__name__, expected=expected.__name__):
                result = cls._wrap(items)
                self.assertIs(type(result), expected)
                self.assertEqual(bool(result.__dict__.get("_promoted")), promoted)
                self.assertEqual(list(result), items)
        promoted = Nodes._wrap(joints)
        promoted.append(transform)
        self.assertIs(type(promoted), mlib.Nodes)
        # _wrap は、呼んだクラス自身の型を変えない(次の呼び出しに残らない)。
        self.assertIs(type(Nodes._wrap([transform])), mlib.Nodes)

    def test_reload_keeps_caches_working(self):
        """名前を変えたキャッシュが、読み直した後も使われる。

        読み直すと、このファイルの先頭でimportしたクラスが古くなるため、このファイルで最後に実行される名前にしてある。
        """
        mlib.reload()
        # 読み直した後のモジュールを使う。
        from mlib import util as reloaded_util
        from mlib.core import registry as reloaded_registry
        from mlib.nodes import transform as reloaded_transform

        # util: om2の型の判定と、利用者の派生クラスが持つ値の判定。
        self.assertFalse(mlib.Vector(1, 2, 3) == om2.MPoint(1, 2, 3))
        self.assertIn(om2.MPoint, reloaded_util._om2_types)

        class Tagged(mlib.Vector):
            pass

        value = Tagged(1, 2, 3)
        value.tag = "kept"
        copied = copy.copy(value)
        self.assertEqual(copied.tag, "kept")
        self.assertIn(Tagged, reloaded_util._stateful_types)
        # registry: 版で違う型名の読み替えと、型の継承。
        real = reloaded_registry._real_node_type("multDoubleLinear")
        self.assertEqual(reloaded_registry._real_node_type("multDL"), real)
        self.assertEqual(reloaded_registry._real_type_cache.get("multDL"), real)
        node = mlib.createNode("multDL", name=self.name("mdl"))
        self.assertEqual(cmds.nodeType(node.getFullName()), real)
        self.assertTrue(node.isType("multDoubleLinear"))
        joint = mlib.getNode(self.make("joint", "joint"))
        self.assertIsInstance(joint, mlib.Joint)
        self.assertTrue(joint.isType("transform"))
        self.assertEqual(reloaded_registry._inherited_types_cache["joint"][0], "joint")
        network = mlib.getNode(self.make("network", "net"))
        generated = type(network)
        self.assertIn(mlib.nodes.Node._registry, list(reloaded_registry._generating_registries))
        reloaded_registry._clear_type_hierarchy_cache()
        self.assertEqual(reloaded_registry._inherited_types_cache, {})
        self.assertEqual(reloaded_registry._real_type_cache, {})
        self.assertEqual(mlib.nodes.Node._registry._generated, {})
        self.assertIsNot(type(mlib.getNode(network.getFullName())), generated)
        # transform: アトリビュートの照会のキャッシュ。
        transform = mlib.getNode(self.make())
        cmds.setAttr(transform.getFullName() + ".tx", 4)
        self.assertEqual(transform.getMatrix().translate, mlib.Translate(4, 0, 0))
        self.assertIn("matrix", reloaded_transform._transform_attributes)

    def test_double3_value_types(self):
        node = mlib.getNode(self.make())
        cmds.addAttr(node.getFullName(), longName="custom", attributeType="double3")
        for axis in "XYZ":
            cmds.addAttr(node.getFullName(), longName="custom" + axis, attributeType="double", parent="custom")
        cases = (
            ("translate", mlib.Translate),
            ("t", mlib.Translate),
            ("rotate", mlib.EulerRotate),
            ("scale", mlib.Scale),
            ("shear", mlib.Shear),
            ("rotatePivot", mlib.Vector),
            ("rotateAxis", mlib.Vector),
            ("custom", mlib.Vector),
        )
        for name, expected in cases:
            with self.subTest(name=name):
                self.assertIs(type(node.getPlug(name).get()), expected)


class JsonHelpersTest(_Case):
    """``_current_fps`` と ``ValidationReport._add_skipped``・``warn``。"""

    def test_current_fps_follows_the_time_unit(self):
        saved = cmds.currentUnit(query=True, time=True)
        try:
            for unit, fps in (("film", 24.0), ("ntsc", 30.0), ("pal", 25.0), ("game", 15.0), ("ntscf", 60.0)):
                with self.subTest(unit=unit):
                    cmds.currentUnit(time=unit)
                    self.assertAlmostEqual(json_file._current_fps(), fps, places=9)
                    self.assertIs(type(json_file._current_fps()), float)
        finally:
            cmds.currentUnit(time=saved)

    def test_add_skipped_records_name_and_reason(self):
        report = ValidationReport()
        self.assertIsNone(report._add_skipped("pCube1.tx", "locked"))
        report._add_skipped("pCube1.tx", "locked")
        report._add_skipped("pCube1.ty", "connected")
        self.assertEqual(report.skipped, ["pCube1.tx: locked", "pCube1.tx: locked", "pCube1.ty: connected"])
        self.assertTrue(report.valid)
        self.assertEqual(report.missing, [])
        self.assertEqual(repr(report), "ValidationReport(missing=0, skipped=3, errors=0)")
        listed = report.skipped
        listed.clear()
        self.assertEqual(len(report.skipped), 3)

    def test_warn_message_is_japanese(self):
        """warn は見つからないもの・飛ばしたものの件数を、日本語の1回の警告にまとめる。"""
        report = ValidationReport()
        report._add_missing("pCube1")
        report._add_skipped("pCube1.tx", "locked")
        report._add_skipped("pCube1.ty", "connected")
        with mock.patch.object(logger, "warning") as warning:
            report.warn("PoseSnapshot")
        self.assertEqual(warning.call_count, 1)
        message = warning.call_args[0][0] % warning.call_args[0][1:]
        self.assertTrue(message.startswith("PoseSnapshot: 1件が見つかりません("), message)
        self.assertIn("2件を飛ばしました(", message)
        self.assertNotIn("skipped", message.split("(")[0])
        with mock.patch.object(logger, "warning") as warning:
            ValidationReport().warn("PoseSnapshot")
        warning.assert_not_called()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
