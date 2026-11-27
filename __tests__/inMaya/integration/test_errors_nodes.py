"""ノードのクラスの公開メソッドについて、docstring の Raises に書かれた例外を確かめる。

対象は Mesh・Node・Nodes・NurbsCurve・ObjectSet・計算ノード・Reference・ShadingEngine・SkinCluster・Transform。

各テストは Raises に書かれた入力を作って ``assertRaises`` で例外の型を確かめ、可能なものは例外の後に
シーンが変わっていないこと(ノードが増えない・値や接続が戻る・ファイルが残らない)も確かめる。
docstring と実際の挙動が食い違う項目はここでは確かめず、別途の記録に回している。

あわせて次も確かめる。

- nodes のメソッド(aimConstraint〜mesh)の docstring の Raises に書かれた例外を確かめる。
"""

import functools
import math
import os
import shutil
import sys
import tempfile
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _ErrorCase(NamespaceCase):
    """削除済みノードの作成など、各テストで共通の補助を持つ。"""

    PREFIX = "mlibSpecErrNodesA_"
    CLEAR_SELECTION = True

    def dead(self, kind):
        """名前空間に作ってすぐ削除したノードのラッパーを返す(無効なノードの確認用)。"""
        node = mlib.getNode(self.make(kind))
        cmds.delete(node.getName(full=True))
        self.assertFalse(node.isValid())
        return node

    def cube(self, text):
        """履歴なしの polyCube を作り、transform の名前を返す。"""
        return cmds.polyCube(name=self.name(text), constructionHistory=False)[0]

    def joints(self, *names):
        """名前の順に親子にした joint を作り、名前を返す。"""
        cmds.select(clear=True)
        result = [cmds.joint(name=self.name(name), position=(0, i, 0)) for i, name in enumerate(names)]
        cmds.select(clear=True)
        return result


class AngleUnitArgumentTest(_ErrorCase):
    """AimConstraint.setRestRotate の unit の検証(getはEulerRotateを返し、unitを持たない)。"""

    def test_unit_type_and_name(self):
        aim = mlib.getNode(self.make("aimConstraint"))
        for method in ("getRestRotate",):
            with self.subTest(method=method), self.assertRaises(TypeError):
                getattr(aim, method)(unit="rad")
        for method in ("setRestRotate",):
            with self.subTest(method=method):
                getattr(aim, method)((0, 0, 0), unit="rad")
                for unit in (1, 1.0, ["deg"]):
                    with self.assertRaises(TypeError):
                        getattr(aim, method)((0, 0, 0), unit=unit)
                for unit in ("grad", "", "DEG?"):
                    with self.assertRaises(ValueError):
                        getattr(aim, method)((0, 0, 0), unit=unit)


