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


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
