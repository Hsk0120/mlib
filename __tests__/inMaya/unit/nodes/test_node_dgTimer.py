"""DG計測状態は通常のシーン編集やUndoと独立して扱う。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class NodeDgTimerTest(NamespaceCase):
    def test_state_results_reset_and_undo_queue(self):
        node = mlib.getNode(cmds.createNode("multiplyDivide", name=self.ns + ":node"))
        fn = om2.MFnDependencyNode(node.mnode())
        undo_name = cmds.undoInfo(query=True, undoName=True)
        undo_state = cmds.undoInfo(query=True, state=True)
        try:
            self.assertIsNone(node.setDgTimerEnabled(True))
            self.assertEqual(node.getDgTimerState(), om2.MFnDependencyNode.kTimerOn)
            for metric in range(om2.MFnDependencyNode.kTimerMetrics):
                for kind in range(om2.MFnDependencyNode.kTimerTypes):
                    self.assertEqual(node.getDgTimer(metric, timerType=kind), fn.dgTimer(metric, kind))
            names, values = fn.dgCallbacks(0)
            self.assertEqual(node.getDgCallbacks(), list(zip(names, values)))
            self.assertIsNone(node.resetDgTimer())
            self.assertEqual(node.getDgTimerState(), om2.MFnDependencyNode.kTimerOn)
            self.assertIsNone(node.setDgTimerEnabled(False))
            self.assertEqual(node.getDgTimerState(), om2.MFnDependencyNode.kTimerOff)
            self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
            self.assertEqual(cmds.undoInfo(query=True, state=True), undo_state)
        finally:
            fn.dgTimerOff()
        with self.assertRaises(TypeError):
            node.setDgTimerEnabled(1)
        with self.assertRaises(TypeError):
            node.getDgTimer(True)
        with self.assertRaises(ValueError):
            node.getDgTimer(9)
        with self.assertRaises(ValueError):
            node.getDgCallbacks(timerType=-1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