class AnimCurveErrorTest(_ErrorCase):
    """AnimCurve.getKeyValues・evaluate・getTangent・getDrivenPlugs。"""

    def setUp(self):
        super().setUp()
        self.target = self.make("transform", "animated")
        cmds.setKeyframe(self.target, attribute="rx", time=1, value=10)
        cmds.setKeyframe(self.target, attribute="rx", time=10, value=20)
        self.curve = mlib.getNode(cmds.listConnections(self.target + ".rx", source=True, destination=False)[0])
        self.assertEqual(self.curve.getKeyCount(), 2)

    def test_unit_arguments(self):
        calls = (
            ("getKeyValues", lambda **kw: self.curve.getKeyValues(**kw)),
            ("evaluate", lambda **kw: self.curve.evaluate(5, **kw)),
            ("getTangent", lambda **kw: self.curve.getKeyframes(0).getTangent(**kw)),
        )
        for name, call in calls:
            with self.subTest(method=name, flag="unit"):
                with self.assertRaises(TypeError):
                    call(unit=1)
                with self.assertRaises(ValueError):
                    call(unit="grad")
            if name == "getTangent":
                continue  # getTangent は timeUnit を持たない
            with self.subTest(method=name, flag="timeUnit"):
                with self.assertRaises(TypeError):
                    call(timeUnit=1)
                with self.assertRaises(ValueError):
                    call(timeUnit="minute")

    def test_evaluate_input(self):
        time = cmds.currentTime(query=True)
        for value in (object(), None, [1]):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.curve.evaluate(value)
        for value in ("abc", float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.curve.evaluate(value)
        self.assertAlmostEqual(self.curve.evaluate(1), 10.0)
        self.assertAlmostEqual(self.curve.evaluate("10"), 20.0)
        # 評価しても現在時刻は変わらない。
        self.assertEqual(cmds.currentTime(query=True), time)

    def test_evaluate_empty_curve_rejected_before_input_conversion(self):
        empty = mlib.createNode("animCurveTL", name=self.name("empty"))
        with self.assertRaises(RuntimeError):
            empty.evaluate(1)
        # 空カーブは入力変換より先に拒否する(変換できない入力でも RuntimeError)。
        with self.assertRaises(RuntimeError):
            empty.evaluate(object())

    def test_get_tangent_index(self):
        for index in (True, False, 1.0, "0", -1, 2, 99):
            with self.subTest(index=index):
                with self.assertRaises(IndexError):
                    self.curve.getKeyframes(index).getTangent()
        info = self.curve.getKeyframes(1).getTangent()
        self.assertEqual(info["inTangentType"], cmds.keyTangent(self.curve.getName(full=True), query=True, index=(1, 1), inTangentType=True)[0])

    def test_get_driven_plugs(self):
        plugs = self.curve.getDrivenPlugs()
        self.assertEqual([plug.getName(full=True) for plug in plugs], [mlib.getPlug(self.target + ".rx").getName(full=True)])
        self.assertEqual(mlib.createNode("animCurveTL", name=self.name("free")).getDrivenPlugs(), [])
        with self.assertRaises(RuntimeError):
            self.dead("animCurveTL").getDrivenPlugs()


class BlendShapeErrorTest(_ErrorCase):
    """BlendShape.getBaseGeometry・getInBetweenWeights・resetTargetVertices(tolerance)・getTargetsData・exportTargets。"""

    def setUp(self):
        super().setUp()
        self.base = self.cube("base")
        self.target = self.cube("target")
        cmds.move(0, 1, 0, self.target + ".vtx[0]", relative=True)
        self.bs = mlib.getNode(cmds.blendShape(self.target, self.base, name=self.name("bs"))[0])
        self.item = self.bs.getName(full=True) + ".inputTarget[0].inputTargetGroup[0].inputTargetItem[6000]"
        self.directory = tempfile.mkdtemp(prefix="mlibSpecErrNodesA_")

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        super().tearDown()

    def curve_blend_shape(self):
        """カーブをベースにした blendShape(メッシュでないベース)を作る。"""
        points = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)]
        base = cmds.curve(point=points, name=self.name("curveBase"))
        target = cmds.curve(point=[(0, 1, 0), *points[1:]], name=self.name("curveTarget"))
        return mlib.getNode(cmds.blendShape(target, base, name=self.name("curveBs"))[0])

    def item_state(self):
        """項目のデルタと、ターゲット形状の接続をまとめる。"""
        deltas = {vertex: tuple(round(v, 6) for v in delta) for vertex, delta in self.bs.getTargetDeltas(0).items()}
        source = cmds.listConnections(self.item + ".inputGeomTarget", source=True, destination=False)
        return deltas, source

    def test_get_base_geometry(self):
        shape = cmds.listRelatives(self.base, shapes=True, fullPath=True)[0]
        self.assertEqual([node.getName(full=True) for node in self.bs.getBaseGeometry()], [shape])
        with self.assertRaises(RuntimeError):
            self.dead_blend_shape().getBaseGeometry()

    def dead_blend_shape(self):
        node = mlib.getNode(cmds.blendShape(self.cube("deadBase"), name=self.name("deadBs"))[0])
        cmds.delete(node.getName(full=True))
        return node

    def test_get_in_between_weights(self):
        between = self.cube("between")
        cmds.blendShape(self.bs.getName(full=True), edit=True, inBetween=True, target=(self.base, 0, between, 0.5))
        self.assertEqual(self.bs.getInBetweenWeights(0), [0.5])
        for target in (1.5, None, True, [0]):
            with self.subTest(target=target):
                with self.assertRaises(TypeError):
                    self.bs.getInBetweenWeights(target)
        with self.subTest(base=1):
            with self.assertRaises(TypeError):
                self.bs.getInBetweenWeights(0, base=1)
        for target in ("missing", 9):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    self.bs.getInBetweenWeights(target)
        with self.subTest(base="other"):
            with self.assertRaises(ValueError):
                self.bs.getInBetweenWeights(0, base=self.cube("other"))

    def test_reduce_target_deltas_invalid_arguments(self):
        before = self.item_state()
        type_errors = (dict(tolerance="a"), dict(disconnect=1), dict(fast=1), dict(target=1.5), dict(tolerance=None), dict(vertices=[0]))
        value_errors = (dict(tolerance=-1), dict(tolerance=float("inf")), dict(tolerance=float("nan")), dict(target="missing"), dict(fullWeight=0.5))
        for flags, error in [(f, TypeError) for f in type_errors] + [(f, ValueError) for f in value_errors]:
            # tolerance を指定しない行は、以前の既定の 0.0 で呼ぶ。vertices と tolerance の両方・どちらも無しは TypeError。
            flags = dict({"tolerance": 0.0}, **flags)
            target = flags.pop("target", 0)
            with self.subTest(flags=flags, target=target):
                with self.assertRaises(error):
                    self.bs.resetTargetVertices(target, **flags)
                self.assertEqual(self.item_state(), before)

    def test_reduce_target_deltas_connected_target(self):
        before = self.item_state()
        self.assertEqual(before[0].keys(), {0})
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    self.bs.resetTargetVertices(0, tolerance=10.0, fast=fast)
                self.assertEqual(self.item_state(), before)
        # disconnect=True なら接続を切ってから取り除く。
        self.bs.resetTargetVertices(0, tolerance=10.0, disconnect=True)
        self.assertEqual(self.item_state(), ({}, None))

    def test_targets_data_requires_mesh_bases(self):
        data = self.bs.getTargetsData()
        self.assertEqual(sorted(data), ["bases", "blendShape", "folders", "targets"])
        curve_bs = self.curve_blend_shape()
        with self.assertRaises(TypeError):
            curve_bs.getTargetsData()
        with self.assertRaises(RuntimeError):
            self.dead_blend_shape().getTargetsData()

    def test_export_targets_errors(self):
        path = os.path.join(self.directory, "targets.json")
        with self.assertRaises(TypeError):
            self.curve_blend_shape().exportTargets(path)
        self.assertFalse(os.path.exists(path))
        missing = os.path.join(self.directory, "no_such_dir", "targets.json")
        with self.assertRaises(OSError):
            self.bs.exportTargets(missing)
        self.assertFalse(os.path.exists(os.path.dirname(missing)))
        written = self.bs.exportTargets(path)
        self.assertTrue(written.is_file())


class DagNodeInvalidTest(_ErrorCase):
    """DagNode の照会メソッドが、削除済みのノード・取り除いたインスタンスで RuntimeError になること。"""

    #: (メソッド名, キーワード引数)。
    DELETED = (
        ("getBindPoses", {}),
        ("mpath", {}),
        ("getRoot", {}),
        ("isIntermediateObject", {}),
        ("getInstances", {}),
        ("getParent", {"instances": True}),
        ("getParent", {"instances": True, "indirect": True}),
        ("isVisible", {}),
        ("getColor", {}),
        ("getColor", {"outliner": True}),
        ("getDrawColor", {}),
        ("getBoundingBox", {"corners": True}),
        ("getDisplayType", {}),
        ("getSkinClusters", {}),
    )
    REMOVED_INSTANCE = (
        ("getBindPoses", {}),
        ("mpath", {}),
        ("getRoot", {}),
        ("getSiblings", {}),
        ("isIntermediateObject", {}),
        ("getInstances", {}),
        ("getParent", {"instances": True}),
        ("isVisible", {}),
        ("getSkinClusters", {}),
    )

    def test_deleted_node(self):
        node = self.dead("transform")
        for method, flags in self.DELETED:
            with self.subTest(method=method, flags=flags):
                with self.assertRaises(RuntimeError):
                    getattr(node, method)(**flags)
        # getSiblings は無効なノードでは空リストを返す(docstring の記載どおり)。
        self.assertEqual(node.getSiblings(), [])

    def test_removed_instance_path(self):
        first, second = self.make("transform", "first"), self.make("transform", "second")
        child = self.make("transform", "child", parent=first)
        cmds.parent(child, second, addObject=True)
        instance = next(node for node in mlib.getNode(child).getInstances() if node.getName(full=True).startswith(cmds.ls(second, long=True)[0] + "|"))
        cmds.parent(instance.getName(full=True), removeObject=True)
        # ノード自体は残り、保持するパスだけが無効になる。
        self.assertTrue(instance.isValid())
        for method, flags in self.REMOVED_INSTANCE:
            with self.subTest(method=method, flags=flags):
                with self.assertRaises(RuntimeError):
                    getattr(instance, method)(**flags)

    def test_get_color_shape_flag(self):
        node = mlib.getNode(self.make("transform"))
        for value in (1, 0, None, "true"):
            with self.subTest(shape=value):
                with self.assertRaises(TypeError):
                    node.getColor(toShape=value)
        self.assertIsNone(node.getColor(toShape=True))

    def test_get_bind_poses_with_invalid_connection(self):
        (joint,) = self.joints("bindJoint")
        cube = self.cube("skinned")
        skin = mlib.getNode(cmds.skinCluster(joint, cube, name=self.name("skin"))[0])
        pose = skin.getBindPose()
        self.assertEqual(mlib.getNode(cube).getBindPoses(), [pose])
        cmds.disconnectAttr(pose.getName(full=True) + ".message", skin.getName(full=True) + ".bindPose")
        cmds.connectAttr(self.make("network", "fakePose") + ".message", skin.getName(full=True) + ".bindPose")
        for name in (cube, joint):
            with self.subTest(node=name):
                with self.assertRaises(RuntimeError):
                    mlib.getNode(name).getBindPoses(influence=name == joint)


