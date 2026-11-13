"""mlib.decorator (undoChunk/preservedSelection/preservedSkinShape) を検証するMaya内テスト。

あわせて次も確かめる。

- mlib.decorator・mlib.util・mlib.logger の約束を固定する仕様テスト(担当D)。
"""

import io
import logging
import sys
from unittest import mock
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib import decorator, logger, util
from mlib.decorator import (
    nativeUnits,
    preservedSelection,
    preservedSkinShape,
    undoChunk,
    undoTransaction,
    viewportOff,
)
from mlib.nodes.joint import Joint


class UndoDecoratorsTest(unittest.TestCase):
    """undoChunk のwith構文とデコレータ が単一Undoチャンクとして機能することを検証する。"""

    def tearDown(self):
        for name in ("mlibUndoChunkNode", "mlibUndoableNode"):
            if cmds.objExists(name):
                cmds.delete(name)

    def test_decorator_repeated_calls_and_nested_chunks(self):
        @undoChunk("outer")
        def create_and_move():
            """Nested chunk example."""
            with undoChunk("inner"):
                node = cmds.createNode("transform", name="mlibUndoChunkNode")
                cmds.setAttr(node + ".translateX", 7)
            return node

        self.assertEqual(create_and_move.__doc__, "Nested chunk example.")
        for _ in range(2):
            node = create_and_move()
            self.assertEqual(cmds.undoInfo(query=True, undoName=True), "outer")
            cmds.undo()
            self.assertFalse(cmds.objExists(node))
            cmds.redo()
            self.assertEqual(cmds.getAttr(node + ".translateX"), 7)
            cmds.undo()

    def test_undo_chunk_groups_multiple_operations(self):
        with undoChunk("mlibTestChunk"):
            cmds.createNode("transform", name="mlibUndoChunkNode")
            cmds.setAttr("mlibUndoChunkNode.translateX", 5.0)

        self.assertTrue(cmds.objExists("mlibUndoChunkNode"))
        cmds.undo()
        self.assertFalse(cmds.objExists("mlibUndoChunkNode"))

    def test_public_operations_have_separate_undo_steps(self):
        node = mlib.createNode("transform", name="mlibUndoChunkNode")
        node.getPlug("visibility").set(False)
        cmds.undo()
        self.assertTrue(cmds.objExists("mlibUndoChunkNode"))
        self.assertTrue(cmds.getAttr("mlibUndoChunkNode.visibility"))
        cmds.undo()
        self.assertFalse(cmds.objExists("mlibUndoChunkNode"))
        cmds.redo()
        cmds.redo()
        self.assertFalse(cmds.getAttr("mlibUndoChunkNode.visibility"))

    def test_tool_groups_public_operations_and_queries_add_no_step(self):
        @undoChunk("createControlTool")
        def create_control():
            node = mlib.createNode("transform", name="mlibUndoChunkNode")
            node.getPlug("visibility").set(False)
            return node

        node = create_control()
        mlib.ls(type="transform")
        mlib.getNode(node.getName())
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "createControlTool")
        cmds.undo()
        self.assertFalse(cmds.objExists("mlibUndoChunkNode"))
        cmds.redo()
        self.assertFalse(cmds.getAttr("mlibUndoChunkNode.visibility"))

    def test_undo_chunk_wraps_function_in_single_chunk(self):
        @undoChunk("mlibTestUndoable")
        def create_and_move():
            cmds.createNode("transform", name="mlibUndoableNode")
            cmds.setAttr("mlibUndoableNode.translateX", 3.0)

        create_and_move()
        self.assertTrue(cmds.objExists("mlibUndoableNode"))
        cmds.undo()
        self.assertFalse(cmds.objExists("mlibUndoableNode"))

    def test_undo_chunk_propagates_exception_and_still_closes_chunk(self):
        with self.assertRaises(RuntimeError):
            with undoChunk("mlibTestChunkError"):
                cmds.createNode("transform", name="mlibUndoChunkNode")
                raise RuntimeError("boom")
        # 例外前の操作はロールバックされない(自動ロールバックしない設計)。
        self.assertTrue(cmds.objExists("mlibUndoChunkNode"))

        # チャンクが finally で正しく閉じられていれば、直後に別のチャンクを
        # 問題なく開始できる。
        with undoChunk("mlibTestChunkAfterError"):
            cmds.setAttr("mlibUndoChunkNode.translateX", 9.0)
        self.assertEqual(cmds.getAttr("mlibUndoChunkNode.translateX"), 9.0)

    def test_undo_chunk_propagates_exception_without_rollback(self):
        @undoChunk("mlibTestUndoableError")
        def create_then_fail():
            cmds.createNode("transform", name="mlibUndoableNode")
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            create_then_fail()
        # undoChunk は完了済み操作を自動ロールバックしない。
        self.assertTrue(cmds.objExists("mlibUndoableNode"))

    def test_undo_chunk_preserves_function_metadata_and_return_value(self):
        @undoChunk()
        def sample_function():
            """docstring for sample_function."""
            return 42

        self.assertEqual(sample_function.__name__, "sample_function")
        self.assertEqual(sample_function(), 42)


