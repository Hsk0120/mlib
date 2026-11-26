"""Transformationの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は om2 の ``MTransformationMatrix`` の成分(平行移動・回転・スケール・シアー・ピボット)と突き合わせる。
数学型はシーンを変えないので、Undo・fast の性質は当てはまらない(表は ``writes=False``)。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.maths import Matrix, Transformation

K = om2.MSpace.kTransform


def _om2(offset=0.0):
    tm = om2.MTransformationMatrix()
    tm.setTranslation(om2.MVector(1.0 + offset, 2.0, 3.0), K)
    tm.setRotation(om2.MEulerRotation(0.1, 0.2, 0.3))
    tm.setScale((1.0, 2.0, 3.0), K)
    tm.setShear((0.1, 0.0, 0.0), K)
    tm.setRotatePivot(om2.MPoint(0.5, 0.0, 0.0), K, False)
    return tm


def _transformation(case):
    return Transformation(_om2())


def _components(tm):
    """om2 で読む成分の並び。"""
    rotation = tm.rotation()
    return [*tm.translation(K), rotation.x, rotation.y, rotation.z, *tm.scale(K), *tm.shear(K), *list(tm.rotatePivot(K))[:3], *list(tm.scalePivot(K))[:3]]


def _value(case, target):
    return _components(target) if isinstance(target, om2.MTransformationMatrix) else None


def _expect_equivalent(case, call):
    """om2 の成分の差の最大と tolerance の関係で結果を決める(差がちょうど境界の候補は置かない)。"""
    difference = max(abs(a - b) for a, b in zip(_components(call.target), _components(call.kwargs["other"])))
    case.assertIs(call.result, difference <= call.kwargs.get("tolerance", 1e-10) + 1e-12)


METHODS = (
    Method(
        "isEquivalent",
        _transformation,
        args=(om2.MTransformationMatrix(),),
        values={
            "other": (
                _om2(),
                Transformation(_om2()),
                _om2(0.25),
                Transformation(_om2(2.0)),
                om2.MTransformationMatrix(),
                Transformation(om2.MTransformationMatrix(Matrix())),
            )
        },
        replace=("other",),
        invalid={"other": (Matrix(), om2.MMatrix(), (1.0, 2.0, 3.0), "abc", None)},
        expect=_expect_equivalent,
        state=_value,
        writes=False,
    ),
)


class TransformationArgumentSweepTest(ArgumentSweepCase):
    """Transformationの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