class DagPoseErrorTest(_ErrorCase):
    """DagPose の照会と addMembers。"""

    def setUp(self):
        super().setUp()
        self.root, self.tip = self.joints("root", "tip")
        cmds.select(clear=True)
        (self.free,) = self.joints("free")
        pose = cmds.dagPose(self.root, self.tip, save=True, selection=True)
        self.pose = mlib.getNode(cmds.rename(pose, self.name("pose")))

    def members(self):
        return [node.getName(full=True) for node in self.pose.getMembers()]

    def test_queries_on_deleted_pose(self):
        pose = mlib.getNode(cmds.rename(cmds.dagPose(self.root, save=True, selection=True), self.name("gone")))
        cmds.delete(pose.getName(full=True))
        for method in ("getNotAtPose", "getSkinClusters", "isBindPose", "getMemberIndices", "getMembers"):
            with self.subTest(method=method):
                with self.assertRaises(RuntimeError):
                    getattr(pose, method)()
        with self.assertRaises(RuntimeError):
            pose.addMembers(self.free)

    def test_add_members_invalid_input_keeps_members(self):
        before = self.members()
        shape = cmds.listRelatives(self.cube("mesh"), shapes=True, fullPath=True)[0]
        cases = (
            (TypeError, (1,)),
            (TypeError, (None,)),
            (TypeError, ([self.free, 1.5],)),
            (ValueError, ()),
            (ValueError, ([],)),
            (ValueError, (shape,)),
            (ValueError, (self.free, "time1")),
            (RuntimeError, (self.name("missing"),)),
        )
        for error, members in cases:
            with self.subTest(error=error.__name__, members=members):
                with self.assertRaises(error):
                    self.pose.addMembers(*members)
                self.assertEqual(self.members(), before)
        self.pose.addMembers(self.free)
        self.assertEqual(self.members(), [*before, cmds.ls(self.free, long=True)[0]])


class GeometryFilterWeightTest(_ErrorCase):
    """GeometryFilter.getDeformerWeights・setDeformerWeights。"""

    def setUp(self):
        super().setUp()
        self.mesh = self.cube("mesh")
        self.cluster = mlib.getNode(cmds.cluster(self.mesh, name=self.name("cluster"))[0])
        self.cluster.setDeformerWeights([0.5] * 8)

    def test_get_errors(self):
        self.assertEqual(self.cluster.getDeformerWeights(), [0.5] * 8)
        for value in (1.0, True, "0"):
            with self.subTest(geometryIndex=value):
                with self.assertRaises(TypeError):
                    self.cluster.getDeformerWeights(geometryIndex=value)
        for value in (1, 5, -1):
            with self.subTest(geometryIndex=value):
                with self.assertRaises(IndexError):
                    self.cluster.getDeformerWeights(geometryIndex=value)

    def test_skin_cluster_has_no_deformer_weights(self):
        (joint,) = self.joints("joint")
        skin = mlib.getNode(cmds.skinCluster(joint, self.cube("skinned"), name=self.name("skin"))[0])
        with self.assertRaises(TypeError):
            skin.getDeformerWeights()
        with self.assertRaises(TypeError):
            skin.setDeformerWeights([1.0] * 8)

    def test_set_invalid_arguments_keep_weights(self):
        cases = (
            (TypeError, dict(weights=[1.0] * 8, fast=1)),
            (TypeError, dict(weights=[1.0] * 8, geometryIndex=1.0)),
            (TypeError, dict(weights=["a"] * 8)),
            (TypeError, dict(weights=[True] * 8)),
            (TypeError, dict(weights=[1.0], vertices=[1.0])),
            (ValueError, dict(weights=[1.0] * 3)),
            (ValueError, dict(weights=[float("nan")] * 8)),
            (ValueError, dict(weights=[1.0, 1.0], vertices=[1, 1])),
            (IndexError, dict(weights=[1.0] * 8, geometryIndex=5)),
            (IndexError, dict(weights=[1.0], vertices=[99])),
            (IndexError, dict(weights=[1.0], vertices=[-1])),
        )
        for fast in (False, True):
            for error, flags in cases:
                flags = dict(flags)
                flags.setdefault("fast", fast)
                with self.subTest(error=error.__name__, flags=flags):
                    with self.assertRaises(error):
                        self.cluster.setDeformerWeights(**flags)
                    self.assertEqual(self.cluster.getDeformerWeights(), [0.5] * 8)

    def test_set_locked_or_connected_attribute(self):
        weights = self.cluster.getName(full=True) + ".weightList[0].weights"
        cmds.setAttr(weights, lock=True)
        for fast in (False, True):
            with self.subTest(case="locked", fast=fast):
                with self.assertRaises(RuntimeError):
                    self.cluster.setDeformerWeights([0.2], vertices=[0], fast=fast)
                self.assertEqual(self.cluster.getDeformerWeights(), [0.5] * 8)
        cmds.setAttr(weights, lock=False)
        cmds.connectAttr(self.make("transform", "driver") + ".visibility", weights + "[1]")
        for fast in (False, True):
            with self.subTest(case="connected", fast=fast):
                with self.assertRaises(RuntimeError):
                    self.cluster.setDeformerWeights([0.2], vertices=[1], fast=fast)
                self.assertAlmostEqual(cmds.getAttr(weights + "[0]"), 0.5)


class IkHandleErrorTest(_ErrorCase):
    """IkHandle.getEffector。"""

    def test_effector(self):
        start, _, end = self.joints("a", "b", "c")
        cmds.setAttr(end + ".tz", 1)
        handle, effector = cmds.ikHandle(startJoint=start, endEffector=end, name=self.name("ik"))
        ik = mlib.getNode(handle)
        self.assertEqual(ik.getEffector().getName(full=True), cmds.ls(effector, long=True)[0])
        cmds.delete(handle)
        for method in ("getEffector",):
            with self.subTest(method=method):
                with self.assertRaises(RuntimeError):
                    getattr(ik, method)()


