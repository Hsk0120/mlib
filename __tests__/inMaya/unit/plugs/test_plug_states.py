"""Plugの名前・状態フラグ・別名・ミュート・定義照会・有効性の約束を固定する。

期待値はmaya.cmdsとOpenMayaで独立に求めた値と比べる。
"""

import math
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib
from mlib import plugs
from mlib.plugs.plug import MAX_LOGICAL_INDEX, DeletedAttributeError, MissingAttributeError


class _StateSpecCase(unittest.TestCase):
    """専用の名前空間・Undo・単位・時刻を用意し、終了時に元へ戻す。"""

    def setUp(self):
        self.namespace = ":specBStates_" + uuid.uuid4().hex
        self.before = set(cmds.ls(long=True) or [])
        cmds.namespace(add=self.namespace)
        self.undo_state = cmds.undoInfo(query=True, state=True)
        self.units = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True), cmds.currentUnit(query=True, time=True))
        self.time = cmds.currentTime(query=True)
        cmds.undoInfo(state=True)
        cmds.currentUnit(linear="cm", angle="deg", time="film")
        self.node = self.make("transform")
        self.name = self.node.getName()

    def tearDown(self):
        cmds.currentUnit(linear=self.units[0], angle=self.units[1], time=self.units[2])
        cmds.currentTime(self.time)
        for name in sorted(set(cmds.ls(long=True) or []) - self.before, key=len, reverse=True):
            if cmds.objExists(name):
                try:
                    cmds.lockNode(name, lock=False)
                    cmds.delete(name)
                except RuntimeError:
                    pass  # Mayaが自動で作る削除できないノードは残す。
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.undoInfo(state=self.undo_state)

    def make(self, kind="network", **kwargs):
        """Mayaコマンドで作成したノードを取得する。"""
        return mlib.getNode(cmds.createNode(kind, name=self.namespace + ":n#", skipSelect=True, **kwargs))

    def assertUndoEmpty(self):
        """Undoの記録が追加されていないことを確かめる。"""
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))


class PlugNameSpecTest(_StateSpecCase):
    """名前の取得と、名前変更・親変更・別名への追従。"""

    def test_name_forms(self):
        """短い名前・ロング名・ニース名・Plug名とstrの対応。"""
        tx = self.node.getPlug("tx")
        self.assertEqual(tx.getName(), self.name + ".tx")
        self.assertFalse(hasattr(tx, "getAttrName"))
        self.assertEqual(tx.getAttributeName("short"), "tx")
        self.assertEqual(tx.getAttributeName(), "translateX")
        self.assertEqual(tx.getAttributeName("nice"), "Translate X")
        self.assertEqual(tx.getAttributeName("long"), "translateX")
        self.assertEqual(tx.getAttributeName(kind="short"), "tx")
        self.assertEqual(tx.getName(full=True), self.name + ".translateX")

    def test_attribute_name_kinds_match_cmds(self):
        """getAttributeName(kind)はcmds.attributeQuery・cmds.attributeNameと同じ名前。知らないkindはValueError。"""
        cmds.addAttr(self.name, longName="myWeight", shortName="mw", niceName="My Nice Weight", attributeType="double")
        cmds.addAttr(self.name, longName="items", shortName="its", attributeType="double", multi=True)
        for attribute, plug in (
            ("translateX", self.node.getPlug("tx")),
            ("translate", self.node.getPlug("t")),
            ("myWeight", self.node.getPlug("myWeight")),
            ("items", self.node.getPlug("items")),
            ("items", self.node.getPlug("items[3]")),
            ("worldMatrix", self.node.getPlug("worldMatrix[0]")),
        ):
            with self.subTest(plug=str(plug)):
                self.assertEqual(plug.getAttributeName(), cmds.attributeQuery(attribute, node=self.name, longName=True))
                self.assertEqual(plug.getAttributeName("long"), plug.getAttributeName())
                self.assertEqual(plug.getAttributeName("short"), cmds.attributeQuery(attribute, node=self.name, shortName=True))
                self.assertEqual(plug.getAttributeName("nice"), cmds.attributeName(str(plug), nice=True))
        self.assertEqual(self.node.getPlug("myWeight").getAttributeName("nice"), "My Nice Weight")
        tx = self.node.getPlug("tx")
        for kind in ("Long", "niceName", "", "full", None, 1):
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    tx.getAttributeName(kind)
        self.assertEqual(str(tx), tx.getName(full=True))
        self.assertEqual(repr(tx), f"DoubleLinearPlug({tx.getName(full=True)!r})")
        self.assertEqual(cmds.getAttr(tx), 0.0)

    def test_full_attribute_path_option(self):
        """コンパウンドアトリビュートの子でも getName(full=True) は最短のパス(全階層のパスを返す入口は無い)。"""
        child = self.node.getPlug("boundingBoxMinX")
        self.assertFalse(hasattr(child, "getPlugName"))
        self.assertEqual(child.getName(full=True), self.name + ".boundingBoxMinX")

    def test_element_and_child_names(self):
        """マルチアトリビュートの要素の子は必要な論理番号を含む名前になる。"""
        cmds.addAttr(self.name, longName="items", shortName="its", attributeType="compound", numberOfChildren=1, multi=True)
        cmds.addAttr(self.name, longName="weight", shortName="wt", attributeType="double", parent="items")
        child = self.node.getPlug("items[3].weight")
        self.assertEqual(child.getName(full=True), self.name + ".items[3].weight")
        self.assertEqual(child.getName(), self.name + ".its[3].wt")
        self.assertEqual(child.getAttributeName("short"), "wt")
        self.assertEqual(child.getParent().getName(full=True), self.name + ".items[3]")

    def test_world_space_element_names_keep_index(self):
        """worldSpaceの要素もgetNameで論理番号を省かない。アトリビュート部分はgetPlugへ戻せる。"""
        element = self.node.getPlug("worldMatrix[0]")
        self.assertEqual(element.getName(), self.name + ".wm[0]")
        self.assertEqual(element.getAttributeName("short"), "wm")
        self.assertEqual(self.node.getPlug(element.getName().partition(".")[2]), element)
        self.assertEqual(self.node.getPlug("worldMatrix").getName(), self.name + ".wm")

    def test_names_follow_rename_and_reparent(self):
        """名前変更・親変更・Undoに追従し、DAGパスは一意になる最短の形を使う。"""
        group = cmds.createNode("transform", name=self.namespace + ":grp", skipSelect=True)
        tx = self.node.getPlug("tx")
        cmds.parent(self.name, group)
        same = cmds.createNode("transform", name=self.name.split(":")[-1], skipSelect=True)
        cmds.namespace(set=self.namespace)
        try:
            same_in_namespace = cmds.createNode("transform", name=self.name.split(":")[-1], skipSelect=True)
        finally:
            cmds.namespace(set=":")
        self.assertTrue(cmds.objExists(same))
        self.assertTrue(tx.getName(full=True).endswith(self.name + ".translateX"))
        self.assertEqual(len(cmds.ls(tx.getName(full=True))), 1)
        cmds.delete(same_in_namespace)
        cmds.flushUndo()
        renamed = cmds.rename(self.node.getName(full=True), self.namespace + ":renamed")
        self.assertEqual(tx.getName(full=True), renamed + ".translateX")
        cmds.undo()
        self.assertTrue(tx.getName(full=True).endswith(self.name + ".translateX"))

    def test_alias_is_used_by_full_name_only(self):
        """別名があればgetName(full=True)は別名を使い、getName・getAttributeNameは元の名前。"""
        cmds.aliasAttr("myAlias", self.name + ".ty")
        ty = self.node.getPlug("ty")
        self.assertEqual(ty.getName(full=True), self.name + ".myAlias")
        self.assertEqual(ty.getName(), self.name + ".ty")
        self.assertEqual(ty.getAttributeName(), "translateY")
        self.assertEqual(self.node.getPlug("myAlias"), ty)