class UndoTransactionTest(unittest.TestCase):
    """undoTransaction が例外時のみ自動ロールバックすることを検証する。"""

    def tearDown(self):
        for name in ("mlibUndoTxnBefore", "mlibUndoTxnNode", "mlibUndoTxnA", "mlibUndoTxnB"):
            if cmds.objExists(name):
                cmds.delete(name)

    def test_commits_normally_when_no_exception(self):
        with undoTransaction("mlibUndoTxnCommit"):
            cmds.createNode("transform", name="mlibUndoTxnNode")
            cmds.setAttr("mlibUndoTxnNode.translateX", 5.0)

        self.assertTrue(cmds.objExists("mlibUndoTxnNode"))
        # 正常終了時はロールバックせず、undoChunk と同様に1回のUndoにまとまる。
        cmds.undo()
        self.assertFalse(cmds.objExists("mlibUndoTxnNode"))

    def test_rolls_back_all_operations_on_exception(self):
        with self.assertRaises(RuntimeError):
            with undoTransaction("mlibUndoTxnRollback"):
                cmds.createNode("transform", name="mlibUndoTxnA")
                cmds.createNode("transform", name="mlibUndoTxnB")
                raise RuntimeError("boom")

        self.assertFalse(cmds.objExists("mlibUndoTxnA"))
        self.assertFalse(cmds.objExists("mlibUndoTxnB"))

    def test_exception_type_and_message_are_preserved(self):
        with self.assertRaises(ValueError) as context:
            with undoTransaction("mlibUndoTxnMessage"):
                cmds.createNode("transform", name="mlibUndoTxnNode")
                raise ValueError("specific message")
        self.assertEqual(str(context.exception), "specific message")
        self.assertFalse(cmds.objExists("mlibUndoTxnNode"))

    def test_empty_body_exception_does_not_undo_unrelated_prior_operation(self):
        # チャンク内で実際の変更が無いまま例外になっても、直前の無関係な
        # 操作を巻き込んでUndoしてはならない(空チャンクの既定挙動への対策)。
        cmds.createNode("transform", name="mlibUndoTxnBefore")
        self.assertTrue(cmds.objExists("mlibUndoTxnBefore"))

        with self.assertRaises(RuntimeError):
            with undoTransaction("mlibUndoTxnEmptyBody"):
                raise RuntimeError("boom before any Maya operation")

        self.assertTrue(cmds.objExists("mlibUndoTxnBefore"))

    def test_decorator_usage_rolls_back_on_exception(self):
        @undoTransaction("mlibUndoTxnDecorator")
        def create_then_fail():
            cmds.createNode("transform", name="mlibUndoTxnNode")
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            create_then_fail()
        self.assertFalse(cmds.objExists("mlibUndoTxnNode"))

    def test_decorator_usage_commits_on_success(self):
        @undoTransaction("mlibUndoTxnDecoratorOk")
        def create():
            cmds.createNode("transform", name="mlibUndoTxnNode")
            return 42

        self.assertEqual(create(), 42)
        self.assertTrue(cmds.objExists("mlibUndoTxnNode"))


