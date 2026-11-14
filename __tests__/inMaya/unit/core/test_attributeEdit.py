"""アトリビュートの再作成と追加前検証で、定義・接続・Undoを保つ。

あわせて次も確かめる。

- mlib Node/DAG APIを検証するMaya内テスト。
- 内部処理の分割後も、利用側overrideの契約を維持する。
"""

import importlib
import sys
import unittest
import uuid
from unittest.mock import patch

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()


class AttributeEditsTest(unittest.TestCase):
    """専用名前空間で、破壊的な並べ替えと不正な追加を検証する。"""

    def setUp(self):
        """このテストだけが所有するノードとUndo状態を用意する。"""
        self.namespace = "mlibAttributeEdits_" + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)
        self.node = mlib.getNode(cmds.createNode("network", name=self.namespace + ":node"))
        self.undo_enabled = cmds.undoInfo(query=True, state=True)
        if not self.undo_enabled:
            cmds.undoInfo(state=True)

    def tearDown(self):
        """専用ノードを削除し、元のUndo設定へ戻す。"""
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.undoInfo(state=self.undo_enabled)
        self.assertEqual(cmds.undoInfo(query=True, state=True), self.undo_enabled)

    def _definition(self, name):
        """Mayaの定義とPlug状態を、比較できる値として取得する。

        Args:
            name (str): 専用ノードのアトリビュート長名。

        Returns:
            dict: 名前・範囲・定義フラグ・値・表示状態。
        """
        plug = self.node.getPlug(name)
        fn = om2.MFnAttribute(plug.mplug().attribute())
        data = {
            key: getattr(fn, key)
            for key in ("readable", "writable", "storable", "connectable", "cached", "usedAsColor", "usedAsFilename", "disconnectBehavior")
        }
        data.update(
            shortName=plug.getShortName(),
            niceName=plug.getNiceName(),
            value=plug.get(),
            default=plug.getDefault(),
            hidden=fn.hidden,
            channelBoxHidden=plug.isHidden(),
            keyable=plug.isKeyable(),
            channelBox=plug.mplug().isChannelBox,
            locked=plug.isLocked(),
        )
        for flag in ("minExists", "maxExists", "softMinExists", "softMaxExists"):
            data[flag] = cmds.attributeQuery(name, node=self.node.getFullName(), **{flag: True})
        for exists, query in (("minExists", "minimum"), ("maxExists", "maximum"), ("softMinExists", "softMin"), ("softMaxExists", "softMax")):
            if data[exists]:
                data[query] = cmds.attributeQuery(name, node=self.node.getFullName(), **{query: True})
        return data

    def _linked_attributes(self):
        """内部・外部接続とaliasを持つ3個の定義を作る。

        Returns:
            Node: 外部接続先を持つノード。
        """
        for name, value in (("first", 3.0), ("second", 2.0), ("third", 1.0)):
            self.node.addAttr(name, defaultValue=value, keyable=True)
        other = mlib.getNode(cmds.createNode("network", name=self.namespace + ":other"))
        target = other.addAttr("input")
        self.node.getPlug("first").connectTo(self.node.getPlug("second"))
        self.node.getPlug("second").connectTo(self.node.getPlug("third"))
        self.node.getPlug("third").connectTo(target)
        self.node.getPlug("first").setAlias("inputAlias")
        self.node.getPlug("third").setFlags(locked=True)
        return other

    def _assert_links(self, other):
        """現在の定義を再取得し、内部・外部の接続とaliasを確認する。

        Args:
            other (Node): 外部接続先の所有ノード。
        """
        for source, target in (("first", "second"), ("second", "third")):
            self.assertTrue(cmds.isConnected(self.node.getFullName() + "." + source, self.node.getFullName() + "." + target))
        self.assertTrue(cmds.isConnected(self.node.getFullName() + ".third", other.getFullName() + ".input"))
        self.assertEqual(self.node.getPlug("inputAlias"), self.node.getPlug("first"))
        self.assertTrue(self.node.getPlug("third").isLocked())
        self.assertEqual(other.getPlug("input").get(), 3.0)

    def _ordered_names(self):
        """Maya管理のalias保管領域を除く、ユーザー定義の並びを返す。

        Returns:
            list[str]: 表示順を変更するアトリビュート長名。
        """
        return [name for name in [p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)] if name != "attributeAliasList"]

    def test_move_preserves_short_name_limits_and_flags(self):
        """短名・soft limit・表示状態・定義フラグを再作成とUndoで保つ。"""
        cmds.addAttr(
            self.node.getFullName(),
            longName="firstValue",
            shortName="fv",
            niceName="First Value",
            attributeType="double",
            defaultValue=2,
            minValue=0,
            maxValue=10,
            softMinValue=1,
            softMaxValue=9,
            keyable=False,
            storable=False,
            hidden=True,
        )
        first = self.node.getPlug("firstValue")
        first.set(4)
        first.setFlags(channelBox=True, locked=True)
        self.node.addAttr("secondValue")
        before = self._definition("firstValue")
        self.assertIs(self.node.moveAttrOrder("firstValue", 1), self.node)
        self.assertEqual([p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)], ["secondValue", "firstValue"])
        self.assertEqual(self._definition("firstValue"), before)
        self.assertFalse(first.isValid())
        cmds.undo()
        self.assertEqual([p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)], ["firstValue", "secondValue"])
        self.assertEqual(self._definition("firstValue"), before)
        cmds.redo()
        self.assertEqual(self._definition("firstValue"), before)

    def test_move_restores_all_definitions_before_internal_connections(self):
        """作成順に逆らう内部接続も、全定義生成後に一度だけ復元する。"""
        other = self._linked_attributes()
        self.node.moveAttrOrder("first", 2)
        self.assertEqual(self._ordered_names(), ["second", "third", "first"])
        self._assert_links(other)
        cmds.undo()
        self.assertEqual(self._ordered_names(), ["first", "second", "third"])
        self._assert_links(other)
        cmds.redo()
        self._assert_links(other)

    def test_move_restores_non_writable_definition(self):
        """元のreadable/writable定義で作成し、cmdsで値を復元する。"""
        cmds.addAttr(self.node.getFullName(), longName="first", attributeType="double", defaultValue=4, writable=False, readable=False)
        self.node.addAttr("second")
        before = self._definition("first")
        self.node.moveAttrOrder("first", 1)
        self.assertEqual(self._definition("first"), before)

    def test_move_rolls_back_creation_failure_with_order_and_connections(self):
        """一部の再作成後の失敗でも、元の定義順・値・接続へ戻す。"""
        other = self._linked_attributes()
        module = importlib.import_module("mlib.nodes.node")
        original = module._create_movable_attr
        calls = []

        def fail_second(node, info):
            """2個目の再作成でMayaの編集失敗を模擬する。"""
            calls.append(info["longName"])
            if len(calls) == 2:
                raise RuntimeError("simulated recreation failure")
            return original(node, info)

        with patch.object(module, "_create_movable_attr", fail_second):
            with self.assertRaisesRegex(RuntimeError, "simulated recreation failure"):
                self.node.moveAttrOrder("first", 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self._ordered_names(), ["first", "second", "third"])
        self._assert_links(other)

    def test_move_rejects_non_connectable_definition_before_changes(self):
        """cmdsで再現できない特殊フラグを、定義削除前に拒否する。"""
        first = self.node.addAttr("first")
        self.node.addAttr("second")
        om2.MFnAttribute(first.mplug().attribute()).connectable = False
        before = [p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)]
        with self.assertRaisesRegex(TypeError, "接続できないアトリビュート"):
            self.node.moveAttrOrder("first", 1)
        self.assertEqual([p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)], before)
        self.assertTrue(first.isValid())

    def test_move_rejects_undo_disabled_before_changes(self):
        """復旧できないUndo無効時は、定義を削除する前に拒否する。"""
        self.node.addAttr("first")
        self.node.addAttr("second")
        # stateWithoutFlush=Falseは、Maya 2025/2027のmayapyで以後のcreateNodeの名前空間が外れるため、
        # Undoの切替えはstate=を使う。
        before = [p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)]
        cmds.undoInfo(state=False)
        try:
            with self.assertRaisesRegex(RuntimeError, "Undoが必要です"):
                self.node.moveAttrOrder("first", 1)
            self.assertFalse(cmds.undoInfo(query=True, state=True))
            self.assertEqual([p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)], before)
        finally:
            cmds.undoInfo(state=True)
        self.assertTrue(cmds.undoInfo(query=True, state=True))
        # 切替え後も専用名前空間の中にノードを作れる。
        probe = cmds.createNode("network", name=self.namespace + ":probe")
        self.assertEqual(probe, self.namespace + ":probe")
        # fast引数のない操作は外側の呼出しモードに依存せず通常Undoを使う。
        self.node.moveAttrOrder("first", 1)
        self.assertEqual([p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)], ["second", "first"])
        cmds.undo()
        self.assertEqual([p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)], before)

    def test_add_preflights_child_names_and_component_counts(self):
        """親追加前に子の重複・既存名・成分数・不正既定値を拒否する。"""
        self.node.addAttr("existing")
        attempts = [
            dict(childNames=["same", "same", "last"]),
            dict(childNames=["newFirst", "existing", "newLast"]),
            dict(childShortNames=["x", "x", "z"]),
            dict(childNames=["newFirst", "newSecond"]),
            dict(defaultValue=[1, 2]),
            dict(minValue=[0, 0]),
            dict(defaultValue=[1, "invalid", 3]),
        ]
        for fast in (False, True):
            for index, flags in enumerate(attempts):
                name = f"attempt_{int(fast)}_{index}"
                before = [p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)]
                with self.subTest(fast=fast, flags=flags):
                    with self.assertRaises((TypeError, ValueError, RuntimeError)):
                        self.node.addAttr(name, "double3", fast=fast, **flags)
                    self.assertEqual([p.getLongName() for p in self.node.getPlugs(userDefined=True, includeChildren=False)], before)

    def test_add_preflights_typed_defaults_and_keeps_default_return(self):
        """typed既定値を追加前に検証し、既定Plug返却とgetPlug=Falseを保つ。"""
        for fast in (False, True):
            for kind, value in (("matrix", [1, 2]), ("doubleArray", ["invalid"])):
                name = f"invalid_{int(fast)}_{kind}"
                with self.subTest(fast=fast, kind=kind):
                    with self.assertRaises((TypeError, ValueError, RuntimeError)):
                        self.node.addAttr(name, kind, defaultValue=value, fast=fast)
                    self.assertFalse(self.node.hasAttr(name))
        plug = self.node.addAttr("valid", "string", defaultValue="value")
        self.assertIsInstance(plug, mlib.StringPlug)
        self.assertEqual(plug.get(), "value")
        self.assertIsNone(self.node.addAttr("noReturn", getPlug=False))


