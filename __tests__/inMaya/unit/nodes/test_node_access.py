"""ノードの名前・アトリビュートへのアクセスの約束を固定する。

対象: ``node.tx = 5`` の代入(Plug.setと同じ書込み・Undo 1回・度)、Mayaアトリビュートの無い名前への
代入のAttributeError、存在しないメソッドの案内付きAttributeError(Node・Plug・Component)、
無効なノードの getName・getName(short=True) の RuntimeError(str() は空文字列)、``|`` を含む名前の拒否、
一意でない名前の候補の表示、rename/setNamespace が自身を返すこと。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.nodes import Node


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeAccess_"


class SetAttrTest(_SpecCase):
    """Node.__setattr__ は Maya アトリビュートへの書込み。"""

    def test_assign_matches_plug_set_and_undoes_once(self):
        name = self.make()
        node = Node(name)
        cases = (
            ("tx", 5.0, "translateX", 5.0),
            ("rx", 90.0, "rotateX", 90.0),
            ("t", (1.0, 2.0, 3.0), "translate", [(1.0, 2.0, 3.0)]),
            ("visibility", False, "visibility", False),
        )
        for attribute, value, long_name, expected in cases:
            with self.subTest(attribute=attribute):
                before = cmds.getAttr(name + "." + long_name)
                self.flushUndo()
                setattr(node, attribute, value)
                after = cmds.getAttr(name + "." + long_name)
                self.assertEqual(after, expected)
                self.assertUndoesInOneStep(
                    lambda: self.assertEqual(cmds.getAttr(name + "." + long_name), before),
                    lambda: self.assertEqual(cmds.getAttr(name + "." + long_name), after),
                )

    def test_angles_are_degrees_like_plug_set(self):
        name = self.make()
        node = Node(name)
        node.ry = 45
        node.getPlug("rz").set(45)
        self.assertAlmostEqual(cmds.getAttr(name + ".ry"), 45.0)
        self.assertAlmostEqual(cmds.getAttr(name + ".ry"), cmds.getAttr(name + ".rz"))

    def test_unknown_name_raises_and_adds_nothing(self):
        node = Node(self.make())
        with self.assertRaisesRegex(AttributeError, "^'Transform'にMayaのアトリビュート'noSuchAttr'はありません"):
            node.noSuchAttr = 1
        self.assertNotIn("noSuchAttr", vars(node))

    def test_private_and_class_names_keep_python_behavior(self):
        node = Node(self.make())
        node._scratch = 3
        self.assertEqual(node._scratch, 3)
        self.assertFalse(cmds.attributeQuery("_scratch", node=str(node), exists=True))

    def test_locked_and_invalid_targets(self):
        name = self.make()
        node = Node(name)
        cmds.setAttr(name + ".tx", lock=True)
        with self.assertRaises(RuntimeError):
            node.tx = 2
        cmds.delete(name)
        with self.assertRaisesRegex(RuntimeError, "無効な"):
            node.tx = 2


class MissingMemberTest(_SpecCase):
    """存在しないメソッドの AttributeError の文言。"""

    def test_node_message_suggests_close_methods_and_mlib_ways(self):
        joint = Node(self.make("joint"))
        with self.assertRaises(AttributeError) as context:
            joint.orientJoint
        message = str(context.exception)
        self.assertTrue(message.startswith("'Joint'にメソッドやMayaのアトリビュート'orientJoint'はありません"), message)
        self.assertIn("orient()を使います", message)
        self.assertIn("近い名前: orient", message)
        for name, hint in (
            ("getAttr", "getPlug(name).get()"),
            ("setAttr", "getPlug(name).set(value)"),
            ("lockAndHide", "setAttrFlags("),
            ("listConnections", "getConnections()"),
            ("listRelatives", "getChildren()かgetParent()"),
            ("nodeType", "getType()"),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(AttributeError, hint.replace("(", r"\(").replace(")", r"\)") + ".*を使います"):
                    getattr(joint, name)
        self.assertFalse(hasattr(joint, "noSuchThing"))
        self.assertIsNone(getattr(joint, "noSuchThing", None))

    def test_plug_and_component_messages(self):
        node = Node(self.make())
        with self.assertRaisesRegex(AttributeError, "^'DoubleLinearPlug'にメソッド'lockAndHide'はありません。setFlags"):
            node.tx.lockAndHide
        with self.assertRaisesRegex(AttributeError, "近い名前: .*isLocked"):
            node.tx.isLockd
        with self.assertRaisesRegex(AttributeError, "にメソッドや子のアトリビュート'w'はありません"):
            node.translate.w
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        vertex = mlib.ls(cube + ".vtx[0]")[0]
        with self.assertRaisesRegex(AttributeError, "^'Vertex'にメソッド'getPositon'はありません。近い名前: getPosition"):
            vertex.getPositon


class NameTest(_SpecCase):
    """名前の取得・改名の約束。"""

    def test_invalid_node_name_raises_but_str_is_empty(self):
        cmds.flushUndo()
        node = mlib.createNode("transform", name=self.name("undone"))
        cmds.undo()
        self.assertFalse(node.isValid())
        for flags in ({}, {"short": True}):
            with self.subTest(flags=flags):
                with self.assertRaisesRegex(RuntimeError, r"Transformは削除されたか、Undoで取り消されました。使う前にisValid\(\)で確かめてください"):
                    node.getName(**flags)
        self.assertEqual(str(node), "")
        self.assertEqual(repr(node), "<Transform invalid>")

    def test_pipe_in_names_is_rejected_before_creation(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                before = set(cmds.ls(long=True))
                with self.assertRaisesRegex(ValueError, r"に'\|'は使えません"):
                    mlib.createNode("transform", name=self.name("grp|child"), fast=fast)
                self.assertEqual(set(cmds.ls(long=True)), before)
                node = Node(self.make())
                with self.assertRaisesRegex(ValueError, r"に'\|'は使えません"):
                    node.rename("a|b", fast=fast)

    def test_rename_and_set_namespace_return_self(self):
        node = Node(self.make(text="orig"))
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.assertIsNone(node.rename(self.name("renamed"), fast=fast))
                self.assertEqual(node.getName(short=True), self.name("renamed"))
                self.assertIsNone(node.setNamespace(self.ns, fast=fast))
        self.flushUndo()
        node.rename(self.name("again"))
        self.assertUndoesInOneStep(
            lambda: self.assertEqual(node.getName(short=True), self.name("renamed")), lambda: self.assertEqual(node.getName(short=True), self.name("again"))
        )

    def test_not_unique_message_lists_paths(self):
        groups = [self.make(text=f"grp{index}") for index in range(4)]
        for group in groups:
            self.make(text="dup", parent=group)
        name = self.name("dup")
        with self.assertRaises(RuntimeError) as context:
            mlib.getNode(name)
        message = str(context.exception)
        self.assertIn(f"名前が一意ではありません: {name!r}は4個のオブジェクトに一致します", message)
        self.assertIn("、ほか1個", message)
        self.assertIn(f"mlib.ls({name!r})", message)
        self.assertEqual(sum(f"'|{group}|{name}'" in message for group in groups), 3)
        with self.assertRaisesRegex(RuntimeError, f"名前が一意ではありません: '{name}.tx'"):
            mlib.getPlug(name + ".tx")


class NoDuplicateErrorLogTest(_SpecCase):
    """例外を送出する前に logger.error で同じ内容を表示しない。"""

    def test_node_not_found_does_not_log(self):
        import logging

        records = []

        class _Collect(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _Collect()
        logger = mlib.logger.getLogger()
        logger.addHandler(handler)
        try:
            with self.assertRaisesRegex(RuntimeError, "ノードが見つかりません"):
                mlib.getNode(self.name("missing"))
            for group in (self.make(text="g1"), self.make(text="g2")):
                self.make(text="same", parent=group)
            with self.assertRaisesRegex(RuntimeError, "名前が一意ではありません"):
                mlib.getNode(self.name("same"))
        finally:
            logger.removeHandler(handler)
        self.assertEqual([record.getMessage() for record in records if record.levelno >= logging.ERROR], [])


class StaticPlugTest(_SpecCase):
    """同じ名前を繰り返し取得しても、毎回の取得と同じ結果になる(静的アトリビュートは覚えた情報から作る)。"""

    def test_repeated_get_returns_equal_new_plugs(self):
        name = self.make()
        node = Node(name)
        for attr in ("tx", "translateX", "t", "translate", "visibility", "worldMatrix", "message", "rotateOrder"):
            with self.subTest(attr=attr):
                first = node.getPlug(attr)
                second = node.getPlug(attr)
                other = Node(name).getPlug(attr)
                self.assertIsNot(first, second)
                self.assertIs(type(second), type(first))
                self.assertIs(type(second), type(other))
                self.assertEqual(second, first)
                self.assertEqual(hash(second), hash(first))
                self.assertEqual(second.getName(full=True), first.getName(full=True))
                self.assertEqual(str(getattr(node, attr)), first.getName(full=True))
        node.tx = 3
        self.assertEqual(node.getPlug("tx").get(), 3.0)
        self.assertEqual(node.tx.get(), cmds.getAttr(name + ".tx"))

    def test_has_attr_and_missing_name(self):
        node = Node(self.make())
        for _ in range(2):
            self.assertTrue(node.hasAttr("tx"))
            self.assertFalse(node.hasAttr("noSuchAttribute"))
            self.assertFalse(node.hasAttr(""))
            for value in (None, 1.5):
                with self.assertRaises(TypeError):
                    node.hasAttr(value)

    def test_deleted_node_is_rejected_and_undo_restores(self):
        name = self.make()
        node = Node(name)
        node.getPlug("tx")
        cmds.delete(name)
        self.assertFalse(node.hasAttr("tx"))
        with self.assertRaises(RuntimeError):
            node.getPlug("tx")
        cmds.undo()
        self.assertTrue(node.hasAttr("tx"))
        self.assertEqual(node.getPlug("tx").getName(full=True), name + ".translateX")

    def test_dynamic_attribute_follows_delete_and_recreate(self):
        name = self.make()
        node = Node(name)
        cmds.addAttr(name, longName="custom", attributeType="double")
        self.assertEqual(type(node.getPlug("custom")).__name__, "DoublePlug")
        self.assertTrue(node.hasAttr("custom"))
        cmds.deleteAttr(name + ".custom")
        self.assertFalse(node.hasAttr("custom"))
        with self.assertRaises(AttributeError):
            node.getPlug("custom")
        cmds.addAttr(name, longName="custom", dataType="string")
        self.assertEqual(type(node.getPlug("custom")).__name__, "StringPlug")
        cmds.renameAttr(name + ".custom", "renamed")
        self.assertFalse(node.hasAttr("custom"))
        self.assertTrue(node.hasAttr("renamed"))

    def test_unresolved_child_stays_rejected(self):
        node = Node(self.make("plusMinusAverage"))
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                node.getPlug("input3Dx")
            self.assertFalse(node.hasAttr("input3Dx"))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
