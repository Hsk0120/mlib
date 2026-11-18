"""ノードが申告する外部ファイル情報の値と所有権を検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class NodeExternalContentTest(NamespaceCase):
    def test_file_and_audio_report_native_entries_without_changes(self):
        for kind, attr, role in (("file", "fileTextureName", "sourceImages"), ("audio", "filename", "audio")):
            node = mlib.getNode(self.make(kind))
            path = "missing_content/image.png" if kind == "file" else "missing_content/sound.wav"
            cmds.setAttr(str(node) + "." + attr, path, type="string")
            table = om2.MExternalContentInfoTable()
            node.mfn().getExternalContent(table)
            self.flushUndo()
            selection = cmds.ls(selection=True)
            time = cmds.currentTime(query=True)
            result = node.getExternalContent()
            self.assertEqual(len(result), len(table))
            raw = table.getEntry(0)
            self.assertEqual(result[0], dict(key=raw[0], unresolvedLocation=raw[1], resolvedLocation=raw[2], contextNodeFullName=raw[3], roles=list(raw[4])))
            self.assertEqual(result[0]["unresolvedLocation"], path)
            self.assertIn(role, result[0]["roles"])
            result[0]["roles"].append("modified")
            self.assertNotIn("modified", node.getExternalContent()[0]["roles"])
            self.assertEqual(cmds.ls(selection=True), selection)
            self.assertEqual(cmds.currentTime(query=True), time)
            self.assertUndoEmpty()

    def test_empty_deleted_and_plural(self):
        first, second = self.make(), self.make()
        self.assertEqual(mlib.ls(first, second).getExternalContent(), [[], []])
        node = mlib.getNode(first)
        cmds.delete(first)
        with self.assertRaises(RuntimeError):
            node.getExternalContent()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