class PlugFlagSpecTest(_StateSpecCase):
    """setFlags(keyable・channelBox・locked・children・leaf)・getFlags・setLocked。"""

    def state(self, attribute="tx"):
        """(keyable, channelBox) をcmdsで読む。"""
        return (cmds.getAttr(f"{self.name}.{attribute}", keyable=True), cmds.getAttr(f"{self.name}.{attribute}", channelBox=True))

    def test_keyable_and_channel_box_are_exclusive(self):
        """setFlags(channelBox=True)はkeyableを外し、setFlags(keyable=True)はchannelBoxを外す。値を返さない。"""
        tx = self.node.getPlug("tx")
        self.assertTrue(tx.getFlags()["keyable"])
        self.assertFalse(tx.getFlags()["channelBox"])
        self.assertIsNone(tx.setFlags(channelBox=True))
        self.assertEqual(self.state(), (False, True))
        self.assertIsNone(tx.setFlags(keyable=True))
        self.assertEqual(self.state(), (True, False))
        self.assertIsNone(tx.setFlags(keyable=False))
        self.assertFalse(tx.getFlags()["keyable"])
        self.assertFalse(tx.getFlags()["channelBox"])
        # channelBox=False はkeyableを変えない(keyableなら、Channel Boxには出たまま)。
        tx.setFlags(keyable=True)
        tx.setFlags(channelBox=False)
        self.assertEqual(self.state(), (True, False))
        # 両方を明示したときは、渡した値のまま書く。
        tx.setFlags(keyable=False, channelBox=True)
        self.assertEqual(self.state(), (False, True))
        tx.setFlags(keyable=False, channelBox=False)
        self.assertEqual(self.state(), (False, False))

    def test_get_flags_matches_cmds(self):
        """getFlagsは locked・keyable・channelBox・hidden の新しい辞書で、cmds.getAttrの各フラグと一致する。"""
        tx = self.node.getPlug("tx")
        steps = ({}, {"channelBox": True}, {"keyable": True, "locked": True}, {"keyable": False, "channelBox": False}, {"locked": False})
        for flags in steps:
            with self.subTest(flags=flags):
                if flags:
                    tx.setFlags(**flags)
                result = tx.getFlags()
                self.assertEqual(sorted(result), ["channelBox", "hidden", "keyable", "locked"])
                self.assertTrue(all(type(value) is bool for value in result.values()))
                keyable, channel_box = self.state()
                expected = {"locked": cmds.getAttr(self.name + ".tx", lock=True), "keyable": keyable, "channelBox": channel_box}
                expected["hidden"] = not (keyable or channel_box)
                self.assertEqual(result, expected)
                self.assertEqual(result["locked"], tx.isLocked())
                self.assertIsNot(tx.getFlags(), result)
        with self.assertRaises(TypeError):
            tx.getFlags(True)

    def test_flag_undo_and_fast(self):
        """通常の変更は1回のUndoで両方のフラグが元の組み合わせへ戻り、fastは記録しない。"""
        tx = self.node.getPlug("tx")
        cmds.flushUndo()
        tx.setFlags(channelBox=True)
        cmds.undo()
        self.assertEqual(self.state(), (True, False))
        self.assertUndoEmpty()
        cmds.redo()
        self.assertEqual(self.state(), (False, True))
        # Channel Box表示からkeyableへ(2回の書き込み)も、1回のUndoで (keyable=False, channelBox=True) へ戻る。
        cmds.flushUndo()
        tx.setFlags(keyable=True)
        self.assertEqual(self.state(), (True, False))
        cmds.undo()
        self.assertEqual(self.state(), (False, True))
        self.assertUndoEmpty()
        cmds.redo()
        self.assertEqual(self.state(), (True, False))
        cmds.undo()
        # 隠した状態からの keyable=True・channelBox=True も1回で戻る。
        for flags, expected in (({"keyable": True}, (True, False)), ({"channelBox": True}, (False, True))):
            with self.subTest(flags=flags):
                tx.setFlags(keyable=False, channelBox=False)
                cmds.flushUndo()
                tx.setFlags(**flags)
                self.assertEqual(self.state(), expected)
                cmds.undo()
                self.assertEqual(self.state(), (False, False))
                self.assertUndoEmpty()
        cmds.flushUndo()
        tx.setFlags(channelBox=True, fast=True)
        tx.setLocked(True, fast=True)
        self.assertEqual(self.state(), (False, True))
        self.assertTrue(cmds.getAttr(self.name + ".tx", lock=True))
        tx.setFlags(keyable=True, fast=True)
        self.assertEqual(self.state(), (True, False))
        self.assertUndoEmpty()

    def test_leaf_applies_to_children(self):
        """leaves=Trueはコンパウンドアトリビュートの子へ設定し、親自身は変えない。leaves=Falseは親だけを変える。"""
        translate = self.node.getPlug("translate")
        translate.setLocked(True, leaves=True)
        self.assertEqual([cmds.getAttr(self.name + ".t" + a, lock=True) for a in "xyz"], [True] * 3)
        self.assertFalse(cmds.getAttr(self.name + ".t", lock=True))
        translate.setLocked(False)
        self.assertEqual([cmds.getAttr(self.name + ".t" + a, lock=True) for a in "xyz"], [True] * 3)
        translate.setLocked(False, leaves=True)
        parent_state = self.state("t")
        translate.setFlags(keyable=False, leaves=True)
        self.assertEqual([cmds.getAttr(self.name + ".t" + a, keyable=True) for a in "xyz"], [False] * 3)
        self.assertEqual(self.state("t"), parent_state)
        translate.setFlags(channelBox=True, leaves=True)
        self.assertEqual([cmds.getAttr(self.name + ".t" + a, channelBox=True) for a in "xyz"], [True] * 3)
        self.assertEqual(self.state("t"), parent_state)
        with self.assertRaises(TypeError):
            translate.setFlags(keyable=True, children=True, leaves=True)
        self.assertEqual([cmds.getAttr(self.name + ".t" + a, keyable=True) for a in "xyz"], [False] * 3)

    def test_set_flags_validation(self):
        """setFlagsは省略した状態を変えず、bool・None以外は変更前にTypeError。"""
        tx = self.node.getPlug("tx")
        self.assertIsNone(tx.setFlags())
        tx.setFlags(locked=True, keyable=False)
        self.assertTrue(cmds.getAttr(self.name + ".tx", lock=True))
        self.assertFalse(cmds.getAttr(self.name + ".tx", keyable=True))
        tx.setFlags(locked=False, fast=True)
        self.assertFalse(cmds.getAttr(self.name + ".tx", lock=True))
        self.assertFalse(cmds.getAttr(self.name + ".tx", keyable=True))
        for kwargs in (dict(locked=1), dict(keyable="yes"), dict(channelBox=0), dict(fast=None)):
            with self.subTest(**kwargs):
                with self.assertRaises(TypeError):
                    tx.setFlags(**kwargs)
        for label, method in (
            ("setLocked", tx.setLocked),
            ("keyable", lambda state, **kw: tx.setFlags(keyable=state, **kw)),
            ("channelBox", lambda state, **kw: tx.setFlags(channelBox=state, **kw)),
        ):
            with self.subTest(method=label):
                with self.assertRaises(TypeError):
                    method(1)
                with self.assertRaises(TypeError):
                    method(True, fast=1)
        self.assertFalse(cmds.getAttr(self.name + ".tx", lock=True))

    def test_locked_inherits_from_parent_in_query(self):
        """親がロックされていると子のisLockedもTrue(MPlugの判定)。"""
        cmds.setAttr(self.name + ".t", lock=True)
        self.assertTrue(self.node.getPlug("tx").isLocked())
        self.assertEqual(self.node.getPlug("tx").isLocked(), cmds.getAttr(self.name + ".tx", lock=True))


