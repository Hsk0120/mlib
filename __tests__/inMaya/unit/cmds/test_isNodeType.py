"""``mlib.cmds.isNodeType`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()


class IsNodeTypeTest(unittest.TestCase):
    """cmds.allNodeTypesにある型名(抽象型を含む)だけTrueを返す。"""

    def test_known_types(self):
        for name in ("transform", "joint", "skinCluster", "dagNode", "geometryFilter"):
            with self.subTest(name=name):
                self.assertTrue(mlib.isNodeType(name))

    def test_unknown_types(self):
        for name in ("", "noSuchNodeType", "Transform", "transform ", "dagNode (abstract)"):
            with self.subTest(name=name):
                self.assertFalse(mlib.isNodeType(name))

    def test_matches_all_node_types(self):
        for name in cmds.allNodeTypes()[:50]:
            self.assertTrue(mlib.isNodeType(name))

    def test_invalid(self):
        for value in (None, 1, ["transform"], mlib):
            with self.subTest(value=value), self.assertRaises(TypeError):
                mlib.isNodeType(value)


class IsNodeTypeParityTest(unittest.TestCase):
    """cmds.nodeType(isTypeName=True)と同じ判定になる。"""

    def test_matches_node_type_query(self):
        for name in ("transform", "dagNode", "mesh", "noSuchNodeType"):
            with self.subTest(name=name):
                try:
                    expected = bool(cmds.nodeType(name, isTypeName=True))
                except RuntimeError:
                    expected = False
                self.assertEqual(mlib.isNodeType(name), expected)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
