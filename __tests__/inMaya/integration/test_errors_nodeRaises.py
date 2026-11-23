"""ノードのクラスの公開メソッドについて、docstring の Raises に書かれた「無効なノード」の RuntimeError を確かめる。

削除したノード・形状データを持たない空のシェイプのラッパーでメソッドを呼び、``assertRaises`` で
RuntimeError になることと、例外の後にシーンのノードの数が変わらないことを確かめる。
引数の型・値・ロックの例外は ``test_errors_nodeRaisesArguments.py`` で確かめる。

cmds を呼ぶメソッド(Camera の set 系・``getDeformerTools``・コンストレイントのキャッシュ・
``SkinCluster.addInfluences`` 等)も、cmds の ValueError でなく mlib の RuntimeError になることを確かめる。
"""

import os
import shutil
import sys
import tempfile
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _RaisesCase(NamespaceCase):
    """作るノードがすべてこのテストの名前空間に入るよう、現在の名前空間を切り替える。"""

    PREFIX = "mlibSpecErrNodeRaises_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        cmds.namespace(setNamespace=self.ns)

    def tearDown(self):
        cmds.namespace(setNamespace=":")
        super().tearDown()

    def node(self, kind):
        """cmds.createNode で作ったノードのラッパーを返す。"""
        if kind == "inverseMatrix":
            # inverseMatrix は matrixNodes プラグインのノード。
            cmds.loadPlugin("matrixNodes", quiet=True)
        return mlib.getNode(cmds.createNode(kind, skipSelect=True))

    def cube(self):
        """履歴なしの polyCube を作り、transform の名前を返す。"""
        return cmds.polyCube(constructionHistory=False)[0]

    def shape(self, transform):
        """transform の最初のシェイプのラッパーを返す。"""
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def joints(self, *points):
        """点の順に親子にした joint を作り、名前を返す。"""
        cmds.select(clear=True)
        result = [cmds.joint(position=point) for point in points]
        cmds.select(clear=True)
        return result

    def kill(self, node):
        """ノードを削除し、ラッパーが無効になったことを確かめて返す。"""
        cmds.delete(node.getFullName())
        self.assertFalse(node.isValid())
        return node

    def assertFailsWithoutChange(self, error, function, *args, **kwargs):
        """例外の型と、例外の後にシーンのノードの数が変わらないことを確かめる。"""
        before = len(cmds.ls())
        with self.assertRaises(error):
            function(*args, **kwargs)
        self.assertEqual(len(cmds.ls()), before)


class AnimCurveTest(_RaisesCase):
    """削除した animCurve と、キーの無い animCurve。"""

    def curve(self, kind="animCurveTL"):
        name = cmds.createNode(kind, skipSelect=True)
        cmds.setKeyframe(name, time=1, value=0)
        cmds.setKeyframe(name, time=10, value=5)
        return mlib.getNode(name)

    def test_deleted_curve(self):
        cases = (
            ("animCurveTL", "isWeighted", ()),
            ("animCurveTL", "findClosestIndex", (3,)),
            ("animCurveTL", "insertKey", (3,)),
            ("animCurveTL", "replaceKeys", ([(1, 2)],)),
            ("animCurveTL", "getKeyframes", ()),
            ("animCurveTL", "addKeys", ([{"time": 20, "value": 1}],)),
            ("animCurveTA", "eulerFilter", ()),
        )
        for kind, method, args in cases:
            with self.subTest(method=method):
                curve = self.kill(self.curve(kind))
                self.assertFailsWithoutChange(RuntimeError, getattr(curve, method), *args)

    def test_curve_without_keys(self):
        """findClosestIndex・insertKey はキーの無いカーブで RuntimeError。キーは増えない。"""
        curve = self.node("animCurveTL")
        for method in ("findClosestIndex", "insertKey"):
            with self.subTest(method=method):
                self.assertFailsWithoutChange(RuntimeError, getattr(curve, method), 3)
                self.assertEqual(cmds.keyframe(curve.getFullName(), query=True, keyframeCount=True), 0)


class BlendShapeTest(_RaisesCase):
    """削除した blendShape。"""

    def test_deleted_blend_shape(self):
        cases = (("getTargetIndex", (0,)), ("getTargetItemIndices", (0,)), ("getTargetGeometry", (0,)), ("addBaseGeometry", ("cube",)))
        for method, args in cases:
            with self.subTest(method=method):
                base, target = self.cube(), self.cube()
                node = mlib.getNode(cmds.blendShape(target, base)[0])
                args = tuple(self.cube() if value == "cube" else value for value in args)
                self.kill(node)
                self.assertFailsWithoutChange(RuntimeError, getattr(node, method), *args)


