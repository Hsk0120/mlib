"""``mlib.common.sceneTime`` のテスト。

- 入口(作成関数・objExists・Time・キーの追加/削除・Shapeの親変更・setPreferredAngle)の約束を固定する。
- common の照会・コールバックの契約を固定する。
"""

import os
import shutil
import sys
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


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、UI単位・選択の補助。"""

    PREFIX = "mlibSpecEntry_"

    def setUp(self):
        """UI単位・時刻を保存して名前空間を用意する。"""
        super().setUp()
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.time = cmds.currentTime(query=True)
        self.range = (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))

    def tearDown(self):
        """UI単位・時刻を戻す。"""
        cmds.currentUnit(linear=self.linear)
        cmds.playbackOptions(minTime=self.range[0], maxTime=self.range[1])
        cmds.currentTime(self.time)
        super().tearDown()

    def assert_one_undo(self, action):
        """actionを1回のUndoで戻せ、作ったノードが消えることを確かめる。"""
        before = set(cmds.ls(long=True))
        cmds.flushUndo()
        result = action()
        self.assertTrue(set(cmds.ls(long=True)) - before)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        return result


class TimeTest(_SpecCase):
    """Timeは静的メソッドだけで、フレームと秒の両方で時刻・範囲を扱う。"""

    def test_current_ranges_and_preserved(self):
        """時刻・範囲の取得と変更、preservedで元の時刻へ戻ることを確かめる。"""
        cmds.currentUnit(time="film")
        self.assertEqual(Time.setCurrent(12), 12.0)
        self.assertEqual(cmds.currentTime(query=True), 12.0)
        self.assertAlmostEqual(Time.getCurrent(timeUnit="sec"), 0.5)
        Time.setCurrent(1.0, timeUnit="sec")
        self.assertEqual(Time.getCurrent(), 24.0)
        self.assertEqual(Time.setPlaybackRange(5, 48), (5.0, 48.0))
        self.assertEqual(Time.getPlaybackRange(timeUnit="sec"), (5 / 24, 2.0))
        self.assertEqual(Time.getAnimationRange(), (cmds.playbackOptions(query=True, animationStartTime=True),
                                                    cmds.playbackOptions(query=True, animationEndTime=True)))
        with self.assertRaises(ValueError):
            Time.setPlaybackRange(10, 5)
        with self.assertRaises(TypeError):
            Time.setCurrent("1")
        with self.assertRaises(TypeError):
            Time()
        with Time.preserved() as original:
            self.assertEqual(original, 24.0)
            Time.setCurrent(30)
        self.assertEqual(Time.getCurrent(), 24.0)


_FAKE_PLUGIN = "mlibSpecFakePlugin"


class SelectedRangeTest(NamespaceCase):

    def test_batch_returns_none(self):
        """バッチでは範囲を選べないので None。不正な単位は ValueError。"""
        if not cmds.about(batch=True):
            self.skipTest("batch only")
        self.assertIsNone(Time.getSelectedRange())
        self.assertIsNone(Time.getSelectedRange(timeUnit="sec"))
        self.assertRaises(ValueError, Time.getSelectedRange, timeUnit="minute")


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
