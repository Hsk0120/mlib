"""入力参照を指定するdisconnectと、明示的な方向解除を検証する。

あわせて次も確かめる。

- 2026-10-26 に変えた約束(担当A)を実Mayaで検証する。
"""

import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()


class DisconnectReferenceTest(unittest.TestCase):
    """返却型・既存接続・ロック・Undoと廃止引数の拒否を確認する。"""

    def setUp(self):
        """隔離シーンとUndoを初期化する。"""
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)

    def _value(self, name):
        """接続に使う単位なしPlugを作る。"""
        return mlib.createNode("network", name=name).addAttr("value", "double")

    def _chain(self, prefix):
        """入力1本・出力2本の接続を作る。"""
        source, center = self._value(prefix + "Source"), self._value(prefix + "Center")
        destinations = [self._value(prefix + "Out" + str(i)) for i in range(2)]
        center.connect(source)
        for destination in destinations:
            destination.connect(center)
        return source, center, destinations

    def test_reference_inputs_return_the_single_source_and_keep_outputs(self):
        """省略・Plug・MPlug・文字列・source別名は入力元Plugを返す。"""
        for mode in ("default", "plug", "mplug", "string", "source"):
            with self.subTest(mode=mode):
                source, center, destinations = self._chain(mode)
                if mode == "default":
                    result = center.disconnect()
                elif mode == "source":
                    result = center.disconnect(source=source)
                else:
                    value = source.mplug() if mode == "mplug" else source.getFullName() if mode == "string" else source
                    result = center.disconnect(value)
                self.assertIsInstance(result, mlib.Plug)
                self.assertEqual(result, source)
                self.assertIsNone(center.getSource(skipConversionNodes=True))
                self.assertCountEqual(center.getDestinations(skipConversionNodes=True), destinations)
                with self.assertRaises(RuntimeError):
                    center.disconnect()

    def test_removed_directions_and_duplicate_aliases_fail_before_editing(self):
        """bool source・dst/destination・廃止した短縮名srcを変更前に拒否する。"""
        source, center, destinations = self._chain("invalid")
        for flags in ({"src": True}, {"src": False}, {"source": True},
                      {"dst": True}, {"dst": False}, {"destination": True},
                      {"src": source}):
            with self.subTest(flags=flags):
                with self.assertRaises(TypeError):
                    center.disconnect(**flags)
                self.assertEqual(center.getSource(skipConversionNodes=True), source)
                self.assertCountEqual(center.getDestinations(skipConversionNodes=True), destinations)
        for value in (True, False, 1, [], object()):
            with self.assertRaises(TypeError):
                center.disconnect(value)
        self.assertEqual(center.getSource(skipConversionNodes=True), source)

    def test_direction_release_uses_disconnect_all_and_returns_self(self):
        """方向解除を独立した既存APIで行い、通常の一回Undoを保つ。"""
        for src, dst in ((True, False), (False, True), (True, True), (False, False)):
            source, center, destinations = self._chain("directions" + str(src) + str(dst))
            cmds.flushUndo()
            self.assertIs(center.disconnectAll(source=src, destination=dst), center)
            self.assertEqual(center.getSource(skipConversionNodes=True), None if src else source)
            self.assertCountEqual(center.getDestinations(skipConversionNodes=True), [] if dst else destinations)
            if src or dst:
                cmds.undo()
                self.assertEqual(center.getSource(skipConversionNodes=True), source)
                self.assertCountEqual(center.getDestinations(skipConversionNodes=True), destinations)
            else:
                self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))

    def test_multi_search_keeps_specified_targets_and_other_connections(self):
        """naは指定srcに直結したマルチアトリビュートの要素だけを返し、他の入出力を残す。"""
        array = mlib.createNode("network").addAttr("values", "double", multi=True)
        source, other = self._value("arraySource"), self._value("arrayOther")
        first, second, independent = array[3], array[9], array[15]
        first.connect(source)
        second.connect(source)
        independent.connect(other)
        output = self._value("arrayOutput")
        output.connect(first)
        cmds.flushUndo()
        self.assertCountEqual(array.disconnect(source=source, nextAvailable=True), [first, second])
        self.assertEqual(independent.getSource(skipConversionNodes=True), other)
        self.assertEqual(output.getSource(skipConversionNodes=True), first)
        with self.assertRaises(RuntimeError):
            array.disconnect(source, na=True)
        cmds.undo()
        self.assertEqual(first.getSource(skipConversionNodes=True), source)
        self.assertEqual(second.getSource(skipConversionNodes=True), source)

    def test_conversion_nodes_are_direct_endpoints(self):
        """変換を飛ばした遠端を切らず、直結した変換出力を返す。"""
        source, destination = self._value("conversionSource"), self._value("conversionDestination")
        conversion = mlib.createNode("unitConversion")
        conversion.getPlug("input").connect(source)
        destination.connect(conversion.getPlug("output"))
        with self.assertRaises(RuntimeError):
            destination.disconnect(source)
        self.assertEqual(destination.disconnect(), conversion.getPlug("output"))
        self.assertEqual(conversion.getPlug("input").getSource(), source)

    def test_parent_disconnect_does_not_recurse_into_children(self):
        """親の入力だけを切り、独立した子の接続と親の出力を残す。"""
        a, b, c = [mlib.createNode("transform") for _ in range(3)]
        parent = b.getPlug("translate")
        parent.connect(a.getPlug("translate"))
        c.getPlug("translate").connect(parent)
        child_output = mlib.createNode("transform").getPlug("translateX")
        child_output.connect(b.getPlug("translateX"))
        self.assertEqual(parent.disconnect(), a.getPlug("translate"))
        self.assertEqual(c.getPlug("translate").getSource(skipConversionNodes=True), parent)
        self.assertEqual(child_output.getSource(skipConversionNodes=True), b.getPlug("translateX"))

    def test_force_restores_parent_lock_and_keeps_one_undo(self):
        """入力切断のforce/fを維持し、上位ロックを復元する。"""
        source = self._value("lockedSource")
        owner = mlib.createNode("network")
        owner.addAttr("payload", attributeType="compound", numberOfChildren=1, getPlug=False)
        destination = owner.addAttr("childValue", attributeType="double", parent="payload")
        destination.connect(source)
        parent = owner.getPlug("payload")
        parent.setFlags(locked=True)
        cmds.flushUndo()
        self.assertEqual(destination.disconnect(source, force=False, f=True), source)
        self.assertTrue(parent.isLocked())
        self.assertIsNone(destination.getSource(skipConversionNodes=True))
        cmds.undo()
        self.assertTrue(parent.isLocked())
        self.assertEqual(destination.getSource(skipConversionNodes=True), source)
        cmds.redo()
        self.assertTrue(parent.isLocked())
        self.assertIsNone(destination.getSource(skipConversionNodes=True))

    def test_fast_disconnect_uses_api_and_preserves_undo_queue(self):
        """fastは同じ直結をAPIで切り、Undoキューを増やさない。"""
        source, center, destinations = self._chain("fast")
        cmds.flushUndo()
        with patch.object(cmds, "disconnectAttr", side_effect=AssertionError("cmds disconnect")):
            self.assertEqual(center.disconnect(source, fast=True), source)
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))
        self.assertIsNone(center.getSource(skipConversionNodes=True))
        self.assertCountEqual(center.getDestinations(skipConversionNodes=True), destinations)

    def test_fast_multi_force_restores_locks_and_keeps_other_connections(self):
        """fastのマルチアトリビュートの検索もf/naを保ち、上位と要素のロックを復元する。"""
        source, other = self._value("fastArraySource"), self._value("fastArrayOther")
        array = mlib.createNode("network").addAttr("values", "double", multi=True)
        first, second, independent = array[3], array[9], array[15]
        first.connect(source)
        second.connect(source)
        independent.connect(other)
        first.setFlags(locked=True)
        array.setFlags(locked=True)
        cmds.flushUndo()
        with patch.object(cmds, "disconnectAttr", side_effect=AssertionError("cmds disconnect")):
            self.assertCountEqual(array.disconnect(source, f=True, na=True, fast=True), [first, second])
        self.assertTrue(array.isLocked())
        self.assertTrue(first.mplug().isLocked)
        self.assertIsNone(first.getSource(skipConversionNodes=True))
        self.assertIsNone(second.getSource(skipConversionNodes=True))
        self.assertEqual(independent.getSource(skipConversionNodes=True), other)
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))

    def test_deleted_source_or_destination_fails_before_maya_disconnect(self):
        """削除したノード/アトリビュートを再解決して同名の別物へ切断しない。"""
        for removed in ("source", "destination", "attribute"):
            for fast in (False, True):
                with self.subTest(removed=removed, fast=fast):
                    source, destination = self._value("deletedSource"), self._value("deletedDestination")
                    destination.connect(source)
                    if removed == "attribute":
                        cmds.deleteAttr(source.getFullName())
                    else:
                        target = source if removed == "source" else destination
                        cmds.delete(target.getNode().getFullName())
                    with patch.object(cmds, "disconnectAttr", side_effect=AssertionError("deleted plug reached cmds")):
                        with self.assertRaises(RuntimeError):
                            destination.disconnect(source, fast=fast)


