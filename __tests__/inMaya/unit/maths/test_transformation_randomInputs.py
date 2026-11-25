"""``mlib.maths.transformation`` をランダムな入力で om2・transform/jointノードの計算と突き合わせるテスト。

乱数は種を固定した ``random.Random`` で作り、失敗したときは subTest に種・番号・入力の値が出る。
translate・rotate(6つの回転順序)・scale・shear・ピボット4種・rotateAxis・jointOrient・inverseScale を
ランダムに入れた Transformation の matrix を、同じ値を設定した transform・joint ノードの matrix と、
om2.MTransformationMatrix で合成・分解した値と比べる。
"""

import math
import random
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate, Matrix, Transformation

SEED = 20261129
COUNT = 60


def fmt(values):
    """subTest に出すため、数値の並びを短い文字列にする。"""
    return "(" + ", ".join(f"{value:.17g}" for value in values) + ")"


def max_diff(a, b):
    """同じ長さの2つの並びの、成分の差の最大値を返す。"""
    return max(abs(x - y) for x, y in zip(list(a), list(b)))


def random_values(rng, joint=False):
    """Transformation と ノードの両方へ入れる、ランダムな値の辞書を返す(角度は rad)。"""

    def vector(scale):
        return tuple(rng.uniform(-scale, scale) for _ in range(3))

    def angles():
        return tuple(rng.uniform(-math.pi, math.pi) for _ in range(3))

    values = {
        "rotateOrder": rng.randrange(6),
        "translate": vector(10.0),
        "rotate": angles(),
        "scale": tuple(rng.choice((-1, 1)) * rng.uniform(0.2, 3.0) for _ in range(3)),
        "shear": vector(0.5),
        "rotateAxis": angles(),
        "rotatePivot": vector(5.0),
        "rotatePivotTranslate": vector(2.0),
        "scalePivot": vector(5.0),
        "scalePivotTranslate": vector(2.0),
    }
    if joint:
        values["jointOrient"] = angles()
    return values


def to_transformation(values, inverse_scale=None):
    """random_values の辞書から Transformation を作る。"""
    keywords = dict(values)
    order = keywords.pop("rotateOrder")
    rotate = keywords.pop("rotate")
    value = Transformation(rotateOrder=order, rotate=EulerRotate(rotate[0], rotate[1], rotate[2], order), **keywords)
    if inverse_scale is not None:
        value.inverseScale = inverse_scale
    return value


def apply_to_node(name, values):
    """random_values の辞書をノードのアトリビュートへ cmds.setAttr で書く。"""
    cmds.setAttr(name + ".rotateOrder", values["rotateOrder"])
    for key, attr in (
        ("translate", "translate"),
        ("scale", "scale"),
        ("shear", "shear"),
        ("rotatePivot", "rotatePivot"),
        ("rotatePivotTranslate", "rotatePivotTranslate"),
        ("scalePivot", "scalePivot"),
        ("scalePivotTranslate", "scalePivotTranslate"),
    ):
        cmds.setAttr(name + "." + attr, *values[key])
    for key in ("rotate", "rotateAxis", "jointOrient"):
        if key in values:
            cmds.setAttr(name + "." + key, *(math.degrees(v) for v in values[key]))