class PlugAliasSpecTest(_StateSpecCase):
    """setAliasの設定・解除・Undo・fast。"""

    def test_set_and_remove_alias(self):
        """別名を設定し、Noneまたは空文字列で解除する。別名が無い解除は何もしない。"""
        tz = self.node.getPlug("tz")
        self.assertIsNone(tz.setAlias("zAlias"))
        self.assertEqual(cmds.aliasAttr(self.name, query=True), ["zAlias", "translateZ"])
        self.assertEqual(tz.getName(full=True), self.name + ".zAlias")
        self.assertIsNone(tz.setAlias())
        self.assertIsNone(cmds.aliasAttr(self.name, query=True))
        tz.setAlias("zAlias")
        tz.setAlias("")
        self.assertIsNone(cmds.aliasAttr(self.name, query=True))
        self.assertIsNone(tz.setAlias(None))
        self.assertEqual(tz.getName(full=True), self.name + ".translateZ")

    def test_alias_undo_fast_and_errors(self):
        """通常の設定は1回のUndoで戻り、fastは記録しない。既存名と重なる別名はRuntimeError。"""
        sx = self.node.getPlug("sx")
        cmds.flushUndo()
        sx.setAlias("sxa")
        cmds.undo()
        self.assertIsNone(cmds.aliasAttr(self.name, query=True))
        cmds.flushUndo()
        sx.setAlias("sxb", fast=True)
        self.assertEqual(cmds.aliasAttr(self.name, query=True), ["sxb", "scaleX"])
        sx.setAlias(None, fast=True)
        self.assertIsNone(cmds.aliasAttr(self.name, query=True))
        self.assertUndoEmpty()
        with self.assertRaises(RuntimeError):
            sx.setAlias("tx")
        with self.assertRaises(TypeError):
            sx.setAlias("x", fast=1)


