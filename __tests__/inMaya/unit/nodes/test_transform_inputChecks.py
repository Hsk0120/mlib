"""``mlib.nodes.transform`` の入力の検査と、通っていなかった取得の経路のテスト。

- getShadingEngines・getTranslation(at=0)・getUnusedIntermediateShapes をcmdsと突き合わせる。
- setQuaternion(ws=True)でjointOrientへ書く経路の値・Undo・fastを確かめる。
- replaceShapes・setParent(fast=True)・setCurveShapesData・addConstraint の不正な入力の例外を確かめる。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate, Quaternion
from mlib.nodes import Joint, Nodes


class _Case(NamespaceCase):
    """このテストファイルの名前空間の先頭。"""

    PREFIX = "mlibSpecTransformInput_"
    UNLOCK_NODES = True

    def joint(self, text, position, parent=None):
        """選択を使わずにjointを作って名前を返す。"""
        cmds.select(clear=True)
        if parent is not None:
            cmds.select(parent, replace=True)
        name = cmds.joint(name=self.name(text), position=position)
        cmds.select(clear=True)
        return name


class TransformQueriesTest(_Case):
    """取得のメソッドをcmdsの結果と比べる。"""

    def test_get_shading_engines(self):
        """直下のシェイプのシェーディンググループをcmdsのlistConnectionsと同じ順で返す。"""
        cube = cmds.polyCube(name=self.name("cube"))[0]
        result = mlib.getNode(cube).getShadingEngines()
        self.assertIsInstance(result, Nodes)
        shape = cmds.listRelatives(cube, shapes=True, fullPath=True)[0]
        expected = cmds.listConnections(shape, type="shadingEngine") or []
        self.assertEqual([node.getName() for node in result], list(dict.fromkeys(expected)))
        empty = mlib.getNode(self.make(text="empty"))
        self.assertEqual(list(empty.getShadingEngines()), [])

    def test_get_translation_at_origin(self):
        """at=0はローカルの原点。ws・worldSpaceでは親のワールドマトリクスの位置になる。"""
        parent = self.make(text="parent")
        cmds.setAttr(parent + ".translate", 1, 2, 3)
        cmds.setAttr(parent + ".rotate", 10, 20, 30)
        child = mlib.getNode(self.make(text="child", parent=parent))
        cmds.setAttr(str(child) + ".translate", 4, 5, 6)
        expected = cmds.xform(parent, query=True, worldSpace=True, translation=True)
        self.assertSequenceAlmostEqual(child.getTranslation(worldSpace=True, at=0), expected)
        self.assertSequenceAlmostEqual(child.getTranslation(ws=True, at=0), expected)
        self.assertSequenceAlmostEqual(child.getTranslation(at=0), (0.0, 0.0, 0.0))

    def test_unused_intermediate_shapes_locked(self):
        """ロックしたTransformは候補を返さない(空の集まり)。"""
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        extra = cmds.createNode("mesh", name=self.name("orig"), parent=cube, skipSelect=True)
        node = mlib.getNode(cube)
        cmds.setAttr(extra + ".intermediateObject", True)
        self.assertTrue(len(node.getUnusedIntermediateShapes()) >= 1)
        cmds.lockNode(cube, lock=True)
        result = node.getUnusedIntermediateShapes()
        self.assertIsInstance(result, Nodes)
        self.assertEqual(list(result), [])


class SetQuaternionWorldJointOrientTest(_Case):
    """setQuaternion(ws=True, r=False)は、子のジョイントのjointOrientへ書いてワールドの回転を合わせる。"""

    def setUp(self):
        super().setUp()
        root = self.joint("root", (0, 0, 0))
        cmds.setAttr(root + ".rotate", 30, 10, 0)
        self.child = Joint(self.joint("child", (1, 0, 0), parent=root))
        cmds.setAttr(str(self.child) + ".rotate", 5, 0, 15)
        self.value = Quaternion(om2.MEulerRotation(0.3, 0.2, 0.1).asQuaternion())

    def world_quaternion(self):
        """cmdsで読んだワールドマトリクスの回転。"""
        matrix = om2.MMatrix(cmds.xform(str(self.child), query=True, worldSpace=True, matrix=True))
        return om2.MTransformationMatrix(matrix).rotation(asQuaternion=True)

    def expected_world(self):
        """rotateを含まない回転が指定の値になるときの、ワールドの回転(rotate、続けて指定の値)。"""
        rotate = [om2.MAngle(value, om2.MAngle.kDegrees).asRadians() for value in cmds.getAttr(str(self.child) + ".rotate")[0]]
        return om2.MEulerRotation(*rotate).asQuaternion() * self.value

    def test_normal_undo_and_get(self):
        """rotateを除いたワールドの回転が指定の値になり、rotateは変えない。Undo1回で戻る。get=Trueは書かない。"""
        before = cmds.getAttr(str(self.child) + ".jointOrient")[0]
        rotate = cmds.getAttr(str(self.child) + ".rotate")[0]
        preview = self.child.setQuaternion(self.value, ws=True, r=False, get=True)
        self.assertIsInstance(preview, EulerRotate)
        self.assertEqual(cmds.getAttr(str(self.child) + ".jointOrient")[0], before)
        self.flushUndo()
        self.assertIsNone(self.child.setQuaternion(self.value, ws=True, r=False))
        self.assertSameRotation(self.world_quaternion(), self.expected_world())
        self.assertSameRotation(self.child.getQuaternion(ws=True, r=False), self.value)
        self.assertSequenceAlmostEqual(cmds.getAttr(str(self.child) + ".rotate")[0], rotate)
        self.assertSequenceAlmostEqual(
            [om2.MAngle(value, om2.MAngle.kDegrees).asRadians() for value in cmds.getAttr(str(self.child) + ".jointOrient")[0]], tuple(preview)
        )
        self.assertUndoesInOneStep(lambda: self.assertSequenceAlmostEqual(cmds.getAttr(str(self.child) + ".jointOrient")[0], before), lambda: None)

    def test_fast_has_no_undo(self):
        """fast=TrueはUndoに載らず、同じワールドの回転になる。"""
        self.flushUndo()
        self.child.setQuaternion(self.value, worldSpace=True, rotate=False, fast=True)
        self.assertSameRotation(self.world_quaternion(), self.expected_world())
        self.assertUndoEmpty()


class SetQuaternionComponentsTest(_Case):
    """setQuaternionの回転の成分の組み合わせ。"""

    def setUp(self):
        super().setUp()
        self.value = Quaternion(om2.MEulerRotation(0.4, -0.2, 0.3).asQuaternion())

    def world_quaternion(self, name):
        """cmdsで読んだワールドマトリクスの回転。"""
        matrix = om2.MMatrix(cmds.xform(name, query=True, worldSpace=True, matrix=True))
        return om2.MTransformationMatrix(matrix).rotation(asQuaternion=True)

    def test_rotate_with_rotate_axis(self):
        """ra=Trueでrotateへ書くと、rotateAxisを含めた回転が指定の値になる。rotateAxisは変えない。"""
        node = mlib.getNode(self.make(text="node"))
        cmds.setAttr(str(node) + ".rotateAxis", 20, 0, 10)
        self.flushUndo()
        node.setQuaternion(self.value, ra=True)
        self.assertSameRotation(node.getQuaternion(ra=True), self.value)
        self.assertSameRotation(self.world_quaternion(str(node)), self.value)
        self.assertSequenceAlmostEqual(cmds.getAttr(str(node) + ".rotateAxis")[0], (20, 0, 10))
        self.assertUndoesInOneStep(lambda: self.assertEqual(cmds.getAttr(str(node) + ".rotate")[0], (0.0, 0.0, 0.0)), lambda: None)

    def test_rotate_axis_without_rotate_on_joint(self):
        """Jointのローカルで、ra=True・r=False・jo=TrueはValueErrorで、何も書かない。"""
        joint = Joint(self.joint("joint", (0, 0, 0)))
        with self.assertRaises(ValueError):
            joint.setQuaternion(self.value, ra=True, r=False)
        for attribute in ("rotate", "rotateAxis", "jointOrient"):
            self.assertEqual(cmds.getAttr(f"{joint}.{attribute}")[0], (0.0, 0.0, 0.0))

    def test_world_under_scaled_joint(self):
        """スケールした親のジョイントの下(inverseScaleが1でない)でも、ワールドの回転が指定の値になる。"""
        root = self.joint("root", (0, 0, 0))
        cmds.setAttr(root + ".scale", 2, 2, 2)
        child = Joint(self.joint("child", (1, 0, 0), parent=root))
        self.assertEqual(cmds.getAttr(str(child) + ".inverseScale")[0], (2.0, 2.0, 2.0))
        for fast in (False, True):
            with self.subTest(fast=fast):
                cmds.setAttr(str(child) + ".rotate", 0, 0, 0)
                child.setQuaternion(self.value, ws=True, fast=fast)
                self.assertSameRotation(self.world_quaternion(str(child)), self.value)


class TransformInputErrorsTest(_Case):
    """入力が正しくないときの例外の型。"""

    def test_replace_shapes_invalid_source(self):
        """削除済みのコピー元はRuntimeError、中間オブジェクトのシェイプはValueError。"""
        target = mlib.getNode(self.make(text="target"))
        removed = mlib.getNode(self.make(text="removed"))
        cmds.delete(str(removed))
        with self.assertRaises(RuntimeError):
            target.replaceShapes(removed)
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        shape = cmds.listRelatives(cube, shapes=True, fullPath=True)[0]
        cmds.setAttr(shape + ".intermediateObject", True)
        with self.assertRaises(ValueError):
            target.replaceShapes(shape)
        self.assertIsNone(cmds.listRelatives(str(target), shapes=True))

    def test_set_translation_component_count(self):
        """setTranslationの成分の数は、checkに関係なく確かめる。有限かどうかはcheck=Trueのときだけ確かめる。"""
        node = mlib.getNode(self.make(text="node"))
        name = node.getName(full=True)
        cmds.setAttr(name + ".translate", 1.0, 1.0, 1.0)
        for kwargs in ({}, {"ws": True}, {"fast": True}, {"check": True}, {"ws": True, "fast": True}):
            for value in ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0)):
                with self.subTest(kwargs=kwargs, value=value), self.assertRaises(ValueError):
                    node.setTranslation(value, **kwargs)
            with self.subTest(kwargs=kwargs, value=5), self.assertRaises(TypeError):
                node.setTranslation(5, **kwargs)
        for kwargs in ({"check": True}, {"ws": True, "check": True}, {"ws": True, "fast": True, "check": True}):
            with self.subTest(kwargs=kwargs, value="inf"), self.assertRaises(ValueError):
                node.setTranslation((float("inf"), 0.0, 0.0), **kwargs)
        self.assertEqual(cmds.getAttr(name + ".translate")[0], (1.0, 1.0, 1.0))
        # MPointは4つの成分を持つが、これまでどおり位置として受け付ける。
        node.setTranslation(om2.MPoint(4.0, 5.0, 6.0))
        self.assertEqual(cmds.getAttr(name + ".translate")[0], (4.0, 5.0, 6.0))

    def test_set_parent_fast_invalid_parent(self):
        """fastの親がtransformでなければTypeError、親のマトリクスが特異ならRuntimeError。どちらも親は変わらない。"""
        node = mlib.getNode(self.make(text="node"))
        dg = self.make("multiplyDivide", "dg")
        with self.assertRaises(TypeError):
            node.setParent(dg, fast=True)
        flat = self.make(text="flat")
        cmds.setAttr(flat + ".scale", 0, 0, 0)
        with self.assertRaises(RuntimeError):
            node.setParent(flat, fast=True)
        self.assertIsNone(cmds.listRelatives(str(node), parent=True))

    def test_curve_shapes_entry_type(self):
        """setCurveShapesDataのshapesの要素がdictでなければValueError。"""
        node = mlib.getNode(self.make(text="node"))
        with self.assertRaises(ValueError):
            node.setCurveShapesData({"shapes": [5]})
        self.assertIsNone(cmds.listRelatives(str(node), shapes=True))

    def test_add_constraint_deleted_target(self):
        """削除済みのターゲットはRuntimeErrorで、コンストレイントを作らない。"""
        node = mlib.getNode(self.make(text="node"))
        removed = mlib.getNode(self.make(text="removed"))
        cmds.delete(str(removed))
        with self.assertRaises(RuntimeError):
            node.addConstraint(removed, type="parent")
        self.assertEqual(cmds.ls(self.ns + ":*", type="constraint"), [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
