"""``mlib.common.sceneTime`` のテスト。

- 入口(作成関数・objExists・Time・キーの追加/削除・Shapeの親変更・setPreferredAngle)の約束を固定する。
- common の照会・コールバックの契約を固定する。
"""

import sys
import unittest
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.common import Environment, Time
from mlib.common import sceneTime as scene_time_module


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、UI単位・選択の補助。"""

    PREFIX = "mlibSpecEntry_"

    def setUp(self):
        """UI単位・時刻を保存して名前空間を用意する。"""
        super().setUp()
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.time = cmds.currentTime(query=True)
        self.time_unit = cmds.currentUnit(query=True, time=True)
        self.range = (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))
        self.animation_range = (cmds.playbackOptions(query=True, animationStartTime=True), cmds.playbackOptions(query=True, animationEndTime=True))

    def tearDown(self):
        """UI単位・時刻・再生範囲・アニメーション範囲を戻す。"""
        cmds.currentUnit(linear=self.linear, time=self.time_unit)
        cmds.playbackOptions(animationStartTime=self.animation_range[0], animationEndTime=self.animation_range[1])
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
        self.assertIsNone(Time.setCurrent(12))
        self.assertEqual(Time.getCurrent(), 12.0)
        self.assertEqual(cmds.currentTime(query=True), 12.0)
        self.assertAlmostEqual(Time.getCurrent(timeUnit="sec"), 0.5)
        Time.setCurrent(1.0, timeUnit="sec")
        self.assertEqual(Time.getCurrent(), 24.0)
        self.assertIsNone(Time.setRange(5, 48))
        self.assertEqual(Time.getRange(), (5.0, 48.0))
        self.assertEqual(Time.getRange(animation=False), (5.0, 48.0))
        self.assertEqual(Time.getRange(timeUnit="sec"), (5 / 24, 2.0))
        self.assertEqual((cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True)), (5.0, 48.0))
        self.assertEqual(
            Time.getRange(animation=True), (cmds.playbackOptions(query=True, animationStartTime=True), cmds.playbackOptions(query=True, animationEndTime=True))
        )
        self.assertIsNone(Time.setRange(1, 60, animation=True))
        self.assertEqual(Time.getRange(animation=True), (1.0, 60.0))
        self.assertEqual(Time.getRange(animation=True, timeUnit="sec"), (1 / 24, 2.5))
        self.assertEqual((cmds.playbackOptions(query=True, animationStartTime=True), cmds.playbackOptions(query=True, animationEndTime=True)), (1.0, 60.0))
        self.assertEqual(Time.getRange(), (5.0, 48.0))
        with self.assertRaises(ValueError):
            Time.setRange(10, 5)
        with self.assertRaises(ValueError):
            Time.setRange(10, 5, animation=True)
        self.assertEqual(Time.getRange(animation=True), (1.0, 60.0))
        with self.assertRaises(TypeError):
            Time.setCurrent("1")
        with self.assertRaises(TypeError):
            Time()
        with Time.preserved() as original:
            self.assertEqual(original, 24.0)
            Time.setCurrent(30)
        self.assertEqual(Time.getCurrent(), 24.0)

    def test_range_flags_are_checked(self):
        """animation・selected は bool でなければ TypeError、両方 True も TypeError。範囲は変えない。"""
        before = (Time.getRange(), Time.getRange(animation=True))
        for kwargs in ({"animation": 1}, {"animation": None}, {"selected": 1}, {"selected": "yes"}, {"animation": True, "selected": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                Time.getRange(**kwargs)
        for value in (1, None, "yes"):
            with self.subTest(animation=value), self.assertRaises(TypeError):
                Time.setRange(1, 10, animation=value)
        with self.assertRaises(TypeError):
            Time.setRange(1, 10, True)
        with self.assertRaises(TypeError):
            Time.getRange(True)
        self.assertEqual((Time.getRange(), Time.getRange(animation=True)), before)

    def test_set_current_update_flag(self):
        """update=Falseでも時刻は変わり、updateがbool以外ならTypeErrorで時刻を変えない。"""
        cmds.currentUnit(time="film")
        Time.setCurrent(7, update=False)
        self.assertEqual(cmds.currentTime(query=True), 7.0)
        for value in (1, None, "no"):
            with self.subTest(update=value), self.assertRaises(TypeError):
                Time.setCurrent(9, update=value)
        self.assertEqual(cmds.currentTime(query=True), 7.0)
        for value in (float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Time.setCurrent(value)
        with self.assertRaises(ValueError):
            Time.setCurrent(1, timeUnit="minute")


def _undo_if_recorded():
    """Undoの記録があれば1回戻す(playbackOptionsはMayaの版によってUndoに記録されない)。

    Returns:
        bool: 記録があって戻した場合はTrue。
    """
    if cmds.undoInfo(query=True, undoQueueEmpty=True):
        return False
    cmds.undo()
    return True


class TimeUndoParityTest(_SpecCase):
    """setCurrent・setRange のUndoの扱いは、同じ値を渡した cmds.currentTime・cmds.playbackOptions と同じになる。"""

    def _range(self, animation):
        flags = ("animationStartTime", "animationEndTime") if animation else ("minTime", "maxTime")
        return tuple(cmds.playbackOptions(query=True, **{flag: True}) for flag in flags)

    def test_set_current_undo_matches_cmds(self):
        cmds.currentUnit(time="film")
        results = []
        for setter in (lambda: Time.setCurrent(7), lambda: cmds.currentTime(7)):
            cmds.currentTime(3)
            cmds.flushUndo()
            setter()
            after = cmds.currentTime(query=True)
            results.append((after, _undo_if_recorded(), cmds.currentTime(query=True)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 7.0)

    def test_set_range_undo_matches_cmds(self):
        cmds.currentUnit(time="film")
        for animation in (False, True):
            flags = ("animationStartTime", "animationEndTime") if animation else ("minTime", "maxTime")
            results = []
            for use_mlib in (True, False):
                cmds.playbackOptions(animationStartTime=1, animationEndTime=100, minTime=1, maxTime=100)
                cmds.flushUndo()
                if use_mlib:
                    Time.setRange(5, 50, animation=animation)
                else:
                    cmds.playbackOptions(**{flags[0]: 5, flags[1]: 50})
                after = self._range(animation)
                results.append((after, _undo_if_recorded(), self._range(animation)))
            with self.subTest(animation=animation):
                self.assertEqual(results[0], results[1])
                self.assertEqual(results[0][0], (5.0, 50.0))


class SimulatedSelectedRangeTest(_SpecCase):
    """タイムスライダーの代役で、selected=Trueの範囲の読み方(終わりは1フレーム引く)を確かめる。"""

    def setUp(self):
        super().setUp()
        self.slider = {"name": "mlibFakeSlider", "exists": True, "visible": True, "range": [10.0, 21.0]}

        def mel_eval(command):
            if isinstance(self.slider["name"], Exception):
                raise self.slider["name"]
            return self.slider["name"]

        def time_control(name, **kwargs):
            if kwargs.get("exists"):
                return self.slider["exists"]
            if kwargs.get("rangeVisible"):
                return self.slider["visible"]
            if kwargs.get("rangeArray"):
                return list(self.slider["range"])
            raise AssertionError(kwargs)

        for patcher in (
            mock.patch.object(Environment, "isBatch", return_value=False),
            mock.patch.object(scene_time_module.mel, "eval", mel_eval),
            mock.patch.object(cmds, "timeControl", time_control),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_selected_range_in_frames_and_seconds(self):
        """rangeArrayの終わりから1フレーム引いた範囲を、フレームと秒で返す。"""
        cmds.currentUnit(time="film")
        self.assertEqual(Time.getRange(selected=True), (10.0, 20.0))
        start, end = Time.getRange(selected=True, timeUnit="sec")
        self.assertAlmostEqual(start, 10.0 / 24.0)
        self.assertAlmostEqual(end, 20.0 / 24.0)
        self.slider["range"] = [5.0, 6.0]
        self.assertEqual(Time.getRange(selected=True), (5.0, 5.0))

    def test_selected_range_is_none_without_slider_or_selection(self):
        """範囲を選んでいない・スライダーが無い・名前が取れない場合はNone。"""
        self.slider["visible"] = False
        self.assertIsNone(Time.getRange(selected=True))
        self.slider["visible"] = True
        self.slider["exists"] = False
        self.assertIsNone(Time.getRange(selected=True))
        self.slider["exists"] = True
        for name in ("", RuntimeError("no variable")):
            with self.subTest(name=name):
                self.slider["name"] = name
                self.assertIsNone(Time.getRange(selected=True))


_FAKE_PLUGIN = "mlibSpecFakePlugin"


class SelectedRangeTest(NamespaceCase):
    def test_batch_returns_none(self):
        """バッチでは範囲を選べないので None。不正な単位は ValueError。"""
        if not cmds.about(batch=True):
            self.skipTest("batch only")
        self.assertIsNone(Time.getRange(selected=True))
        self.assertIsNone(Time.getRange(selected=True, timeUnit="sec"))
        self.assertRaises(ValueError, Time.getRange, selected=True, timeUnit="minute")


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