class PreservedSelectionTest(unittest.TestCase):
    """preservedSelection が選択状態を保存・復元することを検証する。"""

    def setUp(self):
        self.nodes = [
            cmds.createNode("transform", name="mlibPreservedSelectionA"),
            cmds.createNode("transform", name="mlibPreservedSelectionB"),
            cmds.createNode("transform", name="mlibPreservedSelectionC"),
        ]

    def tearDown(self):
        for name in self.nodes:
            if cmds.objExists(name):
                cmds.delete(name)
        cmds.select(clear=True)

    def test_restores_original_selection_after_block(self):
        cmds.select(self.nodes[0], replace=True)

        with preservedSelection():
            cmds.select(self.nodes[1], replace=True)
            self.assertEqual(cmds.ls(sl=True, long=True), cmds.ls(self.nodes[1], long=True))

        self.assertEqual(cmds.ls(sl=True, long=True), cmds.ls(self.nodes[0], long=True))

    def test_restores_empty_selection_when_nothing_was_selected(self):
        cmds.select(clear=True)

        with preservedSelection():
            cmds.select(self.nodes[2], replace=True)

        self.assertEqual(cmds.ls(sl=True), [])

    def test_restores_selection_even_when_block_raises(self):
        cmds.select(self.nodes[0], replace=True)

        with self.assertRaises(RuntimeError):
            with preservedSelection():
                cmds.select(self.nodes[1], replace=True)
                raise RuntimeError("boom")

        self.assertEqual(cmds.ls(sl=True, long=True), cmds.ls(self.nodes[0], long=True))


class PreservedSkinShapeTest(unittest.TestCase):
    """preservedSkinShape がjoint姿勢の変更中もスキン変形を保つことを検証する。"""

    def setUp(self):
        self.joint = cmds.createNode("joint", name="mlibPreservedSkinShapeJoint")
        cmds.setAttr(self.joint + ".translateY", 1.0)
        self.mesh_transform, _ = cmds.polyCube(name="mlibPreservedSkinShapeMesh")
        cmds.move(0, 1, 0, self.mesh_transform, relative=True)
        self.skin_name = cmds.skinCluster(self.joint, self.mesh_transform)[0]

    def tearDown(self):
        if cmds.objExists(self.mesh_transform):
            cmds.delete(self.mesh_transform)
        if cmds.objExists(self.joint):
            cmds.delete(self.joint)
        cmds.select(clear=True)

    def _vertex_positions(self):
        return cmds.xform(self.mesh_transform + ".vtx[*]", query=True, worldSpace=True, translation=True)

    def test_reorienting_joint_does_not_move_the_mesh(self):
        before = self._vertex_positions()
        before_world_matrix = cmds.xform(self.joint, query=True, worldSpace=True, matrix=True)

        with preservedSkinShape([Joint(self.joint)]) as skins:
            self.assertEqual([skin.getFullName() for skin in skins], [self.skin_name])
            cmds.setAttr(self.joint + ".jointOrientZ", 45.0)

        after_world_matrix = cmds.xform(self.joint, query=True, worldSpace=True, matrix=True)
        self.assertNotEqual(after_world_matrix, before_world_matrix)
        after = self._vertex_positions()
        for a, b in zip(after, before):
            self.assertAlmostEqual(a, b, places=6)

    def test_normal_deformation_resumes_after_the_block(self):
        # cmds.skinCluster(query=True, moveJointsMode=True) は常にNoneを返す既知のMaya挙動
        # のため、フラグ値ではなく「ブロックを抜けた後は通常通りjointの回転がメッシュへ
        # 反映される(=moveJointsModeが元に戻っている)」という観測可能な挙動で検証する。
        with preservedSkinShape([Joint(self.joint)]):
            cmds.setAttr(self.joint + ".jointOrientZ", 45.0)

        before = self._vertex_positions()
        cmds.setAttr(self.joint + ".rotateZ", 30.0)
        after = self._vertex_positions()
        self.assertNotEqual(after, before)

    def test_normal_deformation_resumes_even_when_block_raises(self):
        with self.assertRaises(RuntimeError):
            with preservedSkinShape([Joint(self.joint)]):
                raise RuntimeError("boom")

        before = self._vertex_positions()
        cmds.setAttr(self.joint + ".rotateZ", 30.0)
        after = self._vertex_positions()
        self.assertNotEqual(after, before)

    def test_is_undoable_as_a_single_step(self):
        before = self._vertex_positions()
        original_orient = cmds.getAttr(self.joint + ".jointOrientZ")

        with preservedSkinShape([Joint(self.joint)]):
            cmds.setAttr(self.joint + ".jointOrientZ", 45.0)

        cmds.undo()

        self.assertAlmostEqual(cmds.getAttr(self.joint + ".jointOrientZ"), original_orient, places=6)
        after = self._vertex_positions()
        for a, b in zip(after, before):
            self.assertAlmostEqual(a, b, places=6)

    def test_ignores_joints_without_a_skin_cluster(self):
        lone_joint = cmds.createNode("joint", name="mlibPreservedSkinShapeLoneJoint")
        try:
            with preservedSkinShape([Joint(lone_joint)]) as skins:
                self.assertEqual(list(skins), [])
                cmds.setAttr(lone_joint + ".jointOrientZ", 45.0)
            self.assertAlmostEqual(cmds.getAttr(lone_joint + ".jointOrientZ"), 45.0, places=6)
        finally:
            if cmds.objExists(lone_joint):
                cmds.delete(lone_joint)


