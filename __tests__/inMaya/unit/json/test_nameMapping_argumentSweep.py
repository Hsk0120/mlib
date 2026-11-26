"""NameMapping.convert の引数を、表から網羅して確かめる(段1〜3)。

結果は docstring の規則(nameMap → replace → namespaceMap の順)で手で求めた名前と突き合わせる。
シーンを変えないので、Undo・fast の性質は当てはまらない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.json import NameMapping

#: 名前と、変換後の名前(nameMap={"arm_L_jnt": "leftArm"}・replace=[("_L_", "_R_")]・namespaceMap={"chrA": "chrB", "": "root"})。
EXPECTED = {
    "chrA:arm_L_jnt": "chrB:leftArm",
    "chrA:leg_L_jnt": "chrB:leg_R_jnt",
    "leg_L_jnt": "root:leg_R_jnt",
    "chrA:sub:x_L_y": "chrB:sub:x_R_y",
    ":chrA:arm_L_jnt": "chrB:leftArm",
    "other:arm_L_jnt": "other:leftArm",
    "other:plain": "other:plain",
    "": "root:",
}


def _mapping(case):
    return NameMapping(nameMap={"arm_L_jnt": "leftArm"}, replace=[("_L_", "_R_")], namespaceMap={"chrA": "chrB", "": "root"})


def _expect_convert(case, call):
    case.assertEqual(call.result, EXPECTED[call.kwargs["name"]])
    case.assertEqual(NameMapping().convert(call.kwargs["name"]), call.kwargs["name"].lstrip(":"))


METHODS = (
    Method(
        "convert",
        _mapping,
        args=("chrA:arm_L_jnt",),
        values={"name": tuple(EXPECTED)},
        replace=("name",),
        invalid={"name": (1.5, None, b"chrA:arm", ("chrA:arm",))},
        expect=_expect_convert,
        writes=False,
    ),
)


class NameMappingArgumentSweepTest(ArgumentSweepCase):
    """NameMapping.convert の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