class NodeApiTest(unittest.TestCase):
    """基本Node/DAG APIを検証する。"""

    namespace = ":mlibNodeApiTest"

    def setUp(self):
        self.created = []
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.namespace(add=self.namespace)

    def tearDown(self):
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)

    def create_transform(self, name):
        node = mlib.createNode(type="transform", name=name)
        self.created.append(node.getName())
        return node

    def assert_channels(self, name, rotate, scale, places=9):
        for actual, expected in zip(cmds.getAttr(name + ".rotate")[0], rotate):
            self.assertAlmostEqual(actual, expected, places=places)
        for actual, expected in zip(cmds.getAttr(name + ".scale")[0], scale):
            self.assertAlmostEqual(actual, expected, places=places)

    def test_move_attribute_reorders_and_preserves_state_and_connections(self):
        node = self.create_transform("mlibNodeApiMoveAttrNode")
        source = self.create_transform("mlibNodeApiMoveAttrSource")
        node.addAttr("attrA", attributeType="double", defaultValue=1.0, keyable=True)
        node.addAttr("attrB", attributeType="double", defaultValue=2.0, keyable=True)
        node.addAttr("attrC", attributeType="double", defaultValue=3.0, keyable=True)
        node.getPlug("attrB").set(5.0)
        node.getPlug("attrB").setFlags(locked=True)
        source.getPlug("translateX").set(7.0)
        source.getPlug("translateX").connectTo(node.getPlug("attrC"))
        self.assertEqual([p.getLongName() for p in node.getPlugs(userDefined=True, includeChildren=False)], ["attrA", "attrB", "attrC"])

        result = node.moveAttrOrder("attrC", -2)

        self.assertIs(result, node)
        self.assertEqual([p.getLongName() for p in node.getPlugs(userDefined=True, includeChildren=False)], ["attrC", "attrA", "attrB"])
        self.assertEqual(node.getPlug("attrA").get(), 1.0)
        self.assertEqual(node.getPlug("attrB").get(), 5.0)
        self.assertTrue(node.getPlug("attrB").isLocked())
        # attrC は接続で駆動されているため、再作成後も接続元の値がそのまま反映される。
        self.assertEqual(node.getPlug("attrC").get(), 7.0)
        reconnected_source = node.getPlug("attrC").getSource()
        self.assertIsNotNone(reconnected_source)
        self.assertEqual(reconnected_source.getFullName(), source.getPlug("translateX").getFullName())

    def test_move_attribute_supports_enum_and_string_attributes(self):
        node = self.create_transform("mlibNodeApiMoveAttrEnumString")
        node.addAttr("attrA", attributeType="double", defaultValue=0.0)
        node.addAttr("attrMode", attributeType="enum", enumName="Off:On:Auto", defaultValue=1)
        node.addAttr("attrLabel", dataType="string")
        node.getPlug("attrMode").set(2)
        node.getPlug("attrLabel").set("hello world")

        node.moveAttrOrder("attrMode", 1)

        self.assertEqual([p.getLongName() for p in node.getPlugs(userDefined=True, includeChildren=False)], ["attrA", "attrLabel", "attrMode"])
        self.assertEqual(node.getPlug("attrMode").get(), 2)
        self.assertEqual(node.getPlug("attrMode").getEnumName(), "Auto")
        self.assertEqual(node.getPlug("attrLabel").get(), "hello world")

    def test_move_attribute_offset_clamps_and_is_a_noop_within_bounds(self):
        node = self.create_transform("mlibNodeApiMoveAttrClamp")
        node.addAttr("attrA", attributeType="double", defaultValue=0.0)
        node.addAttr("attrB", attributeType="double", defaultValue=0.0)

        result = node.moveAttrOrder("attrA", 0)
        self.assertIs(result, node)
        self.assertEqual([p.getLongName() for p in node.getPlugs(userDefined=True, includeChildren=False)], ["attrA", "attrB"])

        node.moveAttrOrder("attrA", 100)
        self.assertEqual([p.getLongName() for p in node.getPlugs(userDefined=True, includeChildren=False)], ["attrB", "attrA"])

        node.moveAttrOrder("attrA", -100)
        self.assertEqual([p.getLongName() for p in node.getPlugs(userDefined=True, includeChildren=False)], ["attrA", "attrB"])

    def test_move_attribute_raises_for_unknown_name_and_unsupported_type(self):
        node = self.create_transform("mlibNodeApiMoveAttrErrors")
        node.addAttr("attrA", attributeType="double", defaultValue=0.0)
        cmds.addAttr(node.getFullName(), longName="attrCompound", attributeType="double3")
        cmds.addAttr(node.getFullName(), longName="attrCompoundX", attributeType="double", parent="attrCompound")
        cmds.addAttr(node.getFullName(), longName="attrCompoundY", attributeType="double", parent="attrCompound")
        cmds.addAttr(node.getFullName(), longName="attrCompoundZ", attributeType="double", parent="attrCompound")
        node.addAttr("attrB", attributeType="double", defaultValue=0.0)

        with self.assertRaises(ValueError):
            node.moveAttrOrder("doesNotExist", 1)

        with self.assertRaises(TypeError):
            node.moveAttrOrder("attrB", -1)
        # 型エラー時は何も削除・変更されていない(ダンプ段階での検証が先に走るため)。
        self.assertEqual([p.getLongName() for p in node.getPlugs(userDefined=True, includeChildren=False)], ["attrA", "attrCompound", "attrB"])