class PlugMuteSpecTest(_StateSpecCase):
    """setMuted・isMuted(mute・unmuteは無い)。"""

    def setUp(self):
        super().setUp()
        self.sz = self.node.getPlug("sz")
        cmds.setKeyframe(self.name + ".sz", time=1, value=2)
        cmds.setKeyframe(self.name + ".sz", time=10, value=4)
        cmds.currentTime(5)

    def test_mute_holds_current_value_and_unmute_restores_animation(self):
        """setMuted(True)は現在値で固定し、setMuted(False)はアニメーションへ戻す。繰り返しても状態は同じ。"""
        held = cmds.getAttr(self.name + ".sz")
        self.assertIsNone(self.sz.setMuted(True))
        self.assertTrue(self.sz.isMuted())
        self.assertTrue(cmds.mute(self.name + ".sz", query=True))
        cmds.currentTime(10)
        self.assertAlmostEqual(self.sz.get(), held)
        self.sz.setMuted(True)
        self.assertTrue(self.sz.isMuted())
        self.assertIsNone(self.sz.setMuted(False))
        self.assertFalse(self.sz.isMuted())
        self.assertAlmostEqual(self.sz.get(), 4.0)
        self.assertIsNone(self.sz.setMuted(False))
        self.assertFalse(self.sz.isMuted())

    def test_mute_undo(self):
        """通常のmuteは1回のUndoで戻る。"""
        cmds.flushUndo()
        self.sz.setMuted(True)
        cmds.undo()
        self.assertFalse(self.sz.isMuted())
        self.assertFalse(cmds.mute(self.name + ".sz", query=True))

    def test_argument_errors(self):
        """bool以外の状態とfast引数(持たない)はTypeErrorで、状態を変えない。"""
        for call in (lambda: self.sz.setMuted(1), lambda: self.sz.setMuted(True, fast=True)):
            with self.assertRaises(TypeError):
                call()
        self.assertFalse(self.sz.isMuted())

    def test_mute_without_animation_is_silent_noop(self):
        """アニメーションの無いチャンネルのmuteはMayaが警告して何もせず、自身を返す。"""
        sy = self.node.getPlug("sy")
        self.assertIsNone(sy.setMuted(True))
        self.assertFalse(sy.isMuted())
        self.assertFalse(cmds.listConnections(self.name + ".sy", source=True, destination=False))

    def test_is_muted_only_for_mute_node(self):
        """isMutedは直接の入力がmuteノードの場合だけTrue。"""
        other = self.make("transform")
        cmds.connectAttr(other.getName() + ".sx", self.name + ".sx")
        self.assertFalse(self.node.getPlug("sx").isMuted())
        self.assertFalse(self.node.getPlug("sy").isMuted())


