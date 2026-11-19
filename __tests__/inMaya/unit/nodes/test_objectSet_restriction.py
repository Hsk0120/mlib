"""Maya標準の照会と、既存の取得対象との違いを検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class ObjectSetRestrictionTest(NamespaceCase):
    def test_unrestricted_and_vertex_restricted_sets(self):
        for flag, expected in (({}, om2.MFnSet.kNone), ({"vertices": True}, om2.MFnSet.kVerticesOnly)):
            node = mlib.getNode(cmds.sets(empty=True, name=self.ns + ":set", **flag))
            self.assertEqual(node.getRestriction(), expected)
            cmds.delete(node.getName())
            with self.assertRaises(RuntimeError):
                node.getRestriction()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
