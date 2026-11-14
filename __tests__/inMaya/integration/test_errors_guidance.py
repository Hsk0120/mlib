"""編集の案内・一括適用・Undo の表示名の約束を固定する。

対象: 位置・回転・マトリクスの ``space=``/``ws=`` と成分を分けた指定の案内、ロック・接続された成分の案内、
DrivenKey.setKey の既存の入力の案内、getChildren(type=)、resetAttrs/setAttrFlags の Plug 指定、
複数形の一括の書込み(Undo 1回・fast)、Undo の表示名(``mlib setTranslation <対象>``)。

あわせて次も確かめる。

- Transform・Joint・ミラー軸・エラー文の約束を固定する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.common.drivenKey import DrivenKey
from mlib.decorator import undoChunk
from mlib.nodes import Joints, Node, Nodes


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecGuidance_"


class ArgumentHintTest(_SpecCase):
    """よくある引数の誤りの案内。"""

    def test_space_keywords_suggest_world_space(self):
        node = Node(self.make())
        calls = (
            ("setTranslation", ((1, 2, 3),)),
            ("getTranslation", ()),
            ("setRotate", ((1, 2, 3),)),
            ("getRotate", ()),
            ("setMatrix", (node.getMatrix(),)),
            ("getMatrix", ()),
        )
        for method, args in calls:
            for keyword, value in (("space", "world"),):
                with self.subTest(method=method, keyword=keyword):
                    self.flushUndo()
                    with self.assertRaisesRegex(TypeError, rf"unexpected keyword argument '{keyword}'; use worldSpace=True"):
                        getattr(node, method)(*args, **{keyword: value})
                    self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_spread_components_suggest_a_sequence(self):
        node = Node(self.make())
        for method in ("setTranslation", "setRotate", "setScale"):
            with self.subTest(method=method):
                with self.assertRaisesRegex(TypeError, rf"pass a sequence: {method}\(\(x, y, z\)\)"):
                    getattr(node, method)(1, 2, 3)
        self.assertEqual(cmds.getAttr(str(node) + ".t")[0], (0.0, 0.0, 0.0))

    def test_locked_or_connected_child_is_named(self):
        name = self.make()
        node = Node(name)
        cmds.setAttr(name + ".ty", lock=True)
        with self.assertRaisesRegex(RuntimeError, rf"{name}\.translateY is locked; .*safe=True"):
            node.setTranslation((1, 2, 3))
        node.setTranslation((1, 2, 3), safe=True)
        self.assertEqual(cmds.getAttr(name + ".t")[0], (1.0, 0.0, 3.0))
        source = self.make("plusMinusAverage", "pma")
        cmds.connectAttr(source + ".output1D", name + ".rz")
        with self.assertRaisesRegex(RuntimeError, rf"rotateZ is connected from {source}\.output1D"):
            node.setRotate((10, 20, 30))

    def test_driven_key_existing_input_is_explained(self):
        driver = Node(self.make(text="driver"))
        driven = Node(self.make(text="driven"))
        source = self.make("plusMinusAverage", "pma")
        cmds.connectAttr(source + ".output1D", str(driven) + ".tx")
        key = DrivenKey(driver.getPlug("tx"), driven.getPlug("tx"))
        with self.assertRaisesRegex(RuntimeError, rf"already has an input from {source}\.output1D .*blendWeighted"):
            key.setKey(0, 1)


class ChildrenTypeTest(_SpecCase):
    """getChildren(type=)。"""

    def test_type_filter_matches_list_relatives(self):
        root = self.make("joint", "root")
        child = self.make("joint", "child", parent=root)
        group = self.make("transform", "grp", parent=child)
        leaf = self.make("joint", "leaf", parent=group)
        shape = self.make("mesh", "rootShape", parent=self.make("transform", "geo", parent=root))
        node = Node(root)
        for flags, kind in (({}, "joint"), ({"allDescendents": True}, "joint"), ({"allDescendents": True}, "transform"), ({"allDescendents": True}, "mesh")):
            with self.subTest(flags=flags, type=kind):
                expected = cmds.listRelatives(root, type=kind, fullPath=True, **flags) or []
                actual = [item.getFullName() for item in node.getChildren(type=kind, **flags)]
                self.assertEqual(sorted(actual), sorted(expected))
        # 探索は型で絞らず、結果だけを絞る(型の違う grp の下の leaf も見つかる)。深さ優先の順。
        self.assertEqual(
            [item.getNodeName() for item in node.getChildren(type=["joint", "mesh"], allDescendents=True)],
            [self.name("child"), self.name("leaf"), self.name("rootShape")],
        )
        self.assertEqual(Node(shape).getNodeName(), self.name("rootShape"))
        self.assertEqual(Node(group).getChildren(type="joint"), [Node(leaf)])
        with self.assertRaises(TypeError):
            node.getChildren(type=1)
        with self.assertRaises(ValueError):
            node.getChildren(type="")


class PlugArgumentTest(_SpecCase):
    """resetAttrs・setAttrFlags の Plug 指定。"""

    def test_set_attr_flags_accepts_plugs(self):
        node = Node(self.make())
        self.flushUndo()
        self.assertIs(node.setAttrFlags([node.tx, "ty", node.getPlug("rotateX")], locked=True), node)
        for attribute in ("tx", "ty", "rx"):
            self.assertTrue(cmds.getAttr(str(node) + "." + attribute, lock=True))
        self.assertUndoesInOneStep(
            lambda: self.assertFalse(cmds.getAttr(str(node) + ".tx", lock=True)), lambda: self.assertTrue(cmds.getAttr(str(node) + ".tx", lock=True))
        )
        other = Node(self.make())
        with self.assertRaisesRegex(ValueError, "does not belong to"):
            node.setAttrFlags(other.tx, locked=True)
        with self.assertRaises(TypeError):
            node.setAttrFlags([1], locked=True)


class BulkWriteTest(_SpecCase):
    """複数形の一括の書込み。"""

    def test_bulk_writes_match_singular_and_undo_once(self):
        names = [self.make(text=f"n{index}") for index in range(3)]
        nodes = Nodes(names)
        cases = (
            (lambda: nodes.setAttrFlags(["tx"], locked=True), lambda name: cmds.getAttr(name + ".tx", lock=True)),
            (lambda: nodes.setLocked(True), lambda name: cmds.lockNode(name, query=True, lock=True)[0]),
            (lambda: nodes.setVisibility(False), lambda name: not cmds.getAttr(name + ".v")),
            (lambda: nodes.hide(), lambda name: not cmds.getAttr(name + ".v")),
            (lambda: nodes.setOverrideColor(17), lambda name: cmds.getAttr(name + ".overrideColor") == 17),
        )
        for action, check in cases:
            with self.subTest(action=action):
                self.flushUndo()
                result = action()
                self.assertIs(result, nodes)
                self.assertUndoesInOneStep(
                    lambda: self.assertFalse(any(check(name) for name in names)), lambda: self.assertTrue(all(check(name) for name in names))
                )

    def test_bulk_fast_and_reset(self):
        names = [self.make(text=f"f{index}") for index in range(2)]
        for name in names:
            cmds.setAttr(name + ".tx", 4)
        nodes = Nodes(names)
        self.flushUndo()
        plugs = nodes.resetAttrs(["tx"], fast=True)
        self.assertEqual(len(plugs), 2)
        self.assertEqual([cmds.getAttr(name + ".tx") for name in names], [0.0, 0.0])
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        with self.assertRaises(TypeError):
            nodes.setLocked(True, fast=1)

    def test_set_parent_and_joints(self):
        group = self.make(text="grp")
        names = [self.make(text=f"p{index}") for index in range(2)]
        Nodes(names).setParent(group)
        self.assertEqual(sorted(cmds.listRelatives(group, children=True)), sorted(names))
        joints = Joints([self.make("joint", "j0"), self.make("joint", "j1")])
        self.flushUndo()
        self.assertIs(joints.setRadius(3.0), joints)
        self.assertEqual([joint.getRadius() for joint in joints], [3.0, 3.0])
        self.assertTrue(cmds.undoInfo(query=True, undoName=True).startswith("mlib setRadius"))
        cmds.undo()
        self.assertEqual([joint.getRadius() for joint in joints], [1.0, 1.0])

    def test_unsupported_items_are_rejected_before_writing(self):
        dg = self.make("multiplyDivide", "md")
        transform = self.make(text="dag")
        with self.assertRaisesRegex(TypeError, r"requires every item to support setVisibility"):
            Nodes([transform, dg]).setVisibility(False)
        self.assertTrue(cmds.getAttr(transform + ".v"))


class UndoNameTest(_SpecCase):
    """Undo の表示名。"""

    def test_names_show_method_and_target(self):
        name = self.make(text="L_arm_CTRL")
        node = Node(name)
        cases = (
            (lambda: node.setTranslation((1, 2, 3)), "mlib setTranslation " + node.getName()),
            (lambda: node.getPlug("rx").set(10), f"mlib set {node.getName()}.rotateX"),
            (lambda: node.setAttrFlags("tx", keyable=False), "mlib setAttrFlags " + node.getName()),
            (lambda: mlib.createNode("transform", name=self.name("made")), "mlib createNode transform"),
        )
        for action, expected in cases:
            with self.subTest(expected=expected):
                action()
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), expected)

    def test_user_chunk_names_are_kept(self):
        node = Node(self.make())
        with undoChunk("mlibMyToolStep"):
            node.setTranslation((1, 0, 0))
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "mlibMyToolStep")
        with undoChunk("my tool"):
            node.setTranslation((2, 0, 0))
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "my tool")

        @undoChunk("mlibDecorated")
        def edit():
            node.setTranslation((3, 0, 0))

        edit()
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "mlibDecorated")


_EQUIVALENT_AXES = (("x", "YZ", "zy", "X", 0), ("y", "XZ", "ZX", "zx", 1), ("z", "XY", "YX", "xy", 2))


class _SpecCaseTranslationMirrorErrors(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecTransMirErr_"
    CLEAR_SELECTION = True


class AddConstraintOrderTest(_SpecCaseTranslationMirrorErrors):
    """型名をターゲットの位置へ渡した場合に、正しい引数の順を案内する。"""

    def test_swapped_type_and_target_are_guided(self):
        """addConstraint("parent", ctrl) は addConstraint(target, type="parent") を案内する TypeError。"""
        node = Node(self.make("transform", "driven"))
        ctrl = Node(self.make("transform", "ctrl"))
        before = cmds.ls(type="constraint")
        for kind in ("parent", "pointConstraint", "aim"):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(TypeError, rf"addConstraint\(target, type='{kind}'\)"):
                    node.addConstraint(kind, ctrl)
        with self.assertRaisesRegex(TypeError, r"type must be a string.*addConstraint\(target, type=\"parent\"\)"):
            node.addConstraint(ctrl, 1)
        self.assertEqual(cmds.ls(type="constraint"), before)
        constraint = node.addConstraint(ctrl, type="parent")
        self.assertTrue(constraint.isType("parentConstraint"))


class SetParentCycleTest(_SpecCaseTranslationMirrorErrors):
    """自身・子孫を親にした場合は、Maya の分かりにくいエラーでなく原因が分かる RuntimeError。"""

    MESSAGE = "Cannot parent a node under itself or one of its descendants"

    def setUp(self):
        super().setUp()
        self.root_name = self.make("transform", "root")
        self.child_name = self.make("transform", "child", parent=self.root_name)
        self.grandchild_name = self.make("transform", "grandchild", parent=self.child_name)

    def hierarchy(self):
        return [cmds.ls(name, long=True)[0] for name in (self.root_name, self.child_name, self.grandchild_name)]

    def test_transform_self_and_descendant(self):
        """通常経路と fast のどちらも、変更の前に同じ型・文言で拒否する。"""
        before = self.hierarchy()
        root = Node(self.root_name)
        for fast in (False, True):
            for parent in (self.root_name, self.child_name, Node(self.grandchild_name)):
                with self.subTest(fast=fast, parent=parent):
                    with self.assertRaisesRegex(RuntimeError, self.MESSAGE):
                        root.setParent(parent, fast=fast)
                    self.assertEqual(self.hierarchy(), before)

    def test_joint_and_fast_joint(self):
        """Joint も同じ文言。fast の Joint 未対応より先に親の検査を行う。"""
        root = Node(self.make("joint", "jointRoot"))
        child = Node(self.make("joint", "jointChild", parent=root.getFullName()))
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaisesRegex(RuntimeError, self.MESSAGE):
                    root.setParent(child, fast=fast)
                with self.assertRaisesRegex(RuntimeError, self.MESSAGE):
                    root.setParent(root, fast=fast)
        self.assertEqual(child.getParent(), root)
        with self.assertRaises(NotImplementedError):
            child.setParent(None, fast=True)

    def test_nodes_set_parent_checks_every_item_before_editing(self):
        """Nodes.setParent は1つでも該当すれば、どの要素も変更しない。"""
        other_name = self.make("transform", "other")
        before = self.hierarchy() + cmds.ls(other_name, long=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                nodes = Nodes([Node(other_name), Node(self.root_name)])
                with self.assertRaisesRegex(RuntimeError, self.MESSAGE):
                    nodes.setParent(self.child_name, fast=fast)
                self.assertEqual(self.hierarchy() + cmds.ls(other_name, long=True), before)
        Nodes([Node(other_name)]).setParent(self.grandchild_name)
        self.assertEqual(Node(other_name).getParent(), Node(self.grandchild_name))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
