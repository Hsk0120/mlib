"""統合したconstraintコマンドのフラグ・戻り値・Undoを検証する。

あわせて次も確かめる。

- 形状ラッパーと標準コンストレイントを Maya 内で検証する。
- Reference・Container・DagPose・マテリアル系・Constraint・AnimCurve の参照の少ないAPIの約束を固定する(担当C)。
"""

import importlib
import unittest
import uuid
from pathlib import Path

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Node


class UnifiedConstraintTest(unittest.TestCase):
    """削除した個別コマンドの機能を統合入口から確認する。"""

    def setUp(self):
        self.selection = cmds.ls(selection=True, long=True) or []
        self.namespace = ":constraintTest_" + uuid.uuid4().hex
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(add=self.namespace)
        cmds.namespace(set=self.namespace)
        self.source = mlib.createNode("transform", name="source", skipSelect=True)
        self.target = mlib.createNode("transform", name="target", skipSelect=True)
        self.up = mlib.createNode("transform", name="up", skipSelect=True)
        self.source.getPlug("translateZ").set(5)
        self.up.getPlug("translateY").set(5)

    def tearDown(self):
        cmds.namespace(set=self.previous)
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.select(self.selection, replace=True) if self.selection else cmds.select(clear=True)

    def test_aim_flags_queries_edit_and_undo(self):
        result = mlib.getNode(self.target).addConstraint(self.source, typ="aim", aim=(0, 0, 1), u=(0, 1, 0), wut="object", wuo=self.up)
        self.assertEqual(result.getType(), "aimConstraint")
        self.assertEqual(result.getPlug("worldUpMatrix").getSource().getNode().getUuid(), self.up.getUuid())
        self.assertEqual(result.getTargets()[0].getUuid(), self.source.getUuid())
        weight = result.getWeightPlugs()[0]
        result.setWeight(0.25)
        self.assertAlmostEqual(weight.get(), 0.25)
        cmds.undo()
        self.assertAlmostEqual(weight.get(), 1.0)
        name = result.getFullName()
        cmds.undo()
        self.assertFalse(cmds.objExists(name))
        cmds.redo()
        self.assertTrue(cmds.objExists(name))

    def test_parent_orient_and_transform_creation(self):
        for kind in ("parent", "orient"):
            with self.subTest(kind=kind):
                result = self.target.addConstraint(self.source, type=kind, weight=0.3)
                self.assertEqual(result.getType(), kind + "Constraint")
                self.assertAlmostEqual(result.getWeights()[0], 0.3)
                cmds.delete(result.getFullName())

    def test_conflicting_flags_and_modes_do_not_create_nodes(self):
        before = set(cmds.ls())
        with self.assertRaises(TypeError):
            mlib.getNode(self.target).addConstraint(self.source, type="aim", wuo=self.up, worldUpObject=self.up)
        with self.assertRaises(ValueError):
            self.target.addConstraint(self.source, type="aim", q=True)
        with self.assertRaises(ValueError):
            mlib.getNode(self.target).addConstraint(self.source, type="aim", query=True, edit=True)
        self.assertEqual(set(cmds.ls()), before)

    def test_individual_command_exports_and_files_are_removed(self):
        for name in ("aimConstraint", "parentConstraint", "orientConstraint", "poleVectorConstraint"):
            self.assertFalse(hasattr(mlib, name))
            self.assertFalse(hasattr(mlib.cmds, name))
            self.assertFalse((Path(mlib.__file__).parent / "cmds" / (name + ".py")).exists())


mlib_cmds = importlib.import_module("mlib.cmds")


