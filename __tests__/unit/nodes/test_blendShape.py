"""``mlib.nodes.blendShape`` のテスト。

- リグ構築の補助APIの約束を固定する。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.nodes import BlendShape, IkHandle, Joint, Joints, Node
from mlib.plugs import Plug
from support.namespaceCase import NamespaceCase


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
            if (name not in self.existing and cmds.objExists(name) and not cmds.lockNode(name, query=True)[0]
                    and not cmds.objectType(name, isAType="ikSolver")):
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
        pairs = [(int(target[target.index("[") + 1:-1]), alias)
                 for alias, target in zip(items[::2], items[1::2]) if target.startswith("weight[")]
        return [alias for _index, alias in sorted(pairs)]

    def leaf(self, name):
        """完全パス・名前空間を除いた名前を返す。"""
        return name.split("|")[-1].split(":")[-1]


class BlendShapeTargetTest(_SpecCase):
    """ターゲット名による照会・追加・除去。"""

    def setUp(self):
        super().setUp()
        self.base = self.sphere("base")
        self.smile = self.sphere("smile_L")
        self.frown = self.sphere("frown")
        self.blink = self.sphere("blink")
        self.bs = mlib.createBlendShape(self.base, [self.smile, self.frown], name=self.name("bs"))
        self.full = self.bs.getFullName()

    def test_membership_and_weight_plug(self):
        """in はターゲット名の有無、getWeightPlug は weight[i] の Plug を返す。"""
        self.assertIn("smile_L", self.bs)
        self.assertNotIn("missing", self.bs)
        plug = self.bs.getWeightPlug("frown")
        self.assertIsInstance(plug, Plug)
        self.assertEqual((plug.getMulti().getLongName(), plug.getIndex()), ("weight", 1))
        plug.set(0.25)
        self.assertAlmostEqual(cmds.getAttr(self.full + ".frown"), 0.25)

    def test_lookup_errors(self):
        """存在しない名前・番号は ValueError、名前・番号・Plug 以外(bool を含む)は TypeError。"""
        with self.assertRaisesRegex(ValueError, "No blendShape target named 'missing'"):
            self.bs.getTargetIndex("missing")
        with self.assertRaises(ValueError):
            self.bs.getWeightPlug("missing")
        self.assertEqual(self.bs.getTargetIndex(0), 0)
        with self.assertRaises(ValueError):
            self.bs.getTargetIndex(99)
        with self.assertRaises(TypeError):
            self.bs.getTargetIndex(True)
        with self.assertRaises(TypeError):
            self.bs.getTargetIndex(0.0)
        with self.assertRaises(TypeError):
            0 in self.bs

    def test_add_target_and_undo(self):
        """次の番号へ追加し、name でエイリアスを付ける。cmds の照会と一致し、Undo 1回で戻る。"""
        self.flushUndo()
        plug = self.bs.addTarget(self.blink, name="eyeBlink")
        self.assertEqual((plug.getMulti().getLongName(), plug.getIndex()), ("weight", 2))
        self.assertEqual(self.bs.getTargetNames(), ["smile_L", "frown", "eyeBlink"])
        self.assertEqual(self.bs.getTargetNames(), self.aliases(self.bs))
        self.assertUndoesInOneStep(
            lambda: self.assertEqual(self.bs.getTargetNames(), ["smile_L", "frown"]),
            lambda: self.assertIn("eyeBlink", self.bs))

    def test_add_target_default_name(self):
        """name を省略すると Maya の既定(メッシュの名前)になる。"""
        self.bs.addTarget(self.blink)
        self.assertEqual(self.bs.getTargetNames(), ["smile_L", "frown", "blink"])

    def test_add_target_errors(self):
        """重複名・不正な name・存在しないメッシュは追加前に拒否する。"""
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.bs.addTarget(self.blink, name="frown")
        with self.assertRaises(ValueError):
            self.bs.addTarget(self.blink, name="")
        with self.assertRaises(TypeError):
            self.bs.addTarget(self.blink, name=3)
        with self.assertRaises(RuntimeError):
            self.bs.addTarget(self.name("missing"))
        self.assertEqual(self.bs.getTargetNames(), ["smile_L", "frown"])

    def test_remove_target_fully(self):
        """weight の要素・エイリアス・inputTargetGroup を消す(cmds の remove と同じ)。Undo 1回で戻る。"""
        self.flushUndo()
        self.assertIs(self.bs.removeTarget("smile_L"), self.bs)
        self.assertEqual(self.bs.getTargetNames(), ["frown"])
        self.assertEqual(cmds.getAttr(self.full + ".weight", multiIndices=True), [1])
        self.assertEqual(cmds.getAttr(self.full + ".inputTarget[0].inputTargetGroup", multiIndices=True), [1])
        self.assertNotIn("smile_L", cmds.aliasAttr(self.full, query=True))
        self.assertUndoesInOneStep(
            lambda: self.assertEqual(self.bs.getTargetNames(), ["smile_L", "frown"]),
            lambda: self.assertNotIn("smile_L", self.bs))
        self.assertEqual(cmds.getAttr(self.full + ".inputTarget[0].inputTargetGroup", multiIndices=True), [0, 1])

    def test_remove_matches_cmds_remove(self):
        """cmds.blendShape(edit=True, remove=True) と同じ属性の状態になる。"""
        other_base = self.sphere("otherBase")
        other = cmds.blendShape(self.smile, self.frown, other_base, name=self.name("other"))[0]
        cmds.blendShape(other, edit=True, remove=True, target=(other_base, 0, self.smile, 1.0))
        self.bs.removeTarget("smile_L")
        for attribute in ("weight", "inputTarget[0].inputTargetGroup"):
            self.assertEqual(cmds.getAttr(self.full + "." + attribute, multiIndices=True),
                             cmds.getAttr(other + "." + attribute, multiIndices=True))
        self.assertEqual(self.bs.getTargetNames(), self.aliases(other))

    def test_remove_with_deleted_target_mesh(self):
        """ターゲットのメッシュを削除した後でも除去できる。"""
        cmds.delete(self.smile)
        self.bs.removeTarget("smile_L")
        self.assertEqual(self.bs.getTargetNames(), ["frown"])
        self.assertEqual(cmds.getAttr(self.full + ".inputTarget[0].inputTargetGroup", multiIndices=True), [1])

    def test_remove_errors(self):
        """存在しない名前は ValueError、ロックしたウェイトは RuntimeError で、何も変えない。"""
        with self.assertRaises(ValueError):
            self.bs.removeTarget("missing")
        cmds.setAttr(self.full + ".weight[0]", lock=True)
        with self.assertRaisesRegex(RuntimeError, "locked"):
            self.bs.removeTarget("smile_L")
        self.assertEqual(self.bs.getTargetNames(), ["smile_L", "frown"])

    def test_deleted_node(self):
        """削除済みの blendShape の照会は RuntimeError。"""
        cmds.delete(self.full)
        with self.assertRaises(RuntimeError):
            self.bs.getTargetNames()


if __name__ == "__main__":
    unittest.main()