class EditRefactoringTest(unittest.TestCase):
    """専用名前空間のノードで公開入口の契約を確認する。"""

    def setUp(self):
        """他のシーン内容から独立した対象を作る。"""
        self.namespace = "mlibEditRefactor_" + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)
        self.names = [cmds.createNode("transform", name=self.namespace + ":node" + str(i)) for i in range(2)]

    def tearDown(self):
        """このテストが作ったノードだけを削除する。"""
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)

    def test_compound_creation_reenters_user_override_in_child_order(self):
        """子作成でも公開addAttrのoverrideとgetPlug=False指定を保つ。"""
        calls = []

        original = mlib.Node.addAttr

        def record_add_attr(node, *args, **kwargs):
            """呼出時に差し替えた公開入口でも子作成の入力を受け取る。"""
            calls.append((args, dict(kwargs)))
            return original(node, *args, **kwargs)

        node = mlib.Transform(self.names[0])
        with patch.object(mlib.Node, "addAttr", record_add_attr):
            plug = node.addAttr(
                "customVector",
                "double3",
                childNames=["redValue", "greenValue", "blueValue"],
                childShortNames=["rv", "gv", "bv"],
                defaultValue=(1, 2, 3),
                keyable=True,
            )
        self.assertEqual([row[0][0] for row in calls], ["customVector", "redValue", "greenValue", "blueValue"])
        self.assertTrue(all(row[1]["getPlug"] is False for row in calls[1:]))
        self.assertEqual([row[1]["shortName"] for row in calls[1:]], ["rv", "gv", "bv"])
        self.assertEqual(tuple(plug.get()), (1, 2, 3))
        cmds.undo()
        self.assertFalse(node.hasAttr("customVector"))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
