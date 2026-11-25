"""``mlib.nodes.reference`` の Reference の、Undo に載らないファイルの操作と、無効なリファレンスでの例外を確かめる。

リファレンスの操作はファイルの操作なので、Mayaは Undo のキューを空にする。各テストは、操作の後に別のノードへの
setAttr を1つ積んでから Undo し、リファレンスの状態が戻らないことを cmds の照会で確かめる。
"""

import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


def _output_directory():
    """一時ファイルを置く手元のフォルダー(書けなければシステムの一時フォルダー)。"""
    try:
        base = Path(__file__).resolve().parents[3] / "_output"
        base.mkdir(parents=True, exist_ok=True)
        return tempfile.mkdtemp(prefix="referenceEdge_", dir=str(base))
    except (OSError, NameError):
        return tempfile.mkdtemp(prefix="referenceEdge_")


class ReferenceEdgeTest(NamespaceCase):
    """一時ファイルを2つ書き出し、1つ目をリファレンスする。"""

    PREFIX = "mlibSpecReferenceEdge_"

    def setUp(self):
        super().setUp()
        self.directory = _output_directory()
        self.paths = []
        for text in ("first", "second"):
            helper = cmds.createNode("transform", name="mlibReferenceEdge_" + text)
            path = str(Path(self.directory) / (text + ".ma")).replace("\\", "/")
            cmds.select(helper, replace=True)
            cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
            cmds.delete(helper)
            self.paths.append(path)
        cmds.select(clear=True)
        self.namespace = "mlibRefEdge_" + uuid.uuid4().hex[:8]
        self.extra_namespaces.append(self.namespace)
        nodes = cmds.file(self.paths[0], reference=True, namespace=self.namespace, returnNewNodes=True)
        self.reference = mlib.getNode(cmds.referenceQuery(nodes[0], referenceNode=True))
        self.name_ = self.reference.getName()
        self.helper = self.namespace + ":mlibReferenceEdge_first"

    def tearDown(self):
        if cmds.objExists(self.name_):
            cmds.file(removeReference=True, referenceNode=self.name_)
        super().tearDown()
        shutil.rmtree(self.directory, ignore_errors=True)

    def undo_other_step(self):
        """別のノードへの setAttr を積んで Undo し、その setAttr だけが戻ることを確かめる。"""
        marker = self.make("transform", "marker#")
        cmds.setAttr(marker + ".translateX", 1)
        cmds.undo()
        self.assertEqual(cmds.getAttr(marker + ".translateX"), 0)

    def edits(self):
        return cmds.referenceQuery(self.name_, editStrings=True) or []

    def test_set_reference_locked_is_not_undone(self):
        """setReferenceLocked は Undo で戻らない。"""
        self.reference.setReferenceLocked(True)
        self.undo_other_step()
        self.assertTrue(cmds.file(self.reference.getFilename(withCopyNumber=True), query=True, lockReference=True))
        self.reference.setReferenceLocked(False)
        self.assertFalse(cmds.file(self.reference.getFilename(withCopyNumber=True), query=True, lockReference=True))

    def test_set_loaded_is_not_undone(self):
        """setLoaded(False) は Undo で戻らない。"""
        self.reference.setLoaded(False)
        self.undo_other_step()
        self.assertFalse(cmds.referenceQuery(self.name_, isLoaded=True))
        self.reference.setLoaded(True)
        self.assertTrue(cmds.referenceQuery(self.name_, isLoaded=True))

    def test_remove_edits_without_reload(self):
        """successful=False・アンロード中の removeEdits は、ロードし直さずに消す。Undo で Edit は戻らない。"""
        cmds.setAttr(self.helper + ".translateX", 3)
        self.assertEqual(len(self.edits()), 1)
        self.reference.removeEdits(successful=False)
        self.assertEqual(len(self.edits()), 1)
        self.assertTrue(cmds.referenceQuery(self.name_, isLoaded=True))
        self.reference.setLoaded(False)
        self.reference.removeEdits()
        self.assertFalse(cmds.referenceQuery(self.name_, isLoaded=True))
        self.assertEqual(self.edits(), [])
        self.undo_other_step()
        self.assertEqual(self.edits(), [])

    def test_replace_file_errors_and_undo(self):
        """replaceFile は、無いファイルで OSError(何も変えない)。置き換えは Undo で戻らない。"""
        with self.assertRaises(OSError):
            self.reference.replaceFile(str(Path(self.directory) / "missing.ma"))
        self.assertEqual(cmds.referenceQuery(self.name_, filename=True, withoutCopyNumber=True), self.paths[0])
        self.reference.replaceFile(self.paths[1])
        self.undo_other_step()
        self.assertEqual(cmds.referenceQuery(self.name_, filename=True, withoutCopyNumber=True), self.paths[1])

    def test_import_contents_is_not_undone(self):
        """importContents の後は Undo してもリファレンスに戻らない。"""
        nodes = self.reference.importContents()
        self.assertEqual([node.getName() for node in nodes], [self.helper])
        self.undo_other_step()
        self.assertFalse(cmds.objExists(self.name_))
        self.assertFalse(cmds.referenceQuery(self.helper, isNodeReferenced=True))

    def test_remove_is_not_undone_and_invalid_reference_errors(self):
        """remove は Undo で戻らない。削除済みのリファレンスの操作は RuntimeError。"""
        self.reference.remove()
        self.undo_other_step()
        self.assertFalse(cmds.objExists(self.name_))
        self.assertFalse(cmds.objExists(self.helper))
        with self.assertRaises(RuntimeError):
            self.reference.remove()
        with self.assertRaises(RuntimeError):
            self.reference.setReferenceLocked(True)
        with self.assertRaises(RuntimeError):
            self.reference.replaceFile(self.paths[1])
        with self.assertRaises(RuntimeError):
            self.reference.getParentReference()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
