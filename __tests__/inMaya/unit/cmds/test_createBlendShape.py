"""``mlib.cmds.createBlendShape`` のテスト。

- リグ構築の補助APIの約束を固定する。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import BlendShape, Node


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecRigBuilders_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        # Maya が現在の名前空間へ作るノード(エフェクター・自動カーブ・名前空間を外した鏡映)も片付ける。
        self.existing = set(cmds.ls(long=True))

    def tearDown(self):
        for name in cmds.ls(long=True):
            if name not in self.existing and cmds.objExists(name) and not cmds.lockNode(name, query=True)[0] and not cmds.objectType(name, isAType="ikSolver"):
                cmds.delete(name)
        super().tearDown()

    def chain(self, *items):
        """(名前, 位置) の並びで、選択を使わずに親子の joint を作る。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(text), position=position) for text, position in items]
        cmds.select(clear=True)
        return [cmds.ls(name, long=True)[0] for name in names]

    def sphere(self, text):
        """構築履歴の無い polySphere の transform を作る。"""
        return cmds.polySphere(name=self.name(text), constructionHistory=False)[0]

    def aliases(self, blend):
        """aliasAttr の照会から、weight のエイリアスを論理番号順に返す。"""
        items = cmds.aliasAttr(str(blend), query=True) or []
        pairs = [(int(target[target.index("[") + 1 : -1]), alias) for alias, target in zip(items[::2], items[1::2]) if target.startswith("weight[")]
        return [alias for _index, alias in sorted(pairs)]

    def leaf(self, name):
        """完全パス・名前空間を除いた名前を返す。"""
        return name.split("|")[-1].split(":")[-1]


class BlendShapeCreateTest(_SpecCase):
    """BlendShape.create は cmds.blendShape と同じターゲット構成を作る。"""

    def setUp(self):
        super().setUp()
        self.base = self.sphere("base")
        self.smile = self.sphere("smile_L")
        self.blink = self.sphere("blink")

    def test_registered_class(self):
        """blendShape は手書きの BlendShape として包まれる。"""
        node = Node(cmds.blendShape(self.smile, self.base)[0])
        self.assertIs(type(node), BlendShape)
        self.assertIn("BlendShape", mlib.nodes.__all__)

    def test_create_matches_cmds(self):
        """ターゲットは指定順に 0 から並び、名前・ウェイトは cmds の照会と一致する。frontOfChain が既定。"""
        bs = mlib.createBlendShape(self.base, [self.smile, self.blink], name=self.name("bs"))
        self.assertIs(type(bs), BlendShape)
        self.assertEqual(bs.getName(), self.name("bs"))
        self.assertEqual(bs.getTargetNames(), self.aliases(bs))
        self.assertEqual(bs.getTargetNames(), ["smile_L", "blink"])
        self.assertEqual(bs.getTargetIndex("blink"), 1)
        self.assertEqual([n.getFullName() for n in bs.getBaseGeometry()], cmds.ls(cmds.blendShape(bs.getFullName(), query=True, geometry=True), long=True))

    def test_front_of_chain(self):
        """既定はスキンより前(履歴の上流)、frontOfChain=False は最後に置く。"""
        cmds.select(clear=True)
        joint = cmds.joint(name=self.name("bind"))
        cmds.select(clear=True)
        skin = cmds.skinCluster(joint, self.base, toSelectedBones=True)[0]
        front = mlib.createBlendShape(self.base, self.smile, name=self.name("front"))
        last = mlib.createBlendShape(self.base, self.blink, name=self.name("last"), frontOfChain=False)
        history = cmds.listHistory(self.base, pruneDagObjects=True, interestLevel=1)
        self.assertLess(history.index(skin), history.index(front.getName()))
        self.assertLess(history.index(last.getName()), history.index(skin))

    def test_empty_create_and_undo(self):
        """ターゲット省略で空の blendShape を作る。作成は Undo 1回で戻る。"""
        self.flushUndo()
        bs = mlib.createBlendShape(self.base, name=self.name("empty"))
        name = bs.getFullName()
        self.assertEqual(bs.getTargetNames(), [])
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))

    def test_create_errors(self):
        """不正な引数は作成前に型付きの例外になり、blendShape を残さない。"""
        before = cmds.ls(type="blendShape")
        with self.assertRaisesRegex(TypeError, "frontOfChainはboolで指定してください"):
            mlib.createBlendShape(self.base, self.smile, frontOfChain=1)
        with self.assertRaises(TypeError):
            mlib.createBlendShape(self.base, self.smile, name=1)
        with self.assertRaises(ValueError):
            mlib.createBlendShape(self.base, self.smile, name="")
        with self.assertRaises(RuntimeError):
            mlib.createBlendShape(self.name("missing"), self.smile)
        self.assertEqual(cmds.ls(type="blendShape"), before)


if __name__ == "__main__":
    unittest.main()
