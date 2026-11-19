"""マルチ要素の接続保護と通常・fast削除を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class MultiConnectionTest(NamespaceCase):
    def test_connected_child_rejected_before_shift(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                node = mlib.createNode("plusMinusAverage", name=self.name("sum"))
                driver = mlib.createNode("transform", name=self.name("driver"))
                array = node.getPlug("input3D")
                array[3].getChildren()[0].connect(driver.getPlug("tx"))
                cmds.flushUndo()
                with self.assertRaises(RuntimeError):
                    array.removeElement(3, fast=fast, breakConnections=False)
                self.assertTrue(array[3].getChildren()[0].isConnected())
                self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))
                array.removeElement(3, fast=fast)
                self.assertNotIn(3, array.getIndices())
                if not fast:
                    cmds.undo()
                    self.assertTrue(array[3].getChildren()[0].isConnected())
                    cmds.redo()
                    self.assertNotIn(3, array.getIndices())
                else:
                    self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))
                node.delete()
                driver.delete()

    def test_shift_protects_later_connections(self):
        node = mlib.createNode("plusMinusAverage", name=self.name("sum"))
        driver = mlib.createNode("transform", name=self.name("driver"))
        array = node.getPlug("input1D")
        array[1].set(2)
        array[4].connect(driver.getPlug("tx"))
        cmds.flushUndo()
        with self.assertRaises(RuntimeError):
            array.removeElement(1, shift=True, breakConnections=False)
        self.assertEqual(array[1].get(), 2)
        self.assertTrue(array[4].isConnected())
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))
        with self.assertRaises(TypeError):
            array.removeElement(1, breakConnections=0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
