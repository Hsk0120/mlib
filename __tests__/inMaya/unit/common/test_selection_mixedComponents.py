"""``Selection.capture`` が同じ形状の種類の違うコンポーネントをすべて返すことのテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.common import Selection


class MixedComponentSelectionTest(NamespaceCase):
    """同じメッシュの頂点・フェース・エッジを一緒に選んだ場合。"""

    PREFIX = "mlibSelectionMixed_"

    def test_capture_returns_every_kind(self):
        """mlib.ls(selection=True) と同じ要素を返す(以前は最初の種類だけだった)。"""
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        other = cmds.polyCube(name=self.name("other"), constructionHistory=False)[0]
        cmds.select(cube + ".vtx[0:2]", cube + ".f[3]", cube + ".e[1]", other, other + ".vtx[5]")
        captured = Selection.capture().getItems()
        listed = list(mlib.ls(selection=True))
        self.assertEqual([item.getFullName() for item in captured], [item.getFullName() for item in listed])
        kinds = [type(item).__name__ for item in captured]
        for kind in ("Vertex", "Face", "Edge"):
            self.assertIn(kind, kinds)
        self.assertEqual(len([item for item in captured if isinstance(item, mlib.Component)]), 6)
        groups = Selection.capture().getComponents()
        self.assertEqual(sorted(type(group).__name__ for group in groups), ["Edges", "Faces", "Vertices", "Vertices"])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