class PlugDefinitionQuerySpecTest(_StateSpecCase):
    """定義の照会(範囲)・Channel Boxの表示(getFlagsのhidden)と構造の判定。"""

    def test_hidden_matches_channel_box_flags(self):
        """getFlags()["hidden"]はkeyableでもChannel Box表示でもないときTrue(attributeQueryのhiddenではない)。"""
        tx = self.node.getPlug("tx")
        self.assertFalse(tx.getFlags()["hidden"])
        self.assertTrue(self.node.getPlug("worldMatrix").getFlags()["hidden"])
        cmds.addAttr(self.name, longName="defHidden", attributeType="double", hidden=True, keyable=True)
        # 定義のhiddenフラグとは別(keyableならChannel Boxに出る扱い)。
        self.assertTrue(cmds.attributeQuery("defHidden", node=self.name, hidden=True))
        self.assertFalse(self.node.getPlug("defHidden").getFlags()["hidden"])
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.assertIsNone(tx.setFlags(keyable=False, channelBox=False, children=True, fast=fast))
                self.assertTrue(tx.getFlags()["hidden"])
                tx.setFlags(keyable=True, children=True, fast=fast)
                self.assertFalse(tx.getFlags()["hidden"])
                self.assertEqual((cmds.getAttr(tx, keyable=True), cmds.getAttr(tx, channelBox=True)), (True, False))
                tx.setFlags(channelBox=True, children=True, fast=fast)
                self.assertFalse(tx.getFlags()["hidden"])
                self.assertEqual((cmds.getAttr(tx, keyable=True), cmds.getAttr(tx, channelBox=True)), (False, True))
                self.assertEqual(tx.getFlags()["hidden"], not (cmds.getAttr(tx, keyable=True) or cmds.getAttr(tx, channelBox=True)))
                tx.setFlags(keyable=True, children=True, fast=fast)

    def test_hidden_for_compound(self):
        """コンパウンドアトリビュートは子孫の末端がすべて隠れているときTrue。"""
        translate = self.node.getPlug("t")
        self.assertFalse(translate.getFlags()["hidden"])
        translate.setFlags(keyable=False, channelBox=False, children=True)
        self.assertTrue(translate.getFlags()["hidden"])
        self.node.getPlug("ty").setFlags(keyable=True)
        self.assertFalse(translate.getFlags()["hidden"])
        # 親だけを隠しても、子が表示されていればChannel Boxに出る。
        translate.setFlags(keyable=True, children=True)
        translate.setFlags(keyable=False, channelBox=False)
        self.assertFalse(translate.getFlags()["hidden"])
        # 子(末端)だけを隠すと、親のフラグが残っていても隠れている扱い。
        translate.setFlags(keyable=True)
        translate.setFlags(keyable=False, channelBox=False, leaves=True)
        self.assertTrue(cmds.getAttr(self.name + ".t", keyable=True))
        self.assertTrue(translate.getFlags()["hidden"])

    def test_structure_predicates(self):
        """isMulti・isCompoundと、その element=True・child=True はMPlugの構造を返す。"""
        world = self.node.getPlug("worldMatrix")
        self.assertEqual((world.isMulti(), world.isCompound(), world.isMulti(element=True), world.isCompound(child=True)), (True, False, False, False))
        element = world[0]
        self.assertEqual((element.isMulti(), element.isMulti(element=True)), (False, True))
        tx = self.node.getPlug("tx")
        self.assertEqual((tx.isCompound(child=True), tx.isCompound()), (True, False))
        self.assertTrue(self.node.getPlug("translate").isCompound())
        self.assertIsNone(self.node.getPlug("translate").getParent())
        for plug in (world, element, tx, self.node.getPlug("translate")):
            with self.subTest(plug=str(plug)):
                mplug = plug.mplug()
                self.assertEqual(
                    (plug.isMulti(), plug.isMulti(element=True), plug.isCompound(), plug.isCompound(child=True)),
                    (mplug.isArray, mplug.isElement, mplug.isCompound, mplug.isChild),
                )
        for call in (lambda: tx.isMulti(True), lambda: tx.isCompound(True)):
            with self.assertRaises(TypeError):
                call()

    def test_numeric_ranges(self):
        """数値の範囲はfloat、無い側はNone。softの有無で制限とソフトリミットを分けて返す。"""
        cmds.addAttr(self.name, longName="rng", attributeType="double", minValue=-1, maxValue=2, softMinValue=0, softMaxValue=1)
        cmds.addAttr(self.name, longName="soft", attributeType="double", softMinValue=-5, softMaxValue=5)
        rng, soft = self.node.getPlug("rng"), self.node.getPlug("soft")
        self.assertEqual(rng.getRange(), (-1.0, 2.0))
        self.assertEqual(rng.getRange(soft=True), (0.0, 1.0))
        self.assertEqual(rng.getRange(soft=False), rng.getRange())
        self.assertTrue(all(type(value) is float for value in rng.getRange() + rng.getRange(soft=True)))
        self.assertEqual(soft.getRange(), (None, None))
        self.assertEqual(soft.getRange(soft=True), (-5.0, 5.0))
        tx = self.node.getPlug("tx")
        self.assertEqual(tx.getRange(), (None, None))
        self.assertEqual(tx.getRange(soft=True), (None, None))
        self.assertEqual(self.node.getPlug("visibility").getRange()[0], 0.0)
        # 片側だけの制限は、無い側だけがNone。cmds.attributeQueryと突き合わせる。
        cmds.addAttr(self.name, longName="low", attributeType="double", minValue=-3)
        cmds.addAttr(self.name, longName="high", attributeType="double", softMaxValue=7)
        self.assertEqual(self.node.getPlug("low").getRange(), (-3.0, None))
        self.assertEqual(self.node.getPlug("high").getRange(soft=True), (None, 7.0))
        for name in ("rng", "soft", "low", "high"):
            with self.subTest(attribute=name):

                def query(exists, value, name=name):
                    return (
                        cmds.attributeQuery(name, node=self.name, **{value: True})[0] if cmds.attributeQuery(name, node=self.name, **{exists: True}) else None
                    )

                plug = self.node.getPlug(name)
                self.assertEqual(plug.getRange(), (query("minExists", "minimum"), query("maxExists", "maximum")))
                self.assertEqual(plug.getRange(soft=True), (query("softMinExists", "softMin"), query("softMaxExists", "softMax")))
        with self.assertRaises(TypeError):
            rng.getRange(True)

    def test_unit_ranges_return_numbers(self):
        """角度・距離・時間の範囲は get() と同じ規則の数値で返す(角度は度・距離はcm・時間はフレーム)。"""
        cmds.addAttr(self.name, longName="angleLimit", attributeType="doubleAngle", minValue=-1, maxValue=1)
        cmds.addAttr(self.name, longName="lengthLimit", attributeType="doubleLinear", minValue=-2, maxValue=3)
        angle, length = self.node.getPlug("angleLimit"), self.node.getPlug("lengthLimit")
        for value in (angle.getRange()[0], angle.getRange()[1], length.getRange()[0], length.getRange()[1]):
            self.assertIsInstance(value, float)
        self.assertAlmostEqual(angle.getRange()[0], math.degrees(-1.0))
        self.assertAlmostEqual(angle.getRange(unit="rad")[1], 1.0)
        self.assertAlmostEqual(length.getRange()[0], -2.0)
        self.assertAlmostEqual(length.getRange()[1], 3.0)
        previous = cmds.currentUnit(query=True, linear=True)
        try:
            # cm 以外の UI 単位でも、既定は get() と同じ cm、uiUnits=True は UI 単位。
            cmds.currentUnit(linear="mm")
            self.assertAlmostEqual(length.getRange()[1], 3.0)
            self.assertAlmostEqual(length.getRange(uiUnits=True)[1], 30.0)
        finally:
            cmds.currentUnit(linear=previous)

    def test_time_ranges_return_frames(self):
        """時間の範囲は現在のUI時間単位のフレーム、timeUnit="sec" は秒。"""
        previous = cmds.currentUnit(query=True, time=True)
        try:
            cmds.currentUnit(time="film")
            cmds.addAttr(self.name, longName="timeLimit", attributeType="time", minValue=0, maxValue=48)
            plug = self.node.getPlug("timeLimit")
            self.assertAlmostEqual(plug.getRange()[1], 48.0)
            self.assertAlmostEqual(plug.getRange(timeUnit="sec")[1], 2.0)
            self.assertIsInstance(plug.getRange()[0], float)
        finally:
            cmds.currentUnit(time=previous)

    def test_ranges_of_non_numeric_types(self):
        """文字列・マトリクス・messageには範囲が無い。"""
        cmds.addAttr(self.name, longName="txt", dataType="string")
        for attr in ("txt", "message", "worldMatrix"):
            with self.subTest(attr=attr):
                plug = self.node.getPlug(attr)
                self.assertEqual(plug.getRange(), (None, None))
                self.assertEqual(plug.getRange(soft=True), (None, None))

    def test_identity_get_node_and_mplug(self):
        """getNodeは所有Nodeそのもの、mplugは保持中のMPlug。同じアトリビュートは等しくハッシュも同じ。"""
        tx = self.node.getPlug("tx")
        self.assertIs(tx.getNode(), self.node)
        self.assertIsInstance(tx.mplug(), om2.MPlug)
        self.assertIs(tx.mplug(), tx.mplug())
        other = self.node.getPlug("translateX")
        self.assertEqual(tx, other)
        self.assertEqual(hash(tx), hash(other))
        self.assertNotEqual(tx, self.node.getPlug("ty"))
        self.assertNotEqual(tx, "tx")
        self.assertEqual(len({tx, other}), 1)
        self.assertEqual(MAX_LOGICAL_INDEX, 2147483647)


