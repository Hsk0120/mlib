"""Transformationの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は om2 の ``MTransformationMatrix`` の成分(平行移動・回転・スケール・シアー・ピボット)と突き合わせる。
数学型はシーンを変えないので、Undo・fast の性質は当てはまらない(表は ``writes=False``)。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
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


def _constructor(cls):
    """コンストラクターを、``__init__`` の署名と docstring を持つ関数にする。

    クラスをそのまま ``function=`` に渡すと、署名は ``__new__`` の ``*args, **kwargs``、docstring はクラスの説明になり、
    ``__init__`` の Args・Raises を読めない。
    """

    def construct(*args, **kwargs):
        return cls(*args, **kwargs)

    signature = inspect.signature(cls.__init__)
    construct.__signature__ = signature.replace(parameters=list(signature.parameters.values())[1:])
    construct.__doc__ = cls.__init__.__doc__
    return construct


def _xyz(value):
    """3成分の値を、比べられる数の並びにする(MPoint の w は除く)。"""
    return list(value)[:3]


#: 3成分の候補(なし・タプル・リスト・om2 の型)。
XYZ = (None, (1.0, 2.0, 3.0), [0, 0, 0], om2.MVector(-1.0, 0.5, 4.0), om2.MPoint(2.0, -2.0, 2.0))
#: 回転の候補(なし・XYZ のラジアン・回転順序つきのオイラー回転・クォータニオン)。
ROTATIONS = (None, (0.1, -0.2, 0.3), om2.MEulerRotation(0.5, 0.0, 0.25, om2.MEulerRotation.kYZX), om2.MQuaternion(0.0, 0.0, 0.7071, 0.7071))
#: om2 で読む成分(引数の名前と、om2.MTransformationMatrix から読む関数)。
READERS = (
    ("translate", lambda tm: tm.translation(K)),
    ("scale", lambda tm: tm.scale(K)),
    ("shear", lambda tm: tm.shear(K)),
    ("rotatePivot", lambda tm: tm.rotatePivot(K)),
    ("rotatePivotTranslate", lambda tm: tm.rotatePivotTranslation(K)),
    ("scalePivot", lambda tm: tm.scalePivot(K)),
    ("scalePivotTranslate", lambda tm: tm.scalePivotTranslation(K)),
)


def _expect_init(case, call):
    """value だけなら om2 で作った値の成分と同じ。成分の引数は、om2 で読んだ成分が渡した値と同じ。"""
    kwargs = {name: value for name, value in call.kwargs.items() if value is not None}
    case.assertIs(type(call.result), Transformation)
    if list(kwargs) == ["value"]:
        value = kwargs["value"]
        expected = value if isinstance(value, om2.MTransformationMatrix) else om2.MTransformationMatrix(om2.MMatrix(value))
        case.assertSequenceAlmostEqual(_components(call.result), _components(expected), places=6)
    for name, read in READERS:
        if name in kwargs:
            case.assertSequenceAlmostEqual(_xyz(read(call.result)), _xyz(kwargs[name]), places=9)
    if "rotateOrder" in kwargs and not isinstance(kwargs.get("rotate"), om2.MEulerRotation):
        case.assertEqual(call.result.rotation().order, kwargs["rotateOrder"])


def _expect_copy(case, call):
    case.assertIs(type(call.result), type(call.target))
    case.assertIsNot(call.result, call.target)
    case.assertSequenceAlmostEqual(_components(call.result), _components(call.target), places=12)


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
    Method(
        "__init__",
        _transformation,
        function=_constructor(Transformation),
        values={
            "value": (
                None,
                _om2(),
                Transformation(_om2(0.25)),
                om2.MMatrix(Matrix(translate=(1.0, 2.0, 3.0), rotate=(0.1, 0.2, 0.3))),
                Matrix(),
                list(Matrix()),
            ),
            "translate": XYZ,
            "rotate": ROTATIONS,
            "rotateOrder": (None, 0, 3, 5),
            "scale": (None, (1.0, 1.0, 1.0), (2.0, 0.5, -1.0), om2.MVector(3.0, 3.0, 3.0)),
            "shear": (None, (0.0, 0.0, 0.0), (0.1, 0.2, 0.3)),
            "rotateAxis": ROTATIONS,
            "jointOrient": ROTATIONS,
            "rotatePivot": XYZ,
            "rotatePivotTranslate": XYZ,
            "scalePivot": XYZ,
            "scalePivotTranslate": XYZ,
            "inverseScale": (None, (1.0, 1.0, 1.0), (2.0, 4.0, 0.5)),
        },
        replace=("value", "translate", "rotate", "rotateOrder", "scale", "shear", "rotateAxis", "jointOrient"),
        invalid={"value": (list(range(15)), "abc", 1.0, object()), "rotateOrder": (6, -1, 1.5, "a", True)},
        expect=_expect_init,
        state=_value,
        writes=False,
    ),
    Method("copy", _transformation, expect=_expect_copy, state=_value, writes=False),
)


class TransformationArgumentSweepTest(ArgumentSweepCase):
    """Transformationの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