class CameraTest(_RaisesCase):
    """削除したカメラの Shape。"""

    CASES = (
        ("getDepthOfFieldRange", (), {}),
        ("getFieldOfView", (), {}),
        ("getCenterOfInterestPoint", (), {}),
        ("getViewDirection", (), {}),
        ("getUpDirection", (), {}),
        ("setUpDirection", ((0, 1, 0),), {}),
        ("getProjectionMatrix", (), {}),
        ("getRenderingFrustum", (1.5,), {}),
        ("getViewingFrustum", (1.5,), {}),
        ("getViewParameters", (1.5,), {}),
        ("getPortFieldOfView", (640, 480), {}),
        ("getPostProjectionMatrix", (), {}),
        ("isOrtho", (), {}),
        ("setCenterOfInterestPoint", ((0, 0, -5),), {"fast": True}),
        ("copyViewFrom", ("camera",), {"fast": True}),
        ("setVerticalLocked", (True,), {}),
        ("setFieldOfView", (40.0,), {}),
        ("setNearFocusDistance", (5.0,), {}),
        ("setFarFocusDistance", (50.0,), {}),
        ("setAspectRatio", (1.5,), {}),
    )

    def test_deleted_camera(self):
        for method, args, flags in self.CASES:
            with self.subTest(method=method):
                camera = mlib.getNode(cmds.camera()[1])
                args = tuple(mlib.getNode(cmds.camera()[1]) if value == "camera" else value for value in args)
                self.kill(camera)
                self.assertFailsWithoutChange(RuntimeError, getattr(camera, method), *args, **flags)


class DagNodeTest(_RaisesCase):
    """削除した DAG ノード。"""

    def test_deleted_transform(self):
        cases = (("getSetsAndMembers", ()), ("isInUnderworld", ()), ("isInModel", ()), ("deleteHistory", ()))
        for method, args in cases:
            with self.subTest(method=method):
                node = self.kill(mlib.getNode(self.cube()))
                self.assertFailsWithoutChange(RuntimeError, getattr(node, method), *args)

    def test_object_group_components(self):
        """形状に番号の無い groupId・削除した形状は RuntimeError。"""
        shape = self.shape(self.cube())
        self.assertFailsWithoutChange(RuntimeError, shape.getObjectGroupComponents, 12345)
        self.kill(shape)
        self.assertFailsWithoutChange(RuntimeError, shape.getObjectGroupComponents, 0)


class DagPoseTest(_RaisesCase):
    """削除した dagPose と、削除した skinCluster からの取得。"""

    def pose(self):
        joints = self.joints((0, 0, 0), (0, 1, 0))
        return mlib.getNode(cmds.dagPose(joints, save=True)), joints

    def test_deleted_pose(self):
        pose, joints = self.pose()
        other, _ = self.pose()
        self.kill(pose)
        with self.subTest(method="removeMembers"):
            self.assertFailsWithoutChange(RuntimeError, pose.removeMembers, joints[1])
        with self.subTest(method="merge"):
            self.assertFailsWithoutChange(RuntimeError, pose.merge, [other])
            self.assertTrue(other.isValid())

    def test_from_deleted_skin_cluster(self):
        joints = self.joints((0, -1, 0), (0, 1, 0))
        skin = mlib.getNode(cmds.skinCluster(joints, self.cube(), toSelectedBones=True)[0])
        self.kill(skin)
        self.assertFailsWithoutChange(RuntimeError, mlib.DagPose.fromSkinCluster, skin)


class GeometryFilterTest(_RaisesCase):
    """削除したデフォーマー(cluster)。"""

    def test_deleted_deformer(self):
        cases = (
            ("getGeometry", (), {"input": True, "geometryIndex": 0}),
            ("getGeometry", (), {"input": True}),
            ("getGeometry", (), {"geometryIndex": 0}),
            ("getGeometryIndices", (), {}),
            ("getDeformerTools", (), {}),
        )
        for method, args, flags in cases:
            with self.subTest(method=method, flags=flags):
                deformer = self.kill(mlib.getNode(cmds.cluster(self.cube())[0]))
                self.assertFailsWithoutChange(RuntimeError, getattr(deformer, method), *args, **flags)


