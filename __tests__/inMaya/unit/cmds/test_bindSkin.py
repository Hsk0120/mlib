"""``mlib.cmds.bindSkin`` のテスト。"""

import json
import sys
import unittest
import uuid
from pathlib import Path

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

_TEMP = Path(__file__).resolve().parents[3] / "_output" / "temp"


class BindSkinTest(NamespaceCase):
    """短縮名・Undo・引数の検査と、ウェイトのファイルを使うバインドを確かめる。"""

    PREFIX = "mlibBindSkin_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        # skinClusterやバインドポーズもこの名前空間へ作らせ、終了時に一緒に消す。
        cmds.namespace(set=self.ns)
        cmds.select(clear=True)
        self.joints = [cmds.joint(name=f"j{index}", position=(0, y, 0)) for index, y in enumerate((-1, 0, 1))]
        cmds.select(clear=True)
        self.files = []

    def tearDown(self):
        cmds.namespace(set=":")
        for path in self.files:
            if path.exists():
                path.unlink()
        super().tearDown()

    def cube(self, text="cube"):
        """ヒストリの無いpolyCubeのtransform名を返す。"""
        return cmds.polyCube(name=text, subdivisionsY=2, constructionHistory=False)[0]

    def exported(self, data=None):
        """1つ目のcubeをバインドしてウェイトを書き出し、(パス, 読み込んだJSON)を返す。dataで中身を差し替える。"""
        source = self.source = self.cube("source")
        skin = mlib.bindSkin(self.joints, source)
        _TEMP.mkdir(parents=True, exist_ok=True)
        path = _TEMP / f"mlibBindSkin_{uuid.uuid4().hex}.json"
        self.files.append(path)
        skin.exportWeights(str(path))
        content = json.loads(path.read_text(encoding="utf-8"))
        if data is not None:
            content["data"].update(data)
            path.write_text(json.dumps(content), encoding="utf-8")
        return path, content

    def test_binds_only_given_joints_by_default(self):
        """既定はtoSelectedBones=True(指定したjointだけ)で、toSelectedBones・tsbを渡せばその値を使う(子孫もバインド)。"""
        root = cmds.ls(self.joints[0], long=True)[0]
        skin = mlib.bindSkin([root], self.cube("onlyRoot"))
        self.assertEqual(cmds.ls(cmds.skinCluster(skin.getName(full=True), query=True, influence=True), long=True), [root])
        for flags in ({"toSelectedBones": False}, {"tsb": False}):
            with self.subTest(flags=flags):
                skin = mlib.bindSkin([root], self.cube("hierarchy"), **flags)
                self.assertEqual(len(cmds.skinCluster(skin.getName(full=True), query=True, influence=True)), 3)

    def test_short_flag_and_undo_once(self):
        """miはmaximumInfluencesと同じ値でバインドし、Undo 1回でskinClusterが消える。"""
        cube = self.cube()
        self.flushUndo()
        skin = mlib.bindSkin(self.joints, cube, mi=2)
        name = skin.getName(full=True)
        self.assertEqual(cmds.skinCluster(name, query=True, maximumInfluences=True), 2)
        self.assertEqual(cmds.getAttr(name + ".normalizeWeights"), 1)
        self.assertEqual(len(cmds.skinCluster(name, query=True, influence=True)), 3)
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))

    def test_invalid_arguments_bind_nothing(self):
        """不正な引数はバインドせずに例外にする。"""
        cube = self.cube()
        for args, kwargs, error in (
            ((self.joints, cube), {"query": True}, TypeError),
            ((self.joints, cube), {"e": True}, TypeError),
            ((self.joints, cube), {"maximumInfluences": 0}, ValueError),
            ((self.joints, cube), {"maximumInfluences": True}, ValueError),
            ((self.joints, cube), {"maximumInfluences": 2, "mi": 2}, TypeError),
            (([], cube), {}, ValueError),
            ((None, cube), {}, ValueError),
            ((self.joints, cube), {"namespaceMap": {"a": "b"}}, TypeError),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                mlib.bindSkin(*args, **kwargs)
        self.assertFalse(cmds.ls(cmds.listHistory(cube), type="skinCluster"))
        mlib.bindSkin(self.joints, cube)
        with self.assertRaises(ValueError):
            mlib.bindSkin(self.joints, cube)

    def test_weights_with_explicit_joints_and_flags(self):
        """weightsとjointsを両方渡すと、ファイルのインフルエンスも加えて書き込む。書き込んだ後の設定はファイルの値になる。"""
        path, content = self.exported()
        target = self.cube("target")
        skin = mlib.bindSkin([self.joints[0]], target, weights=str(path), normalizeWeights=2)
        name = skin.getName(full=True)
        self.assertEqual(len(cmds.skinCluster(name, query=True, influence=True)), 3)
        source = mlib.getNode(cmds.ls(cmds.listHistory(self.source), type="skinCluster")[0])
        self.assertSequenceAlmostEqual(skin.getWeights(self.joints), source.getWeights(self.joints), places=5)
        # 指定したフラグでバインドし、書き込んだ後はファイルの値(Interactive)に戻る。
        self.assertEqual(cmds.getAttr(name + ".normalizeWeights"), 1)
        self.assertEqual(content["data"]["vertexCount"], cmds.polyEvaluate(target, vertex=True))

    def test_weights_file_rejections(self):
        """メッシュでない形状・位置の無いファイル・シーンに無いインフルエンスは、バインドせずにValueErrorにする。"""
        path, _ = self.exported()
        curve = cmds.curve(degree=1, point=[(0, 0, 0), (1, 0, 0)], name="curve")
        with self.assertRaisesRegex(ValueError, "メッシュが必要"):
            mlib.bindSkin(None, curve, weights=str(path))
        target = self.cube("target")
        with self.assertRaisesRegex(ValueError, "インフルエンスがシーンに1つもありません"):
            mlib.bindSkin(None, target, weights=str(path), namespaceMap={self.ns: self.ns + "Missing"})
        no_positions, _ = self.exported({"positions": []})
        with self.assertRaisesRegex(ValueError, "頂点の位置がありません"):
            mlib.bindSkin(None, target, weights=str(no_positions), method="position")
        self.assertFalse(cmds.ls(cmds.listHistory(target), type="skinCluster"))

    def test_missing_file_and_nodes(self):
        mesh = self.cube("target")
        with self.assertRaises(OSError):
            mlib.bindSkin(None, mesh, weights=str(_TEMP / f"mlibBindSkin_missing_{uuid.uuid4().hex}.json"))
        for joints, geometry in ((["noSuchJoint"], mesh), (self.joints, "noSuchGeometry")):
            with self.subTest(joints=joints, geometry=geometry), self.assertRaises(RuntimeError):
                mlib.bindSkin(joints, geometry)
        self.assertEqual(cmds.ls(cmds.listHistory(mesh) or [], type="skinCluster"), [])

    def test_weights_onto_shape(self):
        """weightsで、transformでなくメッシュのシェイプを渡してもバインドできる。"""
        path, _content = self.exported()
        target = self.cube("target")
        shape = cmds.listRelatives(target, shapes=True, fullPath=True)[0]
        skin = mlib.bindSkin(None, shape, weights=str(path))
        self.assertEqual(cmds.ls(cmds.listHistory(target), type="skinCluster"), [skin.getName()])
        source_skin = cmds.ls(cmds.listHistory(self.source), type="skinCluster")[0]
        for got, want in zip(
            cmds.skinPercent(skin.getName(), target + ".vtx[0]", query=True, value=True),
            cmds.skinPercent(source_skin, self.source + ".vtx[0]", query=True, value=True),
        ):
            self.assertAlmostEqual(got, want, places=5)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
