"""``mlib.common.scene`` のテスト。

Scene がパスとして振る舞うことと、今のシーンの照会・新規・開く・保存・インポート・リファレンス・書き出しを確かめる。
シーンを初期化するので、作業中の Maya GUI へ送らない。
"""

import shutil
import sys
import unittest
import uuid
from pathlib import Path

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Scene
from mlib.nodes.reference import Reference

#: 一時ファイルを作る場所(``__tests__/_output/temp``。Git の対象外)。
_TEMP_ROOT = Path(__file__).resolve().parents[3] / "_output" / "temp"


def _make_folder():
    """``__tests__/_output/temp`` の下に、このテスト専用の空のフォルダーを作る。

    Returns:
        Path: 作ったフォルダー。
    """
    folder = _TEMP_ROOT / ("scene_" + uuid.uuid4().hex[:12])
    folder.mkdir(parents=True)
    return folder


class _PreservedSceneCase(unittest.TestCase):
    """このクラスのテストの前に今のシーンを書き出し、終わったあとに元の名前・変更の有無で戻す。"""

    @classmethod
    def setUpClass(cls):
        cls.session_folder = _make_folder()
        cls.session_name = cmds.file(query=True, sceneName=True)
        cls.session_modified = cmds.file(query=True, modified=True)
        cls.session_backup = cls.session_folder / "session.ma"
        cmds.file(str(cls.session_backup), exportAll=True, type="mayaAscii", force=True, preserveReferences=True)

    @classmethod
    def tearDownClass(cls):
        try:
            cmds.file(new=True, force=True)
            if cls.session_name:
                cmds.file(str(cls.session_backup), open=True, force=True, prompt=False)
                cmds.file(rename=cls.session_name)
            else:
                cmds.file(str(cls.session_backup), i=True, prompt=False, preserveReferences=True)
            cmds.file(modified=cls.session_modified)
        finally:
            shutil.rmtree(str(cls.session_folder), ignore_errors=True)


class ScenePathTest(unittest.TestCase):
    """Scene は Path の派生で、パスの操作はそのまま使える(シーンは変えない)。"""

    def test_is_path(self):
        scene = Scene("C:/shots/shot010.ma") if sys.platform == "win32" else Scene("/shots/shot010.ma")
        self.assertIsInstance(scene, Path)
        self.assertEqual(scene.stem, "shot010")
        self.assertEqual(scene.suffix, ".ma")
        self.assertIsInstance(scene.with_suffix(".mb"), Scene)
        self.assertIsInstance(scene.parent, Scene)
        self.assertEqual(scene, Path(str(scene)))
        self.assertEqual(repr(Scene("a.ma")), "Scene('a.ma')")

    def test_is_exported(self):
        self.assertIs(mlib.Scene, Scene)
        self.assertIs(mlib.common.Scene, Scene)


