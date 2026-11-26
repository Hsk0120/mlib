"""Place2dTextureのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method

from mlib.nodes import Place2dTexture

#: connectTexture がつなぐアトリビュートの組(place2dTexture 側, テクスチャ側)。
PAIRS = (
    *(
        (name, name)
        for name in (
            "coverage",
            "translateFrame",
            "rotateFrame",
            "mirrorU",
            "mirrorV",
            "stagger",
            "wrapU",
            "wrapV",
            "repeatUV",
            "offset",
            "rotateUV",
            "noiseUV",
            "vertexUvOne",
            "vertexUvTwo",
            "vertexUvThree",
            "vertexCameraOne",
        )
    ),
    ("outUV", "uvCoord"),
    ("outUvFilterSize", "uvFilterSize"),
)


def _make_place(case):
    """place2dTexture 2つ・file・checker・lambert を作り、1つ目の place2dTexture を返す。

    file はまだつないでいない。checker の uvCoord には2つ目の place2dTexture をつないでおく(force の確かめ)。
    """
    place = cmds.shadingNode("place2dTexture", asUtility=True, name=case.name("place#"))
    other = cmds.shadingNode("place2dTexture", asUtility=True, name=case.name("place#"))
    cmds.shadingNode("file", asTexture=True, name=case.name("file#"))
    checker = cmds.shadingNode("checker", asTexture=True, name=case.name("checker#"))
    cmds.shadingNode("lambert", asShader=True, name=case.name("mat#"))
    cmds.connectAttr(other + ".outUV", checker + ".uvCoord")
    return Place2dTexture(place)


def _named(pattern, wrap=False):
    def make(case):
        name = cmds.ls(case.ns + ":" + pattern)[0]
        return mlib.getNode(name) if wrap else name

    return Lazy(make, f"<{pattern}{'のNode' if wrap else ''}>")


def _expect_connected(case, call):
    """テクスチャに有るアトリビュートが、すべて place2dTexture からつながったことを確かめる。"""
    case.assertIsNone(call.result)
    place, texture = str(call.target), str(call.kwargs["texture"])
    for origin, target in PAIRS:
        if cmds.attributeQuery(target, node=texture, exists=True):
            sources = cmds.listConnections(f"{texture}.{target}", source=True, destination=False, plugs=True) or []
            case.assertEqual(sources, [f"{place}.{origin}"], target)


#: 段1のテクスチャの候補(Node・名前・別のテクスチャ型)。
TEXTURE_VALUES = (_named("file*", wrap=True), _named("file*"), _named("checker*", wrap=True))
#: 段2のテクスチャの誤った値(Texture2d でないノード・削除済み・存在しない名前・数)。
TEXTURE_INVALID = (_named("mat*"), _named("place*"), DELETED_NODE, MISSING_NAME, 1.5, None)


#: 正しい呼び方の表。
METHODS = (
    Method(
        "connectTexture",
        _make_place,
        args=(_named("file*", wrap=True),),
        values={"texture": TEXTURE_VALUES},
        replace=("texture",),
        invalid={"texture": TEXTURE_INVALID},
        expect=_expect_connected,
        limit=30,
    ),
)


class Place2dTextureArgumentSweepTest(ArgumentSweepCase):
    """Place2dTextureのメソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
