"""``mlib.maths.matrix`` の番号での書き込み・複製の境界と、``mlib.maths.vector`` の再構築の境界のテスト。

- ``m[i] = v`` で、番号が int・tuple 以外(float・bool・``__index__`` を持つ値)の場合。
- ``isIdentity`` の許容誤差の型と値。
- ``Matrix._wrap`` に ``om2.MFloatMatrix`` を渡した場合。
- pickle の再構築(``vector._rebuild``)で、Matrix の値の数が合わない場合と、対応しない型の場合。
"""

import sys
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from mlib.maths import Matrix, Vector
from mlib.maths import vector as vector_module


class _Index:
    """``__index__`` だけを持つ番号。"""

    def __index__(self):
        return 3


class MatrixSetItemTest(unittest.TestCase):
    """int・tuple以外の番号での書き込み。"""

    def test_index_like_values_follow_python_rules(self):
        """__index__を持つ値とboolは整数として使い、floatはTypeErrorで何も変えない。"""
        matrix = Matrix()
        matrix[_Index()] = 2.0
        self.assertEqual(matrix[0, 3], 2.0)
        matrix[True] = 5.0
        self.assertEqual(matrix[0, 1], 5.0)
        before = list(matrix)
        with self.assertRaises(TypeError):
            matrix[1.0] = 7.0
        self.assertEqual(list(matrix), before)
        expected = om2.MMatrix()
        expected.setElement(0, 3, 2.0)
        expected.setElement(0, 1, 5.0)
        self.assertTrue(matrix.isEquivalent(expected, 0.0))


class MatrixIdentityTest(unittest.TestCase):
    """isIdentityの許容誤差。"""

    def test_tolerance_type_and_value(self):
        """数値でなければTypeError、負や有限でなければValueError。"""
        for tolerance, error in (("a", TypeError), (None, TypeError), (-1.0, ValueError), (float("nan"), ValueError), (float("inf"), ValueError)):
            with self.subTest(tolerance=tolerance):
                with self.assertRaises(error):
                    Matrix().isIdentity(tolerance)
        self.assertTrue(Matrix().isIdentity(0.0))
        self.assertEqual(Matrix().isIdentity(), om2.MMatrix().isEquivalent(om2.MMatrix.kIdentity))


class MatrixWrapTest(unittest.TestCase):
    """MFloatMatrixからの複製。"""

    def test_wrap_float_matrix_copies_values(self):
        """MFloatMatrixは値を写した新しいMatrixになる。"""
        values = [float(index) for index in range(16)]
        result = Matrix._wrap(om2.MFloatMatrix(values))
        self.assertIs(type(result), Matrix)
        self.assertEqual(list(result), values)


class RebuildTest(unittest.TestCase):
    """pickleの再構築の境界。"""

    def test_matrix_needs_sixteen_values(self):
        """Matrixは16個の値が要り、それ以外はValueError。"""
        with self.assertRaises(ValueError):
            vector_module._rebuild(Matrix, (1.0, 2.0))
        result = vector_module._rebuild(Matrix, tuple(float(index) for index in range(16)))
        self.assertEqual(list(result), [float(index) for index in range(16)])

    def test_unsupported_class_raises_type_error(self):
        """om2の数学型の派生でないクラスはTypeError。"""
        for cls in (int, dict):
            with self.subTest(cls=cls.__name__):
                with self.assertRaises(TypeError):
                    vector_module._rebuild(cls, (1,))
        self.assertEqual(vector_module._rebuild(Vector, (1.0, 2.0, 3.0)), Vector(1.0, 2.0, 3.0))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
