"""Mayaの保持状態と番号の対応を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class MultiPhysicalIndicesTest(NamespaceCase):
    def test_sparse_array_and_uncreated_reference(self):
        node = mlib.getNode(cmds.createNode("network", name=self.ns + ":node"))
        cmds.addAttr(node.getName(), longName="values", attributeType="double", multi=True)
        plug = node.getPlug("values")
        plug[9].set(3)
        plug[2].set(4)
        self.assertEqual(plug[700].getIndex(), 700)
        self.assertEqual(plug.getElementCount(), 2)
        self.assertEqual(plug.getElementCount(evaluate=True), 2)
        self.assertNotIn(700, plug.getIndices())
        for physical in range(2):
            self.assertEqual(plug.getElement(physical, physical=True).getIndex(), plug.mplug().elementByPhysicalIndex(physical).logicalIndex())
        for index in (-1, 2):
            with self.assertRaises(IndexError):
                plug.getElement(index, physical=True)
        with self.assertRaises(TypeError):
            plug.getElement(True, physical=True)
        with self.assertRaises(TypeError):
            plug.getElementCount(evaluate=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