class ShapesConstraintsTest(unittest.TestCase):
    """専用名前空間に作成したノードだけで動作を確認する。"""

    def setUp(self):
        self.selection = cmds.ls(selection=True, long=True) or []
        self.previous_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.namespace = ":mlibShapesConstraints_" + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)
        cmds.namespace(set=self.namespace)

    def tearDown(self):
        cmds.namespace(set=self.previous_namespace)
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        if self.selection:
            cmds.select(self.selection, replace=True)
        else:
            cmds.select(clear=True)

    def getTransform(self):
        return mlib_cmds.createNode("transform")

    def test_delete_constraints_direct_and_undo(self):
        source, driven, other = self.getTransform(), self.getTransform(), self.getTransform()
        constraint = driven.addConstraint(source)
        untouched = other.addConstraint(driven)
        name, untouched_name = constraint.getFullName(), untouched.getFullName()
        self.assertEqual(driven.deleteConstraints(), [name])
        self.assertFalse(cmds.objExists(name))
        self.assertTrue(cmds.objExists(untouched_name))
        self.assertTrue(source.isValid())
        cmds.undo()
        self.assertTrue(cmds.objExists(name))
        cmds.redo()
        self.assertFalse(cmds.objExists(name))
        self.assertEqual(driven.deleteConstraints(), [])

    def test_delete_constraints_pair_blend_preserves_animation(self):
        source, driven = self.getTransform(), self.getTransform()
        cmds.setKeyframe(driven.getFullName(), attribute="translateX", time=1, value=2)
        animation = cmds.listConnections(driven.getFullName(), source=True, destination=False, type="animCurve")[0]
        constraint = driven.addConstraint(source, type="point")
        name = constraint.getFullName()
        blends = cmds.listConnections(driven.getFullName(), source=True, destination=False, type="pairBlend")
        self.assertTrue(blends)
        deleted = driven.deleteConstraints()
        self.assertIn(name, deleted)
        for blend in blends:
            self.assertIn(blend, deleted)
            self.assertFalse(cmds.objExists(blend))
        self.assertTrue(cmds.objExists(animation))
        cmds.undo()
        self.assertTrue(cmds.objExists(name))
        self.assertTrue(cmds.objExists(blends[0]))

    def test_delete_constraints_shared_output_rejected(self):
        source, driven, other = self.getTransform(), self.getTransform(), self.getTransform()
        constraint = driven.addConstraint(source, type="point")
        cmds.connectAttr(constraint.getFullName() + ".constraintTranslateX", other.getFullName() + ".translateX")
        with self.assertRaises(RuntimeError):
            driven.deleteConstraints()
        self.assertTrue(constraint.isValid())

    def test_delete_constraints_keeps_unrelated_pair_blend(self):
        driven = self.getTransform()
        blend = cmds.createNode("pairBlend")
        cmds.connectAttr(blend + ".outTranslate", driven.getFullName() + ".translate")
        self.assertEqual(driven.deleteConstraints(), [])
        self.assertTrue(cmds.objExists(blend))

    def test_basic_constraints_targets_weights_and_registration(self):
        for kind in ("parent", "point", "orient", "scale", "aim"):
            with self.subTest(kind=kind):
                source, second, driven = self.getTransform(), self.getTransform(), self.getTransform()
                cmds.setAttr(source.getFullName() + ".translateX", 3)
                result = driven.addConstraint([source, second], kind, maintainOffset=True)
                expected = getattr(mlib.nodes, kind.title() + "Constraint")
                self.assertIsInstance(result, expected)
                self.assertIsInstance(mlib.Node(result.getFullName()), expected)
                self.assertEqual([node.getUuid() for node in result.getTargets()], [source.getUuid(), second.getUuid()])
                self.assertEqual(result.getWeights(), [1.0, 1.0])
                self.assertEqual(len(result.getWeightAliases()), 2)
                result.getWeightPlugs()[0].set(0.25)
                self.assertEqual(result.getWeights(), [0.25, 1.0])

    def test_constraint_set_weight(self):
        source, second, driven = self.getTransform(), self.getTransform(), self.getTransform()
        result = driven.addConstraint([source, second], "point", maintainOffset=True)
        self.assertEqual(result.getWeights(), [1.0, 1.0])

        returned = result.setWeight(0.5)
        self.assertIs(returned, result)
        self.assertEqual(result.getWeights(), [0.5, 0.5])

        result.setWeight(0.25, source)
        self.assertEqual(result.getWeights(), [0.25, 0.5])

        result.setWeight(0.75, source, second)
        self.assertEqual(result.getWeights(), [0.75, 0.75])

        unrelated = self.getTransform()
        with self.assertRaises(ValueError):
            result.setWeight(1.0, unrelated)

    def test_specialized_constraints(self):
        mesh = mlib.Node(cmds.polyPlane(constructionHistory=False)[0])
        for kind, expected in [("geometry", mlib.GeometryConstraint), ("normal", mlib.NormalConstraint), ("pointOnPoly", mlib.PointOnPolyConstraint)]:
            with self.subTest(kind=kind):
                result = self.getTransform().addConstraint(mesh, kind)
                self.assertIsInstance(result, expected)
                self.assertEqual(len(result.getTargets()), 1)
                self.assertEqual(result.getWeights(), [1.0])
        curve = mlib.Node(cmds.curve(degree=1, point=[(0, 0, 0), (3, 0, 0)]))
        result = self.getTransform().addConstraint(curve, "tangent")
        self.assertIsInstance(result, mlib.TangentConstraint)
        self.assertEqual(len(result.getTargets()), 1)
        self.assertEqual(result.getWeights(), [1.0])

        cmds.select(clear=True)
        start = cmds.joint(position=(0, 0, 0))
        cmds.joint(position=(2, 1, 0))
        end = cmds.joint(position=(4, 0, 0))
        handle = mlib.Node(cmds.ikHandle(startJoint=start, endEffector=end, solver="ikRPsolver")[0])
        self.assertIsInstance(handle, mlib.IkHandle)
        result = handle.addConstraint(self.getTransform(), "poleVector")
        self.assertIsInstance(result, mlib.PoleVectorConstraint)
        self.assertEqual(len(result.getTargets()), 1)
        self.assertEqual(result.getWeights(), [1.0])

    def test_creation_undo_and_redo(self):
        if not cmds.undoInfo(query=True, state=True):
            self.skipTest("Undo is disabled in this Maya session")
        source, driven = self.getTransform(), self.getTransform()
        result = driven.addConstraint(source, "pointConstraint")
        name = result.getFullName()
        cmds.undo()
        self.assertFalse(cmds.objExists(name))
        cmds.redo()
        self.assertIsInstance(mlib.Node(name), mlib.PointConstraint)

    def test_point_evaluation_and_parent_offset(self):
        source, driven = self.getTransform(), self.getTransform()
        cmds.setAttr(source.getFullName() + ".translateX", 4)
        driven.addConstraint(source.getFullName(), "point")
        self.assertAlmostEqual(cmds.getAttr(driven.getFullName() + ".translateX"), 4)
        cmds.setAttr(source.getFullName() + ".translateX", 7)
        self.assertAlmostEqual(cmds.getAttr(driven.getFullName() + ".translateX"), 7)

        offset_driven = self.getTransform()
        cmds.setAttr(offset_driven.getFullName() + ".translateX", 10)
        offset_driven.addConstraint(source, maintainOffset=True)
        self.assertAlmostEqual(cmds.getAttr(offset_driven.getFullName() + ".translateX"), 10)
        cmds.setAttr(source.getFullName() + ".translateX", 9)
        self.assertAlmostEqual(cmds.getAttr(offset_driven.getFullName() + ".translateX"), 12)

    def test_invalid_requests_do_not_create_nodes(self):
        source, driven = self.getTransform(), self.getTransform()
        before = set(cmds.ls(long=True))
        invalid_requests = [([], "point", ValueError), (source, "unknown", ValueError), ([object()], "point", TypeError)]
        for sources, kind, error in invalid_requests:
            with self.assertRaises(error):
                driven.addConstraint(sources, kind)
        self.assertEqual(before, set(cmds.ls(long=True)))

    def mirror_shapes(self):
        """非対称カーブと履歴付きメッシュを変換済みの親の下へ作成する。"""
        cube = mlib.Node(cmds.polyCube()[0])
        curve = mlib.Node(cmds.curve(degree=1, point=[(1, 2, 3), (4, 1, -2), (2, 5, 1)]))
        parent = self.getTransform()
        cmds.setAttr(parent.getFullName() + ".translate", 4, -2, 3)
        cmds.setAttr(parent.getFullName() + ".rotate", 23, 41, -17)
        cmds.setAttr(parent.getFullName() + ".scale", 2, 0.7, 1.3)
        cmds.parent(cube.getFullName(), curve.getFullName(), parent.getFullName(), relative=True)
        return [cube.getShape(), curve.getShape()]

    def positions(self, shape, ws=False):
        """API の内部距離単位で形状の全位置を返す。"""
        points = shape.getPoints(ws) if isinstance(shape, mlib.Mesh) else shape.getCvPositions(ws)
        return [tuple(point)[:3] for point in points]

    def assert_positions(self, actual, expected):
        """全成分を許容誤差付きで比較する。"""
        self.assertEqual(len(actual), len(expected))
        for point, reference in zip(actual, expected):
            for component, value in zip(point, reference):
                # Mesh の座標保存精度を考慮し、距離単位変更時も相対誤差で比較する。
                self.assertAlmostEqual(component, value, delta=max(1e-5, abs(value) * 1e-6))


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeMisc_"
    CLEAR_SELECTION = True