class PlugValiditySpecTest(_StateSpecCase):
    """削除済みのノード・アトリビュート、Undo・Redoでの有効性と例外。"""

    def test_deleted_dynamic_attribute(self):
        """deleteAttr後はisValid=False・名前は空・値と照会はRuntimeError。構造の判定は例外にしない。"""
        cmds.addAttr(self.name, longName="dynValue", attributeType="double")
        plug = self.node.getPlug("dynValue")
        plug.set(3)
        cmds.flushUndo()
        cmds.deleteAttr(self.name + ".dynValue")
        self.assertFalse(plug.isValid())
        self.assertEqual((plug.getName(full=True), plug.getName(), str(plug)), ("", "", ""))
        self.assertEqual(repr(plug), "<DoublePlug invalid>")
        self.assertFalse(plug.isMulti())
        self.assertIs(type(plug), plugs.DoublePlug)
        for method in (
            "get",
            "getAttributeName",
            "getType",
            "getParent",
            "isLocked",
            "getFlags",
            "isConnected",
            "getConnections",
            "getDefault",
            "getRange",
            "isSettable",
            "getAnimCurve",
            "isMuted",
            "reset",
            "delete",
            "disconnectAll",
        ):
            with self.subTest(method=method):
                with self.assertRaises(RuntimeError):
                    getattr(plug, method)()
        self.assertFalse(plug.isValid(elements=True))
        self.assertFalse(plug.isMulti(element=True))
        self.assertFalse(plug.isCompound(child=True))
        for call in (
            lambda: plug.getAttributeName("short"),
            lambda: plug.getAttributeName("nice"),
            lambda: plug.getParent(all=True),
            lambda: plug.isConnected(source=False),
            lambda: plug.isConnected(destination=False),
            lambda: plug.getConnections(input=True),
            lambda: plug.getConnections(output=True),
            lambda: plug.getRange(soft=True),
            lambda: plug.setRange(0.0),
            lambda: plug.setFlags(keyable=True),
            lambda: plug.getAnimCurve(suitableType=True),
            lambda: plug.disconnectAll(destination=False),
            lambda: plug.disconnectAll(destination=False, fast=True),
            lambda: plug.set(1),
            lambda: plug.set(1, fast=True),
            lambda: plug.setLocked(True),
            lambda: plug.setIfChanged(2.0),
            lambda: plug.getEnumNames(value=0),
            lambda: plug.connect(self.node.getPlug("tx")),
        ):
            with self.assertRaises(RuntimeError):
                call()
        self.assertEqual(plug.set(1, safe=True), 1)
        with self.assertRaises(DeletedAttributeError):
            mlib.getNode(plug)
        cmds.undo()
        self.assertTrue(plug.isValid())
        self.assertEqual(plug.get(), 3.0)
        self.assertEqual(plug.getName(full=True), self.name + ".dynValue")
        cmds.redo()
        self.assertFalse(plug.isValid())

    def test_readded_attribute_is_different(self):
        """同じ名前で追加し直したアトリビュートは別のアトリビュートで、古い参照は無効のまま。"""
        cmds.addAttr(self.name, longName="dynValue", attributeType="double")
        old = self.node.getPlug("dynValue")
        cmds.deleteAttr(self.name + ".dynValue")
        cmds.addAttr(self.name, longName="dynValue", attributeType="double")
        new = self.node.getPlug("dynValue")
        self.assertFalse(old.isValid())
        self.assertTrue(new.isValid())
        self.assertNotEqual(old, new)

    def test_deleted_attribute_error_types(self):
        """DeletedAttributeErrorはValueErrorだけの派生(クラスの親は1つ)。"""
        self.assertEqual(DeletedAttributeError.__bases__, (ValueError,))
        self.assertFalse(issubclass(DeletedAttributeError, RuntimeError))

    def test_missing_attribute_error_is_shared(self):
        """存在しないアトリビュートは mlib.getPlug・node.getPlug とも MissingAttributeError で文言も同じ。"""
        self.assertEqual(MissingAttributeError.__bases__, (AttributeError,))
        self.assertFalse(issubclass(MissingAttributeError, RuntimeError))
        expected = f"アトリビュートが見つかりません: {self.name}.nope"
        for label, call in (("mlib.getPlug", lambda: mlib.getPlug(self.name + ".nope")), ("Node.getPlug", lambda: self.node.getPlug("nope"))):
            for error in (MissingAttributeError, AttributeError):
                with self.subTest(call=label, error=error.__name__):
                    with self.assertRaises(error) as context:
                        call()
                    self.assertIs(type(context.exception), MissingAttributeError)
                    self.assertEqual(str(context.exception), expected)
        self.assertFalse(self.node.hasAttr("nope"))
        # 属性参照は候補つきのAttributeErrorで、原因にMissingAttributeErrorを持つ。無関係な候補は出さない。
        with self.assertRaises(AttributeError) as context:
            self.node.nope
        self.assertIsInstance(context.exception.__cause__, MissingAttributeError)
        self.assertNotIn("近い名前", str(context.exception))

    def test_deleted_node(self):
        """所有ノードの削除後は無効、Undoで同じ参照が再び有効になる。"""
        node = self.make("transform")
        tx = node.getPlug("tx")
        tx.set(4)
        cmds.flushUndo()
        cmds.delete(node.getName(full=True))
        self.assertFalse(tx.isValid())
        self.assertEqual(tx.getName(full=True), "")
        self.assertEqual(repr(tx), "<DoubleLinearPlug invalid>")
        self.assertFalse(tx.isMulti())
        with self.assertRaises(RuntimeError):
            tx.get()
        with self.assertRaises(RuntimeError):
            tx.getAttributeName()
        with self.assertRaises(RuntimeError):
            tx.set(1)
        cmds.undo()
        self.assertTrue(tx.isValid())
        self.assertEqual(tx.get(), 4.0)
        self.assertEqual(cmds.getAttr(tx), 4.0)

    def test_plug_constructor_rejects_foreign_mplug(self):
        """所有ノードではないNodeとMPlugの組はRuntimeError。"""
        other = self.make("transform")
        with self.assertRaises(RuntimeError):
            plugs.Plug(self.node, other.getPlug("tx").mplug())

    def test_missing_element_reference_is_valid(self):
        """未作成のマルチアトリビュートの要素の参照は有効で、名前を返す。"""
        net = self.make("network")
        cmds.addAttr(net.getName(), longName="vals", attributeType="double", multi=True)
        element = net.getPlug("vals")[20]
        self.assertTrue(element.isValid())
        self.assertEqual(element.getName(full=True), net.getName() + ".vals[20]")
        self.assertEqual(cmds.getAttr(net.getName() + ".vals", multiIndices=True), None)


