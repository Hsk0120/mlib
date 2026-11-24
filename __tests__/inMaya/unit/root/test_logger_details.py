"""``mlib.logger`` のテスト。

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


class DetailedNotificationTest(unittest.TestCase):
    """詳細はScript Editor、本文はViewportへ表示する。"""

    def test_formatter_and_exception_are_only_in_script_editor(self):
        try:
            raise ValueError("exception detail")
        except ValueError:
            record = logging.LogRecord("mlib", logging.ERROR, __file__, 0, "operation %s <failed>", ("A",), sys.exc_info())
        handler = logger.MayaHandler()
        handler.setFormatter(logging.Formatter("CUSTOM %(levelname)s %(message)s"))
        display = mock.Mock()
        with mock.patch.object(om2, "MGlobal", SimpleNamespace(displayError=display)), mock.patch.object(cmds, "inViewMessage") as viewport:
            handler.emit(record)
        details = display.call_args[0][0]
        self.assertIn("CUSTOM ERROR operation A <failed>", details)
        self.assertIn("Traceback", details)
        self.assertIn("ValueError: exception detail", details)
        summary = viewport.call_args[1]["amg"]
        self.assertIn("operation A &lt;failed&gt;", summary)
        self.assertNotIn("exception detail", summary)
        self.assertNotIn("CUSTOM", summary)

    def test_stack_info_and_info_level_do_not_create_viewport_notification(self):
        record = logging.LogRecord("mlib", logging.INFO, __file__, 0, "value=%s", (3,), None, sinfo="stack detail")
        display = mock.Mock()
        with mock.patch.object(om2, "MGlobal", SimpleNamespace(displayInfo=display)), mock.patch.object(cmds, "inViewMessage") as viewport:
            logger.MayaHandler().emit(record)
        self.assertEqual(display.call_args[0][0], "value=3\nstack detail")
        viewport.assert_not_called()

    def test_missing_formatter_field_falls_back_to_exception_details(self):
        try:
            raise ValueError("original detail")
        except ValueError:
            record = logging.LogRecord("mlib", logging.WARNING, __file__, 0, "operation failed", (), sys.exc_info())
        handler = logger.MayaHandler()
        handler.setFormatter(logging.Formatter("%(tool)s %(message)s"))
        display = mock.Mock()
        with mock.patch.object(om2, "MGlobal", SimpleNamespace(displayWarning=display)), mock.patch.object(cmds, "inViewMessage") as viewport:
            handler.emit(record)
        details = display.call_args[0][0]
        self.assertIn("operation failed", details)
        self.assertIn("ValueError: original detail", details)
        self.assertIn("ログ書式の適用に失敗", details)
        self.assertNotIn("original detail", viewport.call_args[1]["amg"])


class HandlerFallbackTest(unittest.TestCase):
    """Mayaの表示が使えないときも、ハンドラーが例外を出さずに戻ることを確かめる。"""

    def record(self, level):
        """指定のレベルのレコードを作る。"""
        return logging.getLogger("mlibHandlerFallback").makeRecord("mlibHandlerFallback", level, __file__, 0, "fallback message", None, None)

    def test_uninitialized_maya_shows_nothing(self):
        """maya.cmdsにaboutが無い(mayapyの初期化前)なら、何も表示しない。"""
        import maya

        bare = SimpleNamespace()
        display = mock.Mock()
        with mock.patch.object(maya, "cmds", bare), mock.patch.dict(sys.modules, {"maya.cmds": bare}), mock.patch.object(
            om2, "MGlobal", SimpleNamespace(displayWarning=display)
        ):
            logger.MayaHandler().emit(self.record(logging.WARNING))
        display.assert_not_called()

    def test_missing_open_maya_shows_nothing(self):
        """maya.api.OpenMayaをimportできなければ、何も表示しない。"""
        with mock.patch.dict(sys.modules, {"maya.api.OpenMaya": None}), mock.patch.object(cmds, "inViewMessage") as viewport:
            logger.MayaHandler().emit(self.record(logging.ERROR))
        viewport.assert_not_called()

    def test_display_errors_are_ignored(self):
        """Script Editorとビューポートの表示がRuntimeErrorでも、例外を出さない。"""
        display = mock.Mock(side_effect=RuntimeError("display"))
        with mock.patch.object(om2, "MGlobal", SimpleNamespace(displayWarning=display)), mock.patch.object(
            cmds, "inViewMessage", side_effect=RuntimeError("viewport")
        ) as viewport:
            logger.MayaHandler().emit(self.record(logging.WARNING))
        display.assert_called_once()
        viewport.assert_called_once()

    def test_exception_formatter_needs_maya_utils(self):
        """maya.utilsが無いか、差し替え口が無ければ、設定せずFalseを返す。"""
        import maya.utils as maya_utils

        with mock.patch.dict(sys.modules, {"maya.utils": None}):
            self.assertFalse(logger._install_exception_formatter())
        with mock.patch.object(maya_utils, "formatGuiException", None, create=True):
            self.assertFalse(logger._install_exception_formatter())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