def _unlock_and_remove(namespace):
    """名前空間内のロックを外して、名前空間ごと削除する。

    Args:
        namespace (str): 削除する名前空間。
    """
    if not cmds.namespace(exists=namespace):
        return
    for node in cmds.ls(namespace + ":*", long=True) or []:
        if cmds.objExists(node) and cmds.lockNode(node, query=True, lock=True)[0]:
            cmds.lockNode(node, lock=False)
    cmds.namespace(removeNamespace=namespace, deleteNamespaceContent=True)


class DisconnectReturnTest(unittest.TestCase):
    """disconnect が手元の入力元Plugを返し、名前から取り直さないことを確かめる。"""

    def setUp(self):
        self.ns = "mlibContractA_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)
        self.a = cmds.createNode("transform", name=self.ns + ":a")
        self.b = cmds.createNode("transform", name=self.ns + ":b")
        self.bs = cmds.createNode("blendShape", name=self.ns + ":bs")

    def tearDown(self):
        _unlock_and_remove(self.ns)

    def test_explicit_source_is_returned_as_is(self):
        """Plug を渡すとそのオブジェクト、MPlug・名前は解決したPlugを返す(fast・通常)。"""
        node_a, node_b = mlib.getNode(self.a), mlib.getNode(self.b)
        for fast in (False, True):
            for mode in ("plug", "mplug", "string"):
                with self.subTest(fast=fast, mode=mode):
                    cmds.connectAttr(self.a + ".tx", self.b + ".tx")
                    source = node_a.getPlug("tx")
                    value = {"plug": source, "mplug": source.mplug(), "string": self.a + ".tx"}[mode]
                    result = node_b.getPlug("tx").disconnect(value, fast=fast)
                    if mode == "plug":
                        self.assertIs(result, source)
                    self.assertIsInstance(result, mlib.Plug)
                    self.assertEqual(result, source)
                    self.assertFalse(cmds.isConnected(self.a + ".tx", self.b + ".tx"))

    def test_omitted_source_returns_acquired_plug(self):
        """省略時は切断前に取得した入力元Plugを返し、切断後も同じアトリビュートを指す。"""
        node_b, node_bs = mlib.getNode(self.b), mlib.getNode(self.bs)
        for fast in (False, True):
            with self.subTest(fast=fast):
                cmds.connectAttr(self.a + ".r", self.b + ".r")
                cmds.connectAttr(self.a + ".ty", self.bs + ".weight[2]")
                result = node_b.getPlug("r").disconnect(fast=fast)
                self.assertEqual(result.getFullName(), mlib.getNode(self.a).getPlug("r").getFullName())
                self.assertIsInstance(result, mlib.CompoundPlug)
                element = node_bs.getPlug("weight[2]").disconnect(fast=fast)
                self.assertEqual(element.getFullName(), mlib.getNode(self.a).getPlug("ty").getFullName())
                self.assertTrue(element.isValid())

    def test_alias_source_resolves_to_real_attribute(self):
        """エイリアス名で渡した入力元も、解決したPlug(実際のアトリビュート)を返す。"""
        cmds.addAttr(self.a, longName="driver", attributeType="double")
        cmds.aliasAttr("drv", self.a + ".driver")
        cmds.connectAttr(self.a + ".driver", self.b + ".sx")
        result = mlib.getNode(self.b).getPlug("sx").disconnect(self.a + ".drv")
        self.assertEqual(result, mlib.getNode(self.a).getPlug("driver"))
        self.assertFalse(cmds.isConnected(self.a + ".driver", self.b + ".sx"))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
