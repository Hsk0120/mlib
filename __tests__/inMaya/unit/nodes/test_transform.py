"""Transformの空間・単位・親子変更と失敗時の状態を検証する。

あわせて次も確かめる。

- mlib Node/DAG APIを検証するMaya内テスト。
- NurbsSurface・Transform・Vector・コンポーネント等のメソッド・引数の名前を確かめる。
"""

import math
import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Translate, Vector
from mlib.nodes import Node


class NodeApiTest(unittest.TestCase):
    """基本Node/DAG APIを検証する。"""

    namespace = ":mlibNodeApiTest"

    def setUp(self):
        self.created = []
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.namespace(add=self.namespace)

    def tearDown(self):
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)

    def create_transform(self, name):
        node = mlib.createNode(type="transform", name=name)
        self.created.append(node.getName())
        return node

    def test_transform_matrix_round_trip_uses_om2_maths_values(self):
        transform = self.create_transform("mlibNodeApiMatrix")

        transform.setTranslation((1.0, 2.0, 3.0), at=4)
        transform.setRotate((0.0, 90.0, 0.0))
        transform.setScale((2.0, 1.0, 1.0))

        translate = transform.getTranslation(at=4)
        self.assertIsInstance(translate, Translate)
        self.assertEqual(translate, Translate(1.0, 2.0, 3.0))

        scale = transform.getScale()
        self.assertIsInstance(scale, Scale)
        self.assertAlmostEqual(scale.x, 2.0, places=6)

        matrix = transform.getMatrix()
        self.assertIsInstance(matrix, Matrix)
        self.assertEqual(matrix.translate, translate)

        # om2.MVector を継承するため、等価比較は om2 と同じ値の比較になり、
        # 派生型(Translate/Scale)が違っても成分が同じなら等しい。型は保持される。
        self.assertEqual(translate, Scale(1.0, 2.0, 3.0))
        self.assertIsNot(type(translate), Scale)

    def test_transform_pivot_get_set_local_and_world(self):
        transform = self.create_transform("mlibNodeApiPivot")

        default_pivot = transform.getPivot()
        self.assertIsInstance(default_pivot, Translate)
        self.assertEqual(default_pivot, Translate(0.0, 0.0, 0.0))

        result = transform.setPivot((1.0, 2.0, 3.0), kind="both", preserve=False)
        self.assertIs(result, transform)
        self.assertEqual(transform.getPivot(), Translate(1.0, 2.0, 3.0))
        cmds.undo()
        self.assertEqual(transform.getPivot(), default_pivot)
        cmds.redo()
        self.assertEqual(transform.getPivot(), Translate(1.0, 2.0, 3.0))

        transform.setTranslation((10.0, 0.0, 0.0), at=4)
        self.assertEqual(transform.getPivot(worldSpace=True), Translate(11.0, 2.0, 3.0))

        previous_unit = cmds.currentUnit(query=True, linear=True)
        try:
            cmds.currentUnit(linear="m")
            transform.setPivot((25.0, 50.0, 75.0), worldSpace=True, kind="both", preserve=False)
            self.assertEqual(transform.getPivot(worldSpace=True), Translate(25.0, 50.0, 75.0))
            cmds.undo()
            self.assertEqual(transform.getPivot(worldSpace=True), Translate(11.0, 2.0, 3.0))
            cmds.redo()
            self.assertEqual(transform.getPivot(worldSpace=True), Translate(25.0, 50.0, 75.0))
        finally:
            cmds.currentUnit(linear=previous_unit)

    def test_transform_bounding_box_local_and_world(self):
        mesh_transform_name = cmds.polyCube(name="mlibNodeApiBoundingBoxMesh", constructionHistory=False)[0]
        self.created.append(mesh_transform_name)
        transform = Node(mesh_transform_name)

        box = transform.getBoundingBox()
        self.assertAlmostEqual(box.min.x, -0.5, places=5)
        self.assertAlmostEqual(box.max.x, 0.5, places=5)

        # boundingBox() は自身の translate は含むが、親の変換はまだ無いので world と一致する。
        transform.setTranslation((10.0, 0.0, 0.0), at=4)
        self.assertAlmostEqual(transform.getBoundingBox().min.x, 9.5, places=5)
        self.assertAlmostEqual(transform.getBoundingBox(worldSpace=True).min.x, 9.5, places=5)

        parent = self.create_transform("mlibNodeApiBoundingBoxParent")
        parent.setTranslation((100.0, 0.0, 0.0), at=4)
        # relative=True で子のローカル translate を変えずに親子付けする
        # (既定はワールド位置維持のためローカル値が自動調整されてしまう)。
        cmds.parent(mesh_transform_name, parent.getName(), relative=True)

        # ws=False は親の translate を含まない。ws=True は含む。
        self.assertAlmostEqual(transform.getBoundingBox().min.x, 9.5, places=5)
        world_box = transform.getBoundingBox(worldSpace=True)
        self.assertAlmostEqual(world_box.min.x, 109.5, places=5)
        self.assertAlmostEqual(world_box.max.x, 110.5, places=5)

    def test_transform_leaves_siblings_and_child_transforms(self):
        root = self.create_transform("mlibNodeApiLeavesRoot")
        branch_a = self.create_transform("mlibNodeApiLeavesA")
        branch_b = self.create_transform("mlibNodeApiLeavesB")
        leaf_a1 = self.create_transform("mlibNodeApiLeavesA1")
        branch_a.setParent(root)
        branch_b.setParent(root)
        leaf_a1.setParent(branch_a)

        self.assertEqual(sorted(node.getName() for node in root.getChildren()), ["mlibNodeApiLeavesA", "mlibNodeApiLeavesB"])

        leaf_names = sorted(node.getName() for node in root.getChildren(leaves=True, includeSelf=True))
        self.assertEqual(leaf_names, ["mlibNodeApiLeavesA1", "mlibNodeApiLeavesB"])
        self.assertEqual(leaf_a1.getChildren(leaves=True, includeSelf=True), [leaf_a1])

        self.assertEqual([s.getName() for s in branch_a.getSiblings()], ["mlibNodeApiLeavesB"])
        self.assertEqual(branch_b.getSiblings()[0].getName(), "mlibNodeApiLeavesA")

        self.create_transform("mlibNodeApiLeavesWorldSibling")
        root_sibling_names = {s.getName() for s in root.getSiblings()}
        self.assertIn("mlibNodeApiLeavesWorldSibling", root_sibling_names)
        self.assertNotIn("mlibNodeApiLeavesRoot", root_sibling_names)

    def test_transform_show_hide(self):
        transform = self.create_transform("mlibNodeApiShowHide")

        result = transform.setVisibility(False)
        self.assertIs(result, transform)
        self.assertFalse(transform.getPlug("visibility").get())

        transform.setVisibility(True)
        self.assertTrue(transform.getPlug("visibility").get())

    def test_transform_make_identity_freezes_transform(self):
        transform = self.create_transform("mlibNodeApiFreeze")
        transform.setTranslation((1.0, 2.0, 3.0), at=4)

        result = transform.makeIdentity(apply=True, translate=True)
        self.assertIs(result, transform)
        self.assertEqual(transform.getTranslation(at=4), Translate(0.0, 0.0, 0.0))

    def test_transform_closest_axis_to_vector(self):
        transform = self.create_transform("mlibNodeApiClosestAxis")

        self.assertEqual(transform.getClosestAxisToVector(Vector(1.0, 0.0, 0.0)), "x")
        self.assertEqual(transform.getClosestAxisToVector(Vector(0.0, -1.0, 0.0)), "-y")
        self.assertEqual(transform.getClosestAxisToVector(Vector(0.0, 1.0, 0.0), includeNegative=False), "y")

        transform.setRotate((0.0, 90.0, 0.0))
        self.assertEqual(transform.getClosestAxisToVector(Vector(0.0, 0.0, -1.0)), "x")

    def test_transform_shear_quaternion_euler_and_decompose(self):
        transform = self.create_transform("mlibNodeApiShearQuat")
        result = transform.setShear((0.1, 0.2, 0.3))
        self.assertIs(result, transform)
        shear = transform.getShear()
        self.assertIsInstance(shear, Shear)
        self.assertAlmostEqual(shear.x, 0.1, places=6)
        self.assertAlmostEqual(shear.y, 0.2, places=6)
        self.assertAlmostEqual(shear.z, 0.3, places=6)

        transform.setRotate((0.0, 90.0, 0.0))
        quaternion = transform.getQuaternion()
        self.assertIsInstance(quaternion, Quaternion)
        euler = transform.getRotate(order=0)
        self.assertIsInstance(euler, EulerRotate)
        self.assertAlmostEqual(euler.y, math.radians(90.0), places=6)

        matrix = transform.getMatrix(worldSpace=True)
        self.assertIsInstance(matrix, Matrix)
        self.assertEqual(matrix, transform.getMatrix(worldSpace=True))

    def test_transform_set_matrix_round_trips_matrix_and_rejects_non_matrix(self):
        source = self.create_transform("mlibNodeApiComposeSource")
        source.setTranslation((1.0, 2.0, 3.0), at=4)
        source.setRotate((0.0, 45.0, 0.0))
        matrix = source.getMatrix(worldSpace=True)

        target = self.create_transform("mlibNodeApiComposeTarget")
        result = target.setMatrix(matrix, worldSpace=True)
        self.assertIs(result, target)
        self.assertTrue(target.getMatrix(worldSpace=True).isEquivalent(matrix, tolerance=1e-6))

        with self.assertRaises(ValueError):
            target.setMatrix((1, 2, 3))

    def test_transform_set_matrix_direct_accepts_raw_values_and_guards_invalid_node(self):
        transform = self.create_transform("mlibNodeApiSetMatrixDirect")
        matrix = Matrix(translate=(1.0, 2.0, 3.0))
        result = transform.setMatrix(matrix)
        self.assertIs(result, transform)
        self.assertEqual(transform.getTranslation(at=4), Translate(1.0, 2.0, 3.0))

        # Matrix以外の16要素入力も内部でMatrixへ変換して受け付ける。
        transform.setMatrix((1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 5.0, 6.0, 7.0, 1.0))
        self.assertEqual(transform.getTranslation(at=4), Translate(5.0, 6.0, 7.0))

        cmds.delete(transform.getName())
        with self.assertRaises(RuntimeError):
            transform.setMatrix(matrix)

    def test_transform_set_matrix_round_trip_preserves_world_for_every_rotate_order(self):
        # XYZ で分解した回転をノードの rotateOrder へ並べ替えて書き込むため、
        # xyz 以外の順序でも setMatrix / setTranslation / rotate プラグの往復で姿勢が変わらない。
        parent = self.create_transform("mlibNodeApiOrderParent")
        cmds.setAttr(parent.getFullName() + ".rotate", 10.0, 20.0, 30.0)
        for order in range(6):
            node = self.create_transform(f"mlibNodeApiOrder{order:d}")
            node.setParent(parent)
            name = node.getFullName()
            cmds.setAttr(name + ".rotateOrder", order)
            cmds.setAttr(name + ".translate", 1.0, 2.0, 3.0)
            cmds.setAttr(name + ".rotate", 40.0, -50.0, 60.0)
            cmds.setAttr(name + ".scale", 1.0, 2.0, 3.0)
            world = node.getMatrix(worldSpace=True)

            node.setMatrix(node.getMatrix())
            self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(world, 1e-9), order)
            node.setMatrix(world, worldSpace=True)
            self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(world, 1e-9), order)
            node.setTranslation((4.0, 5.0, 6.0), at=4)
            self.assertTrue(node.getQuaternion(worldSpace=True).isEquivalent(world.quaternion, 1e-9), order)

            before = node.getMatrix()
            rotate = node.getPlug("rotate").get()
            self.assertIsInstance(rotate, EulerRotate)
            self.assertEqual(rotate.order, order)
            node.getPlug("rotate").set(rotate)
            self.assertTrue(node.getMatrix().isEquivalent(before, 1e-9), order)
            node.setRotate(EulerRotate.fromDegrees(40.0, -50.0, 60.0, order))
            self.assertTrue(node.getMatrix().isEquivalent(before, 1e-9), order)
        with self.assertRaises(ValueError):
            node.setRotate((0.1, 0.2, 0.3), unit="grad")

    def assert_channels(self, name, rotate, scale, places=9):
        for actual, expected in zip(cmds.getAttr(name + ".rotate")[0], rotate):
            self.assertAlmostEqual(actual, expected, places=places)
        for actual, expected in zip(cmds.getAttr(name + ".scale")[0], scale):
            self.assertAlmostEqual(actual, expected, places=places)

    def test_transform_negative_scale_keeps_channel_sign_pattern(self):
        # Matrix の分解は om2 の規約(Z が負)だが、ノードの取得・設定はスケールの符号を
        # 現在の scale チャンネルへ揃えるため、X をミラーしたノードでも rotate が保たれる。
        node = self.create_transform("mlibNodeApiNegativeScale")
        name = node.getFullName()
        cmds.setAttr(name + ".rotate", 10.0, 20.0, 30.0)
        cmds.setAttr(name + ".scale", -1.0, 2.0, 3.0)
        matrix = node.getMatrix()
        transformation = om2.MTransformationMatrix(matrix)
        self.assertTrue(matrix.scale.isEquivalent(Vector(*transformation.scale(om2.MSpace.kTransform)), 1e-12))
        self.assertLess(matrix.scale.z, 0.0)

        scale = node.getScale()
        self.assertIsInstance(scale, Scale)
        self.assertTrue(scale.isEquivalent(Scale(-1.0, 2.0, 3.0), 1e-12))
        rotate = node.getRotate()
        self.assertTrue(rotate.isEquivalent(EulerRotate.fromDegrees(10.0, 20.0, 30.0), 1e-12))
        self.assertTrue(Matrix(rotate=node.getQuaternion(), scale=scale).isEquivalent(matrix, 1e-12))

        world = node.getMatrix(worldSpace=True)
        for operation in (
            lambda: node.setMatrix(matrix),
            lambda: node.setMatrix(world, worldSpace=True),
            lambda: node.setTranslation((0.0, 0.0, 0.0), at=4),
            lambda: node.setScale(node.getScale()),
            lambda: node.setShear(node.getShear()),
            lambda: node.setRotate((10.0, 20.0, 30.0), unit="deg"),
            lambda: node.getPlug("rotate").set(tuple(node.getPlug("rotate").get()), unit="rad"),
            lambda: node.getPlug("rotate").set(node.getPlug("rotate").get(unit="deg")),
        ):
            operation()
            self.assertTrue(node.getMatrix().isEquivalent(matrix, 1e-9))
            self.assert_channels(name, (10.0, 20.0, 30.0), (-1.0, 2.0, 3.0))

        # スケールだけを変えても rotate は変わらない(ミラーを解除しても姿勢が 180 度回らない)。
        node.setScale((1.0, 2.0, 3.0))
        self.assert_channels(name, (10.0, 20.0, 30.0), (1.0, 2.0, 3.0))

    def test_set_scale_writes_the_requested_signs(self):
        # setScale / plug("scale").set で明示した符号は、現在の scale チャンネルの符号に
        # かかわらずそのまま入り、rotate も変わらない(cmds.setAttr で scale を書いた場合と同じ)。
        cases = (
            ((1.0, 1.0, 1.0), (-1.0, 1.0, 1.0)),
            ((-1.0, -2.0, 3.0), (1.0, 1.0, 1.0)),
            ((-1.0, -1.0, 1.0), (2.0, 2.0, 2.0)),
            ((1.0, 1.0, 1.0), (1.0, -1.0, 1.0)),
            ((-1.0, 1.0, 1.0), (-2.0, -3.0, -4.0)),
            ((1.0, 2.0, 3.0), (-1.0, -2.0, -3.0)),
        )
        for kind in ("transform", "joint"):
            for use_plug in (False, True):
                for order in (0, 4):
                    for start, requested in cases:
                        name = cmds.createNode(kind, name=self.namespace + ":mlibNodeApiScaleSign")
                        self.created.append(name)
                        cmds.setAttr(name + ".rotateOrder", order)
                        cmds.setAttr(name + ".rotate", 10.0, 20.0, 30.0)
                        cmds.setAttr(name + ".scale", *start)
                        node = Node(name)
                        if use_plug:
                            node.getPlug("scale").set(requested)
                        else:
                            node.setScale(requested)
                        label = (kind, use_plug, order, start, requested)
                        for actual, expected in zip(cmds.getAttr(name + ".scale")[0], requested):
                            self.assertAlmostEqual(actual, expected, places=9, msg=label)
                        for actual, expected in zip(cmds.getAttr(name + ".rotate")[0], (10.0, 20.0, 30.0)):
                            self.assertAlmostEqual(actual, expected, places=9, msg=label)
                        self.assertTrue(node.getScale().isEquivalent(Scale(*requested), 1e-9), label)
                        cmds.delete(name)

        # ワールド空間でも、親の行列式が正なら要求した符号の組み合わせになる。
        parent = self.create_transform("mlibNodeApiScaleSignParent")
        cmds.setAttr(parent.getFullName() + ".rotate", 30.0, 0.0, 0.0)
        cmds.setAttr(parent.getFullName() + ".scale", 2.0, 2.0, 2.0)
        child = self.create_transform("mlibNodeApiScaleSignChild")
        child.setParent(parent)
        cmds.setAttr(child.getFullName() + ".rotate", 10.0, 20.0, 30.0)
        child.setScale((-1.0, 1.0, 1.0), worldSpace=True)
        self.assert_channels(child.getFullName(), (10.0, 20.0, 30.0), (0.5, 0.5, -0.5))
        self.assertTrue(child.getScale(worldSpace=True).isEquivalent(Scale(1.0, 1.0, -1.0), 1e-9))

        # setMatrix は現在のチャンネルの符号に揃え、合わなければ om2 の規約(Z が負)で書く。
        target = self.create_transform("mlibNodeApiScaleSignMatrix")
        target.setMatrix(Matrix(scale=(-1.0, 1.0, 1.0)))
        self.assert_channels(target.getFullName(), (0.0, 180.0, 0.0), (1.0, 1.0, -1.0))
        self.assertTrue(target.getMatrix().isEquivalent(Matrix(scale=(-1.0, 1.0, 1.0)), 1e-9))

    def test_transform_matrix_writes_choose_the_closest_euler_solution(self):
        node = self.create_transform("mlibNodeApiClosestEuler")
        name = node.getFullName()
        cmds.setAttr(name + ".rotate", 370.0, -20.0, 190.0)
        node.setMatrix(node.getMatrix())
        node.setTranslation((1.0, 2.0, 3.0), at=4)
        self.assert_channels(name, (370.0, -20.0, 190.0), (1.0, 1.0, 1.0))
        # 等価な別解 (180+10, 180-(-20), 180+190) を渡しても、現在値に近い解で書く。
        node.setRotate(EulerRotate.fromDegrees(190.0, 200.0, 370.0))
        self.assert_channels(name, (370.0, -20.0, 190.0), (1.0, 1.0, 1.0))

    def test_transform_flat_rotate_values_use_the_node_rotate_order(self):
        # 3成分の値は cmds.xform と同じくノードの rotateOrder の値として扱うため、
        # plug("rotate") の get と set、getRotate と setRotate が対称になる。
        parent = self.create_transform("mlibNodeApiFlatOrderParent")
        cmds.setAttr(parent.getFullName() + ".rotate", 15.0, -25.0, 40.0)
        for order in range(6):
            node = self.create_transform(f"mlibNodeApiFlatOrder{order:d}")
            node.setParent(parent)
            name = node.getFullName()
            cmds.setAttr(name + ".rotateOrder", order)
            cmds.setAttr(name + ".rotate", 10.0, 20.0, 30.0)
            local = node.getMatrix()
            world = node.getMatrix(worldSpace=True)

            rotate = node.getRotate()
            self.assertEqual(rotate.order, order)
            self.assertTrue(rotate.isEquivalent(EulerRotate.fromDegrees(10.0, 20.0, 30.0, order), 1e-12))

            plug = node.getPlug("rotate")
            plug.set(plug.get(unit="deg"))
            self.assert_channels(name, (10.0, 20.0, 30.0), (1.0, 1.0, 1.0))
            node.setRotate(node.getRotate().asDegrees())
            node.setRotate(tuple(node.getRotate(worldSpace=True)), worldSpace=True, unit="rad")
            self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(world, 1e-9), order)
            node.setRotate(node.getRotate(worldSpace=True).asDegrees(), worldSpace=True)
            self.assertTrue(node.getMatrix().isEquivalent(local, 1e-9), order)

            cmds.setAttr(name + ".rotate", 0.0, 0.0, 0.0)
            node.setRotate((10.0, 20.0, 30.0), unit="deg")
            self.assert_channels(name, (10.0, 20.0, 30.0), (1.0, 1.0, 1.0))
            cmds.setAttr(name + ".rotate", 0.0, 0.0, 0.0)
            plug.set(tuple(math.radians(value) for value in (10.0, 20.0, 30.0)), unit="rad")
            self.assert_channels(name, (10.0, 20.0, 30.0), (1.0, 1.0, 1.0))


