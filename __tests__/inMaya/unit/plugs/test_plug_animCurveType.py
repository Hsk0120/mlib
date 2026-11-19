"""アニメーションカーブの出力型の選択を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class PlugAnimCurveTypeTest(NamespaceCase):
    def test_unit_types_and_no_scene_edits(self):
        node = mlib.getNode(cmds.createNode("transform", name=self.ns + ":node"))
        before = cmds.ls(long=True)
        for attr, suffix in (("tx", "L"), ("rx", "A"), ("sx", "U")):
            plug = node.getPlug(attr)
            self.assertEqual(plug.getAnimCurveType(), "animCurveT" + suffix)
            self.assertEqual(plug.getAnimCurveType(timeInput=False), "animCurveU" + suffix)
        cmds.addAttr(node.getName(), longName="timeValue", attributeType="time")
        self.assertEqual(node.getPlug("timeValue").getAnimCurveType(), "animCurveTT")
        self.assertEqual(node.getPlug("timeValue").getAnimCurveType(timeInput=False), "animCurveUT")
        self.assertEqual(cmds.ls(long=True), before)
        with self.assertRaises(TypeError):
            node.getPlug("tx").getAnimCurveType(timeInput=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
