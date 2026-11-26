"""``mlib.nodes.node`` の入力の検査と、複数形(Nodes)の演算子のテスト。

- addAttr の ``is``・型の接頭辞・enumの既定値・compoundの子の数を確かめる。
- getName・setKey・resetAttrs・setAttrFlags・swapConnections・moveAttrOrder の不正な入力の例外を確かめる。
- Nodes の ``==``・``Nodes[...]``・``+`` と、無効なノードの追加を確かめる。
- setLocked・setAttrFlags の check(リファレンスのノード)を確かめる。
"""

import sys
import unittest
import uuid
from pathlib import Path

import maya.api.OpenMaya as om2
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
            node.getName(full=True, short=True)
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


class AddAttrUnitDefaultTest(_Case):
    """単位のある型の既定値・範囲の型の誤り。"""

    def test_string_default_is_type_error(self):
        """角度・距離・時間の型へ文字列や真偽値の既定値・範囲を渡すと、Mayaの英語のエラーでなく日本語のTypeErrorで、何も足さない。"""
        node = self.node()
        for kind in ("doubleAngle", "doubleLinear", "time"):
            for flag, value in (("defaultValue", "abc"), ("minValue", True), ("maxValue", [1.0])):
                with self.subTest(kind=kind, flag=flag):
                    with self.assertRaisesRegex(TypeError, f"^{flag}は数値か"):
                        node.addAttr("unitValue", attributeType=kind, **{flag: value})
                    self.assertFalse(cmds.attributeQuery("unitValue", node=str(node), exists=True))


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


class NodeKeyRejectTest(_Case):
    """キーの操作(setKey・removeKey・moveKey・setKeyTangent)の型違いと無効なノード。"""

    def keyed(self):
        """translateXに2つのキーを打ったtransformを返す。"""
        node = self.node("keyed")
        cmds.setKeyframe(str(node), attribute="translateX", time=1, value=0)
        cmds.setKeyframe(str(node), attribute="translateX", time=10, value=5)
        return node

    def keys(self, node):
        """cmdsで読んだtranslateXのキーの時刻。"""
        return cmds.keyframe(f"{node}.translateX", query=True, timeChange=True) or []

    def test_type_errors_keep_keys(self):
        """attributesなどの型が違うとTypeErrorで、キーは変わらない。"""
        node = self.keyed()
        before = self.keys(node)
        for label, call in (
            ("removeKey", lambda: node.removeKey(5)),
            ("removeKey item", lambda: node.removeKey([1])),
            ("moveKey", lambda: node.moveKey(5, timeOffset=1)),
            ("moveKey offset", lambda: node.moveKey("translateX", timeOffset="1")),
            ("setKeyTangent", lambda: node.setKeyTangent(5, inTangentType="linear")),
            ("setKeyTangent time", lambda: node.setKeyTangent("translateX", inTangentType="linear", time="1")),
        ):
            with self.subTest(label), self.assertRaises(TypeError):
                call()
            self.assertEqual(self.keys(node), before)

    def test_deleted_node(self):
        """削除したノードへのキーの操作はRuntimeError。"""
        node = self.keyed()
        cmds.delete(str(node))
        for label, call in (
            ("setKey", lambda: node.setKey("translateX")),
            ("setKey value", lambda: node.setKey("translateX", value=1)),
            ("removeKey", lambda: node.removeKey("translateX")),
            ("moveKey", lambda: node.moveKey("translateX", timeOffset=1)),
            ("setKeyTangent", lambda: node.setKeyTangent("translateX", inTangentType="linear")),
        ):
            with self.subTest(label), self.assertRaises(RuntimeError):
                call()

    def test_remove_all_keys_and_undo(self):
        """attributesを省いたremoveKeyはすべてのキーを消し、Undo 1回で戻る。"""
        node = self.keyed()
        cmds.setKeyframe(str(node), attribute="rotateY", time=3, value=30)
        self.flushUndo()
        node.removeKey()
        self.assertEqual(cmds.keyframe(str(node), query=True, keyframeCount=True), 0)
        cmds.undo()
        self.assertEqual(self.keys(node), [1.0, 10.0])
        self.assertEqual(cmds.keyframe(f"{node}.rotateY", query=True, timeChange=True), [3.0])

    def test_set_key_tangent_matches_cmds(self):
        """setKeyTangentを直接呼ぶと、cmds.keyTangentで読んだ接線の型が変わり、Undo 1回で戻る。"""
        node = self.keyed()
        before = cmds.keyTangent(f"{node}.translateX", query=True, outTangentType=True)
        self.flushUndo()
        node.setKeyTangent("translateX", outTangentType="step")
        self.assertEqual(cmds.keyTangent(f"{node}.translateX", query=True, outTangentType=True), ["step", "step"])
        cmds.undo()
        self.assertEqual(cmds.keyTangent(f"{node}.translateX", query=True, outTangentType=True), before)