class PlugDeleteSpecTest(_StateSpecCase):
    """Plug.deleteによる動的アトリビュートの削除。"""

    def test_delete_undo_and_lock(self):
        """deleteはNoneを返して1回のUndoで戻る。ロック中はforce/fが必要。"""
        cmds.addAttr(self.name, longName="extra", attributeType="double")
        plug = self.node.getPlug("extra")
        cmds.flushUndo()
        self.assertIsNone(plug.delete())
        self.assertFalse(cmds.attributeQuery("extra", node=self.name, exists=True))
        cmds.undo()
        self.assertTrue(plug.isValid())
        cmds.setAttr(self.name + ".extra", lock=True)
        with self.assertRaises(RuntimeError):
            plug.delete()
        self.assertTrue(cmds.attributeQuery("extra", node=self.name, exists=True))
        plug.delete(unlock=True)
        self.assertFalse(plug.isValid())

    def test_delete_fast_and_errors(self):
        """fastはUndoへ記録しない。静的・子アトリビュートとロックは拒否、force/f重複はTypeError。"""
        cmds.addAttr(self.name, longName="extra", attributeType="double")
        cmds.addAttr(self.name, longName="locked", attributeType="double")
        cmds.setAttr(self.name + ".locked", lock=True)
        cmds.flushUndo()
        self.node.getPlug("extra").delete(fast=True)
        self.assertFalse(cmds.attributeQuery("extra", node=self.name, exists=True))
        self.assertUndoEmpty()
        with self.assertRaises(RuntimeError):
            self.node.getPlug("locked").delete(fast=True)
        self.node.getPlug("locked").delete(fast=True, unlock=True)
        self.assertFalse(cmds.attributeQuery("locked", node=self.name, exists=True))
        with self.assertRaises(RuntimeError):
            self.node.getPlug("message").delete()
        with self.assertRaises(RuntimeError):
            self.node.getPlug("message").delete(fast=True)
        with self.assertRaises(RuntimeError):
            self.node.getPlug("tx").delete(fast=True)
        with self.assertRaises(TypeError):
            self.node.getPlug("message").delete(fast=1)

    def test_delete_connected_attribute_disconnects(self):
        """接続があるアトリビュートもMayaが切断して削除する。"""
        cmds.addAttr(self.name, longName="extra", attributeType="double")
        other = self.make("transform")
        cmds.connectAttr(self.name + ".extra", other.getName() + ".tx")
        self.node.getPlug("extra").delete()
        self.assertFalse(cmds.listConnections(other.getName() + ".tx", source=True, destination=False))


