"""mlib.logger のロギングヘルパーを検証するMaya内テスト。

あわせて次も確かめる。

- mlib.decorator・mlib.util・mlib.logger の約束を固定する仕様テスト(担当D)。
"""

import contextlib
import io
import logging
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib import decorator, logger
from mlib import logger as output
from mlib.logger import LOGGER_NAME, MayaHandler, debug, error, getLogger, raiseWithNotify, warning


class LoggerTest(unittest.TestCase):
    """getLogger/debug/warning/error/raiseWithNotify/MayaHandler を検証する。"""

    def test_info_supports_logging_format(self):
        with self.assertLogs(LOGGER_NAME, level="INFO") as captured:
            output.info("count=%s", 3)
        self.assertEqual(captured.records[0].levelno, logging.INFO)
        self.assertEqual(captured.records[0].getMessage(), "count=3")

    def test_print_preserves_stream_separator_and_end(self):
        stream = io.StringIO()
        self.assertIsNone(output.print("腕", 3, sep=":", end="!", file=stream, flush=True))
        self.assertEqual(stream.getvalue(), "腕:3!")
        with contextlib.redirect_stdout(stream):
            output.print("next")
        self.assertEqual(stream.getvalue(), "腕:3!next\n")
        with self.assertRaises(TypeError):
            output.print("invalid", sep=1, file=stream)

    def test_old_warning_command_is_removed(self):
        self.assertFalse((Path(mlib.__file__).parent / "cmds" / "warning.py").exists())
        self.assertFalse(hasattr(mlib.cmds, "warning"))
        self.assertFalse(hasattr(mlib, "warning"))
        self.assertIs(mlib.logger.warning, output.warning)

    def test_old_handler_is_replaced_without_removing_external_handlers(self):
        logger = getLogger()
        old_type = type("MayaHandler", (logging.Handler,), {"__module__": output.__name__})
        old_handler = old_type()
        external = logging.NullHandler()
        logger.addHandler(old_handler)
        logger.addHandler(external)
        try:
            getLogger()
            self.assertNotIn(old_handler, logger.handlers)
            self.assertIn(external, logger.handlers)
            self.assertEqual(sum(isinstance(h, output.MayaHandler) for h in logger.handlers), 1)
        finally:
            logger.removeHandler(external)
            external.close()
            logger.removeHandler(old_handler)

    def test_previous_package_handler_is_replaced_after_layout_migration(self):
        """旧utils配下のハンドラを除去し、外部ハンドラと一つの新ハンドラを保つ。"""
        logger = getLogger()
        previous_type = type("MayaHandler", (logging.Handler,), {"__module__": mlib.__name__ + ".utils.logger"})
        previous = previous_type()
        external = logging.NullHandler()
        logger.addHandler(previous)
        logger.addHandler(external)
        try:
            getLogger()
            self.assertNotIn(previous, logger.handlers)
            self.assertIn(external, logger.handlers)
            self.assertEqual(sum(isinstance(handler, output.MayaHandler) for handler in logger.handlers), 1)
        finally:
            logger.removeHandler(previous)
            previous.close()
            logger.removeHandler(external)
            external.close()

    def test_get_logger_is_idempotent_and_configured(self):
        logger = getLogger()
        self.assertEqual(logger.name, LOGGER_NAME)
        self.assertEqual(logger.level, logging.DEBUG)
        self.assertFalse(logger.propagate)
        handlers = [h for h in logger.handlers if isinstance(h, MayaHandler)]
        self.assertEqual(len(handlers), 1)

        getLogger()
        handlers_after = [h for h in logging.getLogger(LOGGER_NAME).handlers if isinstance(h, MayaHandler)]
        self.assertEqual(len(handlers_after), 1, "getLogger() should not add a duplicate MayaHandler")

    def test_debug_warning_error_emit_expected_log_records(self):
        with self.assertLogs(LOGGER_NAME, level="DEBUG") as captured:
            debug("mlib debug message")
            warning("mlib warning message")
            error("mlib error message")

        messages = [record.getMessage() for record in captured.records]
        self.assertIn("mlib debug message", messages)
        self.assertIn("mlib warning message", messages)
        self.assertIn("mlib error message", messages)
        levels = [record.levelname for record in captured.records]
        self.assertEqual(levels, ["DEBUG", "WARNING", "ERROR"])

    def test_debug_warning_error_support_format_args(self):
        with self.assertLogs(LOGGER_NAME, level="DEBUG") as captured:
            debug("value=%s", 42)
        self.assertEqual(captured.records[0].getMessage(), "value=42")

    def test_maya_handler_emit_does_not_raise_for_each_level(self):
        handler = MayaHandler()
        logger = logging.getLogger("mlibHandlerTest")
        for level, message in ((logging.DEBUG, "mlib handler debug"), (logging.WARNING, "mlib handler warning"), (logging.ERROR, "mlib handler error")):
            record = logger.makeRecord("mlibHandlerTest", level, __file__, 0, message, None, None)
            handler.emit(record)  # Maya へ表示するだけで例外を送出しないことを確認する

    def test_raise_with_notify_raises_specified_exception(self):
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            with self.assertRaises(ValueError) as context:
                raiseWithNotify(ValueError, "boom")
        self.assertEqual(str(context.exception), "boom")

    def test_raise_with_notify_passes_extra_constructor_args(self):
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            with self.assertRaises(OSError) as context:
                raiseWithNotify(OSError, "boom", 2)
        self.assertEqual(context.exception.args, ("boom", 2))

    def test_raise_with_notify_chains_from_exception(self):
        original = RuntimeError("original")
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            with self.assertRaises(ValueError) as context:
                raiseWithNotify(ValueError, "boom", fromException=original)
        self.assertIs(context.exception.__cause__, original)

    def test_raise_with_notify_suppresses_chain_when_from_exception_is_none(self):
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            with self.assertRaises(ValueError) as context:
                raiseWithNotify(ValueError, "boom", fromException=None)
        self.assertIsNone(context.exception.__cause__)
        self.assertTrue(context.exception.__suppress_context__)

    def test_raise_with_notify_preserves_implicit_chain_when_omitted(self):
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            try:
                try:
                    raise KeyError("inner")
                except KeyError:
                    raiseWithNotify(ValueError, "boom")
            except ValueError as outer:
                self.assertIsInstance(outer.__context__, KeyError)