class NodeSelectRejectTest(_Case):
    """select・Nodes.select のフラグの重なりと無効なノード。"""

    CLEAR_SELECTION = True

    def test_invalid_flags(self):
        """add・deselectの型の誤り・同時の指定・cmds.selectのほかのフラグはTypeErrorで、選択は変わらない。"""
        node = self.node()
        for flags in ({"add": True, "deselect": True}, {"add": 1}, {"deselect": "yes"}, {"replace": True}, {"hierarchy": True}):
            for label, target in (("Node", node), ("Nodes", Nodes([node]))):
                with self.subTest(label, flags=flags), self.assertRaises(TypeError):
                    target.select(**flags)
                self.assertEqual(cmds.ls(selection=True), [])

    def test_nodes_deleted_member(self):
        """削除したノードを含むNodes.selectはRuntimeErrorで、選択は変わらない。"""
        first, second = self.node("first"), self.node("second")
        nodes = Nodes([first, second])
        cmds.select(str(first), replace=True)
        cmds.delete(str(second))
        with self.assertRaises(RuntimeError):
            nodes.select()
        self.assertEqual(cmds.ls(selection=True, long=True), cmds.ls(str(first), long=True))


class NodeResetAndFlagsRejectTest(_Case):
    """resetAttrs・setAttrFlags の存在しないアトリビュートと、Mayaの拒否。"""

    def test_missing_attribute(self):
        """存在しないアトリビュートはAttributeErrorで、ほかのアトリビュートは変わらない。"""
        node = self.node()
        cmds.setAttr(f"{node}.translateX", 3)
        for label, call in (
            ("resetAttrs", lambda: node.resetAttrs(["translateX", "noSuchAttr"])),
            ("setAttrFlags", lambda: node.setAttrFlags(["translateX", "noSuchAttr"], locked=True)),
            ("Nodes.resetAttrs", lambda: Nodes([node]).resetAttrs("noSuchAttr")),
        ):
            with self.subTest(label), self.assertRaises(AttributeError):
                call()
        self.assertEqual(cmds.getAttr(f"{node}.translateX"), 3)
        self.assertFalse(cmds.getAttr(f"{node}.translateX", lock=True))

    def test_nodes_reset_type_error(self):
        """Nodes.resetAttrsへ名前・Plug以外を渡すとTypeError。"""
        node = self.node()
        with self.assertRaises(TypeError):
            Nodes([node]).resetAttrs(5)
        with self.assertRaises(TypeError):
            Nodes([node]).resetAttrs([5], check=True)

    def test_reset_defaults_on_dg_node(self):
        """attributesを省いたresetAttrsは、DGノードのキーを設定できる値を既定へ戻し、cmdsの値と合う。Undo 1回で戻る。"""
        node = mlib.getNode(self.make("multiplyDivide", "md"))
        cmds.setAttr(f"{node}.input1X", 4)
        cmds.setAttr(f"{node}.input2X", 3)
        self.flushUndo()
        plugs = node.resetAttrs()
        names = {plug.getAttributeName() for plug in plugs}
        self.assertIn("input1X", names)
        self.assertEqual(cmds.getAttr(f"{node}.input1X"), 0)
        self.assertEqual(cmds.getAttr(f"{node}.input2X"), 1)
        cmds.undo()
        self.assertEqual(cmds.getAttr(f"{node}.input1X"), 4)
        self.assertEqual(cmds.getAttr(f"{node}.input2X"), 3)

    def test_set_attr_flags_on_locked_node(self):
        """ロックしたノードのアトリビュートのロックを変えると、MayaのRuntimeError。"""
        node = self.node()
        cmds.lockNode(str(node), lock=True)
        try:
            with self.assertRaises(RuntimeError):
                node.setAttrFlags("translateX", locked=True)
            self.assertFalse(cmds.getAttr(f"{node}.translateX", lock=True))
        finally:
            cmds.lockNode(str(node), lock=False)