class ConstraintAnimCurveTest(_SpecCase):
    """Constraint.getWeightAliases と AnimCurve.isTimeInput。"""

    def test_weight_aliases(self):
        """getTargets と同じ順の weight 名。ノードの aliasAttr を列挙する getAliases とは別。"""
        first = cmds.createNode("transform", name=self.name("first"), skipSelect=True)
        second = cmds.createNode("transform", name=self.name("second"), skipSelect=True)
        driven = cmds.createNode("transform", name=self.name("driven"), skipSelect=True)
        constraint = cmds.parentConstraint(first, second, driven)[0]
        node = Node(constraint)
        aliases = node.getWeightAliases()
        self.assertEqual(aliases, cmds.parentConstraint(constraint, query=True, weightAliasList=True))
        self.assertEqual(len(aliases), 2)
        self.assertEqual([target.getName() for target in node.getTargets()], [first, second])
        # parentConstraint の weight は aliasAttr ではなく動的アトリビュートなので、getAliases には出ない。
        self.assertTrue(all(node.hasAttr(alias) for alias in aliases))
        self.assertEqual([plug.getFullName().split(".")[-1] for plug in node.getWeightPlugs()], aliases)

    def test_is_time_input(self):
        """横軸が時間の T 型は True、U 型は False。削除済みは RuntimeError。"""
        for kind, expected in (("animCurveTL", True), ("animCurveTA", True), ("animCurveUL", False), ("animCurveUU", False)):
            with self.subTest(kind=kind):
                curve = Node(cmds.createNode(kind, name=self.name(kind), skipSelect=True))
                self.assertIs(curve.isTimeInput(), expected)
        deleted = Node(cmds.createNode("animCurveTT", name=self.name("deletedCurve"), skipSelect=True))
        cmds.delete(deleted.getName())
        with self.assertRaises(RuntimeError):
            deleted.isTimeInput()


if __name__ == "__main__":
    unittest.main()
