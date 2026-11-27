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
            self.assertEqual(node.getDgTimer(kind="state"), om2.MFnDependencyNode.kTimerOn)
            for metric in range(om2.MFnDependencyNode.kTimerMetrics):
                for kind in range(om2.MFnDependencyNode.kTimerTypes):
                    self.assertEqual(node.getDgTimer(metric, timerType=kind), fn.dgTimer(metric, kind))
            names, values = fn.dgCallbacks(0)
            self.assertEqual(node.getDgTimer(kind="callbacks"), list(zip(names, values)))
            self.assertIsNone(node.resetDgTimer())
            self.assertEqual(node.getDgTimer(kind="state"), om2.MFnDependencyNode.kTimerOn)
            self.assertIsNone(node.setDgTimer(False))
            self.assertEqual(node.getDgTimer(kind="state"), om2.MFnDependencyNode.kTimerOff)
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
            node.getDgTimer(kind="callbacks", timerType=-1)

    def test_get_state_matches_api(self):
        """getDgTimer(kind="state") は MFnDependencyNode.dgTimerQueryState と同じ値を返す。"""
        node = mlib.getNode(cmds.createNode("multiplyDivide", name=self.ns + ":state"))
        fn = om2.MFnDependencyNode(node.mnode())
        try:
            for on in (True, False, True):
                with self.subTest(on=on):
                    node.setDgTimer(on)
                    state = node.getDgTimer(kind="state")
                    self.assertIs(type(state), int)
                    self.assertEqual(state, fn.dgTimerQueryState())
                    self.assertEqual(state, om2.MFnDependencyNode.kTimerOn if on else om2.MFnDependencyNode.kTimerOff)
        finally:
            fn.dgTimerOff()

    def test_get_requires_exactly_one_query(self):
        """getDgTimer は kind="metric"(既定)のときだけ metric を必ず受ける(TypeError)。kind は文字列だけ(TypeError)で、知らない名前は ValueError。"""
        node = mlib.getNode(cmds.createNode("multiplyDivide", name=self.ns + ":query"))
        with self.assertRaises(ValueError):
            node.getDgTimer(kind="unknown")
        cases = (
            ("nothing", lambda: node.getDgTimer()),
            ("metric and state", lambda: node.getDgTimer(0, kind="state")),
            ("metric and callbacks", lambda: node.getDgTimer(0, kind="callbacks")),
            ("kind int", lambda: node.getDgTimer(kind=1)),
            ("removed callbacks", lambda: node.getDgTimer(callbacks=True)),
            ("removed state", lambda: node.getDgTimer(state=True)),
            ("kind positional", lambda: node.getDgTimer(0, "metric")),
        )
        for label, call in cases:
            with self.subTest(label), self.assertRaises(TypeError):
                call()

    def test_reset_keeps_state_and_undo_queue(self):
        """resetDgTimer は計測結果だけを消し、開始・停止の状態と Undo の記録を変えない。"""
        node = mlib.getNode(cmds.createNode("multiplyDivide", name=self.ns + ":reset"))
        fn = om2.MFnDependencyNode(node.mnode())
        metric, kind = om2.MFnDependencyNode.kTimerMetric_callback, om2.MFnDependencyNode.kTimerType_count
        try:
            for on in (False, True):
                with self.subTest(on=on):
                    node.setDgTimer(on)
                    self.flushUndo()
                    self.assertIsNone(node.resetDgTimer())
                    self.assertUndoEmpty()
                    self.assertEqual(fn.dgTimerQueryState(), om2.MFnDependencyNode.kTimerOn if on else om2.MFnDependencyNode.kTimerOff)
                    self.assertEqual(node.getDgTimer(metric, timerType=kind), fn.dgTimer(metric, kind))
        finally:
            fn.dgTimerOff()

    def test_state_defaults_to_true(self):
        """setDgTimer() は state の既定 True で計測を始める。bool 以外と、以前の reset 引数は TypeError で、状態は変わらない。"""
        node = mlib.getNode(cmds.createNode("multiplyDivide", name=self.ns + ":default"))
        fn = om2.MFnDependencyNode(node.mnode())
        try:
            self.assertIsNone(node.setDgTimer())
            self.assertEqual(fn.dgTimerQueryState(), om2.MFnDependencyNode.kTimerOn)
            node.setDgTimer(False)
            before = fn.dgTimerQueryState()
            cases = (
                ("state None", lambda: node.setDgTimer(None)),
                ("state int", lambda: node.setDgTimer(1)),
                ("removed reset", lambda: node.setDgTimer(reset=True)),
                ("reset positional", lambda: node.setDgTimer(True, True)),
                ("reset with argument", lambda: node.resetDgTimer(True)),
            )
            for label, call in cases:
                with self.subTest(label), self.assertRaises(TypeError):
                    call()
                self.assertEqual(fn.dgTimerQueryState(), before)
        finally:
            fn.dgTimerOff()

    def test_state_is_not_undone(self):
        """setDgTimer・setDgTimingEnabledはUndoに載らず、直前の編集をUndoしても計測の状態は変わらない。"""
        node = mlib.getNode(cmds.createNode("multiplyDivide", name=self.ns + ":undo"))
        fn = om2.MFnDependencyNode(node.mnode())
        global_state = cmds.dgtimer(query=True, on=True)
        try:
            cmds.setAttr(f"{node}.input1X", 2)
            node.setDgTimer(True)
            mlib.Node.setDgTimingEnabled(True)
            cmds.undo()
            self.assertEqual(cmds.getAttr(f"{node}.input1X"), 0)
            self.assertEqual(fn.dgTimerQueryState(), om2.MFnDependencyNode.kTimerOn)
            self.assertTrue(cmds.dgtimer(query=True, on=True))
            cmds.redo()
            self.assertEqual(cmds.getAttr(f"{node}.input1X"), 2)
            self.assertEqual(fn.dgTimerQueryState(), om2.MFnDependencyNode.kTimerOn)
            mlib.Node.setDgTimingEnabled(False)
            self.assertFalse(cmds.dgtimer(query=True, on=True))
            with self.assertRaises(TypeError):
                mlib.Node.setDgTimingEnabled(1)
        finally:
            fn.dgTimerOff()
            mlib.Node.setDgTimingEnabled(bool(global_state))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