class JointDisconnectInverseScaleTest(_ErrorCase):
    """Joint.disconnectInverseScale。"""

    def setUp(self):
        super().setUp()
        self.parent, self.child = self.joints("parent", "child")
        self.joint = mlib.getNode(self.child)

    def source(self):
        return cmds.listConnections(self.child + ".inverseScale", source=True, destination=False)

    def test_errors_keep_connection(self):
        before = self.source()
        self.assertTrue(before)
        with self.assertRaises(TypeError):
            self.joint.disconnectInverseScale(fast=1)
        self.assertEqual(self.source(), before)
        cmds.setAttr(self.child + ".inverseScale", lock=True)
        for fast in (False, True):
            with self.subTest(case="locked", fast=fast):
                with self.assertRaises(RuntimeError):
                    self.joint.disconnectInverseScale(fast=fast)
                self.assertEqual(self.source(), before)
        cmds.setAttr(self.child + ".inverseScale", lock=False)
        dead = mlib.getNode(self.joints("gone")[0])
        cmds.delete(dead.getName(full=True))
        with self.assertRaises(RuntimeError):
            dead.disconnectInverseScale()
        self.assertIsNone(self.joint.disconnectInverseScale())
        self.assertIsNone(self.source())


class MeshClosestVertexTest(_ErrorCase):
    """Mesh.getClosestVertices(点1つ)。docstring と食い違う成分数の誤り・データの無いメッシュは扱わない。"""

    def setUp(self):
        super().setUp()
        self.mesh = mlib.getNode(cmds.listRelatives(self.cube("mesh"), shapes=True, fullPath=True)[0])

    def test_errors(self):
        self.assertEqual(self.mesh.getVertices(self.mesh.getClosestVertices([(0.5, 0.5, 0.5)])[0]).index, 3)
        for point in ("abc", object(), ("a", 0, 0)):
            with self.subTest(point=point):
                with self.assertRaises(TypeError):
                    self.mesh.getClosestVertices([point])
        for flags in (dict(worldSpace=1), dict(ws="yes"), dict(worldSpace=True, ws=True)):
            with self.subTest(flags=flags):
                with self.assertRaises(TypeError):
                    self.mesh.getClosestVertices([(0, 0, 0)], **flags)
        for point in ((float("nan"), 0, 0), (0, float("inf"), 0)):
            with self.subTest(point=point):
                with self.assertRaises(ValueError):
                    self.mesh.getClosestVertices([point])

    def test_mesh_without_vertices(self):
        parent = om2.MSelectionList().add(self.make("transform", "emptyMesh")).getDependNode(0)
        shape = om2.MFnMesh().create([], [], [], parent=parent)
        empty = mlib.getNode(om2.MFnDagNode(shape).fullPathName())
        with self.assertRaises(ValueError):
            empty.getClosestVertices([(0, 0, 0)])


class _Case(NamespaceCase):
    """名前空間にノードを作る補助。"""

    PREFIX = "mlibErrNodesB_"
    CLEAR_SELECTION = True

    def node(self, node_type, text=None, **flags):
        """mlib.createNode で名前空間にノードを作る。"""
        return mlib.createNode(node_type, name=self.name(text or node_type + "#"), **flags)

    def deleted(self, node_type="transform", flush=False):
        """作ってすぐ削除したノードのラッパーを返す。flush=True なら Undo の記録も消す。"""
        node = self.node(node_type)
        cmds.delete(node.getName(full=True))
        if flush:
            cmds.flushUndo()
        return node

    def namespace_nodes(self):
        """名前空間にあるノードの名前の集合。"""
        return set(cmds.ls(self.ns + ":*", long=True) or [])

    def temp_dir(self):
        """テスト終了時に消える一時フォルダーを返す。"""
        path = tempfile.mkdtemp(prefix="mlibErrNodesB_")
        self.addCleanup(shutil.rmtree, path, True)
        return path

    def track_outside_nodes(self):
        """以後に名前空間の外へできたノード(bindPose 等)を、テスト終了時に削除する。"""
        before = set(cmds.ls(long=True))

        def cleanup():
            created = [name for name in set(cmds.ls(long=True)) - before if cmds.objExists(name) and not cmds.ls(name, readOnly=True)]
            for name in created:
                if cmds.objExists(name):
                    cmds.delete(name)

        self.addCleanup(cleanup)


