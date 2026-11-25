"""``mlib.json.poseSnapshot`` の、取得する値の種類のテスト。

- チャンネルボックスに表示される文字列のアトリビュートは、スカラーでないので保存しない。
- 別名(alias)を付けたアトリビュートは、ロング名で1回だけ保存する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.json import PoseSnapshot


class PoseValueTest(NamespaceCase):
    """保存する値の選び方。"""

    PREFIX = "mlibJsonPoseValue_"

    def setUp(self):
        super().setUp()
        self.node = cmds.createNode("transform", name=self.name("node"))

    def test_string_attribute_in_channel_box_is_not_saved(self):
        """文字列はスカラーでないので保存せず、ほかの値はgetAttrと同じ値で保存する。"""
        cmds.addAttr(self.node, longName="note", dataType="string")
        cmds.setAttr(self.node + ".note", "text", type="string")
        cmds.setAttr(self.node + ".note", channelBox=True)
        self.assertIn("note", cmds.listAttr(self.node, channelBox=True))
        cmds.setAttr(self.node + ".tx", 2.5)
        attrs = PoseSnapshot.capture(self.node).toData()["nodes"][0]["attrs"]
        self.assertNotIn("note", attrs)
        self.assertEqual(attrs["translateX"], cmds.getAttr(self.node + ".tx"))

    def test_alias_is_saved_once_by_long_name(self):
        """別名を付けたアトリビュートは、ロング名で保存する。"""
        cmds.aliasAttr("slide", self.node + ".tx")
        cmds.setAttr(self.node + ".tx", 1.5)
        attrs = PoseSnapshot.capture(self.node).toData()["nodes"][0]["attrs"]
        self.assertNotIn("slide", attrs)
        self.assertEqual(attrs["translateX"], 1.5)
        self.assertEqual(list(attrs).count("translateX"), 1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
