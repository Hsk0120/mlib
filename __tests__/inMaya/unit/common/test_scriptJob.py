"""``mlib.common.scriptJob`` のテスト。

- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
"""

import sys
import unittest
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Environment, ScriptJob, ScriptJobs


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

    def test_new_options_are_checked_before_batch(self):
        """uiDeleted・allChildren・parent・runOnce・protectedの誤りは、バッチ判定より前に例外にする。"""
        cases = [
            ({"event": "SelectionChanged", "uiDeleted": "window1"}, ValueError),
            ({"event": "SelectionChanged", "allChildren": True}, ValueError),
            ({"event": "SelectionChanged", "parent": ""}, ValueError),
            ({"uiDeleted": ""}, ValueError),
            ({"event": "SelectionChanged", "runOnce": 1}, TypeError),
            ({"event": "SelectionChanged", "protected": "yes"}, TypeError),
            ({"attribute": "persp.tx", "allChildren": 1}, TypeError),
        ]
        for kwargs, error in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                ScriptJob(callback=lambda: None, **kwargs)
        if cmds.about(batch=True):
            with self.assertRaises(RuntimeError):
                ScriptJob(uiDeleted="window1", callback=lambda: None, runOnce=True, protected=True)

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


class _FakeScriptJob:
    """cmds.scriptJob の代役。登録の引数を記録し、ID・exists・killに答える。"""

    def __init__(self):
        self.registered = []
        self.alive = set()
        self.killed = []

    def __call__(self, **kwargs):
        if "exists" in kwargs:
            return kwargs["exists"] in self.alive
        if "kill" in kwargs:
            self.killed.append((kwargs["kill"], kwargs.get("force")))
            self.alive.discard(kwargs["kill"])
            return None
        self.registered.append(kwargs)
        job_id = 1000 + len(self.registered)
        self.alive.add(job_id)
        return job_id


class ScriptJobSimulatedTest(unittest.TestCase):
    """scriptJobの代役で、GUIで渡すフラグの組み立てと、stop・existsを確かめる(イベントの発生はGUIのテストが確かめる)。"""

    def setUp(self):
        import mlib.common.scriptJob as script_job_module

        self.ns = "mlibSpecSJob_" + str(id(self))
        cmds.namespace(add=self.ns)
        self.node = cmds.createNode("transform", name=self.ns + ":node")
        self.fake = _FakeScriptJob()
        for patcher in (mock.patch.object(Environment, "isBatch", return_value=False), mock.patch.object(script_job_module.cmds, "scriptJob", self.fake)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def callback(self):
        """登録に渡すだけの処理。"""

    def test_event_with_default_options(self):
        """eventだけなら、killWithSceneとcompressUndoだけを付けて登録する。"""
        job = ScriptJob(event="SelectionChanged", callback=self.callback)
        self.assertEqual(self.fake.registered, [{"killWithScene": False, "compressUndo": False, "event": ["SelectionChanged", self.callback]}])
        self.assertEqual(job.id, 1001)
        self.assertTrue(job.exists())

    def test_attribute_with_all_options(self):
        """attributeは完全名へ解決し、allChildren・parent・runOnce・protectedを渡す。"""
        ScriptJob(
            attribute=mlib.getPlug(self.node + ".tx"),
            callback=self.callback,
            killWithScene=True,
            compressUndo=True,
            allChildren=True,
            parent="mlibWindow",
            runOnce=True,
            protected=True,
        )
        options = self.fake.registered[-1]
        self.assertEqual(options["attributeChange"], [mlib.getPlug(self.node + ".tx")._full_name(), self.callback])
        self.assertTrue(options["killWithScene"])
        self.assertTrue(options["compressUndo"])
        self.assertTrue(options["allChildren"])
        self.assertEqual(options["parent"], "mlibWindow")
        self.assertTrue(options["runOnce"])
        self.assertTrue(options["protected"])
        self.assertNotIn("event", options)

    def test_attribute_by_name_without_options(self):
        """attributeの名前も受け付け、既定のオプションは付けない。"""
        ScriptJob(attribute=self.node + ".translate", callback=self.callback)
        options = self.fake.registered[-1]
        self.assertEqual(options["attributeChange"][0], mlib.getPlug(self.node + ".translate")._full_name())
        for key in ("allChildren", "parent", "runOnce", "protected"):
            self.assertNotIn(key, options)

    def test_ui_deleted(self):
        """uiDeletedはUIの名前とcallbackの組で渡す。"""
        ScriptJob(uiDeleted="mlibWindow", callback=self.callback)
        self.assertEqual(self.fake.registered[-1]["uiDeleted"], ["mlibWindow", self.callback])

    def test_stop_kills_with_force_once(self):
        """stopはforce付きで1回だけ解除し、以後existsはFalse。2回目は何もしない。"""
        job = ScriptJob(event="SelectionChanged", callback=self.callback, protected=True)
        job.stop()
        self.assertFalse(job.exists())
        job.stop()
        self.assertEqual(self.fake.killed, [(job.id, True)])

    def test_exists_follows_maya(self):
        """Maya側で消えた(runOnceで呼ばれた後など)監視はexistsがFalseで、stopはkillしない。"""
        job = ScriptJob(event="SelectionChanged", callback=self.callback, runOnce=True)
        self.fake.alive.discard(job.id)
        self.assertFalse(job.exists())
        job.stop()
        self.assertEqual(self.fake.killed, [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