class PlugSetKeySpecTest(_StateSpecCase):
    """setKeyの通常経路。fast引数は無い。"""

    def test_set_key(self):
        """setKeyは自身を返しキーを作る。時間はUI単位のフレーム、値はget()と同じcm(uiUnits=TrueはUI単位)。"""
        cmds.currentUnit(linear="mm")
        tz = self.node.getPlug("tz")
        self.assertIsNone(tz.setKey(t=5, v=2))
        self.assertEqual(cmds.keyframe(self.name + ".tz", query=True, timeChange=True), [5.0])
        self.assertEqual(cmds.keyframe(self.name + ".tz", query=True, valueChange=True), [20.0])
        tz.setKey(t=5, v=20, uiUnits=True)
        self.assertEqual(cmds.keyframe(self.name + ".tz", query=True, valueChange=True), [20.0])
        with self.assertRaises(ValueError):
            tz.setKey(t=5, v=1, unit="rad", uiUnits=True)
        cmds.currentUnit(linear="cm")
        rx = self.node.getPlug("rx")
        rx.setKey(t=1, v=90)
        self.assertAlmostEqual(cmds.keyframe(self.name + ".rx", query=True, valueChange=True)[0], 90.0)
        rx.setKey(t=2, v=1.0, unit="rad")
        self.assertAlmostEqual(cmds.getAttr(self.name + ".rx", time=2), 57.29577951308232)
        cmds.currentUnit(linear="mm")
        tz.setKey(time=10, value=3)
        self.assertEqual(cmds.keyframe(self.name + ".tz", query=True, timeChange=True), [5.0, 10.0])
        self.assertAlmostEqual(cmds.getAttr(self.name + ".tz", time=10), 30.0)
        with self.assertRaises(TypeError):
            tz.setKey(time=12, value=1, fast=True)

    def test_set_key_undo(self):
        """通常のsetKeyは1回のUndoでカーブごと戻る。"""
        cmds.flushUndo()
        self.node.getPlug("ty").setKey(t=1, v=1)
        cmds.undo()
        self.assertIsNone(cmds.keyframe(self.name + ".ty", query=True, timeChange=True))

    def test_anim_layers_without_layers(self):
        """アニメーションレイヤーが無ければgetAnimLayersは空のlist。"""
        self.node.getPlug("tz").setKey(t=1, v=1)
        self.assertEqual(self.node.getPlug("tz").getAnimLayers(), [])


if __name__ == "__main__":
    unittest.main()
