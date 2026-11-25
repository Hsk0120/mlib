"""ノードの編集・削除の前の検査と、fastのcreateNode(nodeEdit)を確かめる。"""

import sys
import unittest
import uuid
from pathlib import Path

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.core import nodeEdit

_TEMP = Path(__file__).resolve().parents[3] / "_output" / "temp"


class _MissingNode:
    """MObjectを持たない(解決できない)ノードの代わり。"""

    def mnode(self):
        return None

    def _full_name(self):
        return "missing"


class NodeEditTest(NamespaceCase):
    """無効なノード・リファレンスの子孫・sharedのfast作成を確かめる。"""

    PREFIX = "mlibNodeEdit_"

    def test_invalid_nodes_are_rejected(self):
        """削除されたノードの編集と、解決できないノードの削除は、番号付きのRuntimeErrorにする。"""
        name = self.make("network", "gone")
        obj = mlib.getNode(name).mnode()
        cmds.delete(name)
        with self.assertRaisesRegex(RuntimeError, "無効なノードは編集できません"):
            nodeEdit.require_editable(obj)
        kept = mlib.getNode(self.make("network", "kept"))
        for fast, message in ((False, "無効なノードは削除できません"), (True, "無効なノードは編集できません")):
            with self.subTest(fast=fast), self.assertRaisesRegex(RuntimeError, message) as caught:
                nodeEdit.check_deletion([kept, _MissingNode()], fast=fast)
            self.assertEqual(caught.exception.index, 1)
        self.assertTrue(kept.isValid())

    def test_instanced_descendants_are_checked_once(self):
        """インスタンスで2回現れる子孫も調べ、ロックされていれば例外にする。"""
        group = self.make("transform", "group")
        first = self.make("transform", "first", parent=group)
        second = self.make("transform", "second", parent=group)
        shape = self.make("locator", "shape", parent=first)
        cmds.parent(shape, second, shape=True, addObject=True)
        nodeEdit.require_editable(mlib.getNode(group).mnode(), descendants=True)
        shape = cmds.listRelatives(first, shapes=True, fullPath=True)[0]
        cmds.lockNode(shape, lock=True)
        try:
            with self.assertRaisesRegex(RuntimeError, "ロックされているか"):
                nodeEdit.require_editable(mlib.getNode(group).mnode(), descendants=True)
        finally:
            cmds.lockNode(shape, lock=False)

    def test_referenced_descendant_blocks_deletion(self):
        """子孫にリファレンスのノードがあると、通常・fastとも何も削除しない。"""
        _TEMP.mkdir(parents=True, exist_ok=True)
        path = (_TEMP / f"mlibNodeEdit_{uuid.uuid4().hex}.ma").as_posix()
        modified = cmds.file(query=True, modified=True)
        source = cmds.createNode("transform", name="mlibNodeEditRef_" + uuid.uuid4().hex, skipSelect=True)
        cmds.select(source)
        cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(source)
        namespace = self.ns + "_ref"
        reference = cmds.file(path, reference=True, namespace=namespace)
        try:
            group = self.make("transform", "group")
            referenced = cmds.parent(cmds.ls(namespace + ":" + source, long=True)[0], group)[0]
            for fast in (False, True):
                with self.subTest(fast=fast):
                    with self.assertRaisesRegex(RuntimeError, "子孫の.*リファレンスのノードです") as caught:
                        mlib.delete(group, fast=fast)
                    self.assertEqual(caught.exception.index, 0)
                    self.assertTrue(cmds.objExists(group) and cmds.objExists(referenced))
        finally:
            cmds.file(reference, removeReference=True)
            Path(path).unlink()
            if not modified:
                cmds.file(modified=False)

    def test_referenced_message_without_reference(self):
        """リファレンスでない名前でも、文言を作るときに例外を出さない。"""
        name = self.make("transform", "local")
        self.assertIn("リファレンスのノードです", nodeEdit._referenced_message(name))
        self.assertIn("子孫の", nodeEdit._referenced_message(name, owner=name))

    def test_fast_shared_create_with_new_name(self):
        """shared=Trueで同じ名前のノードが無ければ、fastでも新しく作り、Undoに載せない。"""
        name = self.name("sharedNew")
        self.flushUndo()
        node = mlib.createNode("network", name=name, shared=True, fast=True)
        self.assertEqual(node.getName(), name)
        self.assertEqual(mlib.createNode("network", name=name, shared=True, fast=True), node)
        self.assertUndoEmpty()
        with self.assertRaises(RuntimeError):
            nodeEdit.create_node("mlibNoSuchNodeType", {})
        self.assertEqual(om2.MFnDependencyNode(node.mnode()).typeName, "network")


class CreateNodeFastTest(NamespaceCase):
    """fastのノード作成(create_node)の、対応しないフラグ・Undoなし・共有の名前の扱い。"""

    PREFIX = "mlibNodeEditCreate_"

    def test_unsupported_flags_are_rejected_before_creating(self):
        before = set(cmds.ls(self.ns + ":*"))
        with self.assertRaises(NotImplementedError):
            nodeEdit.create_node("transform", {"name": self.name("made"), "foo": 1})
        with self.assertRaises(NotImplementedError):
            mlib.createNode("transform", name=self.name("made"), fast=True, foo=1)
        self.assertEqual(set(cmds.ls(self.ns + ":*")), before)

    def test_fast_create_is_not_undoable(self):
        self.flushUndo()
        made = nodeEdit.create_node("transform", {"name": self.name("made")})
        name = om2.MFnDependencyNode(made).name()
        self.assertEqual(cmds.nodeType(name), "transform")
        self.assertUndoEmpty()

    def test_shared_name_matching_several_nodes_creates_new_node(self):
        """sharedの名前が複数のノードに一致するときは、既存のノードを返さずに新しく作る。"""
        first = self.make("transform", "shr1")
        second = self.make("transform", "shr2")
        made = nodeEdit.create_node("transform", {"name": self.name("shr*"), "shared": True})
        name = om2.MFnDependencyNode(made).name()
        self.assertNotIn(name, (first, second))
        self.assertTrue(cmds.objExists(first) and cmds.objExists(second))
        self.assertEqual(cmds.nodeType(name), "transform")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