class JointTest(_RaisesCase):
    """削除した joint と、削除した要素を含む Joints。"""

    def test_deleted_joint(self):
        cases = (("getPreferredAngle", ()), ("getChainFromHere", ()), ("insertJoints", (1,)), ("getPolePosition", ()))
        for method, args in cases:
            with self.subTest(method=method):
                names = self.joints((0, 0, 0), (0, 1, 0), (1, 2, 0))
                joint = mlib.getNode(names[0])
                self.kill(joint)
                self.assertFailsWithoutChange(RuntimeError, getattr(joint, method), *args)

    def test_joints_with_deleted_element(self):
        """Joints.setRadius・setSegmentScaleCompensate は無効な要素を含むと RuntimeError。残りの値も変わらない。"""
        cases = (("setRadius", (2.0,), "radius", 1.0), ("setSegmentScaleCompensate", (False,), "segmentScaleCompensate", True))
        for method, args, attribute, before in cases:
            for fast in (False, True):
                with self.subTest(method=method, fast=fast):
                    names = self.joints((0, 0, 0), (0, 1, 0))
                    joints = mlib.Joints([mlib.getNode(name) for name in names])
                    cmds.delete(names[1])
                    self.assertFailsWithoutChange(RuntimeError, getattr(joints, method), *args, fast=fast)
                    self.assertEqual(cmds.getAttr(names[0] + "." + attribute), before)


class MeshTest(_RaisesCase):
    """形状データの無いメッシュ・削除したメッシュ。"""

    def test_empty_and_deleted_mesh(self):
        with self.subTest(case="empty getHoles"):
            self.assertFailsWithoutChange(RuntimeError, self.node("mesh").getHoles)
        with self.subTest(case="empty getClosestVertices"):
            self.assertFailsWithoutChange(RuntimeError, self.node("mesh").getClosestVertices, [(0, 0, 0)])
        with self.subTest(case="deleted getHoles"):
            mesh = self.kill(self.shape(self.cube()))
            self.assertFailsWithoutChange(RuntimeError, mesh.getHoles)


class NodeTest(_RaisesCase):
    """削除したノードの Node の照会、削除した要素を含む Nodes。"""

    def test_deleted_node(self):
        cases = (
            ("getDgTimer", (), {"state": True}),
            ("setDgTimer", (True,), {}),
            ("setDgTimer", (), {"reset": True}),
            ("getDgTimer", (0,), {}),
            ("getDgTimer", (), {"callbacks": True}),
            ("getContainer", (), {}),
            ("getPlugs", (), {"animatable": True}),
            ("hasUniqueName", (), {}),
        )
        for kind in ("transform", "multiplyDivide"):
            for method, args, flags in cases:
                with self.subTest(kind=kind, method=method, flags=flags):
                    node = self.kill(self.node(kind))
                    self.assertFailsWithoutChange(RuntimeError, getattr(node, method), *args, **flags)

    def test_nodes_with_deleted_element(self):
        """Nodes.setColors・callEach・getNames は無効な要素を含むと RuntimeError。残りの要素も変えない。"""
        for fast in (False, True):
            with self.subTest(method="setColors", fast=fast):
                first, second = self.node("transform"), self.node("transform")
                nodes = mlib.Nodes([first, second])
                self.kill(second)
                self.assertFailsWithoutChange(RuntimeError, nodes.setColors, [1, 2], fast=fast)
                self.assertFalse(cmds.getAttr(first.getFullName() + ".overrideEnabled"))
        with self.subTest(method="callEach"):
            first, second = self.node("transform"), self.node("transform")
            nodes = mlib.Nodes([first, second])
            self.kill(second)
            self.assertFailsWithoutChange(RuntimeError, nodes.callEach, "getName")
        with self.subTest(method="getNames full"):
            first, second = self.node("transform"), self.node("transform")
            nodes = mlib.Nodes([first, second])
            self.kill(second)
            with self.assertRaisesRegex(RuntimeError, "要素の番号1"):
                nodes.getNames(full=True)