class _SceneCase(unittest.TestCase):
    """一時名前空間とUndo設定・UI単位・選択の保存と復元を共通にする。"""

    @staticmethod
    def opened(spy):
        """mockの呼出しからopenChunkの回数を数える。Python 3.7のため call[1] でキーワードを読む。"""
        return sum(1 for call in spy.call_args_list if call[1].get("openChunk"))

    def setUp(self):
        """状態を保存し、Undoを有効にして一時名前空間を作る。"""
        self.undo_state = cmds.undoInfo(query=True, state=True)
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.angle = cmds.currentUnit(query=True, angle=True)
        self.time = cmds.currentUnit(query=True, time=True)
        self.selection = cmds.ls(selection=True, long=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.ns = "mlibSpecDDeco_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を削除し、保存した状態へ戻す。"""
        cmds.undoInfo(stateWithoutFlush=True)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        cmds.currentUnit(linear=self.linear, angle=self.angle, time=self.time)
        existing = [name for name in self.selection if cmds.objExists(name)]
        if existing:
            cmds.select(existing, replace=True)
        else:
            cmds.select(clear=True)
        cmds.undoInfo(state=self.undo_state)

    def name(self, leaf):
        """一時名前空間内の名前を返す。"""
        return self.ns + ":" + leaf

    def chunk_calls(self):
        """decoratorが呼ぶcmds.undoInfoを記録するmockを返す。"""
        return mock.patch.object(decorator.cmds, "undoInfo", wraps=cmds.undoInfo)


class UndoChunkSpecTest(_SceneCase):
    """undoChunkの入れ子・Undo無効時・名前・戻り値を固定する。"""

    def test_with_value_and_decorator_return(self):
        """withのasはNone、デコレーターは戻り値と関数名を保つ。"""
        with undoChunk("mlibSpecD") as value:
            self.assertIsNone(value)

        @undoChunk("mlibSpecD")
        def make(name):
            """ノードを作る。"""
            return cmds.createNode("transform", name=name)

        self.assertEqual(make(self.name("made")), self.name("made"))
        self.assertEqual(make.__name__, "make")
        cmds.undo()
        self.assertFalse(cmds.objExists(self.name("made")))

    def test_nested_chunks_open_once(self):
        """入れ子のundoChunkは外側の1チャンクだけを開き、1回のUndoで全て戻る。"""
        with self.chunk_calls() as spy:
            with undoChunk("outer"):
                cmds.createNode("transform", name=self.name("a"))
                with undoChunk("inner"):
                    cmds.createNode("transform", name=self.name("b"))
                    with undoChunk():
                        cmds.createNode("transform", name=self.name("c"))
        self.assertEqual(self.opened(spy), 1)
        cmds.undo()
        self.assertFalse(any(cmds.objExists(self.name(n)) for n in "abc"))

    def test_disabled_undo_does_not_open_chunk(self):
        """開始時にUndoが無効ならチャンクを開閉せず、入れ子でも問い合わせを繰り返さない。"""
        cmds.undoInfo(state=False)
        with self.chunk_calls() as spy:
            with undoChunk("off"):
                with undoChunk("inner"):
                    # Undo無効時のMaya 2027では名前空間付きの名前が外れる場合があるため戻り値で確かめる。
                    created = cmds.createNode("transform", name=self.name("off"))
        try:
            self.assertEqual(self.opened(spy), 0)
            self.assertEqual(sum(1 for call in spy.call_args_list if call[1].get("closeChunk")), 0)
            self.assertEqual(len(spy.call_args_list), 1)
            self.assertTrue(cmds.objExists(created))
        finally:
            if cmds.objExists(created):
                cmds.delete(created)

    def test_exception_propagates_and_keeps_changes(self):
        """例外は再送出し、先行した変更は巻き戻さない。チャンクは閉じて後の操作は別の段になる。"""
        with self.assertRaises(KeyError):
            with undoChunk("failing"):
                cmds.createNode("transform", name=self.name("kept"))
                raise KeyError("boom")
        self.assertTrue(cmds.objExists(self.name("kept")))
        cmds.createNode("transform", name=self.name("after"))
        cmds.undo()
        self.assertFalse(cmds.objExists(self.name("after")))
        self.assertTrue(cmds.objExists(self.name("kept")))
        cmds.undo()
        self.assertFalse(cmds.objExists(self.name("kept")))

    def test_recursive_decorator_calls_share_one_chunk(self):
        """再帰呼出しでも外側の1チャンクだけを開く。"""
        @undoChunk("recursive")
        def build(count):
            """countの数だけノードを作る。"""
            cmds.createNode("transform", name=self.name("r%d" % count))
            if count:
                build(count - 1)

        with self.chunk_calls() as spy:
            build(3)
        self.assertEqual(self.opened(spy), 1)
        cmds.undo()
        self.assertFalse(cmds.objExists(self.name("r0")))
        self.assertFalse(cmds.objExists(self.name("r3")))


class UndoTransactionSpecTest(_SceneCase):
    """undoTransactionの巻戻しと内側のundoChunkの扱いを固定する。"""

    def test_rolls_back_on_base_exception(self):
        """BaseExceptionでもブロック内の変更を巻き戻し、元の例外を再送出する。"""
        with self.assertRaises(KeyboardInterrupt):
            with undoTransaction("mlibSpecDTx"):
                cmds.createNode("transform", name=self.name("tx"))
                raise KeyboardInterrupt()
        self.assertFalse(cmds.objExists(self.name("tx")))

    def test_named_transaction_does_not_open_inner_chunks(self):
        """名前付きのトランザクション内のundoChunkはMayaのチャンクを入れ子に開かない。"""
        with self.chunk_calls() as spy:
            with undoTransaction("named"):
                with undoChunk("inner"):
                    cmds.createNode("transform", name=self.name("inner"))
        self.assertEqual(self.opened(spy), 1)
        cmds.undo()
        self.assertFalse(cmds.objExists(self.name("inner")))

    def test_unnamed_transaction_opens_inner_chunk(self):
        """名前を省略したトランザクションでは内側のundoChunkも従来どおり開く。"""
        with self.chunk_calls() as spy:
            with undoTransaction():
                with undoChunk("inner"):
                    cmds.createNode("transform", name=self.name("inner"))
        self.assertEqual(self.opened(spy), 2)

    def test_decorator_success_commits_one_step(self):
        """デコレーターとして正常終了した場合は1段のUndoとして残る。"""
        @undoTransaction("mlibSpecDTx")
        def make():
            """2つのノードを作る。"""
            cmds.createNode("transform", name=self.name("x1"))
            cmds.createNode("transform", name=self.name("x2"))

        make()
        self.assertTrue(cmds.objExists(self.name("x2")))
        cmds.undo()
        self.assertFalse(cmds.objExists(self.name("x1")))


class NativeUnitsSpecTest(_SceneCase):
    """nativeUnitsの切替・入れ子・時間単位・Undoへの影響を固定する。"""

    def test_nested_restore_and_time_unit_unchanged(self):
        """入れ子でも外側の終了で開始時の単位へ戻り、時間単位は変えない。"""
        cmds.currentUnit(linear="mm", angle="deg", time="ntsc")
        with nativeUnits():
            with nativeUnits():
                self.assertEqual(cmds.currentUnit(query=True, linear=True), "cm")
                self.assertEqual(cmds.currentUnit(query=True, angle=True), "rad")
            self.assertEqual(cmds.currentUnit(query=True, linear=True), "cm")
            self.assertEqual(cmds.currentUnit(query=True, time=True), "ntsc")
        self.assertEqual(cmds.currentUnit(query=True, linear=True), "mm")
        self.assertEqual(cmds.currentUnit(query=True, angle=True), "deg")
        self.assertEqual(cmds.currentUnit(query=True, time=True), "ntsc")

    def test_values_are_read_in_native_units(self):
        """ブロック内のcmdsの値はcm・radで読み書きされる。"""
        node = cmds.createNode("transform", name=self.name("units"))
        cmds.currentUnit(linear="m", angle="deg")
        cmds.setAttr(node + ".tx", 2.0)
        cmds.setAttr(node + ".rx", 90.0)
        with nativeUnits():
            self.assertAlmostEqual(cmds.getAttr(node + ".tx"), 200.0)
            self.assertAlmostEqual(cmds.getAttr(node + ".rx"), om2.MAngle(90.0, om2.MAngle.kDegrees).asRadians())

    def test_not_recorded_in_undo(self):
        """単位の切替自体はUndoへ記録しない。"""
        cmds.select(clear=True)
        marker = cmds.undoInfo(query=True, undoName=True)
        with nativeUnits():
            pass
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), marker)


