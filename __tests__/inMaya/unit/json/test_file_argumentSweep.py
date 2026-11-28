"""``mlib.json.file`` の Header の引数を、表から網羅して確かめる(段1〜4)。

持たせた値はプロパティで読み直し、省いた fps は om2 の ``MTime`` で求めた今のシーンの fps と突き合わせる。
シーンを変えないので、Undo・fast の性質は当てはまらない。
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

from mlib.json import Header


def _constructor(owner):
    """クラスを、``__init__`` の引数・docstring を持つ関数にする(表は関数の docstring から Args・Raises を読むため)。"""
    signature = inspect.signature(owner.__init__)

    def construct(*args, **kwargs):
        return owner(*args, **kwargs)

    construct.__signature__ = signature.replace(parameters=list(signature.parameters.values())[1:])
    construct.__doc__ = owner.__init__.__doc__
    construct.__name__ = owner.__name__
    return construct


def _header(case):
    return Header("mlib.pose", 1)


def _scene_fps():
    """今のシーンの fps(1秒あたりの、UI の時間単位でのフレーム数)。"""
    return om2.MTime(1.0, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())


def _expect_init(case, call):
    """渡した値をそのまま持つ。fps は float にし、省くと今のシーンの fps になる。"""
    kwargs = call.kwargs
    header = call.result
    case.assertIs(type(header), Header)
    case.assertEqual(header.format, kwargs["format"])
    case.assertEqual(header.version, kwargs["version"])
    case.assertEqual(header.mlib, kwargs.get("mlib"))
    case.assertEqual(header.maya, kwargs.get("maya"))
    case.assertIsInstance(header.fps, float)
    case.assertAlmostEqual(header.fps, _scene_fps() if kwargs.get("fps") is None else kwargs["fps"], places=6)


#: mlib・maya は型を確かめずに持つ(docstring は str | None)。fps は正なら無限大も受け付ける。
KNOWN = {
    "invalid:mlib=*": "mlib は型を確かめずに持つ(docstring は str | None)",
    "invalid:maya=*": "maya は型を確かめずに持つ(docstring は str | None)",
    "invalid:fps=inf": "fps は正かどうかだけを確かめ、無限大を受け付ける",
}

METHODS = (
    Method(
        "__init__",
        _header,
        function=_constructor(Header),
        args=("mlib.pose", 1),
        values={
            "format": ("mlib.pose", "mlib.animation", "x", "日本語"),
            "version": (1, 2, 100),
            "mlib": (None, "0.0.1", ""),
            "maya": (None, "2027", "2022.5"),
            "fps": (None, 24, 24.0, 29.97, 0.5, 6000.0),
        },
        replace=("format", "version", "mlib", "maya", "fps"),
        invalid={
            "format": (1.5, None, "", b"mlib.pose"),
            "version": (0, -1, 1.5, "1", None, True),
            "mlib": (1.5, ["0.0.1"]),
            "maya": (1.5, 2027),
            "fps": (0, -24.0, "24", True, float("nan"), float("inf")),
        },
        expect=_expect_init,
        writes=False,
    ),
)


class FileArgumentSweepTest(ArgumentSweepCase):
    """Header の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
