"""``mlib.common.scriptJob`` のテスト。

- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import ScriptJob, ScriptJobs


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class ScriptJobSpecTest(unittest.TestCase):
    """ScriptJobの入力検証と、バッチ時に登録しないことを固定する。"""

    def test_requires_exactly_one_of_event_and_attribute(self):
        """eventとattributeは片方だけ。両方・どちらもなしはValueError。"""
        with self.assertRaises(ValueError):
            ScriptJob(callback=lambda: None)
        with self.assertRaises(ValueError):
            ScriptJob(event="SelectionChanged", attribute="persp.tx", callback=lambda: None)

    def test_rejects_non_callable(self):
        """callbackが呼び出せない場合はTypeError(バッチ判定より前)。"""
        with self.assertRaises(TypeError):
            ScriptJob(event="SelectionChanged", callback="print(1)")

    def test_batch_session_is_rejected(self):
        """バッチ実行中はRuntimeErrorで、scriptJobを登録しない。"""
        if not cmds.about(batch=True):
            self.skipTest("GUIではscriptJobを登録できるため対象外")
        before = len(cmds.scriptJob(listJobs=True) or [])
        with self.assertRaises(RuntimeError):
            ScriptJob(event="SelectionChanged", callback=lambda: None)
        self.assertEqual(len(cmds.scriptJob(listJobs=True) or []), before)

    def test_script_jobs_group_empty_and_failed_add(self):
        """空のグループはexists()がFalse、登録失敗のキーは保持しない。"""
        group = ScriptJobs()
        self.assertFalse(group.exists())
        self.assertIsNone(group.stop())
        if cmds.about(batch=True):
            with self.assertRaises(RuntimeError):
                group.add("key", event="SelectionChanged", callback=lambda: None)
            self.assertFalse(group.exists())

    def test_script_jobs_temporary_cannot_nest(self):
        """同じインスタンスでtemporaryを入れ子にするとRuntimeError。外側は正常に終わる。"""
        group = ScriptJobs()
        with group.temporary() as active:
            self.assertIs(active, group)
            with self.assertRaises(RuntimeError):
                with group.temporary():
                    pass
        with group.temporary():
            pass


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