class PreservedSelectionSpecTest(_SceneCase):
    """preservedSelectionの復元規則を固定する。"""

    def test_component_selection_is_restored(self):
        """コンポーネント選択を含む選択を、例外時も復元する。"""
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        node = cmds.createNode("transform", name=self.name("node"))
        cmds.select(cube + ".vtx[0:2]", node, replace=True)
        before = cmds.ls(selection=True, flatten=True)
        with self.assertRaises(KeyError):
            with preservedSelection():
                cmds.select(clear=True)
                raise KeyError("boom")
        self.assertEqual(cmds.ls(selection=True, flatten=True), before)

    def test_deleted_items_are_dropped(self):
        """ブロック内で削除された対象は除き、残りがなければ選択を解除する。"""
        a = cmds.createNode("transform", name=self.name("a"))
        b = cmds.createNode("transform", name=self.name("b"))
        cmds.select(a, b, replace=True)
        with preservedSelection():
            cmds.delete(a)
        self.assertEqual(cmds.ls(selection=True), [b])
        with preservedSelection():
            cmds.delete(b)
        self.assertEqual(cmds.ls(selection=True), [])


class OtherContextSpecTest(_SceneCase):
    """viewportOffとpreservedSkinShapeのバッチ・入力検証を固定する。"""

    def test_viewport_off_in_batch_touches_no_ui(self):
        """バッチではメインペインを操作せず、withとデコレーターの両方で使える。"""
        if not cmds.about(batch=True):
            self.skipTest("GUIでは表示を操作するため対象外")
        with mock.patch.object(decorator.cmds, "paneLayout", side_effect=AssertionError("ui")):
            with viewportOff() as value:
                self.assertIsNone(value)

            @viewportOff()
            def compute():
                """値を返す。"""
                return 42

            self.assertEqual(compute(), 42)
            with self.assertRaises(KeyError):
                with viewportOff():
                    raise KeyError("boom")

    def test_preserved_skin_shape_input_validation(self):
        """joint以外はTypeError、skinClusterのないjointでは空のSkinClustersを渡す。"""
        node = cmds.createNode("transform", name=self.name("notJoint"))
        with self.assertRaises(TypeError):
            with preservedSkinShape([node]):
                pass
        joint = cmds.createNode("joint", name=self.name("joint"))
        with preservedSkinShape([joint]) as skins:
            self.assertEqual(len(skins), 0)
            self.assertEqual(type(skins).__name__, "SkinClusters")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