class NurbsTest(_RaisesCase):
    """形状データの無い・削除した NURBS のカーブと曲面。"""

    CURVE = (("getNormalAtParam", (0.5,)), ("getMatricesAlong", (3,)), ("getDerivativesAtParam", (0.5,)))
    SURFACE = (
        ("getForm", ()),
        ("getPatchShaders", ()),
        ("getTrimBoundaryCurveData", (0, 0, 0)),
        ("isPointInTrimmedRegion", (0.5, 0.5)),
        ("getRayIntersection", ((0, 5, 0), (0, -1, 0))),
        ("isPointOnSurface", ((0, 0, 0),)),
        ("getDerivativesAtParam", (0.5, 0.5)),
        ("getNormalAtParam", (0.5, 0.5)),
        ("removeKnot", (0.5,)),
    )

    def curve(self):
        return self.shape(cmds.curve(degree=3, point=[(0, 0, 0), (1, 1, 0), (2, 0, 0), (3, 1, 0), (4, 0, 0)]))

    def surface(self):
        return self.shape(cmds.nurbsPlane(constructionHistory=False)[0])

    def test_curve(self):
        for method, args in self.CURVE:
            with self.subTest(method=method, case="empty"):
                self.assertFailsWithoutChange(RuntimeError, getattr(self.node("nurbsCurve"), method), *args)
            with self.subTest(method=method, case="deleted"):
                self.assertFailsWithoutChange(RuntimeError, getattr(self.kill(self.curve()), method), *args)
        for method, args in (("removeKnot", (1.0,)), ("makeMultipleEndKnots", ())):
            with self.subTest(method=method, case="deleted"):
                self.assertFailsWithoutChange(RuntimeError, getattr(self.kill(self.curve()), method), *args)

    def test_surface(self):
        for method, args in self.SURFACE:
            with self.subTest(method=method, case="empty"):
                self.assertFailsWithoutChange(RuntimeError, getattr(self.node("nurbsSurface"), method), *args)
            with self.subTest(method=method, case="deleted"):
                self.assertFailsWithoutChange(RuntimeError, getattr(self.kill(self.surface()), method), *args)


class ObjectSetTest(_RaisesCase):
    """削除した objectSet(自身または相手)。"""

    def objectSet(self):
        return mlib.getNode(cmds.sets(empty=True))

    def test_deleted_set(self):
        member = cmds.createNode("transform", skipSelect=True)
        with self.subTest(method="getMembers dagOnly"):
            self.assertFailsWithoutChange(RuntimeError, self.kill(self.objectSet()).getMembers, dagOnly=True)
        with self.subTest(method="addMembers exclusive"):
            self.assertFailsWithoutChange(RuntimeError, self.kill(self.objectSet()).addMembers, member, exclusive=True)
            self.assertFalse(cmds.listSets(object=member))
        with self.subTest(method="removeMembers all"):
            self.assertFailsWithoutChange(RuntimeError, self.kill(self.objectSet()).removeMembers, all=True)
        cases = [("combine", (mode,)) for mode in ("union", "intersection", "difference")] + [("isSubSet", ())]
        for method, args in cases:
            with self.subTest(method=method, args=args, case="other"):
                self.assertFailsWithoutChange(RuntimeError, getattr(self.objectSet(), method), self.kill(self.objectSet()), *args)
            with self.subTest(method=method, args=args, case="self"):
                self.assertFailsWithoutChange(RuntimeError, getattr(self.kill(self.objectSet()), method), self.objectSet(), *args)


class ConstraintCacheTest(_RaisesCase):
    """ターゲットが1つで、キャッシュが不要なコンストレイントの createCache は RuntimeError。"""

    def test_single_target(self):
        for kind in ("orientConstraint", "parentConstraint"):
            with self.subTest(kind=kind):
                target = cmds.createNode("transform", skipSelect=True)
                driven = cmds.createNode("transform", skipSelect=True)
                constraint = mlib.getNode(getattr(cmds, kind)(target, driven)[0])
                self.assertFailsWithoutChange(RuntimeError, constraint.createCache, 1, 10)

    def test_deleted_constraint(self):
        """削除したコンストレイントの createCache・deleteCache は RuntimeError。"""
        for kind in ("orientConstraint", "parentConstraint"):
            for method, args in (("createCache", (1, 10)), ("deleteCache", ())):
                with self.subTest(kind=kind, method=method):
                    targets = [cmds.createNode("transform", skipSelect=True) for _ in range(2)]
                    driven = cmds.createNode("transform", skipSelect=True)
                    constraint = self.kill(mlib.getNode(getattr(cmds, kind)(targets, driven)[0]))
                    self.assertFailsWithoutChange(RuntimeError, getattr(constraint, method), *args)