class TransformationRandomTest(unittest.TestCase):
    """シーンに触れない計算を om2 と突き合わせる。"""

    def test_matrix_decomposition_matches_om2(self):
        rng = random.Random(SEED)
        for index in range(COUNT * 2):
            values = random_values(rng)
            source = om2.MTransformationMatrix()
            source.setScale(values["scale"], om2.MSpace.kTransform)
            source.setShear(values["shear"], om2.MSpace.kTransform)
            source.setRotation(om2.MEulerRotation(*values["rotate"], values["rotateOrder"]))
            source.setTranslation(om2.MVector(*values["translate"]), om2.MSpace.kTransform)
            matrix = source.asMatrix()
            with self.subTest(seed=SEED, index=index, matrix=fmt(list(matrix))):
                value = Transformation(Matrix(matrix))
                reference = om2.MTransformationMatrix(matrix)
                self.assertLessEqual(max_diff(value.translate, reference.translation(om2.MSpace.kTransform)), 1e-9)
                self.assertLessEqual(max_diff(value.scale, reference.scale(om2.MSpace.kTransform)), 1e-9)
                self.assertLessEqual(max_diff(value.shear, reference.shear(om2.MSpace.kTransform)), 1e-9)
                self.assertLessEqual(max_diff(value.rotate, reference.rotation()), 1e-9)
                self.assertLessEqual(max_diff(value.matrix, matrix), 1e-9)
                self.assertLessEqual(max_diff(value.asMatrix(), matrix), 1e-9)

    def test_matrix_matches_om2_without_joint_values(self):
        rng = random.Random(SEED + 1)
        for index in range(COUNT * 2):
            values = random_values(rng)
            with self.subTest(seed=SEED + 1, index=index, **{key: fmt(value) if isinstance(value, tuple) else value for key, value in values.items()}):
                value = to_transformation(values)
                # jointOrient・inverseScale が無ければ、om2 の asMatrix と同じになる。
                self.assertLessEqual(max_diff(value.matrix, om2.MTransformationMatrix.asMatrix(value)), 1e-9)
                copied = value.copy()
                self.assertEqual(copied, value)
                self.assertTrue(copied.isEquivalent(value, 1e-12))
                copied.translate = tuple(t + 1e-3 for t in values["translate"])
                self.assertFalse(copied.isEquivalent(value, 1e-6))
                self.assertTrue(copied.isEquivalent(value, 1e-2))
                self.assertEqual(value.rotateOrder, values["rotateOrder"])
                self.assertEqual(value.rotate.order, values["rotateOrder"])
                self.assertLessEqual(max_diff(value.rotate, values["rotate"]), 1e-12)
                self.assertLessEqual(max_diff(value.rotatePivot, values["rotatePivot"]), 1e-12)
                self.assertLessEqual(max_diff(value.scalePivotTranslate, values["scalePivotTranslate"]), 1e-12)


class TransformationNodeRandomTest(NamespaceCase):
    """transform・joint ノードの matrix と突き合わせる。"""

    PREFIX = "mlibTransformationRandom_"

    def test_matrix_matches_transform_node(self):
        rng = random.Random(SEED + 2)
        node = self.make("transform", "node#")
        for index in range(COUNT):
            values = random_values(rng)
            with self.subTest(seed=SEED + 2, index=index, **{key: fmt(value) if isinstance(value, tuple) else value for key, value in values.items()}):
                apply_to_node(node, values)
                expected = cmds.getAttr(node + ".matrix")
                value = to_transformation(values)
                self.assertLessEqual(max_diff(value.matrix, expected), 1e-9, fmt(value.matrix) + " / " + fmt(expected))

    def test_matrix_matches_joint_node(self):
        rng = random.Random(SEED + 3)
        cmds.select(clear=True)
        parent = cmds.joint(name=self.name("parent"))
        child = cmds.joint(name=self.name("child"))
        for index in range(COUNT):
            values = random_values(rng, joint=True)
            # inverseScale は親の scale が接続で入る。segmentScaleCompensate が有効なときだけ使われる。
            parent_scale = tuple(rng.uniform(0.3, 3.0) for _ in range(3))
            compensate = rng.random() < 0.5
            with self.subTest(
                seed=SEED + 3,
                index=index,
                parentScale=fmt(parent_scale),
                ssc=compensate,
                **{key: fmt(value) if isinstance(value, tuple) else value for key, value in values.items()},
            ):
                cmds.setAttr(parent + ".scale", *parent_scale)
                cmds.setAttr(child + ".segmentScaleCompensate", compensate)
                apply_to_node(child, values)
                expected = cmds.getAttr(child + ".matrix")
                value = to_transformation(values, inverse_scale=parent_scale if compensate else (1.0, 1.0, 1.0))
                self.assertLessEqual(max_diff(value.matrix, expected), 1e-9, fmt(value.matrix) + " / " + fmt(expected))


if __name__ == "__main__":
    import sys

    unittest.main(argv=[sys.argv[0]])
