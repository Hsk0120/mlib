"""Mayaの保持状態と番号の対応を検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class PlugInternalStatesTest(NamespaceCase):
    def test_native_states_do_not_mean_connected(self):
        node = mlib.getNode(cmds.createNode("transform", name=self.ns + ":node"))
        plug = node.getPlug("tx")
        native = plug.mplug()
        fn = om2.MFnDependencyNode(node.mnode())
        self.assertEqual(plug.getAttributeClass(), fn.attributeClass(native.attribute()))
        self.assertEqual(plug.isNewAttribute(), fn.isNewAttribute(native.attribute()))
        extra = node.addAttr("extra", attributeType="double")
        self.assertEqual(extra.getAttributeClass(), om2.MFnDependencyNode.kLocalDynamicAttr)
        self.assertTrue(extra.isNewAttribute())
        cmds.delete(node.getName())
        with self.assertRaises(RuntimeError):
            plug.getAttributeClass()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
