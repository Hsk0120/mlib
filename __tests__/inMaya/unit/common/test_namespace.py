"""mlib Namespace APIを検証するMaya内テスト。

あわせて次も確かめる。

- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
- 名前空間・選択・matchTransform の通常経路と、om2 へ置き換えた読み取りを cmds と突き合わせる。
- Node・Plug・MultiPlug・Namespace・Reference のメソッドと units の変換関数を確かめる。
"""

import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.common.namespace import Namespace


class NamespaceApiTest(unittest.TestCase):
    """NamespaceとNodeの相互運用を検証する。"""

    root_name = ":mlibNamespaceTest"

    def _cleanup(self):
        names = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True, absoluteName=True) or []
        for name in sorted(names, key=lambda item: item.count(":"), reverse=True):
            if name == self.root_name or name.startswith(self.root_name + ":") or name in (":mlibNamespaceDestination", ":child", ":renamed"):
                if cmds.namespace(exists=name):
                    cmds.namespace(removeNamespace=name, deleteNamespaceContent=True)
        if cmds.namespace(exists=self.root_name):
            cmds.namespace(removeNamespace=self.root_name, deleteNamespaceContent=True)

    def setUp(self):
        self._cleanup()
        self.root = Namespace.create(self.root_name)

    def tearDown(self):
        self._cleanup()

    def test_namespace_hierarchy(self):
        child = Namespace.create(f"{self.root_name}:child")
        self.assertTrue(self.root.exists())
        self.assertEqual(str(child), self.root_name + ":child")
        self.assertEqual(child.getParent(), self.root)
        self.assertIn(child, self.root.getChildren())

    def test_nodes_and_node_namespace(self):
        node = mlib.createNode(type="transform", name="namespaceNode")
        node.setNamespace(self.root)
        self.assertEqual(node.getNamespace(), self.root)
        self.assertIn(node.getName(), [item.getName() for item in self.root.getNodes()])
        cmds.delete(node.getName())

    def test_nodes_recurse_includes_child_namespace_nodes(self):
        child = Namespace.create(f"{self.root_name}:child")
        top_node = mlib.createNode(type="transform", name="mlibNamespaceRecurseTop")
        top_node.setNamespace(self.root)
        child_node = mlib.createNode(type="transform", name="mlibNamespaceRecurseChild")
        child_node.setNamespace(child)

        direct_names = [item.getName() for item in self.root.getNodes()]
        self.assertIn(top_node.getName(), direct_names)
        self.assertNotIn(child_node.getName(), direct_names)

        recursive_names = [item.getName() for item in self.root.getNodes(recurse=True)]
        self.assertIn(top_node.getName(), recursive_names)
        self.assertIn(child_node.getName(), recursive_names)

        cmds.delete(top_node.getName(), child_node.getName())

    def test_children_returns_only_direct_child_namespaces(self):
        child = Namespace.create(f"{self.root_name}:child")
        Namespace.create(f"{self.root_name}:child:grandchild")

        children = self.root.getChildren()
        self.assertEqual(children, [child])

    def test_exists_is_false_for_unknown_namespace(self):
        self.assertFalse(Namespace(":mlibNamespaceDoesNotExist").exists())

    def test_current_set_as_current_and_as_current_context(self):
        root_current = Namespace.getCurrent()
        try:
            self.root.setCurrent()
            self.assertEqual(Namespace.getCurrent(), self.root)

            child = Namespace.create(f"{self.root_name}:child")
            with child.asCurrent():
                self.assertEqual(Namespace.getCurrent(), child)
            self.assertEqual(Namespace.getCurrent(), self.root)

            try:
                with child.asCurrent():
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
            self.assertEqual(Namespace.getCurrent(), self.root)
        finally:
            if root_current.exists():
                root_current.setCurrent()

    def test_set_as_current_raises_for_missing_namespace(self):
        try:
            Namespace(":mlibNamespaceDoesNotExist").setCurrent()
        except RuntimeError:
            pass
        else:
            raise AssertionError("setCurrent on a missing namespace should raise RuntimeError")

    def test_rename_move_and_remove(self):
        child = Namespace.create(f"{self.root_name}:child")
        destination = Namespace.create(":mlibNamespaceDestination")
        try:
            child.rename("renamed")
            self.assertTrue(Namespace(f"{self.root_name}:renamed").exists())
            child.move(destination)
            moved = Namespace(":mlibNamespaceDestination:renamed")
            self.assertTrue(moved.exists())
            moved.remove()
            self.assertFalse(moved.exists())
        finally:
            if destination.exists():
                cmds.namespace(removeNamespace=destination.name, deleteNamespaceContent=True)


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class NamespaceSpecTest(unittest.TestCase):
    """Namespaceの正規化・作成・変更・削除とUndoを固定する。"""

    def setUp(self):
        """一意な親名前空間名を決める。"""
        self.root = ":mlibSpecDNs_" + uuid.uuid4().hex[:8]
        self.current = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)

    def tearDown(self):
        """作成した名前空間を中身ごと削除し、カレントを戻す。"""
        cmds.namespace(set=":")
        names = cmds.namespaceInfo(":", listOnlyNamespaces=True, recurse=True, absoluteName=True) or []
        for name in sorted(names, key=lambda item: item.count(":"), reverse=True):
            if name.startswith(self.root) and cmds.namespace(exists=name):
                cmds.namespace(removeNamespace=name, deleteNamespaceContent=True)
        if cmds.namespace(exists=self.current):
            cmds.namespace(set=self.current)

    def test_normalization_and_value_semantics(self):
        """/は:と同じ区切り、両端の:は除いて先頭に:を付ける。比較は保持名で行う。"""
        self.assertEqual(Namespace("a/b").name, ":a:b")
        self.assertEqual(Namespace("::a:b::").name, ":a:b")
        self.assertEqual(Namespace(":::").name, ":")
        self.assertEqual(Namespace().name, ":")
        self.assertEqual(Namespace(Namespace("x")).name, ":x")
        self.assertEqual(str(Namespace("x")), ":x")
        self.assertEqual(repr(Namespace("x")), "Namespace(':x')")
        self.assertEqual(Namespace("x"), Namespace(":x"))
        self.assertEqual(hash(Namespace("x")), hash(Namespace(":x")))
        self.assertNotEqual(Namespace("x"), ":x")
        with self.assertRaises(ValueError):
            Namespace("")
        for value in (None, 5):
            with self.assertRaises(TypeError):
                Namespace(value)

    def test_parent_is_computed_from_name(self):
        """getParentは名前から求め、ルートではNone。存在は確認しない。"""
        self.assertIsNone(Namespace(":").getParent())
        self.assertEqual(Namespace(":a:b:c").getParent(), Namespace(":a:b"))
        self.assertEqual(Namespace(":a").getParent(), Namespace(":"))
        missing = Namespace(self.root + ":nothing")
        self.assertFalse(missing.exists())
        self.assertEqual(missing.getChildren(), [])
        self.assertEqual(missing.getNodes(), [])

    def test_create_recursive_returns_existing_and_one_undo(self):
        """多段名は親から作り、既存なら同じ名前を返す。1回のUndoで全て戻る。"""
        created = Namespace.create(self.root + ":a:b")
        self.assertEqual(created.name, self.root + ":a:b")
        self.assertTrue(cmds.namespace(exists=self.root + ":a:b"))
        self.assertEqual(Namespace.getCurrent().name, self.current)
        self.assertEqual(Namespace.create(self.root + ":a:b"), created)
        cmds.undo()  # 既存を返しただけの2回目
        cmds.undo()
        self.assertFalse(cmds.namespace(exists=self.root))

    def test_create_relative_under_parent(self):
        """相対名はparent配下に作り、絶対名はparentを無視する。"""
        parent = Namespace.create(self.root)
        child = Namespace.create("child", parent=parent)
        self.assertEqual(child.name, self.root + ":child")
        absolute = Namespace.create(self.root + ":other", parent=child)
        self.assertEqual(absolute.name, self.root + ":other")
        self.assertIn(child, parent.getChildren())
        # ルートは常に存在するため、作成せずにルートの参照を返す。
        self.assertEqual(Namespace.create(":"), Namespace(":"))

    def test_set_current_and_as_current_restore(self):
        """存在しない名前空間のsetCurrentはRuntimeError。asCurrentは例外時も戻す。"""
        with self.assertRaises(RuntimeError):
            Namespace(self.root + ":missing").setCurrent()
        target = Namespace.create(self.root)
        with self.assertRaises(KeyError):
            with target.asCurrent() as active:
                self.assertIs(active, target)
                self.assertEqual(Namespace.getCurrent(), target)
                raise KeyError("boom")
        self.assertEqual(Namespace.getCurrent().name, self.current)

    def test_rename_move_and_remove(self):
        """renameは親を維持し、moveは既存の親へ移し、removeは内容を移動先へ移す。"""
        source = Namespace.create(self.root + ":src")
        node = cmds.createNode("transform", name=source.name + ":item")
        self.assertIs(source.rename("dst"), source)
        self.assertEqual(source.name, self.root + ":dst")
        self.assertTrue(cmds.objExists(self.root + ":dst:item"))
        self.assertFalse(cmds.namespace(exists=self.root + ":src"))
        holder = Namespace.create(self.root + ":holder")
        source.move(holder)
        self.assertEqual(source.name, self.root + ":holder:dst")
        with self.assertRaises(RuntimeError):
            source.move(self.root + ":missingParent")
        destination = source.remove(self.root)
        self.assertEqual(destination, Namespace(self.root))
        self.assertTrue(cmds.objExists(self.root + ":item"))
        self.assertFalse(cmds.namespace(exists=self.root + ":holder:dst"))
        del node

    def test_root_operations_and_conflicts_are_rejected(self):
        """ルートの変更はValueError、既存の移動先や長短名の同時指定は拒否する。"""
        root = Namespace(":")
        with self.assertRaises(ValueError):
            root.rename("x")
        with self.assertRaises(ValueError):
            root.move(":")
        with self.assertRaises(ValueError):
            root.remove()
        first = Namespace.create(self.root + ":first")
        Namespace.create(self.root + ":second")
        with self.assertRaises(RuntimeError):
            first.rename("second")
        with self.assertRaises(TypeError):
            first.remove(":", destination=":")
        with self.assertRaises(RuntimeError):
            first.remove(self.root + ":missing")
        self.assertTrue(first.exists())