class ReferenceTest(_RaisesCase):
    """削除した reference ノード。"""

    def test_deleted_reference_node(self):
        for method in ("getCopyNumbers", "removeEdits"):
            with self.subTest(method=method):
                self.assertFailsWithoutChange(RuntimeError, getattr(self.kill(self.node("reference")), method))
        for method in ("getEditNodeNames", "getEditAttrNames"):
            with self.subTest(method=method, case="onReferenceNode"):
                live = self.node("reference")
                self.assertFailsWithoutChange(RuntimeError, getattr(live, method), onReferenceNode=self.kill(self.node("reference")))


class ShadingEngineTest(_RaisesCase):
    """削除した shadingEngine。"""

    def test_deleted_shading_engine(self):
        for flags in ({"plug": True}, {}):
            with self.subTest(method="getShader", flags=flags):
                engine = mlib.getNode(cmds.sets(renderable=True, noSurfaceShader=True, empty=True))
                self.assertFailsWithoutChange(RuntimeError, self.kill(engine).getShader, **flags)


class SkinClusterTest(_RaisesCase):
    """削除した skinCluster。"""

    def test_deleted_skin_cluster(self):
        cases = (
            ("getInfluenceIndex", ("joint",)),
            ("recacheBindMatrices", ()),
            ("getBlendWeights", ()),
            ("addInfluences", ("joint",)),
            ("setMoveJointsMode", (True,)),
        )
        for method, args in cases:
            with self.subTest(method=method):
                joints = self.joints((0, -1, 0), (0, 1, 0))
                skin = mlib.getNode(cmds.skinCluster(joints, self.cube(), toSelectedBones=True)[0])
                args = tuple(joints[0] if value == "joint" else value for value in args)
                self.kill(skin)
                self.assertFailsWithoutChange(RuntimeError, getattr(skin, method), *args)


class TransformTest(_RaisesCase):
    """削除した Transform と、削除したシェイプ・データの書き込み先。"""

    def test_deleted_transform(self):
        relative = {"relative": True}
        cases = (
            ("getPivot", (), {"translation": True}),
            ("setPivot", ((1, 2, 3),), {"translation": True}),
            ("getTransformation", (), {}),
            ("getRotateOrder", (), {}),
            ("setTranslation", ((1, 0, 0),), relative),
            ("setRotate", ((10, 0, 0),), relative),
            ("setScale", ((2, 1, 1),), relative),
            ("setShear", ((0.1, 0, 0),), relative),
            ("eulerFilter", (), {}),
        )
        for method, args, flags in cases:
            with self.subTest(method=method, flags=flags):
                node = self.kill(self.node("transform"))
                self.assertFailsWithoutChange(RuntimeError, getattr(node, method), *args, **flags)

    def test_add_shape(self):
        """addShape は自身かシェイプが無効なら RuntimeError。シェイプの親は変わらない。"""
        with self.subTest(case="self"):
            shape = self.shape(cmds.circle(constructionHistory=False)[0])
            parent = shape.getParent().getFullName()
            self.assertFailsWithoutChange(RuntimeError, self.kill(self.node("transform")).addShape, shape)
            self.assertEqual(shape.getParent().getFullName(), parent)
        with self.subTest(case="shape"):
            shape = self.kill(self.shape(cmds.circle(constructionHistory=False)[0]))
            self.assertFailsWithoutChange(RuntimeError, self.node("transform").addShape, shape)

    def test_curve_shapes_data(self):
        """setCurveShapesData・importCurveShapes は自身が無効なら RuntimeError。"""
        source = mlib.getNode(cmds.circle(constructionHistory=False)[0])
        data = source.getCurveShapesData()
        with self.subTest(method="setCurveShapesData"):
            self.assertFailsWithoutChange(RuntimeError, self.kill(self.node("transform")).setCurveShapesData, data)
        with self.subTest(method="importCurveShapes"):
            path = _output_file(self, "curves.json")
            source.exportCurveShapes(path)
            self.assertFailsWithoutChange(RuntimeError, self.kill(self.node("transform")).importCurveShapes, path)


def _output_file(case, name):
    """``__tests__/_output/temp`` に一時ファイルのパスを作り、テストの後に消す。"""
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "_output", "temp")
    try:
        os.makedirs(root, exist_ok=True)
        directory = tempfile.mkdtemp(prefix="mlibErrNodeRaises_", dir=root)
    except OSError:
        directory = tempfile.mkdtemp(prefix="mlibErrNodeRaises_")
    case.addCleanup(shutil.rmtree, directory, True)
    return os.path.join(directory, name)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
