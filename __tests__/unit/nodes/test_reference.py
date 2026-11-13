"""``mlib.nodes.reference`` のテスト。

- mlib.nodes.reference の Reference と mlib.common.references.listReferences を検証するMaya内テスト。
- Reference・Container・DagPose・マテリアル系・Constraint・AnimCurve の参照の少ないAPIの約束を固定する(担当C)。
- Node・Plug・MultiPlug・Namespace・Reference のメソッドと units の変換関数を確かめる。
"""

import math
import os
import shutil
import sys
import tempfile
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Namespace, units
from mlib.common.references import createReference, listReferences
from mlib.components import Face
from mlib.nodes import Container, DagPose, File, Node, Place2dTexture, Reference
from mlib.nodes.reference import Reference
from mlib.plugs import Plug
from support.namespaceCase import NamespaceCase


class ReferenceTest(unittest.TestCase):
    """参照ノードのラップ・照会・ロード制御・削除を検証する。

    現在開いているシーンには一切触れず(file(new=...)等は使わない)、
    一時ファイルへの export と reference の追加・削除だけで完結させる。
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.ref_path = os.path.join(self.tmp_dir, "mlibReferenceTestTarget.ma")
        helper = cmds.createNode("transform", name="mlibReferenceExportHelper")
        cmds.select(helper, replace=True)
        cmds.file(self.ref_path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(helper)
        cmds.select(clear=True)
        self.namespace_name = "mlibReferenceTestNs"
        cmds.file(self.ref_path, reference=True, namespace=self.namespace_name, returnNewNodes=False)
        self.ref_node_name = next(
            name for name in cmds.ls(type="reference") if name != "sharedReferenceNode"
        )

    def tearDown(self):
        if cmds.objExists(self.ref_node_name):
            cmds.file(removeReference=True, referenceNode=self.ref_node_name)
        if os.path.exists(self.ref_path):
            os.remove(self.ref_path)
        if os.path.isdir(self.tmp_dir):
            os.rmdir(self.tmp_dir)

    def test_node_resolves_to_reference_wrapper(self):
        reference = Node(self.ref_node_name)
        self.assertIsInstance(reference, Reference)

    def test_filename_matches_referenceQuery(self):
        reference = Node(self.ref_node_name)
        self.assertEqual(reference.getFilename(), cmds.referenceQuery(self.ref_node_name, filename=True))

    def test_namespace_returns_namespace_instance(self):
        reference = Node(self.ref_node_name)
        namespace = reference.getAssociatedNamespace()
        self.assertIsInstance(namespace, Namespace)
        self.assertEqual(namespace, Namespace(self.namespace_name))

    def test_node_namespace_is_separate_from_reference_namespace(self):
        """継承APIはノード自身、専用APIは参照内容を照会する。"""
        reference = Node(self.ref_node_name)
        self.assertEqual(reference.getNamespace(), Namespace(':'))
        self.assertEqual(reference.getAssociatedNamespace(), Namespace(self.namespace_name))
        with self.assertRaises(RuntimeError):
            reference.isRoot()
        self.assertTrue(reference.isTopLevel())

    def test_is_loaded_and_nodes(self):
        reference = Node(self.ref_node_name)
        self.assertTrue(reference.isLoaded())
        nodes = reference.getNodes()
        self.assertEqual(len(nodes), 1)
        self.assertTrue(nodes[0].getName().startswith(self.namespace_name + ":"))

    def test_parent_reference_is_none_for_top_level(self):
        reference = Node(self.ref_node_name)
        self.assertIsNone(reference.getParentReference())

    def test_is_root_root_and_children_for_top_level_reference(self):
        reference = Node(self.ref_node_name)
        self.assertTrue(reference.isTopLevel())
        self.assertEqual(reference.getRoot().getName(), reference.getName())
        self.assertEqual(reference.getChildren(), [])

    def test_edit_strings_nodes_attrs_reflect_applied_edit(self):
        reference = Node(self.ref_node_name)
        self.assertEqual(reference.getEditStrings(), [])
        self.assertEqual(reference.getEditNodeNames(), [])
        self.assertEqual(reference.getEditAttrNames(), [])

        node_name = f"{self.namespace_name}:mlibReferenceExportHelper"
        cmds.setAttr(node_name + ".translateX", 3.0)

        editStrings = reference.getEditStrings()
        self.assertTrue(any("translate" in edit for edit in editStrings))
        self.assertIn("|" + node_name, reference.getEditNodeNames())
        self.assertIn("translate", reference.getEditAttrNames())

    def test_unload_load_round_trip(self):
        reference = Node(self.ref_node_name)
        result = reference.unload()
        self.assertIs(result, reference)
        self.assertFalse(reference.isLoaded())
        self.assertFalse(cmds.referenceQuery(self.ref_node_name, isLoaded=True))

        result = reference.load()
        self.assertIs(result, reference)
        self.assertTrue(reference.isLoaded())

    def test_nodes_raises_when_unloaded(self):
        reference = Node(self.ref_node_name)
        reference.unload()
        with self.assertRaises(RuntimeError):
            reference.getNodes()

    def test_remove_deletes_reference_node(self):
        reference = Node(self.ref_node_name)
        reference.remove()
        self.assertFalse(cmds.objExists(self.ref_node_name))

    def test_list_references_includes_created_reference(self):
        references = listReferences()
        self.assertIn(self.ref_node_name, [reference.getName() for reference in references])

    def test_list_references_top_level_only_excludes_none_here(self):
        # このテストではネストした参照を作らないため、topLevelOnly=True でも
        # 通常の一覧と同じ結果になることだけを確認する。
        all_refs = {reference.getName() for reference in listReferences()}
        top_refs = {reference.getName() for reference in listReferences(topLevelOnly=True)}
        self.assertEqual(all_refs, top_refs)


class NestedReferenceTest(unittest.TestCase):
    """入れ子(参照が別の参照を持つ)構成での親子関係の解決を検証する。"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.leaf_path = os.path.join(self.tmp_dir, "mlibNestedLeaf.ma")
        self.mid_path = os.path.join(self.tmp_dir, "mlibNestedMid.ma")

        cmds.file(new=True, force=True)
        cmds.polyCube(name="leafCube")
        cmds.file(rename=self.leaf_path)
        cmds.file(save=True, type="mayaAscii", force=True)

        cmds.file(new=True, force=True)
        cmds.file(self.leaf_path, reference=True, namespace="mlibNestedLeafNs")
        cmds.file(rename=self.mid_path)
        cmds.file(save=True, type="mayaAscii", force=True)

        cmds.file(new=True, force=True)
        self.top = createReference(self.mid_path, namespace="mlibNestedMidNs")
        self.nested_name = next(
            name for name in cmds.ls(type="reference")
            if name not in ("sharedReferenceNode", self.top.getName())
        )

    def tearDown(self):
        if cmds.objExists(self.top.getName()):
            cmds.file(removeReference=True, referenceNode=self.top.getName())
        for path in (self.leaf_path, self.mid_path):
            if os.path.exists(path):
                os.remove(path)
        if os.path.isdir(self.tmp_dir):
            os.rmdir(self.tmp_dir)

    def test_top_level_reference_reports_nested_child(self):
        self.assertTrue(self.top.isTopLevel())
        self.assertEqual(self.top.getRoot().getName(), self.top.getName())
        child_names = [child.getName() for child in self.top.getChildren()]
        self.assertEqual(child_names, [self.nested_name])

    def test_nested_reference_resolves_parent_and_root(self):
        nested = Node(self.nested_name)
        self.assertFalse(nested.isTopLevel())
        self.assertEqual(nested.getParentReference().getName(), self.top.getName())
        self.assertEqual(nested.getRoot().getName(), self.top.getName())


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeMisc_"
    CLEAR_SELECTION = True