class _CommonCase(NamespaceCase):
    PREFIX = "mlibSpecCommonEdits_"

    def setUp(self):
        super().setUp()
        self.current = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.relative = cmds.namespace(query=True, relativeNames=True)
        self.selection = cmds.ls(selection=True, long=True)
        cmds.select(clear=True)

    def tearDown(self):
        cmds.namespace(relativeNames=self.relative)
        cmds.namespace(set=self.current if cmds.namespace(exists=self.current) else ":")
        if self.selection:
            cmds.select(self.selection, replace=True)
        else:
            cmds.select(clear=True)
        super().tearDown()

    def namespaces(self, root):
        """root 配下の名前空間を root からの相対名で返す。"""
        names = cmds.namespaceInfo(root, listOnlyNamespaces=True, recurse=True, absoluteName=True) or []
        return sorted(name[len(root) :] for name in names)

    def nodes(self, root):
        """root 配下のノードを root からの相対名で返す。"""
        names = cmds.namespaceInfo(root, listOnlyDependencyNodes=True, recurse=True, absoluteName=True) or []
        return sorted(name[len(root) :] for name in names)


class NamespaceTest(_CommonCase):
    def test_create_nested_and_existing(self):
        """多段の作成は親ごと作り、既存なら同じ名前を返す。relativeNames の設定によらず絶対名。"""
        for relative in (False, True):
            with self.subTest(relativeNames=relative):
                root = ":" + self.ns + ":" + ("rel" if relative else "abs")
                cmds.namespace(add=root.rsplit(":", 1)[-1], parent=":" + self.ns)
                cmds.namespace(set=":" + self.ns)
                cmds.namespace(relativeNames=relative)
                try:
                    created = Namespace.create("a:b", parent=root)
                    again = Namespace.create("a:b", parent=root)
                finally:
                    cmds.namespace(relativeNames=False)
                    cmds.namespace(set=":")
                self.assertEqual(created.name, root + ":a:b")
                self.assertEqual(again, created)
                self.assertEqual(self.namespaces(root), [":a", ":a:b"])

    def test_create_undo_once(self):
        """Undo 1 回で、作った親ごと消える。"""
        root = ":" + self.ns
        cmds.flushUndo()
        Namespace.create("x:y", parent=root)
        cmds.undo()
        self.assertFalse(cmds.namespace(exists=root + ":x"))

    def test_create_sanitized_name(self):
        """Maya が不正文字を置き換える名前は、置き換え後の名前を作って返す(既存なら番号付き)。"""
        root = ":" + self.ns
        for name in ("1bad", "a-b", "a#", "1bad"):
            with self.subTest(name=name):
                actual = Namespace.create(name, parent=root)
                self.assertTrue(actual.exists())
        self.assertIn(":bad1", self.namespaces(root))

    def test_set_current(self):
        """setCurrent は切り替えて自身を返し、存在しない名前空間は RuntimeError。"""
        target = Namespace.create("cur", parent=":" + self.ns)
        self.assertIs(target.setCurrent(), target)
        self.assertEqual(cmds.namespaceInfo(currentNamespace=True, absoluteName=True), target.name)
        cmds.namespace(set=":")
        with self.assertRaises(RuntimeError):
            Namespace(":" + self.ns + ":missing").setCurrent()

    def build(self, root):
        """名前が衝突する A・B を root の下に作る。"""
        for name in ("A", "B", "A:C", "B:C"):
            cmds.namespace(add=name.rsplit(":", 1)[-1], parent=root + (":" + name.rsplit(":", 1)[0] if ":" in name else ""))
        for name in ("A:n1", "A:n2", "A:C:n1", "B:n1", "B:n2", "B:n21", "B:C:n1"):
            cmds.createNode("transform", name=root + ":" + name, skipSelect=True)

    def test_rename_move_remove_match_cmds(self):
        """rename・move・remove は保持名を更新し、cmds.namespace で同じ操作をした結果と同じになる。"""
        mlib_root, cmds_root = ":" + self.ns + ":viaMlib", ":" + self.ns + ":viaCmds"
        for root in (mlib_root, cmds_root):
            cmds.namespace(add=root.rsplit(":", 1)[-1], parent=":" + self.ns)
            self.build(root)
        renamed = Namespace(mlib_root + ":A").rename("R")
        self.assertEqual(renamed.name, mlib_root + ":R")
        moved = renamed.move(mlib_root + ":B")
        self.assertEqual(moved.name, mlib_root + ":B:R")
        destination = moved.remove(mlib_root + ":B")
        self.assertEqual(destination, Namespace(mlib_root + ":B"))
        # cmds.namespace の rename/move に相当する手順(作成・内容の移動・元の削除)。
        cmds.namespace(add="R", parent=cmds_root)
        cmds.namespace(moveNamespace=(cmds_root + ":A", cmds_root + ":R"), force=True)
        cmds.namespace(removeNamespace=cmds_root + ":A")
        cmds.namespace(add="R", parent=cmds_root + ":B")
        cmds.namespace(moveNamespace=(cmds_root + ":R", cmds_root + ":B:R"), force=True)
        cmds.namespace(removeNamespace=cmds_root + ":R")
        cmds.namespace(moveNamespace=(cmds_root + ":B:R", cmds_root + ":B"), force=True)
        cmds.namespace(removeNamespace=cmds_root + ":B:R")
        self.assertEqual(self.namespaces(mlib_root), self.namespaces(cmds_root))
        self.assertEqual(self.nodes(mlib_root), self.nodes(cmds_root))

    def test_remove_into_child_fails_without_change(self):
        """自身の子への移動は RuntimeError。"""
        root = ":" + self.ns
        self.build(root)
        with self.assertRaises(RuntimeError):
            Namespace(root + ":A").remove(root + ":A:C")
        self.assertTrue(cmds.namespace(exists=root + ":A"))


