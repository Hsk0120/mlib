"""ノードのクラスの公開メソッドについて、docstring の Raises に書かれた引数・ロック・ファイルの例外を確かめる。

引数の型(TypeError)・値(ValueError)・番号(IndexError)・未対応の条件(NotImplementedError)・
読み込めないファイル(OSError)・ロックや接続で書き込めない場合(RuntimeError)を ``assertRaises`` で確かめ、
例外の後にシーンのノードの数と、書き込もうとした値・接続が変わらないことも確かめる。
無効なノードの RuntimeError は ``test_errors_nodeRaises.py`` で確かめる。

Mayaが例外にせず黙って何もしない場合(ロックしたピボットへの ``setPivot(translation=True)`` など)も、
mlibが書き込む前に拒否することを確かめる。
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

from mlib.plugs.plug import DeletedAttributeError


class _ArgumentCase(NamespaceCase):
    """作るノードがすべてこのテストの名前空間に入るよう、現在の名前空間を切り替える。"""

    PREFIX = "mlibSpecErrNodeArgs_"
    CLEAR_SELECTION = True
    UNLOCK_NODES = True

    def setUp(self):
        super().setUp()
        cmds.namespace(setNamespace=self.ns)

    def tearDown(self):
        cmds.namespace(setNamespace=":")
        super().tearDown()

    def node(self, kind):
        """cmds.createNode で作ったノードのラッパーを返す。"""
        return mlib.getNode(cmds.createNode(kind, skipSelect=True))

    def cube(self, history=False):
        """polyCube を作り、transform の名前を返す。"""
        return cmds.polyCube(constructionHistory=history)[0]

    def shape(self, transform):
        """transform の最初のシェイプのラッパーを返す。"""
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def joints(self, *points):
        """点の順に親子にした joint を作り、名前を返す。"""
        cmds.select(clear=True)
        result = [cmds.joint(position=point) for point in points]
        cmds.select(clear=True)
        return result

    def lock(self, node, attribute):
        """アトリビュートをロックし、そのPlugの名前を返す。"""
        plug = node.getName(full=True) + "." + attribute
        cmds.setAttr(plug, lock=True)
        return plug

    def temp_file(self, name):
        """``__tests__/_output/temp`` に一時ファイルのパスを作り、テストの後にフォルダーごと消す。"""
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "_output", "temp")
        try:
            os.makedirs(root, exist_ok=True)
            directory = tempfile.mkdtemp(prefix="mlibErrNodeArgs_", dir=root)
        except OSError:
            directory = tempfile.mkdtemp(prefix="mlibErrNodeArgs_")
        self.addCleanup(shutil.rmtree, directory, True)
        return os.path.join(directory, name)

    def assertFails(self, error, function, *args, state=None, **kwargs):
        """例外の型と、例外の後にノードの数と ``state()`` の値が変わらないことを確かめる。"""
        before = (len(cmds.ls()), state() if state else None)
        with self.assertRaises(error):
            function(*args, **kwargs)
        self.assertEqual((len(cmds.ls()), state() if state else None), before)


class AnimCurveTest(_ArgumentCase):
    """単位・時刻・番号・許容値の例外。キーの値は変わらない。"""

    def curve(self):
        curve = self.node("animCurveTL")
        cmds.setKeyframe(curve.getName(full=True), time=1, value=0)
        cmds.setKeyframe(curve.getName(full=True), time=10, value=5)
        return curve

    def keys(self, curve):
        name = curve.getName(full=True)
        return (cmds.keyframe(name, query=True, timeChange=True), cmds.keyframe(name, query=True, valueChange=True))

    def test_argument_errors(self):
        curve = self.curve()
        cases = (
            (TypeError, "getKeyValues", (), {"unit": 1}),
            (TypeError, "getKeyValues", (), {"timeUnit": 1}),
            (TypeError, "findClosestIndex", (None,), {}),
            (TypeError, "findClosestIndex", (3,), {"timeUnit": 1}),
            (TypeError, "addKey", (None,), {}),
            (TypeError, "addKey", (3,), {"timeUnit": 1}),
            (TypeError, "findClosestIndex", ("x",), {}),
            (TypeError, "addKey", ("x",), {}),
            (IndexError, "scaleKey", (2,), {"index": 5}),
            (ValueError, "reduceKeys", (-1,), {}),
            (ValueError, "reduceKeys", (float("nan"),), {}),
            (ValueError, "reduceKeys", (1,), {"timeUnit": "bad"}),
        )
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                self.assertFails(error, getattr(curve, method), *args, state=lambda: self.keys(curve), **flags)


class BlendShapeTest(_ArgumentCase):
    """ターゲット・ベース・頂点・接続の例外。ターゲットのデータは変わらない。"""

    def blend_shape(self):
        base, target = self.cube(), self.cube()
        cmds.move(0, 1, 0, target + ".vtx[0]", relative=True)
        node = mlib.getNode(cmds.blendShape(target, base)[0])
        # 接続したターゲット形状の変位は、最初に読んだときに計算される。読んでから比べる。
        node.getTargetDeltas(0)
        self.data(node)
        return node

    def data(self, node):
        item = node.getName(full=True) + ".inputTarget[0].inputTargetGroup[0].inputTargetItem[6000]"
        return (cmds.getAttr(item + ".inputComponentsTarget"), cmds.listConnections(item + ".inputGeomTarget", plugs=True))

    def test_argument_errors(self):
        node = self.blend_shape()
        cases = (
            (ValueError, "getTargetItemIndices", (5,), {}),
            (ValueError, "getTargetItemIndices", (0,), {"base": "cube"}),
            (ValueError, "getTargetGeometry", (5,), {}),
            (ValueError, "getTargetGeometry", (0,), {"base": "cube"}),
            (TypeError, "removeTarget", (None,), {"inBetween": 0.5}),
            (TypeError, "removeTarget", (0,), {"inBetween": "a"}),
            (IndexError, "setTargetDeltas", (0, {100: (1, 0, 0)}), {"disconnect": True}),
            (TypeError, "resetTargetVertices", (0, 1.5), {}),
            (TypeError, "resetTargetVertices", (0,), {"tolerance": "a"}),
            (TypeError, "resetTargetVertices", (0,), {"tolerance": 0.0, "disconnect": 1}),
            (TypeError, "replaceTarget", (0, 1.5), {}),
        )
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                flags = {key: (self.cube() if value == "cube" else value) for key, value in flags.items()}
                self.assertFails(error, getattr(node, method), *args, state=lambda: self.data(node), **flags)

    def test_connected_target_without_disconnect(self):
        """ターゲット形状が接続されていて disconnect=False なら RuntimeError。接続も変位も残る。"""
        cases = (("resetTargetVertices", (0, [0]), {}), ("resetTargetVertices", (0,), {"tolerance": 10.0}), ("setTargetDeltas", (0, {1: (1, 0, 0)}), {}))
        for method, args, flags in cases:
            with self.subTest(method=method):
                node = self.blend_shape()
                before = self.data(node)
                self.assertTrue(before[1])
                self.assertFails(RuntimeError, getattr(node, method), *args, state=lambda: self.data(node), **flags)

    def test_set_targets_data_without_undo(self):
        """setTargetsData は Undo が無効でも例外にせず書き込む(docstring のとおり)。"""
        data = self.blend_shape().getTargetsData()
        node = mlib.getNode(cmds.blendShape(self.cube())[0])
        state = cmds.undoInfo(query=True, state=True)
        self.addCleanup(cmds.undoInfo, stateWithoutFlush=state)
        cmds.undoInfo(stateWithoutFlush=False)
        report = node.setTargetsData(data, mode="empty")
        cmds.undoInfo(stateWithoutFlush=state)
        self.assertTrue(report.valid)
        self.assertEqual(len(node.getTargetNames()), 1)

    def test_import_missing_file(self):
        """importTargets は読み込めないファイルで OSError。"""
        node = self.blend_shape()
        self.assertFails(OSError, node.importTargets, self.temp_file("missing.json"), state=lambda: self.data(node))


class CameraTest(_ArgumentCase):
    """カメラの設定の引数とロックの例外。カメラの値は変わらない。"""

    def camera(self):
        return mlib.getNode(cmds.camera()[1])

    def state(self, camera):
        name = camera.getName(full=True)
        attributes = ("focalLength", "verticalFilmAperture", "horizontalFilmAperture", "centerOfInterest", "nearClipPlane")
        transform = camera.getParent().getName(full=True)
        values = [cmds.getAttr(name + "." + attribute) for attribute in attributes]
        values.append(cmds.camera(name, query=True, verticalLock=True))
        values.append(tuple(cmds.xform(transform, query=True, matrix=True, worldSpace=True)))
        return values

    def test_argument_errors(self):
        nan = float("nan")
        cases = (
            (TypeError, "setVerticalLocked", (1,), {}),
            (TypeError, "setFieldOfView", (30,), {"vertical": 1}),
            (ValueError, "setFieldOfView", (nan,), {}),
            (ValueError, "setFieldOfView", (500,), {}),
            (ValueError, "setFieldOfView", (30,), {"unit": "bad"}),
            (ValueError, "setFocusDistance", (), {"near": 0}),
            (ValueError, "setFocusDistance", (), {"far": -1}),
            (ValueError, "setAspectRatio", (0,), {}),
            (ValueError, "setAspectRatio", (float("inf"),), {}),
            (TypeError, "setDirection", ("abc",), {"kind": "up"}),
            (ValueError, "setDirection", ((0, 0, 0),), {"kind": "up"}),
            (ValueError, "setDirection", ((0, 0, -1),), {"kind": "up"}),
            (ValueError, "setDirection", ((0, nan, 0),), {"kind": "up"}),
            (TypeError, "setPoint", ("abc", True), {"kind": "centerOfInterest", "fast": True}),
            (TypeError, "setPoint", ((0, 0, -5),), {"kind": "centerOfInterest", "worldSpace": True, "ws": True, "fast": True}),
            (ValueError, "setPoint", ((0, nan, -5), True), {"kind": "centerOfInterest", "fast": True}),
            (ValueError, "setPoint", ((0, 0, 0), True), {"kind": "centerOfInterest", "fast": True}),
            (TypeError, "getFrustum", ("a",), {"kind": "rendering"}),
            (ValueError, "getFrustum", (0,), {"kind": "rendering"}),
            (TypeError, "setView", (None, (0, 0, -1), (0, 1, 0), 30, 1.5), {"fast": True}),
            (TypeError, "setView", ((0, 0, 0), (0, 0, -1), (0, 1, 0), 30, 1.5), {"fast": 1}),
            (TypeError, "copyViewFrom", ("transform",), {"fast": True}),
            (TypeError, "copyViewFrom", ("camera",), {"fast": 1}),
            (NotImplementedError, "copyViewFrom", ("camera",), {}),
        )
        camera = self.camera()
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                args = tuple(self.resolve(value) for value in args)
                self.assertFails(error, getattr(camera, method), *args, state=lambda: self.state(camera), **flags)

    def resolve(self, value):
        if value == "camera":
            other = self.camera()
            cmds.setAttr(other.getParent().getName(full=True) + ".translate", 1, 2, 3)
            return other
        if value == "transform":
            return self.node("transform")
        return value

    def test_locked_center_of_interest(self):
        """setPoint(kind="centerOfInterest", check=True) は centerOfInterest がロックされていると RuntimeError。"""
        camera = self.camera()
        self.lock(camera, "centerOfInterest")
        self.assertFails(RuntimeError, camera.setPoint, (0, 0, -3), True, kind="centerOfInterest", fast=True, check=True, state=lambda: self.state(camera))


class DagNodeTest(_ArgumentCase):
    """DAG ノードの引数・ロックの例外。"""

    def test_argument_errors(self):
        transform = self.cube()
        node = mlib.getNode(transform)
        with self.subTest(method="getSetsAndMembers"):
            self.assertFails(TypeError, node.getSetsAndMembers, renderableOnly=1)
        with self.subTest(method="getObjectGroupComponents"):
            self.assertFails(TypeError, self.shape(transform).getObjectGroupComponents, 1.5)


class DagPoseTest(_ArgumentCase):
    """dagPose の引数の例外。"""

    def test_remove_members_type(self):
        joints = self.joints((0, 0, 0), (0, 1, 0))
        pose = mlib.getNode(cmds.dagPose(joints, save=True))

        def members():
            return cmds.dagPose(pose.getName(full=True), query=True, members=True)

        self.assertFails(TypeError, pose.removeMembers, 1.5, state=members)


class GeometryFilterTest(_ArgumentCase):
    """デフォーマー(cluster)の groupId・コピー先の例外。"""

    def test_argument_errors(self):
        deformer = mlib.getNode(cmds.cluster(self.cube())[0])
        with self.subTest(method="copyDeformerWeightsTo"):
            weights = deformer.getName(full=True) + ".weightList[0].weights"

            def state():
                return cmds.getAttr(weights, multiIndices=True)

            self.assertFails(RuntimeError, deformer.copyDeformerWeightsTo, self.ns + ":noSuchDeformer", state=state)


class IkHandleTest(_ArgumentCase):
    """IkHandle.setChain の例外。チェーンは変わらない。"""

    def handle(self):
        joints = self.joints((0, 0, 0), (0, 1, 0), (0, 2, 1))
        handle = mlib.getNode(cmds.ikHandle(startJoint=joints[0], endEffector=joints[2], solver="ikSCsolver")[0])
        return handle, joints

    def chain(self, handle):
        return cmds.ikHandle(handle.getName(full=True), query=True, jointList=True)

    def test_set_chain_errors(self):
        handle, joints = self.handle()
        other = self.joints((5, 0, 0), (5, 1, 0))
        cases = ((TypeError, ("transform", joints[2])), (ValueError, (joints[2], joints[0])), (ValueError, (joints[0], other[1])))
        for error, args in cases:
            with self.subTest(args=args):
                args = tuple(self.node("transform") if value == "transform" else value for value in args)
                self.assertFails(error, handle.setChain, *args, state=lambda: self.chain(handle))

    def test_set_chain_rejects_invalid_or_locked(self):
        with self.subTest(case="locked"):
            handle, joints = self.handle()
            cmds.lockNode(handle.getName(full=True), lock=True)
            self.assertFails(RuntimeError, handle.setChain, joints[0], joints[1], state=lambda: self.chain(handle))
            cmds.lockNode(handle.getName(full=True), lock=False)
        with self.subTest(case="deleted"):
            handle, joints = self.handle()
            cmds.delete(handle.getName(full=True))
            self.assertFails(RuntimeError, handle.setChain, joints[0], joints[1])


class JointTest(_ArgumentCase):
    """joint のロック・引数の例外。"""

    def test_locked_attributes(self):
        cases = (("setSegmentScaleCompensate", "segmentScaleCompensate", False), ("setRadius", "radius", 2.0))
        for method, attribute, value in cases:
            for fast in (False, True):
                with self.subTest(method=method, fast=fast):
                    joint = mlib.getNode(self.joints((0, 0, 0))[0])
                    plug = self.lock(joint, attribute)
                    self.assertFails(RuntimeError, getattr(joint, method), value, fast=fast, state=lambda: cmds.getAttr(plug))

    def test_reset_scale_orientation_on_locked_joint(self):
        names = self.joints((0, 0, 0), (0, 1, 0))
        joint = mlib.getNode(names[0])
        cmds.lockNode(names[0], lock=True)
        self.assertFails(RuntimeError, joint.resetScaleOrientation, state=lambda: cmds.getAttr(names[1] + ".jointOrient"))

    def test_bone_segments_space_flags(self):
        joint = mlib.getNode(self.joints((0, 0, 0), (0, 1, 0))[0])
        for args, flags in (((1,), {}), ((True,), {"ws": True})):
            with self.subTest(args=args, flags=flags):
                self.assertFails(TypeError, joint.getBoneSegments, *args, **flags)


class MeshTest(_ArgumentCase):
    """メッシュの照会・編集の引数の例外。頂点・法線・色・セットは変わらない。"""

    def mesh(self, colored=False):
        mesh = self.shape(self.cube())
        if colored:
            cmds.polyColorPerVertex(mesh.getName(full=True) + ".vtx[*]", rgb=(1, 0, 0), colorDisplayOption=True)
        return mesh

    def state(self, mesh):
        name = mesh.getName(full=True)
        return (
            cmds.polyColorSet(name, query=True, allColorSets=True),
            cmds.polyColorSet(name, query=True, currentColorSet=True),
            cmds.polyUVSet(name, query=True, allUVSets=True),
            cmds.polyNormalPerVertex(name + ".vtxFace[0][0]", query=True, xyz=True),
            cmds.polyColorPerVertex(name + ".vtx[0]", query=True, rgb=True) if cmds.polyColorSet(name, query=True, allColorSets=True) else None,
            cmds.xform(name + ".vtx[*]", query=True, translation=True, objectSpace=True),
        )

    def test_argument_errors(self):
        nan = float("nan")
        cases = (
            (TypeError, "getVertexNormals", (1,), {}),
            (TypeError, "getVertexNormals", (True,), {"ws": True}),
            (IndexError, "getVertexNormals", (), {"perFace": True, "faceVertices": [(99, 0)]}),
            (IndexError, "getVertexNormals", (), {"perFace": True, "faceVertices": [(0, 99)]}),
            (IndexError, "setFaceVertexNormals", ([(0, 1, 0)],), {"faceVertices": [(99, 0)]}),
            (IndexError, "setFaceVertexNormals", (), {"locked": True, "faceVertices": [(99, 0)]}),
            (TypeError, "getTangentData", (1,), {}),
            (TypeError, "getTangentData", (True,), {"ws": True}),
            (TypeError, "getFaceVertexTangents", (), {"uvSet": 1}),
            (TypeError, "getFaceVertexTangents", (1,), {}),
            (IndexError, "getFaceVertexTangents", (), {"faceVertices": [(99, 0)]}),
            (TypeError, "getFaceVertexTangents", (), {"binormal": True, "uvSet": 1}),
            (IndexError, "getFaceVertexTangents", (), {"binormal": True, "faceVertices": [(99, 0)]}),
            (TypeError, "getMirrorVertexMap", (1.5,), {}),
            (TypeError, "getMirrorVertexMap", (), {"tolerance": "a"}),
            (TypeError, "getMirrorVertexMap", (), {"worldSpace": 1}),
            (TypeError, "getMirrorVertexMap", (), {"worldSpace": True, "ws": True}),
            (TypeError, "getClosestVertices", (1.5,), {}),
            (TypeError, "getClosestVertices", ([("a", "b", "c")],), {}),
            (TypeError, "getPointsAtUV", ("a", 0.5), {}),
            (TypeError, "getPointsAtUV", (0.5, 0.5), {"uvSet": 1}),
            (ValueError, "getPointsAtUV", (nan, 0.5), {}),
            (ValueError, "getPointsAtUV", (0.5, 0.5), {"tolerance": -1}),
            (ValueError, "getPointsAtUV", (0.5, 0.5), {"uvSet": "nope"}),
            (TypeError, "getVertexColors", (), {"perFace": True, "colorSet": 1}),
            (TypeError, "getVertexColors", (), {"perFace": True, "faceVertices": 1.5}),
            (ValueError, "getVertexColors", (), {"perFace": True, "colorSet": "nope"}),
            (IndexError, "getVertexColors", (), {"perFace": True, "faceVertices": [(99, 0)]}),
            (TypeError, "setVertexColors", ([(1, 0, 0)],), {"perFace": True, "colorSet": 1}),
            (IndexError, "setVertexColors", ([(1, 0, 0)],), {"perFace": True, "faceVertices": [(99, 0)]}),
            (IndexError, "setVertexColors", ([(1, 0, 0)],), {"vertices": [99]}),
            (TypeError, "renameSet", (1, "x"), {}),
            (TypeError, "renameSet", ("map1", 1), {}),
            (TypeError, "setCurrentSet", (1,), {"kind": "color"}),
            (ValueError, "setCurrentSet", ("",), {"kind": "color"}),
            (ValueError, "setCurrentSet", ("nope",), {"kind": "color"}),
            (TypeError, "createSet", (1,), {"kind": "color"}),
            (ValueError, "createSet", ("",), {"kind": "color"}),
            (TypeError, "renameSet", (1, "x"), {"kind": "color"}),
            (ValueError, "renameSet", ("colorSet1", ""), {"kind": "color"}),
            (ValueError, "renameSet", ("nope", "x"), {"kind": "color"}),
            (TypeError, "deleteSet", (1,), {"kind": "color"}),
            (ValueError, "deleteSet", ("",), {"kind": "color"}),
            (ValueError, "deleteSet", ("nope",), {"kind": "color"}),
        )
        mesh = self.mesh(colored=True)
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                self.assertFails(error, getattr(mesh, method), *args, state=lambda: self.state(mesh), **flags)

    def test_existing_color_set_names(self):
        """createSet・renameSet(kind="color")は、すでにある名前で ValueError。"""
        mesh = self.mesh(colored=True)
        current = cmds.polyColorSet(mesh.getName(full=True), query=True, currentColorSet=True)[0]
        mesh.createSet("extra", kind="color")
        for method, args in (("createSet", ("extra",)), ("renameSet", (current, "extra"))):
            with self.subTest(method=method):
                self.assertFails(ValueError, getattr(mesh, method), *args, kind="color", state=lambda: self.state(mesh))

    def test_locked_mesh(self):
        """法線・面頂点の色の編集は、ロックされたメッシュで RuntimeError。"""
        cases = (
            ("setFaceVertexNormals", ([(0, 1, 0)],), {"faceVertices": [(0, 0)]}),
            ("setFaceVertexNormals", (), {"locked": True, "faceVertices": [(0, 0)]}),
            ("setVertexColors", ([(0, 1, 0)],), {"perFace": True, "faceVertices": [(0, 0)]}),
        )
        for method, args, flags in cases:
            with self.subTest(method=method, flags=flags):
                mesh = self.mesh(colored=True)
                cmds.lockNode(mesh.getName(full=True), lock=True)
                self.assertFails(RuntimeError, getattr(mesh, method), *args, state=lambda: self.state(mesh), **flags)

    def test_fast_mirror_with_history(self):
        """fast=True の mirror は、inMesh に入力があると NotImplementedError。頂点は変わらない。"""
        mesh = self.shape(self.cube(history=True))
        cmds.move(1, 0, 0, mesh.getName(full=True) + ".vtx[0]", relative=True)
        self.assertFails(NotImplementedError, mesh.mirror, fast=True, state=lambda: self.state(mesh))


class NodeTest(_ArgumentCase):
    """Node の比較・交換の引数の型。"""

    def test_unsupported_other(self):
        cases = (("swapConnections", "multiplyDivide", {}), ("isAncestorOf", "transform", {}), ("isAncestorOf", "transform", {"direct": True}))
        for method, kind, flags in cases:
            with self.subTest(method=method, flags=flags):
                self.assertFails(TypeError, getattr(self.node(kind), method), 1.5, **flags)
        with self.subTest(method="isAncestorOf", case="direct type"):
            self.assertFails(TypeError, self.node("transform").isAncestorOf, self.node("transform"), direct=1)


class NurbsCurveTest(_ArgumentCase):
    """NURBS カーブの編集の例外。CV とノットは変わらない。"""

    def curve(self):
        return self.shape(cmds.curve(degree=3, point=[(0, 0, 0), (1, 1, 0), (2, 0, 0), (3, 1, 0), (4, 0, 0), (5, 1, 0)]))

    def state(self, curve):
        name = curve.getName(full=True)
        return (cmds.getAttr(name + ".cv[*]"), cmds.getAttr(name + ".spans"))

    def test_argument_errors(self):
        curve = self.curve()
        cases = (
            (TypeError, "setKnots", ("abc",), {}),
            (TypeError, "setKnots", (1.5,), {}),
            (TypeError, "reduceKnotMultiplicity", ("a",), {}),
            (TypeError, "removeKnot", ("a",), {}),
            (ValueError, "removeKnot", (float("nan"),), {}),
            (TypeError, "getCollocatedCVGroups", (1,), {}),
            (TypeError, "getCollocatedCVGroups", (True,), {"ws": True}),
        )
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args):
                self.assertFails(error, getattr(curve, method), *args, state=lambda: self.state(curve), **flags)

    def test_locked_curve(self):
        for method, args in (("removeKnot", (1.0,)), ("makeMultipleEndKnots", ())):
            with self.subTest(method=method):
                curve = self.curve()
                cmds.lockNode(curve.getName(full=True), lock=True)
                self.assertFails(RuntimeError, getattr(curve, method), *args, state=lambda: self.state(curve))

    def test_fast_mirror_with_history(self):
        curve = self.shape(cmds.circle()[0])
        self.assertFails(NotImplementedError, curve.mirror, fast=True, state=lambda: self.state(curve))


class NurbsSurfaceTest(_ArgumentCase):
    """NURBS 曲面の例外。CV は変わらない。"""

    def surface(self, patches=1):
        return self.shape(cmds.nurbsPlane(constructionHistory=False, patchesU=patches)[0])

    def test_argument_errors(self):
        surface = self.surface()

        def cvs():
            return cmds.getAttr(surface.getName(full=True) + ".cv[*][*]")

        cases = ((TypeError, "removeKnot", (0.5,), {"all": 1}),)
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                self.assertFails(error, getattr(surface, method), *args, state=cvs, **flags)

    def test_locked_surface(self):
        surface = self.surface(patches=2)
        cmds.lockNode(surface.getName(full=True), lock=True)
        self.assertFails(RuntimeError, surface.removeKnot, 0.5, state=lambda: cmds.getAttr(surface.getName(full=True) + ".spansU"))


class ObjectSetTest(_ArgumentCase):
    """objectSet の引数の例外。メンバーは変わらない。"""

    def test_argument_errors(self):
        object_set = mlib.getNode(cmds.sets(empty=True))

        def members():
            return cmds.sets(object_set.getName(full=True), query=True)

        transform = self.node("transform")
        cases = (
            (TypeError, "getMembers", (), {"dagOnly": True, "shadingOnly": 1}),
            (TypeError, "getMembers", (), {"dagOnly": 1}),
            (TypeError, "getMembers", (), {"dagOnly": True, "flatten": True}),
            (TypeError, "addMembers", (1.5,), {"forceElement": True}),
            (TypeError, "addMembers", (transform,), {"forceElement": 1}),
            (ValueError, "addMembers", (self.ns + ":noSuchObject",), {"forceElement": True}),
            (TypeError, "removeMembers", (), {"all": 1}),
            (TypeError, "combine", (transform,), {"mode": "union"}),
            (TypeError, "combine", (transform,), {"mode": "intersection"}),
            (TypeError, "combine", (transform,), {"mode": "difference"}),
            (TypeError, "combine", (object_set,), {"mode": 1}),
            (ValueError, "combine", (object_set,), {"mode": "xor"}),
            (TypeError, "isSubSet", (transform,), {}),
        )
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args):
                self.assertFails(error, getattr(object_set, method), *args, state=members, **flags)


class ConstraintCacheTest(_ArgumentCase):
    """createCache の時刻の型。"""

    def test_time_type(self):
        for kind in ("orientConstraint", "parentConstraint"):
            with self.subTest(kind=kind):
                targets = [cmds.createNode("transform", skipSelect=True) for _ in range(2)]
                driven = cmds.createNode("transform", skipSelect=True)
                constraint = mlib.getNode(getattr(cmds, kind)(*targets, driven)[0])
                self.assertFails(TypeError, constraint.createCache, "a", 10)


class ReferenceTest(_ArgumentCase):
    """リファレンスの照会・編集の引数の例外。"""

    def setUp(self):
        super().setUp()
        path = self.temp_file("referenced.ma")
        item = cmds.createNode("transform", skipSelect=True)
        cmds.select(item, replace=True)
        cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
        cmds.select(clear=True)
        namespace = "mlibSpecErrNodeArgsRef_" + self.ns.rsplit("_", 1)[-1]
        cmds.file(path, reference=True, namespace=":" + namespace)
        self.path = path
        self.reference_namespace = namespace
        self.reference = mlib.getNode(cmds.referenceQuery(path, referenceNode=True))

    def tearDown(self):
        # 名前空間を消す前にリファレンスを外す(読み込んだ名前空間は読み取り専用で消せないため)。
        cmds.namespace(setNamespace=":")
        if self.reference.isValid():
            cmds.file(self.path, removeReference=True)
        if cmds.namespace(exists=self.reference_namespace):
            cmds.namespace(removeNamespace=self.reference_namespace, deleteNamespaceContent=True)
        super().tearDown()

    def test_argument_errors(self):
        live = self.reference

        def locked():
            return cmds.getAttr(live.getName(full=True) + ".locked")

        transform = self.node("transform")
        cases = (
            (TypeError, "setReferenceLocked", (1,), {}),
            (TypeError, "cleanEdits", (), {"editCommand": 1}),
            (ValueError, "cleanEdits", (), {"editCommand": "bogus"}),
            (TypeError, "getEdits", (), {"what": "node", "editCommand": 1}),
            (ValueError, "getEdits", (), {"what": "node", "editCommand": "bogus"}),
            (TypeError, "getEdits", (), {"what": "node", "onReferenceNode": transform}),
            (TypeError, "getEdits", (), {"what": "attr", "editCommand": 1}),
            (ValueError, "getEdits", (), {"what": "attr", "editCommand": "bogus"}),
            (TypeError, "getEdits", (), {"what": "attr", "onReferenceNode": transform}),
        )
        for error, method, args, flags in cases:
            with self.subTest(method=method, flags=flags):
                self.assertFails(error, getattr(live, method), *args, state=locked, **flags)


class SkinClusterTest(_ArgumentCase):
    """skinCluster の引数・ロック・ファイルの例外。ウェイトと設定は変わらない。"""

    def skin(self, geometry=None):
        joints = self.joints((0, -1, 0), (0, 0, 0), (0, 1, 0))
        geometry = geometry or self.cube()
        node = mlib.getNode(cmds.skinCluster(joints, geometry, toSelectedBones=True)[0])
        return node, joints

    def state(self, node):
        name = node.getName(full=True)
        return (
            cmds.getAttr(name + ".weightList[0].weights"),
            cmds.getAttr(name + ".blendWeights", multiIndices=True),
            cmds.getAttr(name + ".dropoff"),
            cmds.getAttr(name + ".skinningMethod"),
            cmds.getAttr(name + ".normalizeWeights"),
            cmds.getAttr(name + ".maxInfluences"),
            cmds.skinCluster(name, query=True, influence=True),
        )

    def test_argument_errors(self):
        node, joints = self.skin()
        stranger = self.joints((9, 9, 9))[0]
        cases = (
            (TypeError, "setDropoffRate", (joints[0], "a"), {}),
            (TypeError, "setDropoffRate", (1.5, 4.0), {}),
            (ValueError, "setDropoffRate", (joints[0], 100.0), {}),
            (ValueError, "setDropoffRate", (stranger, 4.0), {}),
            (TypeError, "restoreBindPose", (1,), {}),
            (TypeError, "restoreBindPose", (True,), {"ws": True}),
            (TypeError, "removeInfluences", (), {"unused": True, "repair": 1}),
            (TypeError, "removeInfluences", (), {"unused": 1}),
            (TypeError, "removeInfluences", (joints[2],), {"requireAncestor": 1}),
            (TypeError, "removeInfluences", (joints[2],), {"transferToParent": 1}),
            (IndexError, "getWeights", (), {"vertex": 999}),
            (IndexError, "setWeights", ({joints[0]: 1.0},), {"vertex": 999, "normalize": True}),
            (TypeError, "getWeights", (), {"vertex": 0, "vertices": [0]}),
            (TypeError, "setWeights", ({joints[0]: 1.0},), {"vertex": 0}),
            (ValueError, "getBlendWeights", (), {"vertices": [0, 0]}),
            (IndexError, "getBlendWeights", (), {"vertices": [999]}),
            (ValueError, "setBlendWeights", ([0.5, 0.5],), {"vertices": [0, 0]}),
            (IndexError, "setBlendWeights", ([0.5],), {"vertices": [999]}),
            (ValueError, "setBlendWeights", ([0.5, 0.5],), {"vertices": [0]}),
            (ValueError, "setBlendWeights", ([2.0],), {"vertices": [0]}),
            (TypeError, "transferWeights", (1.5,), {}),
            (TypeError, "transferWeights", ([(joints[0], joints[1])],), {"fast": 1}),
            (TypeError, "transferWeights", ([(1.5, 2.5)],), {}),
            (TypeError, "setMoveJointsMode", (1,), {}),
            (TypeError, "normalizeWeights", (), {"force": True, "fast": 1}),
            (TypeError, "normalizeWeights", (), {"force": 1}),
            (TypeError, "normalizeWeights", (3,), {"force": True}),
            (TypeError, "getMode", (), {"kind": 1}),
            (ValueError, "getMode", (), {"kind": "blend"}),
            (ValueError, "setMode", ("post",), {"kind": "blend"}),
            (TypeError, "getMaxInfluences", (), {"maintain": 1}),
            (TypeError, "getInfluences", (), {"locked": 1}),
            (TypeError, "getInfluences", (), {"unused": 1}),
            (TypeError, "setMaxInfluences", (2,), {"maintain": 1}),
            (TypeError, "setMaxInfluences", (2,), {"fast": 1}),
        )
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                self.assertFails(error, getattr(node, method), *args, state=lambda: self.state(node), **flags)

    def test_unlocked_influences(self):
        """unlockedInfluences は型が不正なら TypeError、ロックを外せなければ RuntimeError。"""
        node, joints = self.skin()

        def enter(value):
            with node.unlockedInfluences(value):
                pass

        with self.subTest(case="type"):
            self.assertFails(TypeError, enter, 1.5, state=lambda: self.state(node))
        with self.subTest(case="locked"):
            cmds.setAttr(joints[0] + ".lockInfluenceWeights", True)
            plug = self.lock(mlib.getNode(joints[0]), "lockInfluenceWeights")
            self.assertFails(RuntimeError, enter, joints[0], state=lambda: cmds.getAttr(plug))

    def test_locked_settings(self):
        cases = (
            ("setDropoffRate", ("joint", 4.0), {}, "dropoff"),
            ("setMode", ("dualQuaternion",), {"kind": "skinning"}, "skinningMethod"),
            ("setMode", ("post",), {"kind": "normalize"}, "normalizeWeights"),
            ("setWeights", ("weights",), {"vertex": 0, "normalize": True}, "weightList"),
            ("setWeightsData", ("data",), {}, "weightList"),
        )
        for method, args, flags, attribute in cases:
            with self.subTest(method=method, attribute=attribute):
                node, joints = self.skin()
                data = node.getWeightsData()
                args = tuple(self.resolve(value, joints, data) for value in args)
                self.lock(node, attribute)
                self.assertFails(RuntimeError, getattr(node, method), *args, state=lambda: self.state(node), **flags)

    def resolve(self, value, joints, data):
        if value == "joint":
            return joints[0]
        if value == "weights":
            return {joints[0]: 1.0}
        if value == "data":
            return data
        return value

    def test_locked_node(self):
        for method, args, flags in (("setMoveJointsMode", (True,), {}), ("normalizeWeights", (), {"force": True})):
            with self.subTest(method=method):
                node, _ = self.skin()
                cmds.lockNode(node.getName(full=True), lock=True)
                self.assertFails(RuntimeError, getattr(node, method), *args, state=lambda: self.state(node), **flags)

    def test_curve_output(self):
        """出力が Mesh でない skinCluster では smoothWeights・getInfluenceVertices が NotImplementedError。"""
        node, joints = self.skin(cmds.circle(constructionHistory=False)[0])
        for method, args in (("smoothWeights", ()), ("getInfluenceVertices", (joints[0],))):
            with self.subTest(method=method):
                self.assertFails(NotImplementedError, getattr(node, method), *args, state=lambda: self.state(node))

    def test_import_missing_file(self):
        node, _ = self.skin()
        self.assertFails(OSError, node.importWeights, self.temp_file("missing.json"), state=lambda: self.state(node))


class TransformTest(_ArgumentCase):
    """Transform の引数・ロック・ファイルの例外。トランスフォームとジオメトリは変わらない。"""

    def state(self, node):
        name = node.getName(full=True)
        shapes = cmds.listRelatives(name, shapes=True, fullPath=True) or []
        points = [cmds.xform(shape + (".vtx[*]" if cmds.nodeType(shape) == "mesh" else ".cv[*]"), query=True, translation=True) for shape in shapes]
        return (tuple(cmds.xform(name, query=True, matrix=True)), cmds.xform(name, query=True, rotatePivot=True), points)

    def test_argument_errors(self):
        nan = float("nan")
        cases = (
            (TypeError, "deleteConstraints", (), {"fast": 1}),
            (TypeError, "mirrorGeometry", (), {"worldSpace": 1}),
            (TypeError, "mirrorGeometry", (1.5,), {}),
            (IndexError, "mirrorGeometry", (), {"indices": [999]}),
            (TypeError, "centerPivot", (1.5,), {}),
            (ValueError, "centerPivot", ([],), {}),
            (TypeError, "centerPivot", (), {"fast": 1}),
            (TypeError, "deleteUnusedIntermediateShapes", (), {"fast": 1}),
            (TypeError, "setTranslation", ("abc",), {"relative": True}),
            (TypeError, "setTranslation", ((1, 0, 0), 1), {"relative": True}),
            (TypeError, "setTranslation", ((1, 0, 0),), {"relative": 1}),
            (TypeError, "setTranslation", ((1, 0, 0),), {"relative": True, "at": 0}),
            (ValueError, "setTranslation", ((1, 0),), {"relative": True}),
            (ValueError, "setTranslation", ((1, 0, nan),), {"relative": True}),
            (TypeError, "setRotate", ((1, 0, 0),), {"relative": 1}),
            (TypeError, "setRotate", ("abc",), {"relative": True}),
            (ValueError, "setRotate", ((1, 0, nan),), {"relative": True}),
            (TypeError, "setScale", ((1, 1, 1),), {"relative": 1}),
            (TypeError, "setScale", ((2, 1, 1),), {"relative": True, "worldSpace": True}),
            (TypeError, "setShear", ((1, 1, 1),), {"relative": 1}),
            (TypeError, "setShear", ((2, 1, 1),), {"relative": True, "ws": True}),
            (TypeError, "setShear", ("abc",), {"relative": True}),
            (ValueError, "setShear", ((1, nan, 1),), {"relative": True}),
            (TypeError, "getScale", (1,), {}),
            (TypeError, "getScale", (True,), {"ws": True}),
            (TypeError, "getShear", (1,), {}),
            (TypeError, "getLimits", (), {"unit": 1}),
            (TypeError, "setPivot", ("abc",), {"translation": True}),
            (TypeError, "setPivot", (5,), {"translation": True}),
            (TypeError, "setPivot", ((1, "a", 3),), {"translation": True}),
            (ValueError, "setPivot", ((1, 2),), {"translation": True}),
            (TypeError, "setPivot", ((1, 2, 3),), {"translation": 1}),
            (TypeError, "setPivot", ((1, 2, 3),), {"translation": True, "fast": True}),
            (TypeError, "setPivot", ((1, 2, 3),), {"translation": True, "preserve": False}),
            (TypeError, "getPivot", (), {"translation": 1}),
        )
        node = mlib.getNode(self.cube())
        cmds.setAttr(node.getName(full=True) + ".translate", 1, 2, 3)
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                self.assertFails(error, getattr(node, method), *args, state=lambda: self.state(node), **flags)

    def test_center_pivots_on_other_components(self):
        """centerPivot(components) は別の Transform 下のコンポーネントで ValueError(fast でも同じ)。"""
        node = mlib.getNode(self.cube())
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.assertFails(ValueError, node.centerPivot, self.cube() + ".vtx[0]", fast=fast, state=lambda: self.state(node))

    def test_joint_fast_center_pivot(self):
        """fast の centerPivot は Joint で TypeError。"""
        joint = mlib.getNode(self.joints((0, 0, 0))[0])
        self.assertFails(TypeError, joint.centerPivot, fast=True, state=lambda: self.state(joint))

    def test_fast_mirror_geometry_with_history(self):
        node = mlib.getNode(self.cube(history=True))
        self.assertFails(NotImplementedError, node.mirrorGeometry, fast=True, state=lambda: self.state(node))

    def test_locked_channels(self):
        relative = {"relative": True}
        pivot = {"translation": True}
        cases = (
            ("setTranslation", ((1, 0, 0),), relative, "translate"),
            ("setRotate", ((10, 0, 0),), relative, "rotate"),
            ("setScale", ((2, 1, 1),), relative, "scale"),
            ("setShear", ((0.1, 0, 0),), relative, "shear"),
            ("mirrorTransform", (), {}, "translate"),
            # Mayaは例外にせず何もしないが、mlibはcheckに関係なく書き込む前に拒否する。
            ("setPivot", ((1, 2, 3),), pivot, "rotatePivot"),
            ("setPivot", ((1, 2, 3),), pivot, "rotatePivotTranslate"),
            ("setPivot", ((1, 2, 3),), pivot, "rotatePivotX"),
        )
        for method, args, flags, attribute in cases:
            with self.subTest(method=method, attribute=attribute):
                node = self.node("transform")
                cmds.setAttr(node.getName(full=True) + ".translate", 1, 2, 3)
                cmds.setAttr(node.getName(full=True) + ".shear", 0.5, 0.5, 0.5)
                self.lock(node, attribute)
                self.assertFails(RuntimeError, getattr(node, method), *args, state=lambda: self.state(node), **flags)

    def test_deleted_attribute_plug(self):
        """matchTransform・addConstraint は、アトリビュートを削除した Plug で DeletedAttributeError。"""
        for method, flags in (("matchTransform", {}), ("addConstraint", {"type": "parent"})):
            with self.subTest(method=method):
                node = self.node("transform")
                source = cmds.createNode("transform", skipSelect=True)
                cmds.addAttr(source, longName="extra", attributeType="double")
                plug = mlib.getPlug(source + ".extra")
                cmds.deleteAttr(source + ".extra")
                self.assertFails(DeletedAttributeError, getattr(node, method), plug, state=lambda: self.state(node), **flags)

    def test_import_missing_curve_file(self):
        node = self.node("transform")
        self.assertFails(OSError, node.importCurveShapes, self.temp_file("missing.json"), state=lambda: self.state(node))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