class SceneFileTest(_PreservedSceneCase):
    """今のシーンの照会とファイルの操作。"""

    def setUp(self):
        cmds.file(new=True, force=True)
        self.folder = _make_folder()
        self.source = Scene(self.folder / "source.ma")
        helper = cmds.createNode("transform", name="mlibSceneHelper")
        cmds.createNode("transform", name="mlibSceneChild", parent=helper)
        cmds.file(rename=str(self.source))
        cmds.file(save=True, type="mayaAscii", force=True)
        cmds.file(new=True, force=True)

    def tearDown(self):
        cmds.file(new=True, force=True)
        shutil.rmtree(str(self.folder), ignore_errors=True)

    def test_current_is_none_for_untitled_scene(self):
        self.assertIsNone(Scene.getCurrent())

    def test_open_file_makes_it_current(self):
        self.source.openFile()
        current = Scene.getCurrent()
        self.assertIsInstance(current, Scene)
        self.assertTrue(self.source.isCurrent())
        self.assertEqual(current.name, "source.ma")
        self.assertTrue(cmds.objExists("mlibSceneHelper"))
        self.assertFalse(Scene.isModified())

    def test_open_and_new_refuse_unsaved_changes_without_force(self):
        cmds.createNode("transform", name="mlibSceneUnsaved")
        self.assertTrue(Scene.isModified())
        with self.assertRaises(RuntimeError):
            self.source.openFile()
        with self.assertRaises(RuntimeError):
            Scene.newFile()
        self.assertTrue(cmds.objExists("mlibSceneUnsaved"))
        Scene.newFile(force=True)
        self.assertFalse(cmds.objExists("mlibSceneUnsaved"))
        cmds.createNode("transform", name="mlibSceneUnsaved")
        self.source.openFile(force=True)
        self.assertTrue(cmds.objExists("mlibSceneHelper"))

    def test_open_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            Scene(self.folder / "missing.ma").openFile(force=True)

    def test_save_renames_current_scene(self):
        cmds.createNode("transform", name="mlibSceneSaved")
        target = Scene(self.folder / "saved.mb")
        target.save()
        self.assertTrue(target.is_file())
        self.assertTrue(target.isCurrent())
        self.assertFalse(Scene.isModified())
        # 今のシーンと同じファイルへは force なしで保存し直せる。
        cmds.createNode("transform", name="mlibSceneSavedAgain")
        Scene.getCurrent().save()
        self.assertFalse(Scene.isModified())

    def test_save_refuses_other_existing_file_and_bad_suffix(self):
        with self.assertRaises(FileExistsError):
            self.source.save()
        self.assertIsNone(Scene.getCurrent())
        with self.assertRaises(ValueError):
            Scene(self.folder / "saved.fbx").save()
        self.source.save(force=True)
        self.assertTrue(self.source.isCurrent())

    def test_import_file_returns_new_nodes(self):
        nodes = self.source.importFile(namespace="mlibSceneImport")
        self.assertIsInstance(nodes, mlib.Nodes)
        names = {node.getName() for node in nodes}
        self.assertIn("mlibSceneImport:mlibSceneHelper", names)
        self.assertIn("mlibSceneImport:mlibSceneChild", names)
        self.assertIsNone(Scene.getCurrent())

    def test_import_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            Scene(self.folder / "missing.ma").importFile()

    def test_reference(self):
        reference = self.source.reference(namespace="mlibSceneRef")
        self.assertIsInstance(reference, Reference)
        self.assertTrue(cmds.objExists("mlibSceneRef:mlibSceneHelper"))

    def test_export_all_and_selected(self):
        cmds.createNode("transform", name="mlibSceneA")
        b = cmds.createNode("transform", name="mlibSceneB")
        cmds.select("mlibSceneA", replace=True)
        everything = Scene(self.folder / "all.ma")
        everything.export()
        only_b = Scene(self.folder / "onlyB.mb")
        only_b.export([b])
        # 選択と今のシーンの名前は変わらない。
        self.assertEqual(cmds.ls(selection=True), ["mlibSceneA"])
        self.assertIsNone(Scene.getCurrent())
        names = {node.getName() for node in only_b.importFile(namespace="b")}
        self.assertIn("b:mlibSceneB", names)
        self.assertNotIn("b:mlibSceneA", names)
        names = {node.getName() for node in everything.importFile(namespace="all")}
        self.assertTrue({"all:mlibSceneA", "all:mlibSceneB"} <= names)

    def test_new_file_without_changes_needs_no_force(self):
        """変更が無ければforceなしで新規にでき、名前の無いシーンになる。"""
        self.source.openFile()
        Scene.newFile()
        self.assertIsNone(Scene.getCurrent())
        self.assertFalse(cmds.objExists("mlibSceneHelper"))

    def test_is_current_ignores_case_and_separators_on_windows(self):
        """isCurrentは同じファイルを指すパスならTrue(Windowsでは大文字・小文字と区切り文字を無視)、別のファイルはFalse。"""
        self.source.openFile()
        self.assertTrue(Scene(str(self.source)).isCurrent())
        self.assertFalse(Scene(self.folder / "other.ma").isCurrent())
        if sys.platform == "win32":
            self.assertTrue(Scene(str(self.source).upper().replace("/", "\\")).isCurrent())
        Scene.newFile(force=True)
        self.assertFalse(self.source.isCurrent())

    def test_save_format_follows_suffix(self):
        """.maはmayaAscii、.mbはmayaBinaryで保存し、拡張子の大文字も受け付ける。"""
        ascii_file = Scene(self.folder / "ascii.MA")
        ascii_file.save()
        self.assertEqual(cmds.file(query=True, type=True), ["mayaAscii"])
        self.assertTrue(ascii_file.read_text(encoding="utf-8", errors="replace").startswith("//Maya ASCII"))
        binary_file = Scene(self.folder / "binary.mb")
        binary_file.save()
        self.assertEqual(cmds.file(query=True, type=True), ["mayaBinary"])
        self.assertFalse(binary_file.read_bytes().startswith(b"//Maya ASCII"))

    def test_import_and_reference_without_namespace(self):
        """namespaceを省くとMayaの既定で入れる(インポートは名前空間なし)。"""
        nodes = self.source.importFile()
        self.assertIn("mlibSceneHelper", {node.getName() for node in nodes})
        reference = self.source.reference()
        self.assertIsInstance(reference, Reference)
        # 名前空間はMayaの既定に任せる(このファイルのノードがリファレンスに含まれることだけを確かめる)。
        self.assertTrue(any(name.endswith("mlibSceneHelper") for name in cmds.referenceQuery(reference.getName(), nodes=True)))
        self.assertEqual(Path(cmds.referenceQuery(reference.getName(), filename=True, withoutCopyNumber=True)), Path(str(self.source)))

    def test_export_accepts_node_and_nodes(self):
        """書き出すノードはNode・Nodes・名前の並びで指定でき(名前とNodeは混ぜない)、指定したものだけを書き出す。"""
        a = mlib.getNode(cmds.createNode("transform", name="mlibSceneA"))
        b = cmds.createNode("transform", name="mlibSceneB")
        Scene(self.folder / "fromNode.ma").export(a)
        Scene(self.folder / "fromNodes.ma").export(mlib.Nodes([a, mlib.getNode(b)]))
        names = {node.getName() for node in Scene(self.folder / "fromNode.ma").importFile(namespace="one")}
        self.assertIn("one:mlibSceneA", names)
        self.assertNotIn("one:mlibSceneB", names)
        names = {node.getName() for node in Scene(self.folder / "fromNodes.ma").importFile(namespace="two")}
        self.assertTrue({"two:mlibSceneA", "two:mlibSceneB"} <= names)
        with self.assertRaises(ValueError):
            Scene(self.folder / "bad.obj").export([b])

    def test_export_refuses_existing_file_empty_nodes_and_current_scene(self):
        with self.assertRaises(FileExistsError):
            self.source.export()
        self.source.export(force=True)
        with self.assertRaises(ValueError):
            Scene(self.folder / "empty.ma").export([])
        self.source.openFile(force=True)
        with self.assertRaises(RuntimeError):
            self.source.export(force=True)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
