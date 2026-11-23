"""mlib.nodes.locator の Locator ラッパーを検証するMaya内テスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from mlib.nodes import Node
from mlib.nodes.locator import Locator


class LocatorTest(unittest.TestCase):
    """ラッパーの型と、localPosition の Plug での読み書きを検証する。"""

    def setUp(self):
        self.transform = cmds.spaceLocator(name="mlibLocatorTest")[0]
        self.created = [self.transform]
        shape_name = cmds.listRelatives(self.transform, shapes=True)[0]
        self.locator = Node(shape_name)

    def tearDown(self):
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)

    def test_node_resolves_to_locator_wrapper(self):
        self.assertIsInstance(self.locator, Locator)

    def test_local_position_default(self):
        self.assertFalse(hasattr(Locator, "getPosition"))
        self.assertFalse(hasattr(Locator, "setPosition"))
        self.assertEqual(self.locator.getPlug("localPosition").get(), (0.0, 0.0, 0.0))

    def test_local_position_round_trips(self):
        plug = self.locator.getPlug("localPosition")
        for fast in (False, True):
            with self.subTest(fast=fast):
                value = (1.0, 2.0, 3.0) if not fast else (4.0, 5.0, 6.0)
                result = plug.set(value, fast=fast)
                self.assertIsNone(result)
                self.assertEqual(plug.get(), value)
                self.assertEqual(cmds.getAttr(self.locator.getFullName() + ".localPosition")[0], value)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
