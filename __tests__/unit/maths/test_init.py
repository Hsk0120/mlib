"""``mlib.maths`` のテスト。

- mlib.maths の数学型がom2と同じ意味を持つことを固定する仕様テスト(担当D)。
"""

import copy
import math
import pickle
import sys
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Translate, Vector
from mlib.maths.eulerRotate import ORDER_NAMES, orderIndex


ANGLES = (0.3, -1.1, 2.4)


OM2_ORDERS = (om2.MEulerRotation.kXYZ, om2.MEulerRotation.kYZX, om2.MEulerRotation.kZXY,
              om2.MEulerRotation.kXZY, om2.MEulerRotation.kYXZ, om2.MEulerRotation.kZYX)


def _om2_matrix(values):
    """16要素からom2.MMatrixを作る。"""
    return om2.MMatrix(list(values))


def _sample_matrix():
    """平行移動・回転・不均一スケールを含む固定のom2マトリクスを返す。"""
    tm = om2.MTransformationMatrix()
    tm.setTranslation(om2.MVector(1.0, -2.0, 3.5), om2.MSpace.kTransform)
    tm.setRotation(om2.MEulerRotation(0.4, 0.2, -0.7))
    tm.setScale([1.5, 0.5, 2.0], om2.MSpace.kTransform)
    return tm.asMatrix()


class ValueTypeContractTest(unittest.TestCase):
    """全ての数学型に共通する、可変・ハッシュ不可・om2の派生であることを固定する。"""

    def test_unhashable_and_om2_subclasses(self):
        """全ての数学型はハッシュ不可で、om2の値型を継承する。"""
        values = [(Vector(), om2.MVector), (Translate(), om2.MVector), (Scale(), om2.MVector),
                  (Shear(), om2.MVector), (Quaternion(), om2.MQuaternion),
                  (EulerRotate(), om2.MEulerRotation), (Matrix(), om2.MMatrix)]
        for value, base in values:
            self.assertIsInstance(value, base)
            with self.assertRaises(TypeError):
                hash(value)
            with self.assertRaises(TypeError):
                {value: 1}

    def test_defaults(self):
        """既定値はゼロベクトル・単位クォータニオン・xyz順の0回転・単位マトリクス。"""
        self.assertEqual(tuple(Vector()), (0.0, 0.0, 0.0))
        self.assertEqual(tuple(Scale()), (0.0, 0.0, 0.0))
        self.assertEqual(tuple(Quaternion()), (0.0, 0.0, 0.0, 1.0))
        self.assertEqual(EulerRotate().order, om2.MEulerRotation.kXYZ)
        self.assertEqual(Matrix(), om2.MMatrix())
        self.assertEqual(Matrix.identity(), om2.MMatrix())

    def test_copy_and_pickle_keep_type_and_independence(self):
        """copy・deepcopy・pickleは同じ型の独立した値を作る。"""
        values = [Translate(1, 2, 3), Quaternion(0.1, 0.2, 0.3, 0.9),
                  EulerRotate(0.1, 0.2, 0.3, "zyx"), Matrix(translate=(1, 2, 3))]
        for value in values:
            for duplicate in (copy.copy(value), copy.deepcopy(value), pickle.loads(pickle.dumps(value))):
                self.assertIs(type(duplicate), type(value))
                self.assertEqual(duplicate, value)
                self.assertIsNot(duplicate, value)
        vector = Translate(1, 2, 3)
        duplicate = copy.copy(vector)
        duplicate.x = 9
        self.assertEqual(vector.x, 1.0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
