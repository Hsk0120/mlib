"""``mlib.common.scene`` のテスト。

Scene がパスとして振る舞うことと、今のシーンの照会・新規・開く・保存・インポート・リファレンス・書き出しを確かめる。
シーンを初期化するので、作業中の Maya GUI へ送らない。
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Scene
from mlib.nodes.reference import Reference


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


class SceneFileTest(unittest.TestCase):
    """今のシーンの照会とファイルの操作。"""

    def setUp(self):
        cmds.file(new=True, force=True)
        self.folder = Path(tempfile.mkdtemp())
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
