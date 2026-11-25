"""``mlib.decorator`` のテスト。

- 通知の詳細とスキン保護の失敗診断をMaya内で検証する。
"""

import logging
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib import logger
from mlib.decorator import preservedSkinShape
from mlib.nodes import joint as joint_module


class SkinProtectionDiagnosticsTest(unittest.TestCase):
    """失敗した段階を通知し、従来の継続・復元・例外を維持する。"""

    def _exercise(self, stage, body_error=None):
        """指定段階だけ失敗させ、命令順と警告を収集する。

        Args:
            stage (str): query/switch/recache/restoreのいずれか。
            body_error (Exception | None): with本体で送出する例外。
        Returns:
            tuple: skins・命令呼出・警告・本体通過の記録。
        """
        skins = [SimpleNamespace(_full_name=lambda: "skinA"), SimpleNamespace(_full_name=lambda: "skinB")]
        collection = SimpleNamespace(getSkinClusters=lambda: skins)
        entered = []
        calls = []

        def command(name, **kwargs):
            """照会・更新の段階を識別して障害を注入する。"""
            if kwargs.get("query"):
                actual = "query"
            elif kwargs.get("recacheBindMatrices"):
                actual = "recache"
            elif kwargs.get("moveJointsMode") is True:
                actual = "switch"
            else:
                actual = "restore"
            calls.append((name, actual))
            if name == "skinA" and actual == stage:
                raise RuntimeError("injected failure")
            return False if actual == "query" else None

        with mock.patch.object(joint_module, "Joints", return_value=collection), mock.patch.object(cmds, "skinCluster", side_effect=command), mock.patch.object(
            logger, "warning"
        ) as warning:
            if body_error is None:
                with preservedSkinShape(["joint"]) as result:
                    self.assertIs(result, skins)
                    entered.append(True)
            else:
                with self.assertRaises(type(body_error)) as raised:
                    with preservedSkinShape(["joint"]):
                        entered.append(True)
                        raise body_error
                self.assertIs(raised.exception, body_error)
            messages = [call[0][0] for call in warning.call_args_list]
        return skins, calls, messages, entered

    def test_query_failure_is_reported_without_stopping_other_skin(self):
        _, calls, messages, entered = self._exercise("query")
        self.assertEqual(entered, [True])
        self.assertNotIn(("skinA", "switch"), calls)
        self.assertIn(("skinB", "switch"), calls)
        self.assertIn(("skinA", "recache"), calls)
        self.assertNotIn(("skinA", "restore"), calls)
        self.assertEqual(len(messages), 1)
        self.assertIn("moveJointsModeを取得できませんでした", messages[0])

    def test_switch_failure_still_restores_known_previous_mode(self):
        _, calls, messages, _ = self._exercise("switch")
        self.assertIn(("skinA", "restore"), calls)
        self.assertIn(("skinB", "restore"), calls)
        self.assertEqual(len(messages), 1)
        self.assertIn("moveJointsModeを有効にできませんでした", messages[0])

    def test_recache_failure_does_not_skip_mode_restore(self):
        _, calls, messages, _ = self._exercise("recache")
        self.assertIn(("skinA", "restore"), calls)
        self.assertIn(("skinB", "recache"), calls)
        self.assertIn("バインドマトリクスを再キャッシュできませんでした", messages[0])

    def test_restore_failure_keeps_original_body_exception_and_other_cleanup(self):
        _, calls, messages, entered = self._exercise("restore", ValueError("body"))
        self.assertEqual(entered, [True])
        self.assertIn(("skinB", "restore"), calls)
        self.assertEqual(len(messages), 1)
        self.assertIn("moveJointsModeを元に戻せませんでした", messages[0])

    def test_bad_formatter_does_not_interrupt_cleanup_or_replace_body_exception(self):
        skins = [SimpleNamespace(_full_name=lambda: "skinA"), SimpleNamespace(_full_name=lambda: "skinB")]
        collection = SimpleNamespace(getSkinClusters=lambda: skins)
        handler = next(item for item in logger.getLogger().handlers if isinstance(item, logger.MayaHandler))
        formatter = handler.formatter
        handler.setFormatter(logging.Formatter("%(tool)s %(message)s"))
        restores = []

        def command(name, **kwargs):
            """片方の復元だけ失敗し、残りの復元が実行されるか記録する。"""
            if kwargs.get("query"):
                return False
            if kwargs.get("moveJointsMode") is False:
                restores.append(name)
                if name == "skinA":
                    raise RuntimeError("restore failure")
            return None

        original = ValueError("original body")
        try:
            with mock.patch.object(joint_module, "Joints", return_value=collection), mock.patch.object(
                cmds, "skinCluster", side_effect=command
            ), mock.patch.object(om2, "MGlobal", SimpleNamespace(displayWarning=mock.Mock())), mock.patch.object(cmds, "inViewMessage"):
                with self.assertRaises(ValueError) as raised:
                    with preservedSkinShape(["joint"]):
                        raise original
            self.assertIs(raised.exception, original)
            self.assertEqual(restores, ["skinA", "skinB"])
        finally:
            handler.setFormatter(formatter)


class SkinProtectionModeRestoreTest(unittest.TestCase):
    """実際のskinClusterで、ブロックの前のmoveJointsModeへ戻す。"""

    def setUp(self):
        cmds.select(clear=True)
        self.joint = cmds.ls(cmds.joint(name="mlibSkinModeJoint#"), long=True)[0]
        cmds.select(clear=True)
        self.mesh = cmds.ls(cmds.polyCube(name="mlibSkinModeMesh#", constructionHistory=False)[0], long=True)[0]
        self.skin = mlib.getNode(cmds.skinCluster([self.joint], self.mesh, toSelectedBones=True)[0])

    def tearDown(self):
        cmds.delete([self.mesh, self.joint])

    def follows_joint(self):
        """ジョイントを動かして、メッシュが付いてくるか(moveJointsModeが無効か)を返す。動かした後は元へ戻す。"""
        before = cmds.pointPosition(self.mesh + ".vtx[0]")
        cmds.setAttr(self.joint + ".ty", cmds.getAttr(self.joint + ".ty") + 1.0)
        moved = cmds.pointPosition(self.mesh + ".vtx[0]") != before
        cmds.setAttr(self.joint + ".ty", cmds.getAttr(self.joint + ".ty") - 1.0)
        return moved

    def test_mode_off_before_is_off_after(self):
        """元が無効なら、ブロックの中だけ有効で、終わると無効へ戻る。"""
        self.assertTrue(self.follows_joint())
        with preservedSkinShape([self.joint]):
            self.assertFalse(self.follows_joint())
        self.assertTrue(self.follows_joint())

    def test_mode_on_before_stays_on_after(self):
        """setMoveJointsMode(True)で有効にしていれば、ブロックの後も有効のまま残る(照会がNoneでも覚えている)。"""
        self.skin.setMoveJointsMode(True)
        try:
            with preservedSkinShape([self.joint]):
                pass
            self.assertFalse(self.follows_joint())
        finally:
            self.skin.setMoveJointsMode(False)
        self.assertTrue(self.follows_joint())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