class _Case(NamespaceCase):
    """名前空間の補助。"""

    PREFIX = "mlibNodePlugAddnp_"


class NamespaceNodePlugAdditionsTest(_Case):
    """Namespace の追加メソッド。"""

    def _tree(self):
        """:<ns>:a:b と :<ns>:c を作り、:<ns> の Namespace を返す。"""
        cmds.namespace(add="a", parent=":" + self.ns)
        cmds.namespace(add="b", parent=":" + self.ns + ":a")
        cmds.namespace(add="c", parent=":" + self.ns)
        return Namespace(self.ns)

    def test_children_recurse(self):
        """recurse=False は直下、True は子孫(namespaceInfo の recurse と同じ集合)。"""
        root = self._tree()
        self.assertEqual(sorted(child.name for child in root.getChildren()), [":" + self.ns + ":a", ":" + self.ns + ":c"])
        expected = cmds.namespaceInfo(":" + self.ns, listOnlyNamespaces=True, recurse=True, absoluteName=True)
        self.assertEqual(sorted(child.name for child in root.getChildren(recurse=True)), sorted(expected))
        self.assertEqual(Namespace(":" + self.ns + ":missing").getChildren(recurse=True), [])
        with self.assertRaises(TypeError):
            root.getChildren(recurse=1)

    def test_short_name_and_split(self):
        """末端名・階層の分割。ルートは ':' と空リスト。"""
        namespace = Namespace(":" + self.ns + ":a:b")
        self.assertEqual(namespace.getShortName(), "b")
        self.assertEqual(namespace.split(), [self.ns, "a", "b"])
        self.assertEqual(Namespace(":").getShortName(), ":")
        self.assertEqual(Namespace(":").split(), [])

    def test_get_node(self):
        """名前空間を付けたノードを返し、無ければ RuntimeError。引数の型・空文字列は例外。"""
        name = self.make("transform", "target")
        node = Namespace(self.ns).getNode("target")
        self.assertEqual(node.getFullName(), cmds.ls(name, long=True)[0])
        self.assertEqual(Namespace(":").getNode("time1").getFullName(), "time1")
        for value, error in (("missing", RuntimeError), (1, TypeError), ("", ValueError)):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    Namespace(self.ns).getNode(value)

    def test_remove_delete_contents(self):
        """deleteContents=True は内容と子名前空間を削除して None を返し、Undo 1回で戻る。"""
        self._tree()
        target = ":" + self.ns + ":a"
        inner = cmds.createNode("transform", name=target + ":b:inner", skipSelect=True)
        node = cmds.createNode("transform", name=target + ":node", skipSelect=True)
        self.flushUndo()
        self.assertIsNone(Namespace(target).remove(deleteContents=True))

        def after():
            self.assertFalse(cmds.namespace(exists=target))
            self.assertFalse(cmds.objExists(node) or cmds.objExists(inner))

        def before():
            self.assertTrue(cmds.namespace(exists=target))
            self.assertTrue(cmds.objExists(node) and cmds.objExists(inner))

        self.assertUndoesInOneStep(before, after)
        for args, flags, error in (((), {"deleteContents": 1}, TypeError), ((), {"deleteContents": True}, RuntimeError)):
            with self.subTest(flags=flags):
                with self.assertRaises(error):
                    Namespace(":" + self.ns + ":missing").remove(*args, **flags)
        with self.assertRaises(ValueError):
            Namespace(":").remove(deleteContents=True)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
