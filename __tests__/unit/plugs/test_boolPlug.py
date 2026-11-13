"""``mlib.plugs.boolPlug`` のテスト。

- mlib Node/DAG APIを検証するMaya内テスト。
"""

import math
import sys
import unittest

from maya.api.OpenMaya import MSpace
import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Namespace
from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Translate, Vector
from mlib.nodes import Node


class NodeApiTest(unittest.TestCase):
    """基本Node/DAG APIを検証する。"""

    namespace = ":mlibNodeApiTest"

    def setUp(self):
        self.created = []
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.namespace(add=self.namespace)

    def tearDown(self):
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)

    def create_transform(self, name):
        node = mlib.createNode(type="transform", name=name)
        self.created.append(node.getName())
        return node

    def assert_channels(self, name, rotate, scale, places=9):
        for actual, expected in zip(cmds.getAttr(name + ".rotate")[0], rotate):
            self.assertAlmostEqual(actual, expected, places=places)
        for actual, expected in zip(cmds.getAttr(name + ".scale")[0], scale):
            self.assertAlmostEqual(actual, expected, places=places)

    def test_bool_plug_toggle(self):
        transform = self.create_transform("mlibNodeApiBoolToggle")
        plug = transform.getPlug("visibility")
        plug.set(True)

        result = plug.toggle()
        self.assertIs(result, plug)
        self.assertFalse(plug.get())

        plug.toggle()
        self.assertTrue(plug.get())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
