"""ノードのクラスの公開メソッドについて、docstring の Raises のうち、ほかのテストで確かめていない残りを確かめる。

``test_errors_nodeRaises.py``(無効なノード)・``test_errors_nodeRaisesArguments.py``(引数・ロック・ファイル)で
書かなかった項目を、docstring の条件どおりの入力で ``assertRaises`` し、例外の後にシーンのノードの数と、
書き込もうとした値・接続が変わらないことも確かめる。

Mayaがロックを見ずに通すため、mlibがMayaを呼ぶ前に確かめる項目(``ObjectSet.removeMembers`` のロックなど)は
``LockedNodeTest`` で確かめる。
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


class _RemainingCase(NamespaceCase):
    """作るノードがすべてこのテストの名前空間に入るよう、現在の名前空間を切り替える。"""

    PREFIX = "mlibSpecErrNodeRemain_"
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

    def kill(self, node):
        """ノードを削除し、ラッパーが無効になったことを確かめて返す。"""
        cmds.delete(node.getName(full=True))
        self.assertFalse(node.isValid())
        return node

    def lock(self, name, attribute):
        """アトリビュートをロックし、そのPlugの名前を返す。"""
        plug = name + "." + attribute
        cmds.setAttr(plug, lock=True)
        return plug

    def temp_file(self, name):
        """``__tests__/_output/temp`` に一時ファイルのパスを作り、テストの後にフォルダーごと消す。"""
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "_output", "temp")
        try:
            os.makedirs(root, exist_ok=True)
            directory = tempfile.mkdtemp(prefix="mlibErrNodeRemain_", dir=root)
        except OSError:
            directory = tempfile.mkdtemp(prefix="mlibErrNodeRemain_")
        self.addCleanup(shutil.rmtree, directory, True)
        return os.path.join(directory, name)

    def assertFails(self, error, function, *args, state=None, **kwargs):
        """例外の型と、例外の後にノードの数と ``state()`` の値が変わらないことを確かめる。"""
        before = (len(cmds.ls()), state() if state else None)
        with self.assertRaises(error):
            function(*args, **kwargs)
        self.assertEqual((len(cmds.ls()), state() if state else None), before)


class AnimCurveTest(_RemainingCase):
    """setBreakdown の型の例外。キーとブレイクダウンの状態は変わらない。"""

    def test_set_breakdown_types(self):
        curve = self.node("animCurveTL")
        name = curve.getName(full=True)
        cmds.setKeyframe(name, time=1, value=0)
        cmds.setKeyframe(name, time=10, value=5)

        def state():
            return (cmds.keyframe(name, query=True, valueChange=True), cmds.keyframe(name, query=True, breakdown=True))

        for indices in (0, [0, 1]):
            with self.subTest(indices=indices):
                self.assertFails(TypeError, curve.getKeyframes(indices).setBreakdown, 1, state=state)


class BlendShapeTest(_RemainingCase):
    """ウェイトのPlugの型・baseWeightsの頂点番号・ターゲットの差し替えの例外。"""

    def blend_shape(self):
        base, target = self.cube(), self.cube()
        return mlib.getNode(cmds.blendShape(target, base)[0])

    def test_set_base_weights_out_of_range(self):
        """setTargetWeights(None, ...) は範囲外の頂点番号で IndexError。baseWeights は変わらない。"""
        node = self.blend_shape()
        plug = node.getName(full=True) + ".inputTarget[0].baseWeights"

        def state():
            return cmds.getAttr(plug, multiIndices=True)

        for weights in ({999: 0.5}, {-1: 0.5}):
            for fast in (False, True):
                with self.subTest(weights=weights, fast=fast):
                    self.assertFails(IndexError, node.setTargetWeights, None, weights, fast=fast, state=state)

    def test_replace_target_rejected_by_maya(self):
        """接続先がロックされていて Maya が接続を拒否すると、replaceTarget は RuntimeError。接続は変わらない。"""
        node = self.blend_shape()
        plug = self.lock(node.getName(full=True), "inputTarget[0].inputTargetGroup[0].inputTargetItem[6000].inputGeomTarget")
        replacement = self.cube()

        def state():
            return cmds.listConnections(plug, source=True, destination=False, plugs=True)

        self.assertFails(RuntimeError, node.replaceTarget, 0, replacement, state=state)


class CameraTest(_RemainingCase):
    """getFieldOfView の単位の値の例外。"""

    def test_get_field_of_view_unit(self):
        camera = mlib.getNode(cmds.camera()[1])
        self.assertFails(ValueError, camera.getFieldOfView, unit="bad")


class DagNodeTest(_RemainingCase):
    """visibility を書き込めない場合の RuntimeError。値と接続は変わらない。"""

    def visibility(self, node):
        plug = node.getName(full=True) + ".visibility"
        return (cmds.getAttr(plug), cmds.listConnections(plug, source=True, destination=False, plugs=True))

    def test_set_visibility_locked_or_connected(self):
        for case in ("locked", "connected"):
            for fast in (False, True):
                for check in (False, True):
                    with self.subTest(case=case, fast=fast, check=check):
                        node = self.node("transform")
                        if case == "locked":
                            self.lock(node.getName(full=True), "visibility")
                        else:
                            source = cmds.createNode("transform", skipSelect=True)
                            cmds.connectAttr(source + ".visibility", node.getName(full=True) + ".visibility")
                        self.assertFails(RuntimeError, node.setVisibility, False, fast=fast, check=check, state=lambda: self.visibility(node))

    def test_nodes_set_visibility_with_deleted_element(self):
        """Nodes.setVisibility は無効なノードを含むと RuntimeError。残りの要素も変えない。"""
        first, second = self.node("transform"), self.node("transform")
        nodes = mlib.Nodes([first, second])
        self.kill(second)
        self.assertFails(RuntimeError, nodes.setVisibility, False, state=lambda: self.visibility(first))

    def test_nodes_set_visibility_rejected_by_maya(self):
        """Nodes.setVisibility はロックされた要素で RuntimeError。その要素の値は変わらない。

        先に処理した要素は書き換わったまま残る(docstring は戻すことを約束していない)ので、ここでは確かめない。
        """
        first, second = self.node("transform"), self.node("transform")
        self.lock(second.getName(full=True), "visibility")
        self.assertFails(RuntimeError, mlib.Nodes([first, second]).setVisibility, False, state=lambda: self.visibility(second))


class DagPoseTest(_RemainingCase):
    """merge はロックされたポーズを書き換えず RuntimeError。ポーズとメンバーは変わらない。"""

    def test_merge_with_locked_pose(self):
        names = self.joints((0, 0, 0), (0, 1, 0))
        for case in ("target", "source"):
            with self.subTest(case=case):
                target = mlib.getNode(cmds.dagPose(names, save=True))
                source = mlib.getNode(cmds.dagPose(names, save=True))
                cmds.lockNode((target if case == "target" else source).getName(full=True), lock=True)

                def state():
                    return (cmds.dagPose(target.getName(full=True), query=True, members=True), source.isValid())

                self.assertFails(RuntimeError, target.merge, [source], deleteSources=True, state=state)


class GeometryFilterTest(_RemainingCase):
    """loadDeformerWeights はロックされたウェイトへ書き込めず RuntimeError。ウェイトは変わらない。"""

    def test_load_into_locked_weights(self):
        cases = (
            ("weightList[0].weights", False),
            ("weightList[0].weights", True),
            ("weightList[0].weights[1]", False),
            # fast は要素を1つずつ書くが、書く前に全部の要素を確かめるので、ロックしていない weights[0] も書かない。
            ("weightList[0].weights[1]", True),
        )
        for attribute, fast in cases:
            with self.subTest(attribute=attribute, fast=fast):
                deformer = mlib.getNode(cmds.cluster(self.cube())[0])
                path = self.temp_file("weights.json")
                deformer.dumpDeformerWeights(path)
                weights = deformer.getName(full=True) + ".weightList[0].weights"
                cmds.setAttr(weights + "[0]", 0.5)
                cmds.setAttr(weights + "[1]", 0.25)
                self.lock(deformer.getName(full=True), attribute)
                self.assertFails(RuntimeError, deformer.loadDeformerWeights, path, fast=fast, check=True, state=lambda: cmds.getAttr(weights))


class IkHandleTest(_RemainingCase):
    """setSolver の型・名前・スプラインIKの例外。ソルバーは変わらない。"""

    def solver(self, handle):
        return cmds.listConnections(handle.getName(full=True) + ".ikSolver", source=True, destination=False)

    def test_set_solver_errors(self):
        names = self.joints((0, 0, 0), (0, 1, 0), (0, 2, 1))
        handle = mlib.getNode(cmds.ikHandle(startJoint=names[0], endEffector=names[2], solver="ikSCsolver")[0])
        for error, solver in ((TypeError, 1), (ValueError, "bogus")):
            with self.subTest(solver=solver):
                self.assertFails(error, handle.setSolver, solver, state=lambda: self.solver(handle))

    def test_set_solver_on_spline_handle(self):
        names = self.joints((0, 0, 0), (0, 1, 0), (0, 2, 0), (0, 3, 0))
        handle = mlib.getNode(cmds.ikHandle(startJoint=names[0], endEffector=names[3], solver="ikSplineSolver")[0])
        self.assertFails(ValueError, handle.setSolver, "ikRPsolver", state=lambda: self.solver(handle))


class JointTest(_RemainingCase):
    """setDegreesOfFreedom の軸の文字の例外。jointType は変わらない。"""

    def test_set_degrees_of_freedom_values(self):
        name = self.joints((0, 0, 0))[0]
        joint = mlib.getNode(name)

        def state():
            return [cmds.getAttr(name + ".jointType" + axis) for axis in "XYZ"]

        for axes in ("xa", "xx"):
            for fast in (False, True):
                with self.subTest(axes=axes, fast=fast):
                    self.assertFails(ValueError, joint.setDegreesOfFreedom, axes, fast=fast, state=state)


class MeshTest(_RemainingCase):
    """UVシェルとカラーセットの複製の引数の例外。セットは変わらない。"""

    def test_argument_errors(self):
        mesh = self.shape(self.cube())
        name = mesh.getName(full=True)
        cmds.polyColorPerVertex(name + ".vtx[*]", rgb=(1, 0, 0), colorDisplayOption=True)
        current = cmds.polyColorSet(name, query=True, currentColorSet=True)[0]

        def state():
            return (cmds.polyColorSet(name, query=True, allColorSets=True), cmds.polyUVSet(name, query=True, allUVSets=True))

        cases = (
            (TypeError, "getShells", (), {"uv": True, "uvSet": 1}),
            (ValueError, "getShells", (), {"uv": True, "uvSet": ""}),
            (ValueError, "getShells", (), {"uv": True, "uvSet": "nope"}),
            (TypeError, "copySet", (1, "copied"), {"kind": "color"}),
            (TypeError, "copySet", (current, 1), {"kind": "color"}),
            (ValueError, "copySet", (current, ""), {"kind": "color"}),
            (ValueError, "copySet", ("nope", "copied"), {"kind": "color"}),
            (ValueError, "copySet", (current, current), {"kind": "color"}),
        )
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                self.assertFails(error, getattr(mesh, method), *args, state=state, **flags)


class NodeTest(_RemainingCase):
    """getSets の型・値と、削除したノードの isShared。"""

    def test_get_sets_type(self):
        node = self.node("transform")
        for error, value in ((TypeError, 1), (ValueError, "")):
            with self.subTest(type=value):
                self.assertFails(error, node.getSets, type=value)


class NurbsSurfaceTest(_RemainingCase):
    """曲面の照会の値・番号の例外。CV は変わらない。"""

    def test_param_values(self):
        surface = self.shape(cmds.nurbsPlane(constructionHistory=False)[0])
        nan = float("nan")
        cases = (
            ("getAtParam", (nan, 0.5), {"what": "tangents"}),
            ("getAtParam", (5.0, 0.5), {"what": "tangents"}),
            ("getAtParam", (nan, 0.5), {"what": "matrix"}),
            ("getAtParam", (0.5, 5.0), {"what": "matrix"}),
            ("getAtParam", (0.5, 0.5), {"what": "matrix", "aimAxis": "w"}),
            ("getAtParam", (0.5, 0.5), {"what": "matrix", "aimAxis": "x", "upAxis": "x"}),
        )
        for method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                self.assertFails(ValueError, getattr(surface, method), *args, state=lambda: cmds.getAttr(surface.getName(full=True) + ".cv[*][*]"), **flags)


class ReferenceTest(_RemainingCase):
    """入れ子のリファレンスの編集ロックと、Edit の照会・削除・ファイルの置き換えの引数の例外。"""

    def setUp(self):
        super().setUp()
        cmds.namespace(setNamespace=":")
        token = self.ns.rsplit("_", 1)[-1]
        child = self.temp_file("child.ma").replace("\\", "/")
        parent = os.path.join(os.path.dirname(child), "parent.ma").replace("\\", "/")
        item = cmds.createNode("transform", name="mlibSpecErrNodeRemainItem_" + token, skipSelect=True)
        cmds.select(item, replace=True)
        cmds.file(child, exportSelected=True, type="mayaAscii", force=True)
        cmds.select(clear=True)
        cmds.delete(item)
        # 子のファイルをリファレンスしたまま書き出し、子のリファレンスを持つ親のファイルを作る。
        child_namespace = "mlibSpecErrNodeRemainChild_" + token
        cmds.file(child, reference=True, namespace=":" + child_namespace)
        cmds.select(cmds.ls(child_namespace + ":*", type="transform"), replace=True)
        cmds.file(parent, exportSelected=True, preserveReferences=True, type="mayaAscii", force=True)
        cmds.select(clear=True)
        cmds.file(child, removeReference=True)
        if cmds.namespace(exists=child_namespace):
            cmds.namespace(removeNamespace=child_namespace, deleteNamespaceContent=True)
        self.reference_namespace = "mlibSpecErrNodeRemainRef_" + token
        cmds.file(parent, reference=True, namespace=":" + self.reference_namespace)
        self.outer = mlib.getNode(cmds.referenceQuery(parent, referenceNode=True))
        inner = cmds.referenceQuery(self.outer.getName(), child=True, referenceNode=True)
        self.inner = mlib.getNode(inner[0])
        cmds.namespace(setNamespace=self.ns)

    def tearDown(self):
        # 名前空間を消す前にリファレンスを外す(読み込んだ名前空間は読み取り専用で消せないため)。
        cmds.namespace(setNamespace=":")
        if self.outer.isValid():
            cmds.file(referenceNode=self.outer.getName(), removeReference=True)
        if cmds.namespace(exists=self.reference_namespace):
            cmds.namespace(removeNamespace=self.reference_namespace, deleteNamespaceContent=True)
        super().tearDown()

    def locked(self):
        return (cmds.getAttr(self.outer.getName(full=True) + ".locked"), cmds.getAttr(self.inner.getName(full=True) + ".locked"), self.outer.isLoaded())

    def test_nested_reference_lock(self):
        """入れ子のリファレンスの setReferenceLocked は NotImplementedError。"""
        self.assertFails(NotImplementedError, self.inner.setReferenceLocked, True, state=self.locked)

    def test_argument_errors(self):
        transform = self.node("transform")
        cases = (
            (TypeError, "getEdits", (), {"editCommand": 1}),
            (ValueError, "getEdits", (), {"editCommand": "bogus"}),
            (TypeError, "getEdits", (), {"onReferenceNode": transform}),
            (TypeError, "removeEdits", (), {"successful": 1}),
            (TypeError, "removeEdits", (), {"failed": 1}),
            (TypeError, "removeEdits", (), {"editCommand": 1}),
            (ValueError, "removeEdits", (), {"editCommand": ""}),
            (TypeError, "replaceFile", (1,), {}),
            (ValueError, "replaceFile", ("",), {}),
        )
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                self.assertFails(error, getattr(self.outer, method), *args, state=self.locked, **flags)

    def test_replace_with_missing_file(self):
        """存在しないファイルへの replaceFile は、Mayaを呼ぶ前に FileNotFoundError。参照先と読み込みの状態は変わらない。"""

        def state():
            return (self.outer.getFilename(), self.outer.isLoaded(), self.locked())

        for path in (self.temp_file("missing.ma"), "mlibSpecErrNodeRemainMissing.ma"):
            with self.subTest(path=path):
                self.assertFails(FileNotFoundError, self.outer.replaceFile, path, state=state)


class ScaleGeometryTest(_RemainingCase):
    """Shape・Transform の scaleGeometry は範囲外の番号で IndexError。頂点は変わらない。"""

    def test_out_of_range_indices(self):
        transform = self.cube()
        node = mlib.getNode(transform)

        def points():
            return cmds.xform(transform + ".vtx[*]", query=True, translation=True, objectSpace=True)

        for target in (node, self.shape(transform)):
            for indices in ([999], [-1]):
                for fast in (False, True):
                    with self.subTest(target=type(target).__name__, indices=indices, fast=fast):
                        self.assertFails(IndexError, target.scaleGeometry, 2.0, indices=indices, fast=fast, state=points)


class SkinClusterTest(_RemainingCase):
    """skinCluster の未対応の形状・ロック・不正なウェイトの例外。ウェイトとインフルエンスは変わらない。"""

    def skin(self, *geometries):
        names = self.joints((0, -1, 0), (0, 0, 0), (0, 1, 0))
        geometries = geometries or (self.cube(),)
        node = mlib.getNode(cmds.skinCluster(names, geometries[0], toSelectedBones=True)[0])
        for geometry in geometries[1:]:
            cmds.skinCluster(node.getName(full=True), edit=True, geometry=geometry)
        return node, names

    def state(self, node):
        name = node.getName(full=True)
        return (
            cmds.getAttr(name + ".weightList[0].weights"),
            cmds.getAttr(name + ".blendWeights", multiIndices=True),
            cmds.skinCluster(name, query=True, influence=True),
            cmds.listConnections(name + ".matrix", plugs=True, connections=True),
        )

    def test_unsupported_geometry(self):
        """出力が単一の Mesh でない skinCluster の NotImplementedError。"""
        curve_skin, curve_joints = self.skin(cmds.circle(constructionHistory=False)[0])
        double_skin, double_joints = self.skin(self.cube(), self.cube())
        sculpted = self.cube()
        cases = (
            (curve_skin, "setDropoffRate", (curve_joints[0], 4.0), {}),
            (double_skin, "setDropoffRate", (double_joints[0], 4.0), {}),
            (curve_skin, "invertShape", (sculpted,), {}),
            (curve_skin, "redistributeWeights", ([0],), {}),
            (double_skin, "transferWeights", ([(double_joints[0], double_joints[1])],), {"fast": True}),
        )
        for node, method, args, flags in cases:
            with self.subTest(node=node.getName(), method=method):
                self.assertFails(NotImplementedError, getattr(node, method), *args, state=lambda: self.state(node), **flags)

    def test_locked_weights(self):
        """ロックされたウェイトへ書き込めない場合の RuntimeError。"""
        path = self.temp_file("weights.json")
        cases = (
            ("weightList", "redistributeWeights", ([0],), {}),
            ("weightList", "transferWeights", ("pair",), {"fast": True, "check": True}),
            ("weightList", "transferWeights", ("pair",), {}),
            ("weightList[0].weights", "transferWeights", ("pair",), {}),
            ("weightList", "importWeights", ("path",), {"check": True}),
            ("blendWeights", "setBlendWeights", ([0.5],), {"vertices": [0]}),
            ("blendWeights", "setBlendWeights", ([0.5],), {"vertices": [0], "fast": True, "check": True}),
        )
        for attribute, method, args, flags in cases:
            with self.subTest(attribute=attribute, method=method, flags=flags):
                node, names = self.skin()
                if method == "importWeights":
                    node.exportWeights(path)
                args = tuple(path if value == "path" else [(names[0], names[1])] if value == "pair" else value for value in args)
                self.lock(node.getName(full=True), attribute)
                self.assertFails(RuntimeError, getattr(node, method), *args, state=lambda: self.state(node), **flags)

    def test_remove_unused_influences_rejected_by_maya(self):
        """matrix がロックされて外せない場合、removeInfluences(unused=True) は RuntimeError。インフルエンスと接続は残る。"""
        node, _ = self.skin()
        extra = self.joints((5, 5, 5))[0]
        cmds.skinCluster(node.getName(full=True), edit=True, addInfluence=extra, weight=0)
        self.lock(node.getName(full=True), "matrix")
        self.assertFails(RuntimeError, node.removeInfluences, unused=True, state=lambda: self.state(node))

    def test_unbind_deleted(self):
        node, _ = self.skin()
        self.assertFails(RuntimeError, self.kill(node).unbind)

    def test_force_normalize_invalid_weights(self):
        """負・非有限のウェイトがあると normalizeWeights(force=True) は ValueError。ウェイトは変わらない。"""
        for value in (-0.5, float("nan")):
            for fast in (False, True):
                with self.subTest(value=value, fast=fast):
                    node, _ = self.skin()
                    name = node.getName(full=True)
                    cmds.setAttr(name + ".normalizeWeights", 0)
                    cmds.setAttr(name + ".weightList[0].weights[0]", value)

                    def weights():
                        # nan は自身と等しくならないので、文字列にして比べる。
                        return repr(cmds.getAttr(name + ".weightList[0].weights"))

                    self.assertFails(ValueError, node.normalizeWeights, force=True, fast=fast, state=weights)


class TransformTest(_RemainingCase):
    """Transform の引数・回転の成分の組み合わせ・無効なノードの例外。トランスフォームは変わらない。"""

    def state(self, node):
        name = node.getName(full=True)
        return (tuple(cmds.xform(name, query=True, matrix=True)), cmds.xform(name, query=True, rotatePivot=True), cmds.getAttr(name + ".rotateAxis"))

    def test_argument_errors(self):
        nan = float("nan")
        cases = (
            (TypeError, "setMatrix", ("matrix",), {"fast": 1}),
            (TypeError, "setMatrix", ("matrix",), {"space": "world"}),
            (TypeError, "setMatrix", ("matrix",), {"worldSpace": True, "ws": True}),
            (TypeError, "setScale", ("abc",), {"relative": True}),
            (TypeError, "setScale", (True,), {"relative": True}),
            (TypeError, "setScale", (None,), {"relative": True}),
            (ValueError, "setScale", ((1, 2),), {"relative": True}),
            (ValueError, "setScale", ((1, nan, 1),), {"relative": True}),
            (ValueError, "setScale", (nan,), {"relative": True}),
            (ValueError, "getQuaternion", (), {"rotateAxis": True, "rotate": False, "jointOrient": True}),
            (ValueError, "getQuaternion", (), {"worldSpace": True, "rotateAxis": True, "rotate": False}),
            (ValueError, "setQuaternion", ((0, 0, 0),), {}),
            (ValueError, "setQuaternion", ((0, 0, nan, 1),), {}),
            (ValueError, "setQuaternion", ((0, 0, 0, 1),), {"worldSpace": True, "jointOrient": False}),
            (ValueError, "setQuaternion", ((0, 0, 0, 1),), {"preserve": True}),
            (ValueError, "setQuaternion", ((0, 0, 0, 1),), {"rotateAxis": True, "rotate": False, "preserve": True, "safe": True}),
            (TypeError, "getClosestAxisToVector", ("abc",), {}),
            (TypeError, "getClosestAxisToVector", ((1, 0, 0),), {"includeNegative": 1}),
        )
        node = mlib.getNode(self.cube())
        cmds.setAttr(node.getName(full=True) + ".translate", 1, 2, 3)
        cmds.setAttr(node.getName(full=True) + ".rotate", 10, 20, 30)
        for error, method, args, flags in cases:
            with self.subTest(method=method, args=args, flags=flags):
                args = tuple(mlib.Matrix() if value == "matrix" else value for value in args)
                self.assertFails(error, getattr(node, method), *args, state=lambda: self.state(node), **flags)

    def test_deleted_transform(self):
        cases = (("getClosestAxisToVector", ((1, 0, 0),)), ("getUnusedIntermediateShapes", ()), ("mirrorGeometry", ()))
        for method, args in cases:
            with self.subTest(method=method):
                node = self.kill(mlib.getNode(self.cube()))
                self.assertFails(RuntimeError, getattr(node, method), *args)

    def test_center_pivots_on_joint(self):
        """Joint の centerPivot(components) は、直下のシェイプの頂点を指定しても TypeError(fast でも同じ)。"""
        joint = mlib.getNode(self.joints((0, 0, 0))[0])
        shape = cmds.listRelatives(self.cube(), shapes=True, fullPath=True)[0]
        shape = cmds.parent(shape, joint.getName(full=True), shape=True, relative=True)[0]
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.assertFails(TypeError, joint.centerPivot, shape + ".vtx[0]", fast=fast, state=lambda: self.state(joint))


class LockedNodeTest(_RemainingCase):
    """Mayaがロックを見ずに通すため、mlibがMayaを呼ぶ前に確かめる RuntimeError(check に関係なく)。

    ノードのロック(lockNode)と、書き込む先のアトリビュートのロックで、何も変えずに例外にする。
    """

    def lock_node(self, node):
        """ノードを lockNode し、そのノードを返す。"""
        cmds.lockNode(node.getName(full=True), lock=True)
        return node

    def object_set(self):
        cube = self.cube()
        node = mlib.getNode(cmds.sets(cube, name="lockedSet"))
        return node, cube

    def test_object_set_remove(self):
        """removeMembers(メンバー指定・all=True)は、セットか dagSetMembers がロックされていると外さない。"""
        for case in ("node", "attribute", "element"):
            for remove_all in (False, True):
                with self.subTest(case=case, all=remove_all):
                    node, cube = self.object_set()
                    if case == "node":
                        self.lock_node(node)
                    elif case == "attribute":
                        self.lock(node.getName(full=True), "dagSetMembers")
                    else:
                        self.lock(node.getName(full=True), "dagSetMembers[0]")
                    args = () if remove_all else (cube,)

                    def state():
                        return cmds.sets(node.getName(full=True), query=True)

                    self.assertFails(RuntimeError, node.removeMembers, *args, all=remove_all, state=state)

    def test_mesh_set_vertex_colors(self):
        """setVertexColors は、ロックされたシェイプへ fast でも通常でも書かない。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                mesh = self.lock_node(self.shape(self.cube()))
                name = mesh.getName(full=True)

                def state():
                    return cmds.polyColorSet(name, query=True, allColorSets=True)

                self.assertFails(RuntimeError, mesh.setVertexColors, [(1, 0, 0)] * 8, fast=fast, state=state)

    def test_transform_mirror_geometry(self):
        """mirrorGeometry は、ロックされたシェイプや pnts へ、fast・check に関係なく書かない。"""
        for case in ("node", "pnts", "element"):
            for fast in (False, True):
                with self.subTest(case=case, fast=fast):
                    transform = mlib.getNode(self.cube())
                    cmds.move(1, 0, 0, transform.getName(full=True) + ".vtx[*]", relative=True)
                    shape = transform.getShape(all=True)[0]
                    if case == "node":
                        self.lock_node(shape)
                    elif case == "pnts":
                        self.lock(shape.getName(full=True), "pnts")
                    else:
                        self.lock(shape.getName(full=True), "pnts[0].pntx")
                    name = shape.getName(full=True)

                    def state():
                        return cmds.xform(name + ".vtx[*]", query=True, translation=True, objectSpace=True)

                    self.assertFails(RuntimeError, transform.mirrorGeometry, "x", fast=fast, state=state)

    def test_ik_handle_set_solver(self):
        """setSolver は、ハンドルか ikSolver がロックされていると切り替えない。"""
        for case in ("node", "attribute"):
            with self.subTest(case=case):
                names = self.joints((0, 0, 0), (0, 1, 0), (0, 2, 1))
                handle = mlib.getNode(cmds.ikHandle(startJoint=names[0], endEffector=names[2], solver="ikSCsolver")[0])
                if case == "node":
                    self.lock_node(handle)
                else:
                    self.lock(handle.getName(full=True), "ikSolver")

                def state():
                    return cmds.listConnections(handle.getName(full=True) + ".ikSolver", source=True, destination=False)

                self.assertFails(RuntimeError, handle.setSolver, "ikRPsolver", state=state)

    def test_blend_shape_add_base_geometry(self):
        """addBaseGeometry は、形状の無い transform・joint は ValueError、ロックされた blendShape へは RuntimeError。"""
        base, target = self.cube(), self.cube()
        node = mlib.getNode(cmds.blendShape(target, base)[0])

        def state():
            return cmds.blendShape(node.getName(full=True), query=True, geometry=True)

        for geometry in (cmds.createNode("transform", skipSelect=True), self.joints((0, 0, 0))[0]):
            with self.subTest(geometry=geometry):
                self.assertFails(ValueError, node.addBaseGeometry, geometry, state=state)
        extra = self.cube()
        self.lock_node(node)
        self.assertFails(RuntimeError, node.addBaseGeometry, extra, state=state)

    def skin(self):
        names = self.joints((0, -1, 0), (0, 0, 0), (0, 1, 0))
        node = mlib.getNode(cmds.skinCluster(names, self.cube(), toSelectedBones=True)[0])
        return node, names

    def skin_state(self, node):
        name = node.getName(full=True)
        return (
            cmds.getAttr(name + ".weightList[0].weights"),
            cmds.getAttr(name + ".weightList[1].weights"),
            cmds.skinCluster(name, query=True, influence=True),
            cmds.getAttr(name + ".nodeState"),
            cmds.listConnections(name, source=False, destination=True, plugs=True),
        )

    def test_skin_cluster_locked(self):
        """skinCluster か weightList がロックされていると、mirrorWeights・smoothWeights・unbind・transferWeights は何も変えない。"""
        cases = (
            ("node", "mirrorWeights", (), {}),
            ("weightList", "mirrorWeights", (), {}),
            ("weightList[0].weights", "mirrorWeights", (), {}),
            ("node", "smoothWeights", (), {}),
            ("weightList", "smoothWeights", (), {}),
            ("node", "unbind", (), {}),
            ("node", "unbind", (), {"keepHistory": True}),
            ("nodeState", "unbind", (), {"keepHistory": True}),
            ("node", "transferWeights", ("pair",), {}),
        )
        for lock, method, args, flags in cases:
            with self.subTest(lock=lock, method=method, args=args):
                node, names = self.skin()
                if lock == "node":
                    self.lock_node(node)
                else:
                    self.lock(node.getName(full=True), lock)
                args = tuple([(names[0], names[1])] if value == "pair" else value for value in args)
                self.assertFails(RuntimeError, getattr(node, method), *args, state=lambda: self.skin_state(node), **flags)

    def test_skin_cluster_remove_unused_influences(self):
        """removeInfluences(unused=True) は、skinCluster か外すインフルエンスの bindPreMatrix がロックされていると外さない。"""
        for lock in ("node", "bindPreMatrix", "element"):
            with self.subTest(lock=lock):
                node, _ = self.skin()
                extra = self.joints((5, 5, 5))[0]
                cmds.skinCluster(node.getName(full=True), edit=True, addInfluence=extra, weight=0)
                if lock == "node":
                    self.lock_node(node)
                elif lock == "bindPreMatrix":
                    self.lock(node.getName(full=True), "bindPreMatrix")
                else:
                    self.lock(node.getName(full=True), "bindPreMatrix[3]")
                self.assertFails(RuntimeError, node.removeInfluences, unused=True, state=lambda: self.skin_state(node))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