class TransformBasicsTest(unittest.TestCase):
    """同じ入力をMayaコマンドへ適用した結果と比較する。"""

    def setUp(self):
        self.namespace = ":transformBasics_" + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)
        self.undo_state = cmds.undoInfo(query=True, state=True)
        self.units = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True))
        cmds.undoInfo(state=True)
        cmds.currentUnit(linear="cm", angle="deg")

    def tearDown(self):
        for name in cmds.ls(self.namespace + ":*", long=True) or []:
            if cmds.objExists(name):
                cmds.lockNode(name, lock=False)
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.currentUnit(linear=self.units[0], angle=self.units[1])
        cmds.undoInfo(state=self.undo_state)

    def make(self, parent=None, kind="transform"):
        """選択を変更せずTransformを作る。"""
        flags = {"parent": parent.getFullName()} if parent is not None else {}
        return mlib.getNode(cmds.createNode(kind, name=self.namespace + ":node#", skipSelect=True, **flags))

    def matrix(self, node, world=False):
        """cmdsから16成分を取得し、mlibの取得結果へ依存せず比較する。"""
        return cmds.xform(node.getFullName(), query=True, matrix=True, worldSpace=world)

    def assertValuesAlmostEqual(self, actual, expected):
        """XYZやマトリクスを同じ許容誤差で比較する。"""
        self.assertEqual(len(actual), len(expected))
        for index, (value, reference) in enumerate(zip(actual, expected)):
            self.assertAlmostEqual(value, reference, places=6, msg=f"component {index}")

    def test_local_translation_uses_cm_despite_ui_unit_and_preserves_offsets(self):
        """m表示でもcmでtranslateを設定し、回転・スケール・ピボットを保つ。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                node = self.make()
                name = node.getFullName()
                offsets = {"r": (20, -30, 40), "s": (2, 3, 4), "sh": (0.1, 0.2, 0.3), "rp": (1, 2, 3), "rpt": (4, 5, 6), "sp": (-1, -2, -3)}
                for attr, value in offsets.items():
                    cmds.setAttr(name + "." + attr, *value)
                cmds.currentUnit(linear="m")
                before = {attr: cmds.getAttr(name + "." + attr) for attr in offsets}
                self.assertIs(node.setTranslation((100, -200, 300), at=1, fast=fast), node)
                self.assertValuesAlmostEqual(cmds.getAttr(name + ".t")[0], (1, -2, 3))
                self.assertEqual({attr: cmds.getAttr(name + "." + attr) for attr in offsets}, before)
                self.assertValuesAlmostEqual(tuple(node.getTranslation(at=1)), (100, -200, 300))
                cmds.currentUnit(linear="cm")

    def test_world_origin_translation_under_rotated_scaled_parent(self):
        """非一様スケールを持つ親の下でも、指定ワールド原点へ移動する。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                parent = self.make()
                cmds.setAttr(parent.getFullName() + ".t", 8, -3, 9)
                cmds.setAttr(parent.getFullName() + ".r", 20, 35, -15)
                cmds.setAttr(parent.getFullName() + ".s", 2, 3, 4)
                node = self.make(parent)
                cmds.setAttr(node.getFullName() + ".r", 11, 22, 33)
                cmds.setAttr(node.getFullName() + ".rp", 1, 2, 3)
                rotation = cmds.getAttr(node.getFullName() + ".r")
                self.assertIs(node.setTranslation((30, -20, 10), worldSpace=True, at=4, fast=fast), node)
                self.assertValuesAlmostEqual(self.matrix(node, world=True)[12:15], (30, -20, 10))
                self.assertEqual(cmds.getAttr(node.getFullName() + ".r"), rotation)

    def test_rotation_matches_cmds_for_all_rotate_orders(self):
        """6種のrotateOrderとrotateAxisを含め、角度入力をcmdsと比較する。"""
        for fast in (False, True):
            for order in range(6):
                with self.subTest(fast=fast, order=order):
                    node, reference = self.make(), self.make()
                    for item in (node, reference):
                        name = item.getFullName()
                        cmds.setAttr(name + ".ro", order)
                        cmds.setAttr(name + ".ra", 7, -13, 19)
                        cmds.setAttr(name + ".t", 3, 4, 5)
                        cmds.setAttr(name + ".s", 2, 3, 4)
                        cmds.setAttr(name + ".rp", 1, -2, 3)
                    # setRotateの入力はrotateチャンネルではなく、rotateAxis込みの姿勢。
                    cmds.setAttr(reference.getFullName() + ".ra", 0, 0, 0)
                    cmds.setAttr(reference.getFullName() + ".r", 35, -50, 80)
                    self.assertIs(node.setRotate((35, -50, 80), unit="deg", fast=fast), node)
                    self.assertValuesAlmostEqual(self.matrix(node)[:12], self.matrix(reference)[:12])
                    self.assertEqual(cmds.getAttr(node.getFullName() + ".ra"), [(7, -13, 19)])
                    self.assertEqual(cmds.getAttr(node.getFullName() + ".t"), [(3, 4, 5)])
                    self.assertEqual(cmds.getAttr(node.getFullName() + ".s"), [(2, 3, 4)])
                    self.assertEqual(cmds.getAttr(node.getFullName() + ".rp"), [(1, -2, 3)])

    def test_scale_preserves_signed_channels_and_other_transform_values(self):
        """負スケールの指定値を保ち、回転・移動・シアーには書き込まない。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                node, reference = self.make(), self.make()
                for item in (node, reference):
                    name = item.getFullName()
                    cmds.setAttr(name + ".t", 3, -4, 5)
                    cmds.setAttr(name + ".r", 15, 30, 45)
                    cmds.setAttr(name + ".sh", 0.1, 0.2, -0.3)
                    cmds.setAttr(name + ".sp", 2, 1, -3)
                cmds.setAttr(reference.getFullName() + ".s", -2, 3, -4)
                self.assertIs(node.setScale((-2, 3, -4), fast=fast), node)
                self.assertEqual(cmds.getAttr(node.getFullName() + ".s"), [(-2, 3, -4)])
                self.assertValuesAlmostEqual(self.matrix(node), self.matrix(reference))

    def test_world_matrix_matches_cmds_with_nonuniform_parent(self):
        """ワールドマトリクスを親の非一様スケール込みで往復する。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                parent = self.make()
                cmds.setAttr(parent.getFullName() + ".t", 5, -7, 9)
                cmds.setAttr(parent.getFullName() + ".r", 10, 25, -35)
                cmds.setAttr(parent.getFullName() + ".s", 2, 3, 4)
                node, reference = self.make(parent), self.make()
                cmds.setAttr(reference.getFullName() + ".t", 30, -20, 10)
                cmds.setAttr(reference.getFullName() + ".r", -15, 40, 65)
                cmds.setAttr(reference.getFullName() + ".s", 1.2, 2.3, 3.4)
                cmds.setAttr(reference.getFullName() + ".sh", 0.1, -0.2, 0.3)
                target = self.matrix(reference, world=True)
                self.assertIs(node.setMatrix(target, worldSpace=True, fast=fast), node)
                self.assertValuesAlmostEqual(self.matrix(node, world=True), target)

    def test_matrix_update_is_one_undo_step_for_all_trs_and_shear(self):
        """複数チャンネルを変更するsetMatrixを一度のUndo/redoで戻す。"""
        node, reference = self.make(), self.make()
        cmds.setAttr(node.getFullName() + ".t", 1, 2, 3)
        cmds.setAttr(reference.getFullName() + ".t", 6, 7, 8)
        cmds.setAttr(reference.getFullName() + ".r", 20, 35, 50)
        cmds.setAttr(reference.getFullName() + ".s", 2, 3, 4)
        cmds.setAttr(reference.getFullName() + ".sh", 0.1, 0.2, 0.3)
        before, target = self.matrix(node), self.matrix(reference)
        cmds.flushUndo()
        node.setMatrix(target)
        self.assertValuesAlmostEqual(self.matrix(node), target)
        cmds.undo()
        self.assertValuesAlmostEqual(self.matrix(node), before)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        cmds.redo()
        self.assertValuesAlmostEqual(self.matrix(node), target)

    def test_fast_matrix_update_keeps_existing_undo_entry(self):
        """fastのマトリクス変更は別ノードの通常Undoを消費しない。"""
        node, marker, reference = self.make(), self.make(), self.make()
        cmds.setAttr(reference.getFullName() + ".t", 4, 5, 6)
        cmds.setAttr(reference.getFullName() + ".r", 10, 20, 30)
        target = self.matrix(reference)
        cmds.flushUndo()
        marker.setTranslation((7, 8, 9), at=1)
        entry = cmds.undoInfo(query=True, undoName=True)
        node.setMatrix(target, fast=True)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), entry)
        self.assertTrue(cmds.undoInfo(query=True, state=True))
        cmds.undo()
        self.assertValuesAlmostEqual(self.matrix(node), target)
        self.assertEqual(cmds.getAttr(marker.getFullName() + ".t"), [(0, 0, 0)])

    def test_calculated_world_translation_is_independent_and_does_not_write(self):
        """ロック中でもget=Trueは親空間への計算だけを行い、返すlistは独立する。"""
        parent = self.make()
        cmds.setAttr(parent.getFullName() + ".t", 10, 20, 30)
        cmds.setAttr(parent.getFullName() + ".s", 2, 3, 4)
        node = self.make(parent)
        cmds.setAttr(node.getFullName() + ".tx", lock=True)
        before = self.matrix(node)
        cmds.flushUndo()
        planned = node.setTranslation((14, 29, 46), worldSpace=True, at=1, safe=True, get=True)
        self.assertIsInstance(planned, list)
        self.assertValuesAlmostEqual(planned, (2, 3, 4))
        planned[0] = 999
        self.assertEqual(self.matrix(node), before)
        self.assertTrue(cmds.getAttr(node.getFullName() + ".tx", lock=True))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_reparent_preserves_world_or_local_matrix_as_requested(self):
        """親変更の既定はワールド、relative=Trueはローカルを保持する。"""
        for fast in (False, True):
            for relative in (False, True):
                with self.subTest(fast=fast, relative=relative):
                    old_parent, new_parent = self.make(), self.make()
                    for parent, position in ((old_parent, (5, 7, 9)), (new_parent, (-4, 2, 8))):
                        cmds.setAttr(parent.getFullName() + ".t", *position)
                        cmds.setAttr(parent.getFullName() + ".r", 10, 20, 30)
                        cmds.setAttr(parent.getFullName() + ".s", 2, 3, 4)
                    node = self.make(old_parent)
                    cmds.setAttr(node.getFullName() + ".t", 1, 2, 3)
                    cmds.setAttr(node.getFullName() + ".r", -15, 25, 35)
                    before = self.matrix(node, world=not relative)
                    held = node.getPlug("ty")
                    self.assertIs(node.setParent(new_parent, relative=relative, fast=fast), node)
                    self.assertEqual(node.getParent().mnode(), new_parent.mnode())
                    self.assertTrue(held.isValid())
                    self.assertValuesAlmostEqual(self.matrix(node, world=not relative), before)

    def test_reparent_undo_redo_rebinds_held_node_and_plug(self):
        """保持中のNode/Plugが親変更とUndo/redo後の完全パスへ追従する。"""
        old_parent, new_parent = self.make(), self.make()
        node = self.make(old_parent)
        held = node.getPlug("tx")
        cmds.setAttr(node.getFullName() + ".tx", 6)
        original = node.getFullName()
        cmds.flushUndo()
        node.setParent(new_parent, relative=True)
        changed = node.getFullName()
        self.assertNotEqual(original, changed)
        cmds.undo()
        self.assertEqual(node.getFullName(), original)
        self.assertEqual(held.get(), 6)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        cmds.redo()
        self.assertEqual(node.getFullName(), changed)
        self.assertEqual(held.get(), 6)

    def test_same_parent_and_world_root_are_noops(self):
        """同じ親と既にワールド直下の指定は、Undoへ空の更新を追加しない。"""
        for fast in (False, True):
            parent = self.make()
            child = self.make(parent)
            cmds.flushUndo()
            self.assertIs(child.setParent(parent, fast=fast), child)
            self.assertIs(parent.setParent(None, fast=fast), parent)
            self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_cycle_rejection_preserves_hierarchy_and_transforms(self):
        """子孫を親に指定しても階層とワールドマトリクスを壊さない。"""
        for fast in (False, True):
            root = self.make()
            child = self.make(root)
            leaf = self.make(child)
            cmds.setAttr(root.getFullName() + ".t", 1, 2, 3)
            paths = [node.getFullName() for node in (root, child, leaf)]
            matrices = [self.matrix(node, world=True) for node in (root, child, leaf)]
            with self.assertRaises(RuntimeError):
                root.setParent(leaf, fast=fast)
            self.assertEqual([node.getFullName() for node in (root, child, leaf)], paths)
            self.assertEqual([self.matrix(node, world=True) for node in (root, child, leaf)], matrices)

    def test_singular_parent_matrix_rejection_does_not_write_channels(self):
        """反転できない親の下へのワールド指定は、変更前にValueErrorとなる。"""
        # scale=0はMayaが微小値へ補正するため、実際に特異な親OPMを使う。
        singular = (0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        for fast in (False, True):
            parent = self.make()
            cmds.setAttr(parent.getFullName() + ".offsetParentMatrix", *singular, type="matrix")
            node, reference = self.make(parent), self.make()
            self.assertTrue(node.mpath().exclusiveMatrix().isSingular())
            cmds.setAttr(node.getFullName() + ".t", 1, 2, 3)
            before = self.matrix(node)
            cmds.flushUndo()
            for flags in ({}, {"safe": True}, {"get": True}, {"safe": True, "get": True}):
                with self.subTest(fast=fast, flags=flags):
                    with self.assertRaises(ValueError):
                        node.setMatrix(self.matrix(reference), worldSpace=True, fast=fast, **flags)
                    self.assertEqual(self.matrix(node), before)
                    self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_tiny_but_invertible_parent_is_not_rejected(self):
        """小さい行列式だけで拒否せず、OpenMayaが反転できる親を受け付ける。"""
        for fast in (False, True):
            parent = self.make()
            tiny = (1e-13, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
            cmds.setAttr(parent.getFullName() + ".offsetParentMatrix", *tiny, type="matrix")
            node, reference = self.make(parent), self.make()
            cmds.setAttr(reference.getFullName() + ".t", 3, 4, 5)
            target = self.matrix(reference)
            self.assertIs(node.setMatrix(target, worldSpace=True, fast=fast), node)
            self.assertValuesAlmostEqual(self.matrix(node, world=True), target)

    def test_flag_conflicts_and_invalid_fast_do_not_record_changes(self):
        """長短フラグの競合と不正なfastは、更新とUndo記録より前に拒否する。"""
        node = self.make()
        before = self.matrix(node)
        calls = ((node.setTranslation, (1, 2, 3)), (node.setRotate, (0.1, 0.2, 0.3)), (node.setScale, (2, 3, 4)), (node.setMatrix, before))
        cmds.flushUndo()
        for method, value in calls:
            with self.subTest(method=method.__name__):
                with self.assertRaises(TypeError):
                    method(value, worldSpace=False, ws=False)
                with self.assertRaises(TypeError):
                    method(value, fast=1)
                self.assertEqual(self.matrix(node), before)
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_fast_parenting_unsupported_cases_reject_before_update(self):
        """Jointとadd=Trueのfast親変更は、接続や階層を変えずに拒否する。"""
        parent, node, joint = self.make(), self.make(), self.make(kind="joint")
        for item, flags in ((joint, {}), (node, {"add": True})):
            with self.subTest(kind=type(item).__name__, flags=flags):
                before = item.getFullName()
                with self.assertRaises(NotImplementedError):
                    item.setParent(parent, fast=True, **flags)
                self.assertEqual(item.getFullName(), before)
                self.assertIsNone(item.getParent())


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


class RotateOrderTest(_Case):
    """Transform.getRotateOrder/setRotateOrder。"""

    def test_set_rotate_order_preserve(self):
        """preserve=True は向きを保ち(xform の preserve と同じ rotate)、Undo 1回で戻る。"""
        node = mlib.getNode(self.make("transform", "roo#"))
        twin = self.make("transform", "twin#")
        for name in (node.getFullName(), twin):
            cmds.setAttr(name + ".rotate", 30, 45, 60)
        before = node.getMatrix(worldSpace=True)
        self.assertEqual(node.getRotateOrder(), "xyz")
        cmds.xform(twin, rotateOrder="zxy", preserve=True)
        self.flushUndo()
        self.assertIs(node.setRotateOrder("ZXY"), node)
        self.assertEqual(node.getRotateOrder(), "zxy")
        self.assertSequenceAlmostEqual(cmds.getAttr(node.getFullName() + ".rotate")[0], cmds.getAttr(twin + ".rotate")[0], places=6)
        self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(before, 1e-9))
        self.assertUndoesInOneStep(lambda: self.assertEqual(node.getRotateOrder(), "xyz"), lambda: self.assertEqual(node.getRotateOrder(), "zxy"))

    def test_set_rotate_order_without_preserve(self):
        """preserve=False は rotateOrder だけを変え、rotate はそのまま(番号でも指定できる)。"""
        node = mlib.getNode(self.make("transform", "roo#"))
        cmds.setAttr(node.getFullName() + ".rotate", 30, 45, 60)
        node.setRotateOrder(5, preserve=False)
        self.assertEqual(node.getRotateOrder(), "zyx")
        self.assertSequenceAlmostEqual(cmds.getAttr(node.getFullName() + ".rotate")[0], (30, 45, 60), places=6)

    def test_set_rotate_order_errors(self):
        """未対応の順序は ValueError、preserve の型違いは TypeError で、rotateOrder は変わらない。"""
        node = mlib.getNode(self.make("transform", "roo#"))
        for order, flags, error in (("abc", {}, ValueError), (6, {}, ValueError), ("xyz", {"preserve": 1}, TypeError)):
            with self.subTest(order=order, flags=flags):
                with self.assertRaises(error):
                    node.setRotateOrder(order, **flags)
                self.assertEqual(node.getRotateOrder(), "xyz")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
