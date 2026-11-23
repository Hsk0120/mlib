"""コンポーネントの複数形の ``getNames`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class ComponentNamesTest(NamespaceCase):
    """getNames は cmds.ls(flatten=True) と同じ最短の名前を、持っている順に返す。"""

    PREFIX = "mlibComponentNames_"

    def test_matches_ls_flatten(self):
        """頂点・フェース・CV・曲面のCVで cmds.ls(flatten=True) と同じになる。"""
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        curve = cmds.curve(name=self.name("curve"), point=[(0, 0, 0), (1, 1, 0), (2, 0, 0), (3, 1, 0)], degree=3)
        plane = cmds.nurbsPlane(name=self.name("plane"), patchesU=2, patchesV=2, constructionHistory=False)[0]
        for pattern in (cube + ".vtx[*]", cube + ".f[1:3]", curve + ".cv[*]", plane + ".cv[0:1][2]"):
            with self.subTest(pattern=pattern):
                components = mlib.ls(pattern)
                self.assertEqual(components.getNames(), cmds.ls(pattern, flatten=True))
        vertices = mlib.ls(cube + ".vtx[*]")
        reordered = type(vertices)(vertices.shape, [5, 0, 3])
        self.assertEqual(reordered.getNames(), [f"{cube}.vtx[5]", f"{cube}.vtx[0]", f"{cube}.vtx[3]"])
        self.assertEqual(type(vertices)(vertices.shape, []).getNames(), [])

    def test_two_shapes_keep_shape_name(self):
        """シェイプが2つあるTransformでは、Mayaと同じくシェイプの名前になる。"""
        cube = cmds.polyCube(name=self.name("twin"), constructionHistory=False)[0]
        extra = cmds.polyCube(name=self.name("extra"), constructionHistory=False)[0]
        shape = cmds.listRelatives(extra, shapes=True, fullPath=True)[0]
        cmds.parent(shape, cube, shape=True, relative=True)
        pattern = cmds.listRelatives(cube, shapes=True, fullPath=True)[0] + ".vtx[0:1]"
        self.assertEqual(mlib.ls(pattern).getNames(), cmds.ls(pattern, flatten=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
