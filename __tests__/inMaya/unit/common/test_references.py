"""``mlib.common.references`` のテスト。

- mlib.nodes.reference の Reference と mlib.common.references.listReferences を検証するMaya内テスト。
- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
"""

import contextlib
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Namespace, references
from mlib.common.references import createReference, listReferences
from mlib.nodes.reference import Reference


class CreateReferenceTest(unittest.TestCase):
    """mlib.common.references.createReference による参照の新規作成を検証する。"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.ref_path = os.path.join(self.tmp_dir, "mlibCreateReferenceTarget.ma")
        helper = cmds.createNode("transform", name="mlibCreateReferenceHelper")
        cmds.select(helper, replace=True)
        cmds.file(self.ref_path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(helper)
        cmds.select(clear=True)
        self.created = None

    def tearDown(self):
        if self.created is not None and cmds.objExists(self.created.getName()):
            cmds.file(removeReference=True, referenceNode=self.created.getName())
        if os.path.exists(self.ref_path):
            os.remove(self.ref_path)
        if os.path.isdir(self.tmp_dir):
            os.rmdir(self.tmp_dir)

    def test_creates_reference_under_requested_namespace(self):
        self.created = createReference(self.ref_path, namespace="mlibCreateReferenceNs")
        self.assertIsInstance(self.created, Reference)
        self.assertTrue(self.created.isLoaded())
        self.assertTrue(cmds.objExists("mlibCreateReferenceNs:mlibCreateReferenceHelper"))
        self.assertEqual(self.created.getAssociatedNamespace(), Namespace("mlibCreateReferenceNs"))

    def test_created_reference_is_included_in_list_references(self):
        self.created = createReference(self.ref_path, namespace="mlibCreateReferenceNs2")
        self.assertIn(self.created.getName(), [reference.getName() for reference in listReferences()])

    def test_invalid_path_raises_value_error(self):
        with self.assertRaises(ValueError):
            createReference("")

    def test_reference_is_made_without_prompt(self):
        """確認ダイアログで止めないよう、cmds.file へ reference=True・prompt=False を渡す。"""
        previous = cmds.file(query=True, prompt=True)
        self.addCleanup(cmds.file, prompt=previous)
        with mock.patch.object(references.cmds, "file", wraps=cmds.file) as spy:
            self.created = createReference(self.ref_path, namespace="mlibCreateReferenceNoPrompt")
        calls = [call for call in spy.call_args_list if call[1].get("reference")]
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][1]["prompt"], False)

    def test_prompt_setting_is_restored(self):
        """createReference の後も、Mayaの file -prompt の設定は呼ぶ前の値のまま残る(True・Falseの両方)。"""
        previous = cmds.file(query=True, prompt=True)
        self.addCleanup(cmds.file, prompt=previous)
        for index, state in enumerate((True, False)):
            with self.subTest(state=state):
                cmds.file(prompt=state)
                created = createReference(self.ref_path, namespace=f"mlibCreateReferencePrompt{index}")
                try:
                    self.assertIs(bool(cmds.file(query=True, prompt=True)), state)
                finally:
                    cmds.file(removeReference=True, referenceNode=created.getName())


#: 一時ファイルを作る場所(``__tests__/_output/temp``。Git の対象外)。
_TEMP_ROOT = Path(__file__).resolve().parents[3] / "_output" / "temp"


class CreateReferenceErrorsTest(unittest.TestCase):
    """createReference の例外とUndoの扱い。一時ファイルは ``__tests__/_output/temp`` の下に作る。"""

    def setUp(self):
        self.folder = _TEMP_ROOT / ("references_" + uuid.uuid4().hex[:12])
        self.folder.mkdir(parents=True)
        self.path = self.folder / "target.ma"
        helper = cmds.createNode("transform", name="mlibCreateReferenceErrorsHelper")
        cmds.select(helper, replace=True)
        cmds.file(str(self.path), exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(helper)
        cmds.select(clear=True)
        self.before = set(cmds.ls(type="reference") or [])

    def tearDown(self):
        for name in sorted(set(cmds.ls(type="reference") or []) - self.before):
            with contextlib.suppress(RuntimeError):
                cmds.file(removeReference=True, referenceNode=name)
        shutil.rmtree(str(self.folder), ignore_errors=True)

    def test_missing_file_raises_os_error_before_maya(self):
        """ファイルが無ければ、cmds.file を呼ぶ前に OSError(FileNotFoundError)にし、何も作らない。"""
        with mock.patch.object(cmds, "file", side_effect=AssertionError("file")):
            with self.assertRaises(OSError):
                createReference(self.folder / "missing.ma", namespace="mlibCreateReferenceMissing")
        self.assertEqual(set(cmds.ls(type="reference") or []), self.before)

    def test_unidentified_new_reference_raises_runtime_error(self):
        """新しいトップレベルのリファレンスが1件に決まらない場合は RuntimeError。"""
        # cmds.file(reference=True) は必ず1件作るため、何も作らない代役で0件の場合を作る。
        with mock.patch.object(cmds, "file", return_value=None) as file:
            with self.assertRaises(RuntimeError):
                createReference(self.path, namespace="mlibCreateReferenceNone")
        self.assertEqual(len([call for call in file.call_args_list if call[1].get("reference")]), 1)
        self.assertEqual(set(cmds.ls(type="reference") or []), self.before)

    def test_reference_is_not_recorded_for_undo(self):
        """cmds.file(reference=True) と同じくUndoに記録されず、作ったリファレンスは cmds の照会と一致する。"""
        cmds.flushUndo()
        reference = createReference(self.path, namespace="mlibCreateReferenceUndo")
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertEqual(set(cmds.ls(type="reference")) - self.before, {reference.getName()})
        self.assertEqual(Path(cmds.referenceQuery(reference.getName(), filename=True, withoutCopyNumber=True)), self.path)
        self.assertEqual(cmds.referenceQuery(reference.getName(), namespace=True), ":mlibCreateReferenceUndo")


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class ReferencesSpecTest(unittest.TestCase):
    """references の入力検証と一覧の型を固定する。"""

    def test_list_references_excludes_shared_node(self):
        """listReferencesはsharedReferenceNodeを含めず、Referenceのlistを返す。"""
        from mlib.nodes import Reference

        result = references.listReferences()
        self.assertIsInstance(result, mlib.Nodes)
        self.assertTrue(all(isinstance(item, Reference) for item in result))
        self.assertNotIn("sharedReferenceNode", [item.getName() for item in result])
        top = references.listReferences(topLevelOnly=True)
        self.assertTrue(all(item.getParentReference() is None for item in top))

    def test_create_reference_rejects_invalid_path_before_maya(self):
        """空・str/Path以外のpathはMayaへ渡す前にValueError。"""
        with mock.patch.object(cmds, "file", side_effect=AssertionError("file")):
            for path in ("", None, 5):
                with self.assertRaises(ValueError):
                    references.createReference(path)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
