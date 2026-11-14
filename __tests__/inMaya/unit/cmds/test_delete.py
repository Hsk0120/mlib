"""削除入口の入力検査・参照寿命・Undoとfastの境界を検証する。

あわせて次も確かめる。

- 2026-10-26 に変えた約束(担当A)を実Mayaで検証する。
- mlib.cmds の7入口(getNode・getPlug・createNode・ls・delete・duplicate・select)の仕様テスト(担当D)。
"""

import os
import re
import tempfile
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()


class DeleteBasicsTest(unittest.TestCase):
    """専用名前空間のノードを使い、拒否時に何も消えないことも確認する。"""

    def setUp(self):
        self.namespace = ":deleteBasics_" + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)
        self.undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(state=True)

    def tearDown(self):
        for name in cmds.ls(self.namespace + ":*", long=True) or []:
            if cmds.objExists(name):
                cmds.lockNode(name, lock=False)
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.undoInfo(state=self.undo_state)

    def make(self, kind="transform", parent=None):
        """専用名前空間にノードを作り、ラッパーを取得する。"""
        options = {"name": self.namespace + ":node#", "skipSelect": True}
        if parent is not None:
            options["parent"] = parent.getFullName()
        return mlib.getNode(cmds.createNode(kind, **options))

    def test_command_accepts_name_node_and_api_references(self):
        """文字列・Node・MObject・MDagPathの各入力を通常/fastで削除できる。"""
        for fast in (False, True):
            for mode in ("name", "node", "mobject", "dagpath"):
                with self.subTest(fast=fast, mode=mode):
                    node = self.make()
                    name = node.getFullName()
                    value = {"name": name, "node": node, "mobject": node.mnode(), "dagpath": node.mpath()}[mode]
                    self.assertIsNone(mlib.delete(value, fast=fast))
                    self.assertFalse(cmds.objExists(name))
                    self.assertFalse(node.isValid())

    def test_nested_generator_input_is_deleted_in_one_undo(self):
        """入れ子とgeneratorの重複入力を削除し、1回のUndo/redoで全て戻せる。"""
        first, second, third = (self.make() for _ in range(3))
        names = [node.getFullName() for node in (first, second, third)]
        items = (item for item in (first, (second, [third, first])))
        cmds.flushUndo()
        mlib.delete(items)
        self.assertFalse(any(cmds.objExists(name) for name in names))
        cmds.undo()
        self.assertTrue(all(cmds.objExists(name) for name in names))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        cmds.redo()
        self.assertFalse(any(cmds.objExists(name) for name in names))

    def test_invalid_nested_value_does_not_delete_valid_prefix(self):
        """後半の未対応型を検出しても、先に渡したノードは削除しない。"""
        for fast in (False, True):
            for invalid in (1, object()):
                with self.subTest(fast=fast, invalid=type(invalid).__name__):
                    first, second = self.make(), self.make()
                    names = [first.getFullName(), second.getFullName()]
                    with self.assertRaises(TypeError):
                        mlib.delete([first, [second, invalid]], fast=fast)
                    self.assertTrue(all(cmds.objExists(name) for name in names))

    def test_plug_input_is_rejected_without_deleting_its_owner(self):
        """PlugとMPlugを含む削除要求は所有ノードごと消す操作に変換しない。"""
        for fast in (False, True):
            for raw in (False, True):
                with self.subTest(fast=fast, raw=raw):
                    first, owner = self.make(), self.make()
                    plug = owner.getPlug("tx")
                    with self.assertRaises(TypeError):
                        mlib.delete([first, plug.mplug() if raw else plug], fast=fast)
                    self.assertTrue(first.isValid() and owner.isValid() and plug.isValid())

    def test_empty_collections_are_rejected(self):
        """空list・tuple・generatorでは削除対象を暗黙の選択へ置き換えない。"""
        selected = self.make()
        cmds.select(selected.getFullName())
        for fast in (False, True):
            for kind in (list, tuple, iter):
                with self.subTest(fast=fast, kind=kind.__name__):
                    with self.assertRaises(ValueError):
                        mlib.delete(kind([]), fast=fast)
                    self.assertTrue(selected.isValid())

    def test_invalid_flags_are_rejected_before_deletion(self):
        """fast/safeの不正な型によってノードを削除しない。"""
        node = self.make()
        for value in (None, 0, 1, "true"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    mlib.delete(node, fast=value)
                with self.assertRaises(TypeError):
                    node.delete(safe=value)
                self.assertTrue(node.isValid())

    def test_fast_component_rejection_preserves_all_targets(self):
        """fast非対応のコンポーネントが混ざると、先行ノードも形状も変更しない。"""
        plain = self.make()
        mesh = cmds.polyCube(name=self.namespace + ":mesh", constructionHistory=False)[0]
        before = cmds.polyEvaluate(mesh, vertex=True)
        with self.assertRaises(NotImplementedError):
            mlib.delete([plain.getFullName(), mesh + ".vtx[0]"], fast=True)
        self.assertTrue(plain.isValid())
        self.assertEqual(cmds.polyEvaluate(mesh, vertex=True), before)

    def test_fast_delete_does_not_consume_or_append_undo(self):
        """既存Undoの前後でfast削除が設定やキューを変更しない。"""
        marker, deleted = self.make(), self.make()
        deleted_name = deleted.getFullName()
        cmds.flushUndo()
        marker.getPlug("tx").set(5)
        undo_name = cmds.undoInfo(query=True, undoName=True)
        self.assertIsNone(deleted.delete(fast=True))
        self.assertTrue(cmds.undoInfo(query=True, state=True))
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
        cmds.undo()
        self.assertEqual(cmds.getAttr(marker.getFullName() + ".tx"), 0)
        self.assertFalse(cmds.objExists(deleted_name))

    def test_normal_delete_restores_held_references_across_redo_cycles(self):
        """同じNodeとPlugを保持したまま、削除/Undo/redoを繰り返せる。"""
        node = self.make()
        name = node.getFullName()
        plug = node.getPlug("tx")
        plug.set(7)
        cmds.flushUndo()
        node.delete()
        for _ in range(3):
            self.assertFalse(node.isValid())
            self.assertFalse(plug.isValid())
            with self.assertRaises(RuntimeError):
                plug.get()
            cmds.undo()
            self.assertTrue(node.isValid() and plug.isValid())
            self.assertEqual(plug.get(), 7)
            self.assertEqual(cmds.getAttr(name + ".tx"), 7)
            cmds.redo()

    def test_safe_parent_delete_becomes_possible_after_message_disconnect(self):
        """子のmessage接続で保護された親を、切断後には削除できる。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                parent = self.make()
                child = self.make(parent=parent)
                receiver = self.make("network")
                cmds.addAttr(receiver.getFullName(), longName="owner", attributeType="message")
                source = child.getPlug("message")
                destination = receiver.getPlug("owner")
                destination.connect(source)
                self.assertIsNone(parent.delete(safe=True, fast=fast))
                self.assertTrue(parent.isValid() and child.isValid())
                destination.disconnect(source, fast=fast)
                parent.delete(safe=True, fast=fast)
                self.assertFalse(parent.isValid() or child.isValid())
                self.assertTrue(receiver.isValid())

    def test_locked_descendant_rejection_preserves_siblings_and_values(self):
        """ロックされた孫を含む削除要求で、別枝や既存値を変更しない。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.make()
                child = self.make(parent=root)
                grandchild = self.make(parent=child)
                sibling = self.make()
                sibling.getPlug("tx").set(11)
                names = [node.getFullName() for node in (root, child, grandchild, sibling)]
                cmds.lockNode(grandchild.getFullName(), lock=True)
                with self.assertRaises(RuntimeError):
                    mlib.delete([sibling, root], fast=fast)
                self.assertTrue(all(cmds.objExists(name) for name in names))
                self.assertEqual(cmds.getAttr(sibling.getFullName() + ".tx"), 11)
                cmds.lockNode(grandchild.getFullName(), lock=False)


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


class BatchDeleteTest(unittest.TestCase):
    """削除を1回にまとめ、削除できない対象があれば何も削除しないことを確かめる。"""

    def setUp(self):
        self.ns = "mlibContractA_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)
        self.state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(state=True)

    def tearDown(self):
        cmds.undoInfo(state=self.state)
        if cmds.objExists("|" + self.ns + ":g|persp"):
            cmds.parent("|" + self.ns + ":g|persp", world=True)
        _unlock_and_remove(self.ns)

    def _make(self, *names):
        return [cmds.createNode("transform", name=self.ns + ":" + name) for name in names]

    def test_single_cmds_delete_and_undo(self):
        """通常経路は cmds.delete を1回だけ呼び、Mayaの一括削除と同じ順で消え、1回のUndoで戻る。"""
        names = self._make("d0", "d1", "d2")
        child = cmds.createNode("transform", name=self.ns + ":dc", parent=names[0])
        md = cmds.createNode("multiplyDivide", name=self.ns + ":dmd")
        cmds.connectAttr(md + ".outputX", names[1] + ".tx")
        calls = []
        original = cmds.delete

        def counting(*args, **kwargs):
            calls.append(args)
            return original(*args, **kwargs)

        removed = []
        callback = om2.MDGMessage.addNodeRemovedCallback(lambda obj, _data: removed.append(om2.MFnDependencyNode(obj).name()), "dependNode")
        before = sorted(cmds.ls(long=True))
        cmds.delete = counting
        try:
            mlib.delete([child, md] + names)
        finally:
            cmds.delete = original
            om2.MMessage.removeCallback(callback)
        self.assertEqual(len(calls), 1)
        short = [name.rpartition(":")[2] for name in removed]
        # 渡した順(dc, dmd, d0...)ではなく、Mayaがまとめて削除するときの順になる。
        self.assertEqual(short, ["dc", "d0", "dmd", "d1", "d2"])
        self.assertRegex(cmds.undoInfo(query=True, undoName=True), r"^mlib delete( |$)")
        cmds.undo()
        self.assertEqual(sorted(cmds.ls(long=True)), before)

    def test_locked_node_deletes_nothing(self):
        """ロックされたノード・ロックされた子・参照のノードが含まれると、何も削除しない。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                names = self._make("l0", "l1", "l2")
                cmds.lockNode(names[2], lock=True)
                short = re.escape(names[2])
                pattern = "ノードがロックされているか、リファレンスです: " + short if fast else "ロックされたノード'" + short + "'は削除できません"
                with self.assertRaisesRegex(RuntimeError, pattern):
                    mlib.delete(names, fast=fast)
                self.assertEqual([cmds.objExists(name) for name in names], [True] * 3)
                cmds.lockNode(names[2], lock=False)
                parent = self._make("lp")[0]
                child = cmds.createNode("transform", name=self.ns + ":lc", parent=parent)
                cmds.lockNode(child, lock=True)
                pattern = (
                    "ノードがロックされているか、リファレンスです: " + re.escape(child)
                    if fast
                    else "'" + re.escape(parent) + "'は削除できません。ロックされた子か、読み取り専用の子があります"
                )
                with self.assertRaisesRegex(RuntimeError, pattern):
                    mlib.delete(names + [parent], fast=fast)
                with self.assertRaisesRegex(RuntimeError, pattern):
                    mlib.getNode(parent).delete(fast=fast)
                self.assertTrue(all(cmds.objExists(name) for name in names + [parent, child]))
                cmds.lockNode(child, lock=False)
                mlib.delete(names + [parent], fast=fast)
                self.assertFalse(any(cmds.objExists(name) for name in names + [parent, child]))

    def test_default_and_shared_nodes_fail_without_crash(self):
        """既定・共有ノード(time1・persp・defaultLayer・lambert1)は fast でも異常終了せず例外になる。"""
        others = self._make("n0", "n1")
        for fast in (False, True):
            for target in ("time1", "persp", "defaultLayer", "lambert1", "perspShape"):
                with self.subTest(fast=fast, target=target):
                    with self.assertRaisesRegex(RuntimeError, "削除できないノードです: '" + target + "'"):
                        mlib.delete(others + [target], fast=fast)
                    with self.assertRaisesRegex(RuntimeError, "削除できないノードです"):
                        mlib.getNode(target).delete(fast=fast)
                    self.assertTrue(all(cmds.objExists(name) for name in others + [target]))
            with self.subTest(fast=fast, target="d*"):
                with self.assertRaisesRegex(RuntimeError, "削除できないノードです"):
                    mlib.delete("d*", fast=fast)
                self.assertTrue(cmds.objExists("defaultLayer"))
        # 削除できないノードを子に持つ親も、何も削除しない。
        group = self._make("g")[0]
        cmds.parent("persp", group)
        for fast in (False, True):
            with self.subTest(fast=fast, target="undeletable child"):
                with self.assertRaisesRegex(RuntimeError, "削除できないノードです: 'persp'"):
                    mlib.delete(others + [group], fast=fast)
                self.assertTrue(all(cmds.objExists(name) for name in others + [group]))

    def test_user_shared_node_can_be_deleted(self):
        """利用者が shared で作ったノードは cmds.delete と同じく削除できる(isShared だけで拒否しない)。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                name = cmds.createNode("multiplyDivide", name=self.ns + ":shared", shared=True)
                mlib.delete(name, fast=fast)
                self.assertFalse(cmds.objExists(name))

    def test_referenced_node_deletes_nothing(self):
        """参照のノードを含むと、通常・fast とも何も削除しない。"""
        path = os.path.join(tempfile.gettempdir(), "mlibContractA_" + uuid.uuid4().hex + ".ma").replace("\\", "/")
        current = cmds.file(query=True, sceneName=True)
        modified = cmds.file(query=True, modified=True)
        source = cmds.createNode("transform", name="mlibContractA_refT_" + uuid.uuid4().hex)
        cmds.select(source)
        cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(source)
        reference = cmds.file(path, reference=True, namespace=self.ns + "_ref")
        try:
            ref_node = cmds.ls(self.ns + "_ref:" + source, long=True)[0]
            local = self._make("r0")[0]
            for fast in (False, True):
                with self.subTest(fast=fast):
                    # 通常・fastとも参照ノードであることと参照元を示す。
                    pattern = "リファレンスのノードです\\(リファレンス: '" + self.ns + "_refRN'\\)"
                    with self.assertRaisesRegex(RuntimeError, pattern):
                        mlib.delete([local, ref_node], fast=fast)
                    self.assertTrue(cmds.objExists(local) and cmds.objExists(ref_node))
        finally:
            cmds.file(reference, removeReference=True)
            if os.path.exists(path):
                os.remove(path)
            if current and not modified:
                cmds.file(modified=False)

    def test_duplicates_parent_child_and_cascade(self):
        """重複・親子の両方・連鎖して消えるノード・インスタンスを含めても、1回で全部消える。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                a, b, parent = self._make("a", "b", "p")
                child = cmds.createNode("transform", name=self.ns + ":c", parent=parent)
                cmds.connectAttr(a + ".rx", b + ".ty")
                conversion = cmds.listConnections(b + ".ty", source=True, destination=False)[0]
                cube, history = cmds.polyCube(name=self.ns + ":cube")
                md = cmds.createNode("multiplyDivide", name=self.ns + ":md")
                cmds.connectAttr(a + ".ry", md + ".input1X")
                md_conversion = cmds.listConnections(md + ".input1X", source=True, destination=False)[0]
                targets = [child, parent, parent, b, conversion, cube, history, md, md_conversion]
                mlib.delete(targets, fast=fast)
                self.assertFalse(any(cmds.objExists(name) for name in targets))
                self.assertTrue(cmds.objExists(a))
                # インスタンスされた子は、親の削除後も残る別のインスタンスから消える(従来と同じ)。
                first, second = self._make("ia", "ib")
                cmds.createNode("transform", name=self.ns + ":ix", parent=first)
                shared = cmds.ls(self.ns + ":ix", long=True)[0]
                cmds.parent(shared, second, addObject=True)
                mlib.delete([first, shared], fast=fast)
                self.assertFalse(cmds.objExists(first))
                self.assertEqual(cmds.ls(self.ns + ":ix", long=True, allPaths=True), [])
                self.assertTrue(cmds.objExists(second))
                mlib.delete([a, second], fast=fast)

    def test_missing_name_deletes_nothing(self):
        """存在しない名前を含むと、従来どおり RuntimeError で何も削除しない。"""
        names = self._make("m0")
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    mlib.delete(names + [self.ns + ":missing"], fast=fast)
                self.assertTrue(cmds.objExists(names[0]))


class _CmdsCase(unittest.TestCase):
    """一時名前空間・選択・Undo設定の保存と復元を共通にする。"""

    def setUp(self):
        """一時名前空間を作り、選択とUndo設定を保存する。"""
        self.undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.selection = cmds.ls(selection=True, long=True)
        self.ns = "mlibSpecDCmds_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を中身ごと削除し、選択とUndo設定を戻す。"""
        cmds.select(clear=True)
        if cmds.namespace(exists=self.ns):
            for node in cmds.ls(self.ns + ":*", long=True) or []:
                if cmds.objExists(node) and cmds.lockNode(node, query=True, lock=True)[0]:
                    cmds.lockNode(node, lock=False)
            cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        existing = [name for name in self.selection if cmds.objExists(name)]
        if existing:
            cmds.select(existing, replace=True)
        cmds.undoInfo(state=self.undo_state)

    def name(self, leaf):
        """一時名前空間内の名前を返す。"""
        return self.ns + ":" + leaf

    def transforms(self):
        """一時名前空間内のtransformの数を返す。"""
        return len(cmds.ls(self.ns + ":*", type="transform") or [])


class DeleteSpecTest(_CmdsCase):
    """deleteの一括削除・拒否時に何も消さないこと・Undoを固定する。"""

    def test_returns_none_and_one_undo_restores_all(self):
        """複数対象を1回で削除してNoneを返し、1回のUndoで全て戻る。"""
        names = [cmds.createNode("transform", name=self.name(f"n{i:d}")) for i in range(3)]
        self.assertIsNone(mlib.delete([names[0], (names[1], [names[2]])]))
        self.assertFalse(any(cmds.objExists(name) for name in names))
        cmds.undo()
        self.assertTrue(all(cmds.objExists(name) for name in names))
        mlib.delete([mlib.getNode(name) for name in names])
        self.assertFalse(any(cmds.objExists(name) for name in names))

    def test_mixed_names_and_nodes_are_rejected(self):
        """同じ対象列に名前とNodeが混在すると、何も削除せずTypeError。"""
        names = [cmds.createNode("transform", name=self.name(f"m{i:d}")) for i in range(2)]
        with self.assertRaises(TypeError):
            mlib.delete([mlib.getNode(names[0]), names[1]])
        self.assertTrue(all(cmds.objExists(name) for name in names))

    def test_attribute_name_string_is_rejected(self):
        """アトリビュート名の文字列もPlugと同じく、何も削除せずTypeError。"""
        attribute_owner = cmds.createNode("transform", name=self.name("owner"))
        other = cmds.createNode("transform", name=self.name("other"))
        cube = cmds.polyCube(name=self.name("attrCube"), constructionHistory=False)[0]
        faces = cmds.polyEvaluate(cube, face=True)
        for value in ([attribute_owner + ".tx", other], [other, cube + ".f[0]", attribute_owner + ".worldMatrix[0]"], attribute_owner + ".translate"):
            for fast in (False, True):
                with self.subTest(value=value, fast=fast):
                    with self.assertRaisesRegex(TypeError, "アトリビュート名は指定できません"):
                        mlib.delete(value, fast=fast)
                    self.assertTrue(cmds.objExists(attribute_owner))
                    self.assertTrue(cmds.objExists(other))
                    self.assertEqual(cmds.polyEvaluate(cube, face=True), faces)
        # コンポーネントの文字列は従来どおり削除する。
        mlib.delete([cube + ".f[0]", other])
        self.assertEqual(cmds.polyEvaluate(cube, face=True), faces - 1)
        self.assertFalse(cmds.objExists(other))

    def test_wildcards_and_parent_with_child(self):
        """ワイルドカードは一致したノードへ展開し、親と子の両方の指定も1回で削除する。"""
        parent = cmds.createNode("transform", name=self.name("w_parent"))
        child = cmds.createNode("transform", name=self.name("w_child"), parent=parent)
        mlib.delete([self.name("w_*"), child])
        self.assertFalse(cmds.objExists(parent))

    def test_rejections_delete_nothing(self):
        """空・Plug・存在しない名前・ロック・削除不可ノードを含む場合は何も削除しない。"""
        keep = cmds.createNode("transform", name=self.name("keep"))
        locked = cmds.createNode("transform", name=self.name("locked"))
        cmds.lockNode(locked, lock=True)
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        cases = [
            ([], ValueError),
            ([keep, ""], ValueError),
            ([keep, mlib.getPlug(keep + ".tx")], TypeError),
            ([keep, self.name("missing")], RuntimeError),
            ([keep, locked], RuntimeError),
            ([keep, "persp"], RuntimeError),
            ([keep, 5], TypeError),
        ]
        faces = cmds.polyEvaluate(cube, face=True)
        for value, error in cases:
            with self.assertRaises(error, msg=repr(value)):
                mlib.delete(value + [cube + ".f[0]"] if isinstance(value, list) and value else value)
            self.assertTrue(cmds.objExists(keep))
            self.assertEqual(cmds.polyEvaluate(cube, face=True), faces)
        self.assertTrue(cmds.objExists(locked))

    def test_fast_rules(self):
        """fastはUndoへ記録せず、コンポーネントを含む入力は何も削除せずNotImplementedError。"""
        node = cmds.createNode("transform", name=self.name("fast"))
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        with self.assertRaises(NotImplementedError):
            mlib.delete([node, cube + ".f[0]"], fast=True)
        self.assertTrue(cmds.objExists(node))
        with self.assertRaises(TypeError):
            mlib.delete(node, fast="yes")
        cmds.select(clear=True)
        marker = cmds.undoInfo(query=True, undoName=True)
        mlib.delete(node, fast=True)
        self.assertFalse(cmds.objExists(node))
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), marker)

    def test_components(self):
        """コンポーネントはMayaの削除規則で消し、1回のUndoで戻る。"""
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        mlib.delete(cube + ".f[0:1]")
        self.assertEqual(cmds.polyEvaluate(cube, face=True), 4)
        cmds.undo()
        self.assertEqual(cmds.polyEvaluate(cube, face=True), 6)


if __name__ == "__main__":
    unittest.main()
