"""Maya標準の照会と、既存の取得対象との違いを検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class PlugSetAttrCommandsTest(NamespaceCase):
    def test_commands_match_native_and_do_not_edit(self):
        node = mlib.getNode(cmds.createNode("transform", name=self.ns + ":node"))
        plug = node.getPlug("translateX")
        plug.set(3.5)
        undo_name = cmds.undoInfo(query=True, undoName=True)
        for name, selector in (("all", om2.MPlug.kAll), ("nonDefault", om2.MPlug.kNonDefault), ("changed", om2.MPlug.kChanged)):
            for long_names in (True, False):
                self.assertEqual(plug.getSetAttrCmds(valueSelector=name, useLongNames=long_names), list(plug.mplug().getSetAttrCmds(selector, long_names)))
        self.assertEqual(plug.get(), 3.5)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
        self.assertTrue(plug.getSetAttrCmds())
        with self.assertRaises(TypeError):
            plug.getSetAttrCmds(useLongNames=1)
        with self.assertRaises(ValueError):
            plug.getSetAttrCmds(valueSelector="invalid")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
