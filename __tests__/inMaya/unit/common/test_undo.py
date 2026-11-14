"""``mlib.common.undo`` のテスト。

- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
"""

import sys
import unittest
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Deferred, undo


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class UndoAndDeferredSpecTest(unittest.TestCase):
    """undo.isEnabledとDeferred.callの委譲を固定する。"""

    def setUp(self):
        """開始時のUndo設定を保存する。"""
        self.state = cmds.undoInfo(query=True, state=True)

    def tearDown(self):
        """Undo設定を戻す。"""
        cmds.undoInfo(state=self.state)

    def test_is_enabled_follows_undo_state_without_changing_it(self):
        """isEnabledはundoInfoのstateをboolで返し、設定を変えない。"""
        cmds.undoInfo(stateWithoutFlush=True)
        self.assertIs(undo.isEnabled(), True)
        cmds.undoInfo(state=False)
        self.assertIs(undo.isEnabled(), False)
        self.assertFalse(cmds.undoInfo(query=True, state=True))

    def test_deferred_call_passes_arguments_to_execute_deferred(self):
        """callはcallbackと引数をそのままexecuteDeferredへ渡し、戻り値はNone。"""
        import maya.utils as utils

        def callback(*args, **kwargs):
            """何もしない。"""

        with mock.patch.object(utils, "executeDeferred") as deferred:
            self.assertIsNone(Deferred.call(callback, 1, key="value"))
        deferred.assert_called_once_with(callback, 1, key="value")

    def test_deferred_call_rejects_non_callable(self):
        """コード文字列などcallableでない値はTypeError。"""
        import maya.utils as utils

        with mock.patch.object(utils, "executeDeferred") as deferred:
            for value in ("print(1)", None, 5):
                with self.assertRaises(TypeError):
                    Deferred.call(value)
        deferred.assert_not_called()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