class ReferenceSpecTest(unittest.TestCase):
    """同じファイルを2回参照し、コピー番号付きの参照を作る。開いているシーンは new しない。"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp_dir, "mlibSpecCRef.ma").replace("\\", "/")
        helper = cmds.createNode("transform", name="mlibSpecCRefHelper")
        cmds.select(helper, replace=True)
        cmds.file(self.path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(helper)
        cmds.select(clear=True)
        tag = uuid.uuid4().hex[:8]
        self.namespaces = ["mlibSpecCRefA_" + tag, "mlibSpecCRefB_" + tag]
        for namespace in self.namespaces:
            cmds.file(self.path, reference=True, namespace=namespace)
        self.refs = [cmds.referenceQuery(namespace + ":mlibSpecCRefHelper", referenceNode=True)
                     for namespace in self.namespaces]

    def tearDown(self):
        for ref in self.refs:
            if cmds.objExists(ref):
                cmds.file(removeReference=True, referenceNode=ref)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_reference_fn(self):
        """mfn は自身の MFnReference。"""
        fn = Node(self.refs[0]).mfn()
        self.assertIsInstance(fn, om2.MFnReference)
        self.assertEqual(fn.name(), self.refs[0])

    def test_get_filename_default_and_unresolved(self):
        """既定はコピー番号の無い解決済みの完全パス。resolved=False も同じファイル(パス変数なし)。"""
        second = Node(self.refs[1])
        self.assertIsInstance(second, Reference)
        self.assertEqual(second.getFilename(),
                         cmds.referenceQuery(self.refs[1], filename=True, withoutCopyNumber=True))
        self.assertEqual(second.getFilename(resolved=False), self.path)

    def test_get_filename_with_copy_number(self):
        """withCopyNumber=True は referenceQuery(filename=True) と同じ完全パスで、2つ目以降に {1} 等が付く。

        フラグは MFnReference.fileName の3番目の引数へ渡す。
        """
        expected = cmds.referenceQuery(self.refs[1], filename=True)
        self.assertTrue(expected.endswith("{1}"))
        self.assertEqual(Node(self.refs[1]).getFilename(withCopyNumber=True), expected)
        self.assertEqual(Node(self.refs[1]).getFilename(withCopyNumber=True), self.path + "{1}")
        first = Node(self.refs[0]).getFilename(withCopyNumber=True)
        self.assertEqual(first, cmds.referenceQuery(self.refs[0], filename=True))
        self.assertEqual(first, self.path)

    def test_from_referenced_file_and_edit_filters(self):
        """参照内のノードは isFromReferencedFile=True。成功した編集だけが既定で返り、失敗の指定では空。"""
        content = Node(self.namespaces[0] + ":mlibSpecCRefHelper")
        self.assertTrue(content.isFromReferencedFile())
        self.assertFalse(Node(self.refs[0]).isFromReferencedFile())
        cmds.setAttr(content.getFullName() + ".translateX", 3)
        reference = Node(self.refs[0])
        self.assertEqual(len(reference.getEditStrings()), 1)
        self.assertEqual(reference.getEditStrings(successful=False, failed=True), [])
        self.assertEqual(reference.getEditAttrNames(successful=False), [])
        self.assertEqual(Node(self.refs[1]).getEditNodeNames(), [])


class _Case(NamespaceCase):
    """名前空間の補助。"""

    PREFIX = "mlibNodePlugAddnp_"


class ReferenceNodePlugAdditionsTest(_Case):
    """Reference の追加メソッドと、リファレンス由来の Node・Plug の照会。現在のシーンは開き直さない。"""

    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)
        self.references = []
        token = uuid.uuid4().hex[:8]
        self.asset = "mlibNodePlugAddasset_" + token
        self.driven = "mlibNodePlugAdddriven_" + token
        self.path_a = self._export("a.ma", [self.asset, self.driven], connect=True)
        self.path_b = self._export("b.ma", [self.asset, "mlibNodePlugAddextra_" + token])

    def tearDown(self):
        for reference in self.references:
            if cmds.objExists(reference):
                cmds.file(removeReference=True, referenceNode=reference)
        super().tearDown()

    def _export(self, filename, names, connect=False):
        """ルートに names の transform を作って書き出し、削除してパスを返す。"""
        path = os.path.join(self.tmp_dir, filename).replace("\\", "/")
        created = [cmds.createNode("transform", name=name, skipSelect=True) for name in names]
        if connect:
            cmds.connectAttr(created[0] + ".tx", created[1] + ".ty")
        cmds.select(created, replace=True)
        cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(created)
        cmds.select(clear=True)
        return path

    def _reference(self, path, suffix):
        """path をリファレンスし、Reference を返す。"""
        namespace = self.ns + "_" + suffix
        self.extra_namespaces.append(namespace)
        nodes = cmds.file(path, reference=True, namespace=namespace, returnNewNodes=True)
        name = cmds.referenceQuery(nodes[0], referenceNode=True)
        self.references.append(name)
        return mlib.getNode(name)

    def test_queries(self):
        """コピー番号・名前空間の使用・保留の照会と、Node.getReference・Plug.isFromReferencedFile。"""
        first = self._reference(self.path_a, "r1")
        second = self._reference(self.path_a, "r2")
        self.assertIsInstance(first, Reference)
        self.assertEqual(first.getCopyNumber(), 0)
        self.assertEqual(second.getCopyNumber(), 1)
        self.assertTrue(first.isUsingNamespaces())
        self.assertFalse(first.isDeferred())
        asset = mlib.getNode(self.ns + "_r1:" + self.asset)
        driven = mlib.getNode(self.ns + "_r1:" + self.driven)
        self.assertEqual(asset.getReference().getFullName(), first.getFullName())
        self.assertIsNone(mlib.getNode(self.make("transform")).getReference())
        self.assertTrue(driven.ty.isFromReferencedFile())
        self.assertFalse(driven.tz.isFromReferencedFile())
        local = self.make("transform", "local#")
        cmds.connectAttr(asset.getFullName() + ".tz", local + ".tx")
        self.assertFalse(mlib.getPlug(local + ".tx").isFromReferencedFile())
        second.unload()
        self.assertEqual(second.isDeferred(), cmds.file(cmds.referenceQuery(second.getFullName(), filename=True),
                                                        query=True, deferReference=True))

    def test_remove_edits(self):
        """コマンドで絞って削除し、ロード中の適用済み Edit も消える(ロード状態は保つ)。"""
        reference = self._reference(self.path_a, "r1")
        asset = self.ns + "_r1:" + self.asset
        cmds.setAttr(asset + ".tz", 5.0)
        local = self.make("transform", "local#")
        cmds.connectAttr(asset + ".tx", local + ".tx")
        self.assertIs(reference.removeEdits(editCommand="setAttr"), reference)
        self.assertTrue(reference.isLoaded())
        edits = reference.getEditStrings()
        self.assertFalse([edit for edit in edits if edit.startswith("setAttr")])
        self.assertTrue([edit for edit in edits if edit.startswith("connectAttr")])
        self.assertEqual(cmds.getAttr(asset + ".tz"), 0.0)
        reference.removeEdits()
        self.assertEqual(reference.getEditStrings(), [])
        for flags, error in (({"successful": 1}, TypeError), ({"editCommand": 3}, TypeError),
                             ({"editCommand": ""}, ValueError)):
            with self.subTest(flags=flags):
                with self.assertRaises(error):
                    reference.removeEdits(**flags)

    def test_replace_file(self):
        """別のファイルへ置き換え、名前空間を保つ。不正な path は例外。"""
        reference = self._reference(self.path_a, "r1")
        self.assertIs(reference.replaceFile(self.path_b), reference)
        self.assertEqual(os.path.normcase(reference.getFilename()), os.path.normcase(self.path_b))
        self.assertTrue(cmds.objExists(self.ns + "_r1:mlibNodePlugAddextra_" + self.asset.rsplit("_", 1)[-1]))
        self.assertFalse(cmds.objExists(self.ns + "_r1:" + self.driven))
        for value, error in ((1, TypeError), ("", ValueError),
                             (os.path.join(self.tmp_dir, "missing.ma"), RuntimeError)):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    reference.replaceFile(value)

    def test_import_contents(self):
        """読み込んだノードを返してリファレンスを解除する。removeNamespace=True は名前空間を親へ移す。"""
        reference = self._reference(self.path_a, "r1")
        name = reference.getFullName()
        nodes = reference.importContents()
        self.assertFalse(cmds.objExists(name))
        self.assertIn(self.ns + "_r1:" + self.asset, [node.getNodeName() for node in nodes])
        self.assertFalse(mlib.getNode(self.ns + "_r1:" + self.asset).isFromReferencedFile())
        second = self._reference(self.path_a, "r2")
        imported = second.importContents(removeNamespace=True)
        self.assertFalse(cmds.namespace(exists=":" + self.ns + "_r2"))
        names = [node.getNodeName() for node in imported]
        self.assertIn(self.asset, names)
        for node in imported:
            if node.isValid() and not node.isDefaultNode():
                try:
                    cmds.delete(node.getFullName())
                except RuntimeError:
                    pass
        third = self._reference(self.path_a, "r3")
        third.unload()
        with self.assertRaises(RuntimeError):
            third.importContents()
        with self.assertRaises(TypeError):
            third.importContents(removeNamespace=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
