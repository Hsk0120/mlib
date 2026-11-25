"""``mlib.json.snapshot`` の ``Snapshot`` の、ファイルの読み書きの失敗と、適用できない問題のテスト。

- 無いファイルの ``load``・無いフォルダーへの ``save`` は OSError(一時ファイルを残さない)。
- ``apply`` を上書きしない種類で、検査が問題を見つけたら ValueError で何も変えない。
"""

import shutil
import sys
import unittest
import uuid
from pathlib import Path

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.json import NodeRef, PoseSnapshot, Snapshot

#: 一時ファイルを作る場所(``__tests__/_output/temp``。Git の対象外)。
_TEMP = Path(__file__).resolve().parents[3] / "_output" / "temp"


class _ValueSnapshot(Snapshot):
    """テスト用: translateX を書く種類。apply は基底のまま使う。"""

    FORMAT = "mlib.test.value"
    VERSION = 1

    @classmethod
    def capture(cls, nodes):
        return cls({"items": [{"node": NodeRef.capture(node)._to_data(), "value": cmds.getAttr(node + ".tx")} for node in nodes]})

    def _validate(self, mapping, report, options):  # 基底の契約で受ける引数。
        for item in self._data["items"]:
            if item["value"] < 0:
                report._add_error("負の値は書けません")

    def _apply(self, mapping, report, options, fast):  # 基底の契約で受ける引数。
        for item in self._data["items"]:
            node = NodeRef._from_data(item["node"]).resolve(mapping)
            cmds.setAttr(node.getName(full=True) + ".tx", item["value"])


class SnapshotFileErrorTest(NamespaceCase):
    """ファイルの読み書きの失敗。"""

    PREFIX = "mlibJsonSnapErr_"

    def setUp(self):
        super().setUp()
        self.node = cmds.createNode("transform", name=self.name("node"))
        self.folder = _TEMP / ("snapshotErrors_" + uuid.uuid4().hex[:8])
        self.folder.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(str(self.folder), ignore_errors=True)
        super().tearDown()

    def test_load_missing_file_raises_os_error(self):
        """無いファイルはOSError。"""
        with self.assertRaises(OSError):
            PoseSnapshot.load(self.folder / "missing.json")

    def test_save_into_missing_folder_raises_os_error(self):
        """フォルダーは作らないので、無いフォルダーへの書き出しはOSErrorで、何も残さない。"""
        snap = PoseSnapshot.capture([self.node])
        with self.assertRaises(OSError):
            snap.save(self.folder / "missing" / "pose.json")
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_save_over_folder_raises_os_error_and_removes_temporary(self):
        """書き出し先がフォルダーならOSErrorで、一時ファイルを残さず、フォルダーも変えない。"""
        target = self.folder / "target"
        target.mkdir()
        snap = PoseSnapshot.capture([self.node])
        with self.assertRaises(OSError):
            snap.save(target)
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()), ["target"])
        self.assertTrue(target.is_dir())


class SnapshotApplyErrorTest(NamespaceCase):
    """基底のapplyの、適用できない問題。"""

    PREFIX = "mlibJsonSnapApply_"

    def setUp(self):
        super().setUp()
        self.node = cmds.createNode("transform", name=self.name("node"))

    def test_errors_raise_value_error_without_change(self):
        """検査が問題を見つけたらValueErrorで、シーンも変えない。問題が無ければ1回のUndoで戻せる。"""
        cmds.setAttr(self.node + ".tx", -2.0)
        bad = _ValueSnapshot.capture([self.node])
        cmds.setAttr(self.node + ".tx", 1.0)
        with self.assertRaises(ValueError):
            bad.apply()
        self.assertEqual(cmds.getAttr(self.node + ".tx"), 1.0)
        cmds.setAttr(self.node + ".tx", 3.0)
        good = _ValueSnapshot.capture([self.node])
        cmds.setAttr(self.node + ".tx", 1.0)
        self.flushUndo()
        report = good.apply()
        self.assertEqual((report.missing, report.skipped), ([], []))
        self.assertEqual(cmds.getAttr(self.node + ".tx"), 3.0)
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.node + ".tx"), 1.0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
