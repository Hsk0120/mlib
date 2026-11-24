"""``mlib.nodes.node`` の入力の検査と、複数形(Nodes)の演算子のテスト。

- addAttr の ``is``・型の接頭辞・enumの既定値・compoundの子の数を確かめる。
- getName・setKey・resetAttrs・setAttrFlags・swapConnections・moveAttrOrder の不正な入力の例外を確かめる。
- Nodes の ``==``・``Nodes[...]``・``+`` と、無効なノードの追加を確かめる。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Joint, Joints, Nodes, Transform


class _Case(NamespaceCase):
    """このテストファイルの名前空間の先頭。"""

    PREFIX = "mlibSpecNodeInput_"

    def node(self, text="node"):
        """名前空間にtransformを作って返す。"""
        return mlib.getNode(self.make(text=text))


class AddAttrFlagsTest(_Case):
    """addAttrの別名・型の指定と、作成前に拒否する組み合わせ。"""

    def test_is_flag_and_conflict(self):
        """``is`` はinternalSetとして渡り、internalSetと同時に渡すとTypeError。"""
        node = self.node()
        plug = node.addAttr("withIs", **{"is": True})
        self.assertTrue(cmds.attributeQuery("withIs", node=str(node), exists=True))
        self.assertEqual(plug.getType(), "double")
        with self.assertRaises(TypeError):
            node.addAttr("withBoth", internalSet=True, **{"is": True})
        self.assertFalse(cmds.attributeQuery("withBoth", node=str(node), exists=True))

    def test_name_is_required(self):
        """longNameもshortNameも無いとValueError。"""
        node = self.node()
        before = cmds.listAttr(str(node))
        with self.assertRaises(ValueError):
            node.addAttr("")
        self.assertEqual(cmds.listAttr(str(node)), before)

    def test_type_prefix(self):
        """type= の ``at:``・``dt:`` はattributeType・dataTypeになり、ほかの接頭辞はValueError。"""
        node = self.node()
        node.addAttr("prefAt", type="at:double")
        node.addAttr("prefDt", type="dt:string")
        self.assertEqual(cmds.getAttr(f"{node}.prefAt", type=True), "double")
        self.assertEqual(cmds.getAttr(f"{node}.prefDt", type=True), "string")
        with self.assertRaises(ValueError):
            node.addAttr("prefBad", type="xx:double")
        self.assertFalse(cmds.attributeQuery("prefBad", node=str(node), exists=True))

    def test_attribute_and_data_type_together(self):
        """attributeTypeとdataTypeを同時に指定するとValueErrorで、何も作らない。"""
        node = self.node()
        with self.assertRaises(ValueError):
            node.addAttr("both", attributeType="double", dataType="string")
        self.assertFalse(cmds.attributeQuery("both", node=str(node), exists=True))

    def test_enum_default_name_needs_enum_name(self):
        """enumの既定値を名前で渡すときにenumNameが無いとValueError。"""
        node = self.node()
        with self.assertRaises(ValueError):
            node.addAttr("mode", type="enum", defaultValue="b")
        self.assertFalse(cmds.attributeQuery("mode", node=str(node), exists=True))

    def test_compound_child_count_from_names(self):
        """compoundはchildNamesの数を子の数にして、子を作る。"""
        node = self.node()
        plug = node.addAttr("group", type="compound", childNames=["first", "second"])
        self.assertEqual([child.getAttributeName() for child in plug.getChildren()], ["first", "second"])
        self.assertEqual(cmds.attributeQuery("group", node=str(node), numberOfChildren=True), [2])
        self.assertEqual(cmds.attributeQuery("group", node=str(node), listChildren=True), ["first", "second"])


class NodeArgumentsTest(_Case):
    """getName・キー操作・アトリビュートの一覧の、不正な入力。"""

    def test_get_name_full_with_node(self):
        """full=Trueとnodeを同時に指定するとTypeError。nodeがboolでなければその型のTypeError。"""
        node = self.node()
        with self.assertRaises(TypeError):
            node.getName(full=True, node=True)
        with self.assertRaises(TypeError):
            node.getName(full=True, removeNamespace=True)
        with self.assertRaises(TypeError):
            node.getName(full=True, node=1)

    def test_attribute_names_types(self):
        """setKeyのattributesは名前か名前の並び。それ以外はTypeErrorで、キーを打たない。"""
        node = self.node()
        for value in (5, [5], ["tx", None]):
            with self.subTest(value=value), self.assertRaises(TypeError):
                node.setKey(value)
        self.assertEqual(cmds.keyframe(str(node), query=True, keyframeCount=True), 0)

    def test_empty_attribute_name_in_plugs(self):
        """resetAttrs・setAttrFlagsに空の名前を渡すとValueErrorで、何も変えない。"""
        node = self.node()
        cmds.setAttr(f"{node}.tx", 3)
        with self.assertRaises(ValueError):
            node.resetAttrs(["tx", ""])
        self.assertEqual(cmds.getAttr(f"{node}.tx"), 3)
        with self.assertRaises(ValueError):
            node.setAttrFlags([""], locked=True)
        self.assertFalse(cmds.getAttr(f"{node}.tx", lock=True))

    def test_swap_connections_locked(self):
        """ロックしたノードとの接続の交換はRuntimeErrorで、接続は変わらない。"""
        first = mlib.getNode(self.make("multiplyDivide", "first"))
        second = mlib.getNode(self.make("multiplyDivide", "second"))
        driver = self.make(text="driver")
        cmds.connectAttr(driver + ".tx", f"{first}.input1X")
        cmds.lockNode(str(second), lock=True)
        try:
            with self.assertRaises(RuntimeError):
                first.swapConnections(second)
        finally:
            cmds.lockNode(str(second), lock=False)
        self.assertEqual(cmds.listConnections(f"{first}.input1X", source=True, plugs=True), [driver + ".translateX"])


class MoveAttrOrderTypesTest(_Case):
    """moveAttrOrderが作り直せない型を含むと、変える前に拒否する。"""

    def make_with(self, flags):
        """qq1・qqm(指定の型)・qq2を持つノードを作って返す。"""
        node = self.node()
        node.addAttr("qq1")
        cmds.addAttr(str(node), longName="qqm", **flags)
        node.addAttr("qq2")
        return node

    def test_unsupported_types(self):
        """数値でない型(matrix)・対応表に無い数値の型(char)は TypeError で、並びは変わらない。"""
        for flags in ({"dataType": "matrix"}, {"attributeType": "char"}, {"attributeType": "doubleAngle"}):
            with self.subTest(flags=flags):
                node = self.make_with(flags)
                with self.assertRaises(TypeError):
                    node.moveAttrOrder("qq2", -2)
                self.assertEqual(cmds.listAttr(str(node), userDefined=True), ["qq1", "qqm", "qq2"])

    def test_message_type(self):
        """messageのアトリビュートも、docstringのとおりTypeErrorで拒否し、並びは変わらない。"""
        node = self.make_with({"attributeType": "message"})
        with self.assertRaises(TypeError):
            node.moveAttrOrder("qq2", -2)
        self.assertEqual(cmds.listAttr(str(node), userDefined=True), ["qq1", "qqm", "qq2"])


class NodesOperatorsTest(_Case):
    """Nodesの比較・型注釈・足し算と、無効なノードの追加。"""

    def test_eq_and_class_getitem(self):
        """Nodes と対応しない型の == は False、Nodes[Transform] は Nodes 自身。"""
        nodes = Nodes([self.node()])
        self.assertFalse(nodes == 5)
        self.assertTrue(nodes != "text")
        self.assertIs(Nodes[Transform], Nodes)
        self.assertIs(Joints[Joint], Joints)

    def test_radd_unsupported(self):
        """左辺がlist・tuple以外の足し算はTypeError。"""
        nodes = Nodes([self.node()])
        with self.assertRaises(TypeError):
            5 + nodes
        self.assertEqual(len([self.node("other")] + nodes), 2)  # noqa: RUF005 __radd__を通すため、足し算で書く。

    def test_reset_attrs_iterator_with_check(self):
        """check=Trueでも、使い切りのイテレーターの名前をすべて既定値へ戻す。"""
        nodes = Nodes([self.node("a"), self.node("b")])
        for node in nodes:
            cmds.setAttr(f"{node}.tx", 4)
            cmds.setAttr(f"{node}.ty", 5)
        cmds.flushUndo()
        result = nodes.resetAttrs((name for name in ["tx", "ty"]), check=True)
        self.assertEqual(len(result), 4)
        for node in nodes:
            self.assertEqual(cmds.getAttr(f"{node}.translate"), [(0.0, 0.0, 0.0)])
        cmds.undo()
        for node in nodes:
            self.assertEqual(cmds.getAttr(f"{node}.translate"), [(4.0, 5.0, 0.0)])

    def test_append_invalid_node(self):
        """削除済みのノードは、自動で決まったJointsにも自分で作ったJointsにも足せない(RuntimeError)。"""
        cmds.select(clear=True)
        joint = cmds.joint(name=self.name("joint"))
        cmds.select(clear=True)
        removed = self.node("removed")
        cmds.delete(str(removed))
        promoted = mlib.ls(self.name("joint"))
        self.assertIs(type(promoted), Joints)
        with self.assertRaises(RuntimeError):
            promoted.append(removed)
        self.assertIs(type(promoted), Joints)
        explicit = Joints([Joint(joint)])
        with self.assertRaises(RuntimeError):
            explicit.append(removed)
        self.assertEqual(len(explicit), 1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