class MeshErrorTest(_Case):
    """Mesh の最近点・法線と UV セットの操作。"""

    def cube(self):
        transform = cmds.polyCube(name=self.name("cube#"), constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def faceless(self):
        """頂点だけで面の無いメッシュを om2 で作る。"""
        parent = om2.MFnDagNode().create("transform", self.name("noFace"))
        points = [om2.MPoint(0, 0, 0), om2.MPoint(1, 0, 0), om2.MPoint(0, 1, 0)]
        shape = om2.MFnMesh().create(points, [], [], parent=parent)
        return mlib.getNode(om2.MFnDagNode(shape).fullPathName())

    def test_closest_point_and_normal_reject_invalid_input(self):
        """点が文字列・非シーケンスは TypeError、成分が有限でない・面の無いメッシュは ValueError、worldSpace が bool 以外は TypeError。"""
        mesh = self.cube()
        faceless = self.faceless()
        for method in ("point", "normal"):
            call = functools.partial(mesh.getClosestPoint, what=method)
            with self.subTest(method=method, case="str"):
                self.assertRaises(TypeError, call, "abc")
            with self.subTest(method=method, case="object"):
                self.assertRaises(TypeError, call, object())
            with self.subTest(method=method, case="nan"):
                self.assertRaises(ValueError, call, (float("nan"), 0, 0))
            with self.subTest(method=method, case="inf"):
                self.assertRaises(ValueError, call, (0, float("inf"), 0))
            with self.subTest(method=method, case="worldSpace"):
                self.assertRaises(TypeError, call, (0, 0, 0), worldSpace=1)
                self.assertRaises(TypeError, call, (0, 0, 0), ws="yes")
            with self.subTest(method=method, case="both aliases"):
                self.assertRaises(TypeError, call, (0, 0, 0), worldSpace=True, ws=True)
            with self.subTest(method=method, case="no faces"):
                self.assertRaises(ValueError, faceless.getClosestPoint, (0, 0, 0), what=method)

    def test_closest_point_and_normal_component_count_and_empty_shape(self):
        """成分の数が3でない点は ValueError、形状データを持たない空のシェイプは RuntimeError。"""
        mesh = self.cube()
        empty = self.node("mesh")
        for method in ("point", "normal"):
            call = functools.partial(mesh.getClosestPoint, what=method)
            for point in ((1, 2), (1, 2, 3, 4)):
                with self.subTest(method=method, point=point):
                    self.assertRaises(ValueError, call, point)
            with self.subTest(method=method, case="empty shape"):
                self.assertRaises(RuntimeError, empty.getClosestPoint, (0, 0, 0), what=method)

    def test_closest_normal_on_cube_face(self):
        """正常系: 立方体の +X 面の外の点では、+X 方向の法線になる。"""
        normal = self.cube().getClosestPoint((2, 0.1, 0.1), what="normal")
        self.assertSequenceAlmostEqual(normal, (1, 0, 0), places=6)

    def assertUVSets(self, mesh, expected, current="map1"):
        self.assertEqual(cmds.polyUVSet(mesh.getName(full=True), query=True, allUVSets=True), expected)
        self.assertEqual(cmds.polyUVSet(mesh.getName(full=True), query=True, currentUVSet=True), [current])

    def test_set_current_uv_set_errors(self):
        """name が文字列以外は TypeError、空・存在しない名前は ValueError。UV セットは変わらない。"""
        mesh = self.cube()
        cases = ((TypeError, 5), (TypeError, None), (ValueError, ""), (ValueError, "missing"))
        for error, name in cases:
            with self.subTest(name=name):
                self.assertRaises(error, mesh.setCurrentSet, name)
                self.assertUVSets(mesh, ["map1"])

    def test_create_uv_set_errors(self):
        """name が文字列以外は TypeError、空・既にある名前は ValueError。UV セットは増えない。"""
        mesh = self.cube()
        for error, name in ((TypeError, 5), (TypeError, b"bytes"), (ValueError, ""), (ValueError, "map1")):
            with self.subTest(name=name):
                self.assertRaises(error, mesh.createSet, name)
                self.assertUVSets(mesh, ["map1"])

    def test_copy_uv_set_errors(self):
        """source・target が文字列以外は TypeError、空・source が無い・target が既にあるは ValueError。"""
        mesh = self.cube()
        mesh.createSet("second")
        cases = (
            (TypeError, 5, "copy"),
            (TypeError, "map1", 5),
            (ValueError, "", "copy"),
            (ValueError, "map1", ""),
            (ValueError, "missing", "copy"),
            (ValueError, "map1", "second"),
            (ValueError, "map1", "map1"),
        )
        for error, source, target in cases:
            with self.subTest(source=source, target=target):
                self.assertRaises(error, mesh.copySet, source, target)
                self.assertUVSets(mesh, ["map1", "second"])

    def test_rename_uv_set_errors(self):
        """name・newName が文字列以外は TypeError、空・name が無い・newName が既にあるは ValueError。"""
        mesh = self.cube()
        mesh.createSet("second")
        cases = (
            (TypeError, None, "renamed"),
            (TypeError, "second", 5),
            (ValueError, "", "renamed"),
            (ValueError, "second", ""),
            (ValueError, "missing", "renamed"),
            (ValueError, "second", "map1"),
        )
        for error, name, new_name in cases:
            with self.subTest(name=name, newName=new_name):
                self.assertRaises(error, mesh.renameSet, name, new_name)
                self.assertUVSets(mesh, ["map1", "second"])


class NodeErrorTest(_Case):
    """Node の照会で、無効なノード・不正な入力の例外。"""

    def test_invalid_node_queries_raise_runtime_error(self):
        """削除したノードの findCycles・getAliases は RuntimeError。"""
        for method in ("findCycles", "getAliases"):
            for flush in (False, True):
                with self.subTest(method=method, flush=flush):
                    self.assertRaises(RuntimeError, getattr(self.deleted(flush=flush), method))

    def test_destroyed_node_queries_raise_runtime_error(self):
        """削除して Undo の記録も消えたノードの isFromReferencedFile は RuntimeError。"""
        for method in ("isFromReferencedFile",):
            with self.subTest(method=method):
                self.assertRaises(RuntimeError, getattr(self.deleted(flush=True), method))

    def test_destroyed_node_queries_valid_counterpart(self):
        """正常系: 有効なノードはリファレンスのファイルのものではない。"""
        node = self.node("transform")
        self.assertFalse(node.isFromReferencedFile())

    def test_find_cycles_and_aliases_on_valid_node(self):
        """正常系: 循環の無いノードは空リスト、エイリアスは (名前, Plug) の組。"""
        node = self.node("transform")
        cmds.aliasAttr("moveX", node.getName(full=True) + ".translateX")
        self.assertEqual(node.findCycles(), [])
        aliases = node.getAliases()
        self.assertEqual([alias for alias, _ in aliases], ["moveX"])
        self.assertEqual(aliases[0][1].getAttributeName(), "translateX")

    def test_is_ancestor_of_rejects_unresolvable_input(self):
        """other が未対応型は TypeError、解決できない名前・null の MObject・MPlug は RuntimeError。"""
        parent = self.node("transform")
        child = self.node("transform", parent=parent)
        for error, other in (
            (TypeError, 5),
            (TypeError, None),
            (TypeError, 1.5),
            (RuntimeError, self.name("missing")),
            (RuntimeError, om2.MObject()),
            (RuntimeError, om2.MPlug()),
        ):
            with self.subTest(other=other):
                self.assertRaises(error, parent.isAncestorOf, other)
        self.assertTrue(parent.isAncestorOf(child))
        self.assertFalse(child.isAncestorOf(parent))

    def test_is_ancestor_of_rejects_invalid_self(self):
        """自身を削除した後(Undo の記録の有無によらない)の isAncestorOf は RuntimeError。"""
        for flush in (False, True):
            with self.subTest(flush=flush):
                other = self.node("transform")
                self.assertRaises(RuntimeError, self.deleted(flush=flush).isAncestorOf, other)


class NodesErrorTest(_Case):
    """Nodes の一括照会。"""

    def test_get_color_rejects_non_dag(self):
        """DAG ノード以外を含む Nodes の getColor は TypeError(outliner=True でも同じ)。"""
        dag = self.node("transform")
        for items in ([self.node("multiplyDivide")], [dag, self.node("multiplyDivide")]):
            for outliner in (False, True):
                with self.subTest(items=len(items), outliner=outliner):
                    self.assertRaises(TypeError, mlib.Nodes(items).getColor, outliner=outliner)

    def test_invalid_items_raise_runtime_error(self):
        """保持中のノードを削除した後の getColor・getNames は RuntimeError。"""
        for method, flags in (("getColor", {}), ("getColor", {"outliner": True}), ("getNames", {}), ("getNames", {"full": True})):
            with self.subTest(method=method, flags=flags):
                first, second = self.node("transform"), self.node("transform")
                nodes = mlib.Nodes([first, second])
                cmds.delete(second.getName(full=True))
                self.assertRaises(RuntimeError, getattr(nodes, method), **flags)

    def test_valid_items(self):
        """正常系: getNames は保持順の名前、getColor は各ノードの表示色・アウトライナーの色。"""
        first, second = self.node("transform"), self.node("transform")
        nodes = mlib.Nodes([first, second])
        self.assertEqual(nodes.getNames(), [first.getName(), second.getName()])
        self.assertEqual(nodes.getNames(full=True), [first.getName(full=True), second.getName(full=True)])
        self.assertEqual(nodes.getColor(), [first.getColor(), second.getColor()])
        second.setColor((1.0, 0.5, 0.0), outliner=True)
        self.assertEqual(nodes.getColor(outliner=True), [first.getColor(outliner=True), second.getColor(outliner=True)])
        for flags in ({"full": 1}, {"outliner": 1}):
            with self.subTest(flags=flags):
                method = nodes.getNames if "full" in flags else nodes.getColor
                self.assertRaises(TypeError, method, **flags)


class NurbsCurveErrorTest(_Case):
    """NurbsCurve のパラメーター・弧長の照会。"""

    def curve(self, points=((0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)), degree=3):
        transform = cmds.curve(name=self.name("curve#"), degree=degree, point=points)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def queries(self, curve):
        """照会の呼び方ごとに、位置引数1つ(param か length)とフラグを受けて呼ぶ関数を返す。"""
        return {
            "getAtParam": curve.getAtParam,
            "getAtParam(tangent)": functools.partial(curve.getAtParam, what="tangent"),
            "getLength(param)": curve.getLength,
            "getParam(length)": lambda length, **flags: curve.getParam(length=length, **flags),
        }

    def test_empty_shape_raises_runtime_error(self):
        """形状データを持たない空の nurbsCurve では各照会が RuntimeError。"""
        empty = mlib.getNode(self.make("nurbsCurve", "emptyCurve#", parent=self.make("transform", "emptyParent#")))
        calls = (
            ("getParamRange", ()),
            ("getClosestPoint", ((0, 0, 0),)),
            ("getAtParam", (0.0,)),
            ("getAtParam(tangent)", (0.0,)),
            ("getLength(param)", (0.0,)),
            ("getParam(length)", (0.0,)),
            ("getParamsAlong", (2,)),
        )
        queries = self.queries(empty)
        for method, args in calls:
            with self.subTest(method=method):
                self.assertRaises(RuntimeError, queries.get(method) or getattr(empty, method), *args)

    def test_world_space_must_be_bool(self):
        """worldSpace・ws が bool 以外、または両方の指定は TypeError。"""
        curve = self.curve()
        calls = (
            ("getClosestPoint", ((0, 0, 0),)),
            ("getAtParam", (0.5,)),
            ("getAtParam(tangent)", (0.5,)),
            ("getLength(param)", (0.5,)),
            ("getParam(length)", (1.0,)),
            ("getParamsAlong", (2,)),
        )
        queries = self.queries(curve)
        for method, args in calls:
            call = queries.get(method) or getattr(curve, method)
            with self.subTest(method=method):
                self.assertRaises(TypeError, call, *args, worldSpace=1)
                self.assertRaises(TypeError, call, *args, ws="yes")
                self.assertRaises(TypeError, call, *args, worldSpace=None)
                self.assertRaises(TypeError, call, *args, worldSpace=True, ws=True)

    def test_get_closest_point_errors(self):
        """点が文字列・非シーケンスは TypeError、成分が有限でない場合は ValueError。"""
        curve = self.curve()
        self.assertRaises(TypeError, curve.getClosestPoint, "abc")
        self.assertRaises(TypeError, curve.getClosestPoint, object())
        self.assertRaises(ValueError, curve.getClosestPoint, (float("nan"), 0, 0))
        self.assertRaises(ValueError, curve.getClosestPoint, (1, 2))
        self.assertRaises(ValueError, curve.getClosestPoint, (1, 2, 3, 4))
        position, param = curve.getClosestPoint((1.5, 2, 0))
        self.assertSequenceAlmostEqual(position, (1.5, 0, 0), places=5)
        self.assertAlmostEqual(param, 0.5, places=5)

    def test_param_errors(self):
        """param が数値でない(bool を含む)は TypeError、有限でない・範囲外は ValueError。"""
        curve = self.curve()
        queries = self.queries(curve)
        for method in ("getAtParam", "getAtParam(tangent)", "getLength(param)"):
            call = queries[method]
            for error, param in (
                (TypeError, "a"),
                (TypeError, None),
                (TypeError, True),
                (ValueError, float("nan")),
                (ValueError, float("inf")),
                (ValueError, -0.5),
                (ValueError, 1.5),
            ):
                if param is None and method == "getLength(param)":
                    continue  # getLength の param=None は全長の指定で、例外にならない
                with self.subTest(method=method, param=param):
                    self.assertRaises(error, call, param)

    def test_tangent_undefined_at_coincident_cvs(self):
        """重なった CV で接線が 0 になる位置の getAtParam(what="tangent") は ValueError。"""
        curve = self.curve(points=((0, 0, 0), (0, 0, 0), (1, 0, 0)), degree=1)
        for param in (0.0, 0.5):
            with self.subTest(param=param):
                self.assertRaises(ValueError, curve.getAtParam, param, what="tangent")
        self.assertSequenceAlmostEqual(curve.getAtParam(1.5, what="tangent"), (1, 0, 0), places=6)

    def test_unit_errors(self):
        """distanceUnit が文字列・None 以外は TypeError、未対応の単位名は ValueError。"""
        curve = self.curve()
        queries = self.queries(curve)
        for method, value in (("getLength(param)", 0.5), ("getParam(length)", 1.0)):
            call = queries[method]
            with self.subTest(method=method):
                self.assertRaises(TypeError, call, value, distanceUnit=5)
                self.assertRaises(ValueError, call, value, distanceUnit="furlong")
        self.assertAlmostEqual(curve.getLength(1.0, distanceUnit="m"), 0.03, places=6)
        self.assertAlmostEqual(curve.getParam(length=0.015, distanceUnit="m"), 0.5, places=5)

    def test_get_param_at_length_errors(self):
        """length が数値でないは TypeError、有限でない・負・全長超えは ValueError。"""
        curve = self.curve()
        for error, length in (
            (TypeError, "a"),
            (TypeError, None),
            (ValueError, float("inf")),
            (ValueError, float("nan")),
            (ValueError, -1.0),
            (ValueError, 3.5),
        ):
            with self.subTest(length=length):
                self.assertRaises(error, curve.getParam, length=length)

    def test_get_params_along_errors(self):
        """count が int 以外(bool を含む)は TypeError、1 未満は ValueError。"""
        curve = self.curve()
        for error, count in ((TypeError, True), (TypeError, 2.0), (TypeError, "3"), (ValueError, 0), (ValueError, -1)):
            with self.subTest(count=count):
                self.assertRaises(error, curve.getParamsAlong, count)
        self.assertSequenceAlmostEqual(curve.getParamsAlong(3), (0.0, 0.5, 1.0), places=5)


class ObjectSetErrorTest(_Case):
    """ObjectSet.addMembers で Maya が追加を拒否する場合。"""

    def object_set(self):
        return mlib.getNode(cmds.sets(name=self.name("set#"), empty=True))

    def members(self, object_set):
        return sorted(cmds.sets(object_set.getName(full=True), query=True) or [])

    def test_cycle_is_rejected(self):
        """セット自身の追加は循環になるため RuntimeError で、メンバーは変わらない。"""
        object_set = self.object_set()
        member = self.node("transform")
        object_set.addMembers(member)
        before = self.members(object_set)
        self.assertRaises(RuntimeError, object_set.addMembers, object_set)
        self.assertEqual(self.members(object_set), before)

    def test_partition_exclusivity_is_rejected(self):
        """同じ partition の別のセットに入っているノードの追加は RuntimeError で、どちらも加わらない。"""
        partition = cmds.partition(name=self.name("partition#"))
        first, second = self.object_set(), self.object_set()
        cmds.partition(first.getName(full=True), add=partition)
        cmds.partition(second.getName(full=True), add=partition)
        taken, free = self.node("transform"), self.node("transform")
        first.addMembers(taken)
        self.assertRaises(RuntimeError, second.addMembers, free, taken)
        self.assertEqual(self.members(second), [])
        self.assertEqual(self.members(first), [taken.getName()])

    def test_input_errors(self):
        """未対応型・名前とノードの混在は TypeError、一致しない名前は ValueError で、メンバーは変わらない。"""
        object_set = self.object_set()
        member = self.node("transform")
        for error, members in ((TypeError, (5,)), (TypeError, (None,)), (TypeError, (member, self.name("other"))), (ValueError, (self.name("missing"),))):
            with self.subTest(members=members):
                self.assertRaises(error, object_set.addMembers, *members)
                self.assertEqual(self.members(object_set), [])


class ReferenceErrorTest(_Case):
    """Reference.setLoaded(False) で Maya がアンロードを拒否する場合。"""

    def test_unload_without_file_raises(self):
        """ファイルに結び付いていない reference ノードの setLoaded(False) は RuntimeError。"""
        reference = mlib.getNode(self.make("reference", "unboundRN#"))
        self.assertRaises(RuntimeError, reference.setLoaded, False)
        self.assertTrue(cmds.objExists(reference.getName(full=True)))


class ShadingEngineErrorTest(_Case):
    """ShadingEngine.setShader。"""

    def engine(self):
        return mlib.getNode(cmds.sets(name=self.name("SG#"), renderable=True, noSurfaceShader=True, empty=True))

    def sources(self, engine, attribute="surfaceShader"):
        return cmds.listConnections(engine.getName(full=True) + "." + attribute, source=True, destination=False, plugs=True) or []

    def test_unknown_kind_raises_value_error(self):
        """kind が surface・volume・displacement 以外は ValueError で、接続は変わらない(fast も同じ)。"""
        engine = self.engine()
        shader = self.node("lambert")
        for fast in (False, True):
            for kind in ("missing", "Surface", ""):
                with self.subTest(fast=fast, kind=kind):
                    self.assertRaises(ValueError, engine.setShader, shader, kind=kind, fast=fast)
                    self.assertEqual(self.sources(engine), [])

    def test_maya_rejects_connection(self):
        """自身のアトリビュートへの接続を Maya が拒否すると RuntimeError で、接続は変わらない。"""
        engine = self.engine()
        shader = self.node("lambert")
        engine.setShader(shader)
        before = self.sources(engine)
        self.assertRaises(RuntimeError, engine.setShader, engine.getPlug("surfaceShader"))
        self.assertEqual(self.sources(engine), before)

    def test_replaces_existing_connection(self):
        """正常系: 別のシェーダーを指定すると既存の接続を置き換える。"""
        engine = self.engine()
        first, second = self.node("lambert"), self.node("lambert")
        engine.setShader(first)
        engine.setShader(second)
        self.assertEqual(self.sources(engine), [second.getName() + ".outColor"])

    def test_same_shader_again_is_no_op(self):
        """接続済みの同じシェーダーの再指定は例外にせず、接続も変わらない(fast も同じ)。"""
        engine = self.engine()
        shader = self.node("lambert")
        engine.setShader(shader)
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.assertIsNone(engine.setShader(shader, fast=fast))
                self.assertEqual(self.sources(engine), [shader.getName() + ".outColor"])

    def test_self_connection_rejected_with_fast(self):
        """fast=True でも自身の surfaceShader への接続は RuntimeError で、接続は変わらない。"""
        engine = self.engine()
        shader = self.node("lambert")
        engine.setShader(shader)
        before = self.sources(engine)
        self.assertRaises(RuntimeError, engine.setShader, engine.getPlug("surfaceShader"), fast=True)
        self.assertEqual(self.sources(engine), before)


class SkinClusterErrorTest(_Case):
    """SkinCluster の保存ポーズ・ウェイトの照会と書き出し。"""

    def skin(self):
        self.track_outside_nodes()
        cmds.select(clear=True)
        root = cmds.joint(name=self.name("root"), position=(0, 0, 0))
        cmds.joint(name=self.name("tip"), position=(0, 1, 0))
        cmds.select(clear=True)
        cmds.joint(name=self.name("unused"), position=(5, 5, 5))
        cmds.select(clear=True)
        mesh = cmds.polyCylinder(name=self.name("body"), constructionHistory=False)[0]
        skin = cmds.skinCluster(root, self.name("tip"), self.name("unused"), mesh, toSelectedBones=True, name=self.name("skin"))[0]
        return mlib.getNode(skin)

    def test_get_bind_pose_errors(self):
        """bindPose が dagPose 以外へつながる・skinCluster が無効な場合は RuntimeError。"""
        skin = self.skin()
        plug = skin.getName(full=True) + ".bindPose"
        pose = cmds.listConnections(plug, source=True, destination=False, plugs=True)[0]
        self.assertEqual(skin.getBindPose().getName(full=True), cmds.ls(pose.split(".")[0], long=True)[0])
        cmds.disconnectAttr(pose, plug)
        self.assertIsNone(skin.getBindPose())
        cmds.connectAttr(self.make("transform", "notPose#") + ".message", plug)
        self.assertRaises(RuntimeError, skin.getBindPose)
        cmds.delete(skin.getName(full=True))
        self.assertRaises(RuntimeError, skin.getBindPose)

    def test_get_unused_influences(self):
        """正常系: 頂点にウェイトを持たない influence だけを返す。"""
        skin = self.skin()
        self.assertEqual([node.getName() for node in skin.getInfluences(unused=True)], [self.name("unused")])

    def test_get_unused_influences_invalid(self):
        """削除した skinCluster の getInfluences(unused=True) は RuntimeError(Undo の記録の有無によらない)。"""
        skin = self.skin()
        cmds.delete(skin.getName(full=True))
        self.assertRaises(RuntimeError, skin.getInfluences, unused=True)
        cmds.flushUndo()
        self.assertRaises(RuntimeError, skin.getInfluences, unused=True)

    def test_export_weights_invalid(self):
        """削除した skinCluster の exportWeights は RuntimeError で、ファイルを作らない。"""
        skin = self.skin()
        root = self.temp_dir()
        cmds.delete(skin.getName(full=True))
        self.assertRaises(RuntimeError, skin.exportWeights, os.path.join(root, "weights.json"))
        self.assertEqual(os.listdir(root), [])

    def test_get_weights_data_invalid(self):
        """削除した skinCluster の getWeightsData は RuntimeError。"""
        skin = self.skin()
        self.assertEqual(skin.getWeightsData()["vertexCount"], cmds.polyEvaluate(self.name("body"), vertex=True))
        cmds.delete(skin.getName(full=True))
        self.assertRaises(RuntimeError, skin.getWeightsData)

    def test_export_weights_to_missing_folder(self):
        """存在しないフォルダーへの exportWeights は OSError で、フォルダーもファイルも作らない。"""
        skin = self.skin()
        root = self.temp_dir()
        target = os.path.join(root, "missing", "weights.json")
        self.assertRaises(OSError, skin.exportWeights, target)
        self.assertEqual(os.listdir(root), [])


class TransformErrorTest(_Case):
    """Transform の照会・回転の設定・カーブ形状の書き出し。"""

    def test_invalid_transform_raises_runtime_error(self):
        """削除した Transform の各照会は RuntimeError(Undo の記録の有無によらない)。"""
        calls = (("getOffsetParentMatrix", ()), ("getUnusedIntermediateShapes", ()), ("getCurveShapesData", ()), ("getClosestAxisToVector", ((1, 0, 0),)))
        for method, args in calls:
            for flush in (False, True):
                with self.subTest(method=method, flush=flush):
                    self.assertRaises(RuntimeError, getattr(self.deleted(flush=flush), method), *args)

    def test_export_curve_shapes_errors(self):
        """無効な Transform は RuntimeError、存在しないフォルダーは OSError。ファイルは作らない。"""
        root = self.temp_dir()
        self.assertRaises(RuntimeError, self.deleted().exportCurveShapes, os.path.join(root, "shapes.json"))
        transform = mlib.getNode(cmds.circle(name=self.name("ctrl#"), constructionHistory=False)[0])
        self.assertRaises(OSError, transform.exportCurveShapes, os.path.join(root, "missing", "shapes.json"))
        self.assertEqual(os.listdir(root), [])
        path = transform.exportCurveShapes(os.path.join(root, "shapes.json"))
        self.assertTrue(path.is_file())

    def test_get_pivot_errors(self):
        """kind が rotate・scale 以外は ValueError。"""
        transform = self.node("transform")
        for kind in ("translate", "", "Rotate"):
            with self.subTest(kind=kind):
                self.assertRaises(ValueError, transform.getPivot, kind=kind)
        cmds.xform(transform.getName(full=True), scalePivot=(1, 2, 3))
        self.assertSequenceAlmostEqual(transform.getPivot(kind="scale"), (1, 2, 3))

    def test_get_closest_axis_to_vector_zero_vectors(self):
        """refVector がゼロなら ValueError。ワールドで長さ0になる軸は選ばず、すべて0なら "x"。"""
        transform = self.node("transform")
        self.assertRaises(ValueError, transform.getClosestAxisToVector, (0, 0, 0))
        flat = self.node("transform")
        cmds.setAttr(flat.getName(full=True) + ".offsetParentMatrix", [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], type="matrix")
        empty = self.node("transform")
        cmds.setAttr(empty.getName(full=True) + ".offsetParentMatrix", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1], type="matrix")
        for include_negative in (True, False):
            with self.subTest(includeNegative=include_negative):
                # x の軸は長さ0なので、refVector と同じ向きでも選ばない(内積が同じ0の軸は y・z の順に先のもの)。
                self.assertEqual(flat.getClosestAxisToVector((1, 0, 0), includeNegative=include_negative), "y")
                self.assertEqual(flat.getClosestAxisToVector((0, 1, 0), includeNegative=include_negative), "y")
                self.assertEqual(empty.getClosestAxisToVector((0, 1, 0), includeNegative=include_negative), "x")
        cmds.setAttr(transform.getName(full=True) + ".rotateZ", 90)
        self.assertEqual(transform.getClosestAxisToVector((0, 1, 0)), "x")
        self.assertEqual(transform.getClosestAxisToVector((1, 0, 0)), "-y")

    def test_set_quaternion_errors(self):
        """unit が文字列以外は TypeError、未対応の単位名・未対応の成分と空間の組合せは ValueError。rotate は変わらない。"""
        transform = self.node("transform")
        cmds.setAttr(transform.getName(full=True) + ".rotate", 10, 20, 30)
        half = math.sqrt(0.5)
        value = (0.0, 0.0, half, half)
        cases = (
            (TypeError, {"unit": "deg"}),
            (TypeError, {"unit": "deg", "get": True}),
            (ValueError, {"worldSpace": True, "jointOrient": False}),
            (ValueError, {"worldSpace": True, "rotate": False}),
            (ValueError, {"ws": True, "rotate": False, "rotateAxis": True}),
        )
        for error, flags in cases:
            with self.subTest(flags=flags):
                self.assertRaises(error, transform.setQuaternion, value, **flags)
                self.assertSequenceAlmostEqual(cmds.getAttr(transform.getName(full=True) + ".rotate")[0], (10, 20, 30), places=6)
        transform.setQuaternion(value)
        self.assertSequenceAlmostEqual(cmds.getAttr(transform.getName(full=True) + ".rotate")[0], (0, 0, 90), places=6)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
