"""``mlib.maths.transformation`` のテスト。

Transformation が om2.MTransformationMatrix を継承し、ピボット・回転順序・rotateAxis・jointOrient・inverseScale を
持てること、合成したマトリクスが Maya の transform・joint のローカルのマトリクスと一致することを確かめる。
"""

import math
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Transformation, Translate


def same_rotation(a, b):
    """2つのクォータニオンが同じ回転かを返す(符号の違いは同じ回転とみなす)。"""
    a, b = om2.MQuaternion(a), om2.MQuaternion(b)
    return a.isEquivalent(b, 1e-12) or a.isEquivalent(-b, 1e-12)


class ValueTest(unittest.TestCase):
    """シーンに触れない値としての動き。"""

    def test_is_om2_type_and_defaults(self):
        value = Transformation()
        self.assertIsInstance(value, om2.MTransformationMatrix)
        self.assertEqual(tuple(value.translate), (0.0, 0.0, 0.0))
        self.assertEqual(tuple(value.scale), (1.0, 1.0, 1.0))
        self.assertEqual(value.rotateOrder, 0)
        self.assertEqual(tuple(value.inverseScale), (1.0, 1.0, 1.0))
        self.assertTrue(value.matrix.isEquivalent(om2.MMatrix(), 1e-12))
        self.assertIs(mlib.Transformation, Transformation)

    def test_property_types_and_copies(self):
        value = Transformation(translate=(1, 2, 3), rotate=(0.1, 0.2, 0.3), scale=(2, 3, 4), shear=(0.1, 0.2, 0.3))
        types = {
            "translate": Translate,
            "rotate": EulerRotate,
            "quaternion": Quaternion,
            "scale": Scale,
            "shear": Shear,
            "rotateAxis": Quaternion,
            "jointOrient": Quaternion,
            "rotatePivot": Translate,
            "rotatePivotTranslate": Translate,
            "scalePivot": Translate,
            "scalePivotTranslate": Translate,
            "inverseScale": Scale,
            "matrix": Matrix,
        }
        for name, cls in types.items():
            with self.subTest(name=name):
                self.assertIs(type(getattr(value, name)), cls)
        # 取得した値は複製で、書き換えても自身は変わらない。
        translate = value.translate
        translate.x = 100.0
        self.assertEqual(tuple(value.translate), (1.0, 2.0, 3.0))

    def test_setters_round_trip(self):
        value = Transformation()
        cases = {
            "translate": (1.0, 2.0, 3.0),
            "scale": (2.0, 3.0, 4.0),
            "shear": (0.1, 0.2, 0.3),
            "rotatePivot": (0.5, 0.25, -1.0),
            "rotatePivotTranslate": (0.1, 0.0, 0.2),
            "scalePivot": (1.0, -2.0, 3.0),
            "scalePivotTranslate": (0.3, 0.2, 0.1),
            "inverseScale": (2.0, 2.0, 4.0),
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                setattr(value, name, expected)
                self.assertEqual(tuple(getattr(value, name)), expected)

    def test_rotation_and_order(self):
        value = Transformation(rotateOrder=2, rotate=(0.1, 0.2, 0.3))
        self.assertEqual(value.rotateOrder, 2)
        self.assertEqual((value.rotate.x, value.rotate.y, value.rotate.z, value.rotate.order), (0.1, 0.2, 0.3, 2))
        before = om2.MQuaternion(value.quaternion)
        value.rotateOrder = 5
        self.assertEqual(value.rotateOrder, 5)
        self.assertTrue(same_rotation(value.quaternion, before))
        value.rotate = om2.MEulerRotation(0.3, 0.2, 0.1, om2.MEulerRotation.kYZX)
        self.assertEqual(value.rotateOrder, om2.MEulerRotation.kYZX)
        target = om2.MEulerRotation(0.4, -0.2, 0.9).asQuaternion()
        value.quaternion = target
        self.assertEqual(value.rotateOrder, om2.MEulerRotation.kYZX)
        self.assertTrue(same_rotation(value.quaternion, target))

    def test_copy_equality_and_matrix_input(self):
        value = Transformation(translate=(1, 2, 3), rotate=(0.1, 0.2, 0.3), rotatePivot=(1, 0, 0), jointOrient=(0.2, 0, 0), inverseScale=(2, 2, 2))
        clone = value.copy()
        self.assertIsNot(clone, value)
        self.assertEqual(clone, value)
        self.assertTrue(clone.isEquivalent(value))
        clone.jointOrient = (0.3, 0, 0)
        self.assertNotEqual(clone, value)
        self.assertFalse(clone.isEquivalent(value))
        with self.assertRaises(TypeError):
            hash(value)
        matrix = Matrix(translate=(1, 2, 3), rotate=(0.1, 0.2, 0.3), scale=(2, 2, 2))
        from_matrix = Transformation(matrix)
        self.assertTrue(from_matrix.matrix.isEquivalent(matrix, 1e-9))
        from_om2 = Transformation(om2.MTransformationMatrix(om2.MMatrix(matrix)))
        self.assertTrue(from_om2.isEquivalent(from_matrix))

    def test_invalid_inputs(self):
        with self.assertRaises(TypeError):
            Transformation(translate="abc")
        with self.assertRaises(ValueError):
            Transformation(scale=(1, 2))
        with self.assertRaises(ValueError):
            Transformation(rotateOrder=6)
        with self.assertRaises(TypeError):
            Transformation(rotateOrder=True)
        with self.assertRaises(TypeError):
            Transformation().isEquivalent(Matrix())


class MayaParityTest(NamespaceCase):
    """合成したマトリクスが、Maya のノードのローカルのマトリクスと一致する。"""

    PREFIX = "mlibTransformation_"

    def test_transform_matrix_matches_maya(self):
        node = self.make()
        cmds.setAttr(node + ".rotateOrder", 3)
        values = {
            "t": (1, 2, 3),
            "r": (10, 20, 30),
            "s": (1.5, 2, 0.5),
            "sh": (0.1, 0.2, 0.3),
            "ra": (5, 6, 7),
            "rp": (0.5, 1, -1),
            "rpt": (0.1, 0.2, 0.3),
            "sp": (1, 0, 2),
            "spt": (0.3, 0.1, 0.2),
        }
        for name, item in values.items():
            cmds.setAttr(f"{node}.{name}", *item)
        value = Transformation(
            rotateOrder=3,
            translate=values["t"],
            rotate=[math.radians(v) for v in values["r"]],
            scale=values["s"],
            shear=values["sh"],
            rotateAxis=[math.radians(v) for v in values["ra"]],
            rotatePivot=values["rp"],
            rotatePivotTranslate=values["rpt"],
            scalePivot=values["sp"],
            scalePivotTranslate=values["spt"],
        )
        self.assertSequenceAlmostEqual(list(value.matrix), cmds.getAttr(node + ".matrix"))

    def test_joint_matrix_matches_maya(self):
        cmds.select(clear=True)
        root = cmds.joint(name=self.name("root"))
        cmds.setAttr(root + ".s", 2, 3, 4)
        child = cmds.joint(name=self.name("child"), position=(1, 2, 3))
        cmds.setAttr(child + ".jo", 10, 20, 30)
        cmds.setAttr(child + ".r", 5, 6, 7)
        cmds.setAttr(child + ".ra", 3, 4, 5)
        value = Transformation(
            translate=cmds.getAttr(child + ".t")[0],
            rotate=[math.radians(v) for v in (5, 6, 7)],
            rotateAxis=[math.radians(v) for v in (3, 4, 5)],
            jointOrient=[math.radians(v) for v in (10, 20, 30)],
            inverseScale=(2, 3, 4),
        )
        self.assertSequenceAlmostEqual(list(value.matrix), cmds.getAttr(child + ".matrix"))


if __name__ == "__main__":
    unittest.main()
