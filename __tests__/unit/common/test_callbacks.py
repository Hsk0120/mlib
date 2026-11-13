"""``mlib.common.callbacks`` のテスト。

- common の照会・コールバックの契約を固定する。
"""

import os
import shutil
import tempfile
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Plugin, Time, Version
from mlib.common.callbacks import Callbacks
from mlib.common.environment import Environment
from mlib.nodes import Node
from support.namespaceCase import NamespaceCase


_FAKE_PLUGIN = "mlibSpecFakePlugin"


class CallbacksTest(NamespaceCase):

    def test_attribute_changed(self):
        """setAttr で (message, Plug) が渡り、remove 後は呼ばれない。"""
        node = self.make("transform", "cb")
        calls = []
        callbacks = Callbacks()
        callback_id = callbacks.addAttributeChangedCallback(node, lambda message, plug: calls.append((message, plug)))
        self.assertIsInstance(callback_id, int)
        cmds.setAttr(node + ".translateX", 3)
        self.assertTrue(calls)
        message, plug = calls[-1]
        self.assertTrue(message & om2.MNodeMessage.kAttributeSet)
        self.assertEqual(str(plug), node + ".translateX")
        callbacks.remove()
        count = len(calls)
        cmds.setAttr(node + ".translateX", 4)
        self.assertEqual(len(calls), count)

    def test_attribute_changed_accepts_node(self):
        """Node も受け付ける。"""
        node = mlib.getNode(self.make("transform", "cbNode"))
        calls = []
        with Callbacks() as callbacks:
            callbacks.addAttributeChangedCallback(node, lambda message, plug: calls.append(plug))
            node.tx = 2
        self.assertTrue(calls)
        count = len(calls)
        node.tx = 5
        self.assertEqual(len(calls), count)

    def test_time_changed(self):
        """timeChanged のイベントで呼ばれ、with を抜けると呼ばれない。"""
        calls = []
        with Time.preserved():
            with Callbacks() as callbacks:
                callbacks.addEventCallback("timeChanged", lambda: calls.append("time"))
                cmds.currentTime(cmds.currentTime(query=True) + 1)
            self.assertEqual(calls, ["time"])
            cmds.currentTime(cmds.currentTime(query=True) + 1)
        self.assertEqual(calls, ["time"])

    def test_scene_new(self):
        """afterNew はシーン新規で呼ばれ、remove 後は呼ばれない(この試験だけ新規シーンにする)。"""
        calls = []
        callbacks = Callbacks()
        callbacks.addSceneCallback("beforeNew", lambda: calls.append("before"))
        callbacks.addSceneCallback("afterNew", lambda: calls.append("after"))
        cmds.file(new=True, force=True)
        self.assertEqual(calls, ["before", "after"])
        callbacks.remove()
        cmds.file(new=True, force=True)
        self.assertEqual(calls, ["before", "after"])
        # 名前空間は新規シーンで消えたので、tearDown のために作り直す。
        cmds.namespace(add=self.ns)

    def test_exception_is_swallowed(self):
        """コールバックの例外は警告になり、後続の処理と他のコールバックを止めない。"""
        calls = []

        def fail():
            raise ValueError("boom")

        with Time.preserved():
            with Callbacks() as callbacks:
                callbacks.addEventCallback("timeChanged", fail)
                callbacks.addEventCallback("timeChanged", lambda: calls.append("ok"))
                cmds.currentTime(cmds.currentTime(query=True) + 1)
        self.assertEqual(calls, ["ok"])

    def test_remove_is_repeatable(self):
        """remove は何度呼んでもよい。with を入れ子にすると RuntimeError。"""
        callbacks = Callbacks()
        callbacks.addEventCallback("SelectionChanged", lambda: None)
        callbacks.remove()
        callbacks.remove()
        with callbacks:
            with self.assertRaises(RuntimeError):
                with callbacks:
                    pass

    def test_errors(self):
        """不正な入力は例外で、登録は残さない。"""
        callbacks = Callbacks()
        cases = [
            (ValueError, callbacks.addSceneCallback, "afterOpenTypo", lambda: None),
            (ValueError, callbacks.addSceneCallback, "beforeSaveCheck", lambda: None),
            (ValueError, callbacks.addSceneCallback, "AfterOpen", lambda: None),
            (TypeError, callbacks.addSceneCallback, 1, lambda: None),
            (TypeError, callbacks.addSceneCallback, "afterOpen", None),
            (ValueError, callbacks.addEventCallback, "noSuchEvent", lambda: None),
            (TypeError, callbacks.addEventCallback, None, lambda: None),
            (TypeError, callbacks.addEventCallback, "timeChanged", 3),
            (RuntimeError, callbacks.addAttributeChangedCallback, self.name("missing"), lambda m, p: None),
            (TypeError, callbacks.addAttributeChangedCallback, 1.5, lambda m, p: None),
            (TypeError, callbacks.addAttributeChangedCallback, self.make("transform", "err"), "x"),
        ]
        for error, method, first, second in cases:
            with self.subTest(method=method.__name__, first=first):
                self.assertRaises(error, method, first, second)
        self.assertEqual(callbacks._ids, [])


if __name__ == "__main__":
    unittest.main()
