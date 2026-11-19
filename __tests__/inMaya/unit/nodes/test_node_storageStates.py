"""Mayaの保持状態と番号の対応を検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class NodeStorageStatesTest(NamespaceCase):
    def test_native_states_and_invalid_reference(self):
        node = mlib.getNode(cmds.createNode("network", name=self.ns + ":node"))
        fn = om2.MFnDependencyNode(node.mnode())
        self.assertEqual(node.canBeWritten(), fn.canBeWritten())
        self.assertEqual(node.isShared(), fn.isShared)
        self.assertEqual(node.isTrackingEdits(), fn.isTrackingEdits())
        self.assertEqual(node.getAbsoluteName(), ":" + self.ns + ":node")
        cmds.delete(node.getName())
        with self.assertRaises(RuntimeError):
            node.canBeWritten()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
