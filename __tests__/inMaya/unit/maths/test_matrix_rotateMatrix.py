"""``Matrix.asRotateMatrix`` がスケール・シアーのあるマトリクスでも回転だけを返すことのテスト。"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from mlib.maths import Matrix


class AsRotateMatrixShearTest(unittest.TestCase):
    """親の非一様スケールでシアーが入ったマトリクス。"""

    def setUp(self):
        parent = om2.MTransformationMatrix()
        parent.setScale((1, 3, 0.5), om2.MSpace.kTransform)
        child = om2.MTransformationMatrix()
        child.setRotation(om2.MEulerRotation(math.radians(30), math.radians(40), math.radians(10)))
        self.matrix = Matrix(child.asMatrix() * parent.asMatrix())

    def test_rotation_only(self):
        """正規直交で、asScaleMatrix() * asRotateMatrix() が元の3x3になる。"""
        rotate = self.matrix.asRotateMatrix()
        for row in range(3):
            length = math.sqrt(sum(rotate.getElement(row, column) ** 2 for column in range(3)))
            self.assertAlmostEqual(length, 1.0)
        product = self.matrix.asScaleMatrix() * rotate * self.matrix.asTranslateMatrix()
        self.assertTrue(product.isEquivalent(self.matrix, 1e-9))
        expected = om2.MTransformationMatrix(self.matrix).rotation(asQuaternion=True).asMatrix()
        self.assertTrue(rotate.isEquivalent(expected, 1e-9))

    def test_differs_from_transformation_matrix(self):
        """om2.MTransformationMatrix.asRotateMatrix はスケール・シアーを含んだ3x3を返す(docstringのNoteの内容)。"""
        three = om2.MMatrix(self.matrix)
        for column in range(3):
            three.setElement(3, column, 0.0)
        self.assertTrue(om2.MTransformationMatrix(self.matrix).asRotateMatrix().isEquivalent(three, 1e-9))
        self.assertFalse(self.matrix.asRotateMatrix().isEquivalent(three, 1e-6))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