class NodesRejectTest(_Case):
    """Nodes の sort・setColor・setParent の拒否と、使われていなかった引数。"""

    def test_sort_with_deleted_member(self):
        """keyを省いたsortは、削除したノードを含むとRuntimeErrorで、並びは変わらない。"""
        first, second = self.node("b"), self.node("a")
        nodes = Nodes([first, second])
        cmds.delete(str(second))
        with self.assertRaises(RuntimeError):
            nodes.sort()
        self.assertEqual(list(nodes), [first, second])
        # keyを渡せば、無効なノードがあっても並べ替えられる。
        nodes.sort(key=lambda node: node.isValid())
        self.assertEqual(list(nodes), [second, first])

    def test_set_color_rejects(self):
        """範囲外の色番号はValueError、check=Trueはロックを先に拒否し、削除したノードはRuntimeError。"""
        first, second = self.node("first"), self.node("second")
        nodes = Nodes([first, second])
        for value in (99, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                nodes.setColor(value)
        cmds.setAttr(f"{second}.overrideEnabled", lock=True)
        with self.assertRaises(RuntimeError):
            nodes.setColor(5, check=True)
        self.assertFalse(cmds.getAttr(f"{first}.overrideEnabled"))
        cmds.setAttr(f"{second}.overrideEnabled", lock=False)
        self.flushUndo()
        nodes.setColor(5, check=True)
        self.assertEqual([cmds.getAttr(f"{node}.overrideColor") for node in nodes], [5, 5])
        cmds.undo()
        self.assertEqual([cmds.getAttr(f"{node}.overrideColor") for node in nodes], [0, 0])
        cmds.delete(str(second))
        with self.assertRaises(RuntimeError):
            nodes.setColor(6)
        self.assertEqual(cmds.getAttr(f"{first}.overrideColor"), 0)

    def test_set_parent_flags(self):
        """relative・add・checkをそのまま各要素へ渡し、cmdsで読んだ親が変わる。Undo 1回で戻る。"""
        parent = self.node("parent")
        cmds.setAttr(f"{parent}.translateX", 5)
        first, second = self.node("first"), self.node("second")
        nodes = Nodes([first, second])
        self.flushUndo()
        nodes.setParent(parent, relative=True, check=True)
        for node in (first, second):
            self.assertEqual(cmds.listRelatives(str(node), parent=True, fullPath=True), cmds.ls(str(parent), long=True))
            self.assertEqual(cmds.getAttr(f"{node}.translateX"), 0)
        cmds.undo()
        self.assertIsNone(cmds.listRelatives(first.getName(full=True), parent=True))
        other = self.node("other")
        Nodes([first]).setParent(other, add=True)
        self.assertEqual(om2.MFnDagNode(first.mnode()).instanceCount(False), 2)
        self.assertIn(other.getName(full=True) + "|" + first.getName(short=True), cmds.listRelatives(str(other), children=True, fullPath=True))

    def test_set_parent_to_world_and_rejects(self):
        """parent=Noneはワールドへ移す。Transform以外を含むとTypeError、削除したアトリビュートのPlugはValueError、DGノードの親はMayaが拒否する。"""
        parent = self.node("parent")
        child = mlib.getNode(self.make(text="child", parent=str(parent)))
        Nodes([child]).setParent()
        self.assertIsNone(cmds.listRelatives(str(child), parent=True))
        md = mlib.getNode(self.make("multiplyDivide", "md"))
        with self.assertRaises(TypeError):
            Nodes([child, md]).setParent(parent)
        # 削除したアトリビュートのPlugはDeletedAttributeError(ValueErrorの派生)。
        plug = parent.addAttr("removed")
        cmds.deleteAttr(f"{parent}.removed")
        with self.assertRaises(ValueError):
            Nodes([child]).setParent(plug)
        with self.assertRaises(RuntimeError):
            Nodes([child]).setParent("")
        self.assertIsNone(cmds.listRelatives(str(child), parent=True))
        # 親がTransformでない(DGノード)ときは、子孫の確認を飛ばし、Mayaが拒否する。
        with self.assertRaises(RuntimeError):
            Nodes([child]).setParent(md)
        self.assertIsNone(cmds.listRelatives(str(child), parent=True))


class LockCheckTest(_Case):
    """setLocked・setAttrFlagsのcheck。check=Trueだけ、リファレンスのノードを変える前に拒否する。"""

    def test_check_type(self):
        """checkがboolでなければTypeErrorで、何も変えない。"""
        node = self.node()
        for value in (1, "yes", None):
            with self.subTest(check=value):
                with self.assertRaises(TypeError):
                    node.setLocked(True, check=value)
                self.assertFalse(cmds.lockNode(str(node), query=True, lock=True)[0])
                with self.assertRaises(TypeError):
                    node.setAttrFlags("tx", locked=True, check=value)
                self.assertFalse(cmds.getAttr(f"{node}.tx", lock=True))

    def test_check_on_local_node(self):
        """リファレンスでないノードでは、check=Trueでも通常どおり変える。"""
        node = self.node()
        for fast in (False, True):
            with self.subTest(fast=fast):
                node.setLocked(True, fast=fast, check=True)
                self.assertTrue(cmds.lockNode(str(node), query=True, lock=True)[0])
                node.setLocked(False, fast=fast, check=True)
                node.setAttrFlags("tx", keyable=False, fast=fast, check=True)
                self.assertFalse(cmds.getAttr(f"{node}.tx", keyable=True))
                node.setAttrFlags("tx", keyable=True, fast=fast, check=True)

    def test_check_on_referenced_node(self):
        """リファレンスのノードでは、check=Trueのときだけ、変える前にRuntimeErrorにする。"""
        folder = Path(__file__).resolve().parents[3] / "_output"
        folder.mkdir(exist_ok=True)
        path = (folder / f"mlibSpecNodeInputRef_{uuid.uuid4().hex}.ma").as_posix()
        current = cmds.file(query=True, sceneName=True)
        modified = cmds.file(query=True, modified=True)
        source = cmds.createNode("transform", name="mlibSpecNodeInputRef_" + uuid.uuid4().hex)
        cmds.select(source)
        cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(source)
        reference = cmds.file(path, reference=True, namespace=self.ns + "_ref")
        try:
            node = mlib.getNode(cmds.ls(self.ns + "_ref:" + source, long=True)[0])
            for fast in (False, True):
                with self.subTest(fast=fast):
                    with self.assertRaisesRegex(RuntimeError, "リファレンスのノード"):
                        node.setLocked(True, fast=fast, check=True)
                    self.assertFalse(cmds.lockNode(str(node), query=True, lock=True)[0])
                    with self.assertRaisesRegex(RuntimeError, "リファレンスのノード"):
                        node.setAttrFlags(["tx", "ty"], keyable=False, fast=fast, check=True)
                    self.assertTrue(cmds.getAttr(f"{node}.tx", keyable=True))
                    # ロックだけの変更はMayaも受け付けるので、checkでも拒否しない。
                    node.setAttrFlags("tx", locked=True, fast=fast, check=True)
                    self.assertTrue(cmds.getAttr(f"{node}.tx", lock=True))
                    node.setAttrFlags("tx", locked=False, fast=fast)
            # check=Falseなら、Mayaと同じくリファレンスのノードもロックする。
            node.setLocked(True)
            self.assertTrue(cmds.lockNode(str(node), query=True, lock=True)[0])
            node.setLocked(False)
        finally:
            cmds.file(reference, removeReference=True)
            if Path(path).exists():
                Path(path).unlink()
            if current and not modified:
                cmds.file(modified=False)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
