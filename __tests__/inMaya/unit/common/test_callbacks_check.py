"""``Callbacks.addSceneCheckCallback``・``addTimeChangeCallback`` のテスト。"""

import os
import shutil
import sys
import tempfile
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Callbacks


class SceneCheckCallbackTest(unittest.TestCase):
    """保存などを止められるシーンのコールバック。"""

    def setUp(self):
        cmds.file(new=True, force=True)
        self.tmp_dir = tempfile.mkdtemp()
        cmds.file(rename=os.path.join(self.tmp_dir, "check.ma").replace("\\", "/"))

    def tearDown(self):
        cmds.file(new=True, force=True)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_false_cancels_save(self):
        """Falseを返すと保存を止め、Trueなら保存する。解除後は呼ばれない。"""
        calls = []
        answer = [False]

        def check():
            calls.append(True)
            return answer[0]

        with Callbacks() as group:
            group.addSceneCheckCallback("beforeSaveCheck", check)
            with self.assertRaises(RuntimeError):
                cmds.file(save=True, type="mayaAscii")
            answer[0] = True
            cmds.file(save=True, type="mayaAscii")
        self.assertEqual(len(calls), 2)
        cmds.file(save=True, type="mayaAscii")
        self.assertEqual(len(calls), 2)

    def test_exception_continues(self):
        """関数の例外は警告にして操作を続ける。"""

        def broken():
            raise ValueError("broken")

        with Callbacks() as group:
            group.addSceneCheckCallback("beforeSaveCheck", broken)
            cmds.file(save=True, type="mayaAscii")
        self.assertTrue(os.path.exists(cmds.file(query=True, sceneName=True)))

    def test_file_events_register(self):
        """ファイルを伴うCheck系のイベントも登録・解除できる。"""
        with Callbacks() as group:
            for event in (
                "beforeOpenCheck",
                "beforeImportCheck",
                "beforeExportCheck",
                "beforeCreateReferenceCheck",
                "beforeLoadReferenceCheck",
                "beforeNewCheck",
            ):
                with self.subTest(event=event):
                    self.assertIsInstance(group.addSceneCheckCallback(event, lambda: True), int)

    def test_errors(self):
        """知らないイベント・型の誤りは登録前に拒否する。"""
        group = Callbacks()
        with self.assertRaises(ValueError):
            group.addSceneCheckCallback("beforeSave", lambda: True)
        with self.assertRaises(TypeError):
            group.addSceneCheckCallback(1, lambda: True)
        with self.assertRaises(TypeError):
            group.addSceneCheckCallback("beforeSaveCheck", "check")
        group.remove()


class TimeChangeCallbackTest(unittest.TestCase):
    """時刻の変化のコールバック。"""

    def setUp(self):
        self.unit = cmds.currentUnit(query=True, time=True)
        self.time = cmds.currentTime(query=True)

    def tearDown(self):
        cmds.currentUnit(time=self.unit)
        cmds.currentTime(self.time)

    def test_time_is_passed(self):
        """変わった後の時刻を、UIの時間単位のフレームか秒で渡す。"""
        cmds.currentUnit(time="ntsc")
        frames, seconds = [], []
        with Callbacks() as group:
            group.addTimeChangeCallback(frames.append)
            group.addTimeChangeCallback(seconds.append, timeUnit="sec")
            cmds.currentTime(15)
        self.assertEqual(frames, [15.0])
        self.assertAlmostEqual(seconds[0], 0.5)
        cmds.currentTime(20)
        self.assertEqual(frames, [15.0])

    def test_errors(self):
        """呼び出せない関数・知らない単位を拒否する。"""
        group = Callbacks()
        with self.assertRaises(TypeError):
            group.addTimeChangeCallback(None)
        with self.assertRaises(ValueError):
            group.addTimeChangeCallback(print, timeUnit="deg")
        group.remove()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