class _SceneCase(unittest.TestCase):
    """一時名前空間とUndo設定・UI単位・選択の保存と復元を共通にする。"""

    @staticmethod
    def opened(spy):
        """mockの呼出しからopenChunkの回数を数える。Python 3.7のため call[1] でキーワードを読む。"""
        return sum(1 for call in spy.call_args_list if call[1].get("openChunk"))

    def setUp(self):
        """状態を保存し、Undoを有効にして一時名前空間を作る。"""
        self.undo_state = cmds.undoInfo(query=True, state=True)
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.angle = cmds.currentUnit(query=True, angle=True)
        self.time = cmds.currentUnit(query=True, time=True)
        self.selection = cmds.ls(selection=True, long=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.ns = "mlibSpecDDeco_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を削除し、保存した状態へ戻す。"""
        cmds.undoInfo(stateWithoutFlush=True)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        cmds.currentUnit(linear=self.linear, angle=self.angle, time=self.time)
        existing = [name for name in self.selection if cmds.objExists(name)]
        if existing:
            cmds.select(existing, replace=True)
        else:
            cmds.select(clear=True)
        cmds.undoInfo(state=self.undo_state)

    def name(self, leaf):
        """一時名前空間内の名前を返す。"""
        return self.ns + ":" + leaf

    def chunk_calls(self):
        """decoratorが呼ぶcmds.undoInfoを記録するmockを返す。"""
        return mock.patch.object(decorator.cmds, "undoInfo", wraps=cmds.undoInfo)


class LoggerSpecTest(unittest.TestCase):
    """loggerの出力先と例外の連鎖を固定する。"""

    def setUp(self):
        """記録用のハンドラを共有ロガーへ追加する。"""
        self.records = []
        handler = logging.Handler()
        handler.emit = self.records.append
        self.handler = handler
        logger.getLogger().addHandler(handler)

    def tearDown(self):
        """記録用のハンドラを外す。"""
        logger.getLogger().removeHandler(self.handler)

    def test_shared_logger_configuration(self):
        """共有ロガーはパッケージ名・DEBUG・伝播なしで、MayaHandlerは1つだけ。"""
        first = logger.getLogger()
        self.assertIs(logger.getLogger(), first)
        self.assertEqual(first.name, "mlib")
        self.assertEqual(first.level, logging.DEBUG)
        self.assertFalse(first.propagate)
        self.assertEqual(sum(isinstance(h, logger.MayaHandler) for h in first.handlers), 1)

    def test_levels_and_format_arguments(self):
        """各関数は対応するレベルで記録し、書式引数を標準loggingと同じく適用する。"""
        logger.debug("d %s", 1)
        logger.info("i %d", 2)
        logger.warning("w %s", "x")
        self.assertIsNone(logger.error("e %s", "y"))
        levels = [(record.levelno, record.getMessage()) for record in self.records]
        self.assertEqual(levels, [(logging.DEBUG, "d 1"), (logging.INFO, "i 2"), (logging.WARNING, "w x"), (logging.ERROR, "e y")])

    def test_print_defaults_and_no_log_record(self):
        """printはNoneの区切り・末尾を標準値として扱い、ログには記録しない。"""
        stream = io.StringIO()
        logger.print("a", "b", sep=None, end=None, file=stream)
        logger.print("c", end="", file=stream)
        self.assertEqual(stream.getvalue(), "a b\nc")
        self.assertEqual(self.records, [])

    def test_raise_with_notify(self):
        """通知してから例外を送出し、from_exceptionで連鎖を指定・抑制できる。"""
        with self.assertRaises(KeyError) as context:
            logger.raiseWithNotify(KeyError, "missing")
        self.assertEqual(context.exception.args, ("missing",))
        self.assertEqual(self.records[-1].levelno, logging.ERROR)
        cause = ValueError("cause")
        with self.assertRaises(RuntimeError) as context:
            logger.raiseWithNotify(RuntimeError, "chained", fromException=cause)
        self.assertIs(context.exception.__cause__, cause)
        try:
            raise ValueError("inner")
        except ValueError:
            with self.assertRaises(RuntimeError) as context:
                logger.raiseWithNotify(RuntimeError, "plain", fromException=None)
        self.assertTrue(context.exception.__suppress_context__)
        self.assertIsNone(context.exception.__cause__)

    def test_handler_survives_formatter_failure(self):
        """MayaHandlerは書式の失敗で例外を送出しない。"""
        handler = logger.MayaHandler()

        class Broken(logging.Formatter):
            """常に失敗する書式。"""

            def format(self, record):
                """例外を送出する。"""
                raise ValueError("format failed")

        handler.setFormatter(Broken())
        record = logging.LogRecord("mlib", logging.INFO, __file__, 1, "message", (), None)
        handler.emit(record)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
