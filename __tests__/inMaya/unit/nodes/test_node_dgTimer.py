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
            self.assertIsNone(node.setDgTimer(True))
            self.assertEqual(node.getDgTimer(state=True), om2.MFnDependencyNode.kTimerOn)
            for metric in range(om2.MFnDependencyNode.kTimerMetrics):
                for kind in range(om2.MFnDependencyNode.kTimerTypes):
                    self.assertEqual(node.getDgTimer(metric, timerType=kind), fn.dgTimer(metric, kind))
            names, values = fn.dgCallbacks(0)
            self.assertEqual(node.getDgTimer(callbacks=True), list(zip(names, values)))
            self.assertIsNone(node.setDgTimer(reset=True))
            self.assertEqual(node.getDgTimer(state=True), om2.MFnDependencyNode.kTimerOn)
            self.assertIsNone(node.setDgTimer(False))
            self.assertEqual(node.getDgTimer(state=True), om2.MFnDependencyNode.kTimerOff)
            self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
            self.assertEqual(cmds.undoInfo(query=True, state=True), undo_state)
        finally:
            fn.dgTimerOff()
        with self.assertRaises(TypeError):
            node.setDgTimer(1)
        with self.assertRaises(TypeError):
            node.getDgTimer(True)
        with self.assertRaises(ValueError):
            node.getDgTimer(9)
        with self.assertRaises(ValueError):
            node.getDgTimer(callbacks=True, timerType=-1)

    def test_get_state_matches_api(self):
        """getDgTimer(state=True) は MFnDependencyNode.dgTimerQueryState と同じ値を返す。"""
        node = mlib.getNode(cmds.createNode("multiplyDivide", name=self.ns + ":state"))
        fn = om2.MFnDependencyNode(node.mnode())
        try:
            for on in (True, False, True):
                with self.subTest(on=on):
                    node.setDgTimer(on)
                    state = node.getDgTimer(state=True)
                    self.assertIs(type(state), int)
                    self.assertEqual(state, fn.dgTimerQueryState())
                    self.assertEqual(state, om2.MFnDependencyNode.kTimerOn if on else om2.MFnDependencyNode.kTimerOff)
        finally:
            fn.dgTimerOff()

    def test_get_requires_exactly_one_query(self):
        """getDgTimer は metric・callbacks・state のちょうど1つを指定する(TypeError)。state・callbacks は bool だけ。"""
        node = mlib.getNode(cmds.createNode("multiplyDivide", name=self.ns + ":query"))
        cases = (
            ("nothing", lambda: node.getDgTimer()),
            ("metric and state", lambda: node.getDgTimer(0, state=True)),
            ("metric and callbacks", lambda: node.getDgTimer(0, callbacks=True)),
            ("callbacks and state", lambda: node.getDgTimer(callbacks=True, state=True)),
            ("state int", lambda: node.getDgTimer(state=1)),
            ("callbacks int", lambda: node.getDgTimer(callbacks=1)),
            ("state positional", lambda: node.getDgTimer(0, 0, False, True)),
        )
        for label, call in cases:
            with self.subTest(label), self.assertRaises(TypeError):
                call()

    def test_reset_keeps_state_and_undo_queue(self):
        """setDgTimer(reset=True) は計測結果だけを消し、開始・停止の状態と Undo の記録を変えない。state と一緒にも指定できる。"""
        node = mlib.getNode(cmds.createNode("multiplyDivide", name=self.ns + ":reset"))
        fn = om2.MFnDependencyNode(node.mnode())
        metric, kind = om2.MFnDependencyNode.kTimerMetric_callback, om2.MFnDependencyNode.kTimerType_count
        try:
            for on in (False, True):
                with self.subTest(on=on):
                    node.setDgTimer(on)
                    self.flushUndo()
                    self.assertIsNone(node.setDgTimer(reset=True))
                    self.assertUndoEmpty()
                    self.assertEqual(fn.dgTimerQueryState(), om2.MFnDependencyNode.kTimerOn if on else om2.MFnDependencyNode.kTimerOff)
                    self.assertEqual(node.getDgTimer(metric, timerType=kind), fn.dgTimer(metric, kind))
            # state と reset を一緒に渡すと、消してから開始・停止する。
            self.flushUndo()
            self.assertIsNone(node.setDgTimer(False, reset=True))
            self.assertEqual(fn.dgTimerQueryState(), om2.MFnDependencyNode.kTimerOff)
            self.assertIsNone(node.setDgTimer(True, reset=True))
            self.assertEqual(fn.dgTimerQueryState(), om2.MFnDependencyNode.kTimerOn)
            self.assertUndoEmpty()
        finally:
            fn.dgTimerOff()
        before = fn.dgTimerQueryState()
        cases = (
            ("nothing", lambda: node.setDgTimer()),
            ("reset False only", lambda: node.setDgTimer(reset=False)),
            ("state None only", lambda: node.setDgTimer(None)),
            ("reset int", lambda: node.setDgTimer(reset=1)),
            ("state int with reset", lambda: node.setDgTimer(1, reset=True)),
            ("reset positional", lambda: node.setDgTimer(True, True)),
        )
        for label, call in cases:
            with self.subTest(label), self.assertRaises(TypeError):
                call()
            self.assertEqual(fn.dgTimerQueryState(), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
