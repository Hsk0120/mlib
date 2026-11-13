"""正式コマンド・取得の省略入口と生成専用の契約を検証する。

あわせて次も確かめる。

- 入口(作成関数・objExists・Time・キーの追加/削除・Shapeの親変更・setPreferredAngle)の約束を固定する。
"""

from pathlib import Path
import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Time
from support.namespaceCase import NamespaceCase


class CommandNamesTest(unittest.TestCase):
    """生成の旧名は除去し、取得の省略入口とオブジェクト側の編集を確認する。"""

    def test_exports_and_files(self):
        """基礎コマンドと作成関数だけを、同名のファイルとルートから公開する。"""
        expected = {"getNode", "getPlug", "createNode", "ls", "delete", "duplicate", "select", "objExists", "bindSkin",
                    "bakeDeformer", "bakeResults", "createJointChain",
                    "createContainer", "createDagContainer", "createDagPose", "createIkHandle", "createBlendShape",
                    "createCurve", "createCircle", "createLocator", "createPolyCube", "createPolySphere",
                    "createPolyCylinder", "createPolyPlane", "createGroup", "createNurbsPlane", "createCluster",
                    "createLattice", "createWire"}
        mlib.reload()
        self.assertEqual(set(mlib.cmds.__all__), expected)
        folder = Path(mlib.__file__).parent / "cmds"
        self.assertEqual({path.stem for path in folder.glob("*.py") if path.stem != "__init__"}, expected)
        for name in expected:
            self.assertIs(getattr(mlib, name), getattr(mlib.cmds, name))
            self.assertTrue(callable(getattr(mlib, name)))
        for name in ("node", "plug", "attr", "constraint", "curve", "ikHandle", "sets", "group", "listNodes"):
            self.assertFalse(hasattr(mlib, name), name)
            self.assertNotIn(name, mlib.cmds.__all__)

    def test_enum_edit_and_undo(self):
        """既存Nodeの追加アトリビュートとenum編集はUndoを保つ。"""
        node = mlib.createNode("transform", name="commandNames_" + uuid.uuid4().hex, skipSelect=True)
        try:
            enum = node.addAttr("mode", attributeType="enum", enumName="one:two")
            enum.setEnumNames(["local", "world", "foot"])
            self.assertEqual(enum.getEnumValue("foot"), 2)
            cmds.undo()
            self.assertEqual(enum.getEnumValue("two"), 1)
            cmds.redo()
            self.assertEqual(enum.getEnumValue("world"), 1)
        finally:
            node.delete()


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、UI単位・選択の補助。"""

    PREFIX = "mlibSpecEntry_"

    def setUp(self):
        """UI単位・時刻を保存して名前空間を用意する。"""
        super().setUp()
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.time = cmds.currentTime(query=True)
        self.range = (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))

    def tearDown(self):
        """UI単位・時刻を戻す。"""
        cmds.currentUnit(linear=self.linear)
        cmds.playbackOptions(minTime=self.range[0], maxTime=self.range[1])
        cmds.currentTime(self.time)
        super().tearDown()

    def assert_one_undo(self, action):
        """actionを1回のUndoで戻せ、作ったノードが消えることを確かめる。"""
        before = set(cmds.ls(long=True))
        cmds.flushUndo()
        result = action()
        self.assertTrue(set(cmds.ls(long=True)) - before)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        return result


class CreateNodeFunctionsTest(_SpecCase):
    """クラスメソッドから移した作成関数は型付きのラッパーを返し、旧入口は無い。"""

    def test_functions_and_removed_classmethods(self):
        """container・IK・blendShape・dagPose・bindSkinを作り、旧createとbindは無い。"""
        cmds.select(clear=True)
        j0 = cmds.joint(name=self.name("j0"), position=(0, 0, 0))
        j1 = cmds.joint(name=self.name("j1"), position=(5, 0, 1))
        j2 = cmds.joint(name=self.name("j2"), position=(10, 0, 0))
        self.assertIsInstance(mlib.createContainer(self.name("own")), mlib.Container)
        self.assertIsInstance(mlib.createDagContainer(self.name("dag")), mlib.DagContainer)
        handle = mlib.createIkHandle(j0, j2, name=self.name("ikh"))
        self.assertIsInstance(handle, mlib.IkHandle)
        self.assertIsInstance(mlib.createDagPose(j0, name=self.name("pose")), mlib.DagPose)
        mesh = mlib.createPolyCube(name=self.name("skinned")).getParent()
        skin = mlib.bindSkin([j0, j1], mesh, maximumInfluences=2)
        self.assertIsInstance(skin, mlib.SkinCluster)
        self.assertEqual(skin.getMaxInfluences(), 2)
        with self.assertRaises(ValueError):
            mlib.bindSkin([j0], mesh)
        with self.assertRaises(TypeError):
            mlib.bindSkin([j0], mlib.createPolyCube().getParent(), maximumInfluences=2, mi=2)
        base = mlib.createPolyCube(name=self.name("base")).getParent()
        target = mlib.createPolyCube(name=self.name("target")).getParent()
        self.assertEqual(mlib.createBlendShape(base, [target]).getTargetNames(), [target.getNodeName(removeNamespace=True)])
        for wrapper in (mlib.Container, mlib.DagContainer, mlib.DagPose, mlib.IkHandle,
                        mlib.BlendShape, mlib.NurbsCurve):
            with self.subTest(wrapper=wrapper.__name__):
                self.assertNotIn("create", vars(wrapper))
        self.assertFalse(hasattr(mlib.SkinCluster, "bind"))


if __name__ == "__main__":
    unittest.main()
