"""``mlib.nodes.joint`` のテスト。

- リグ構築の補助APIの約束を固定する。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Joint, Node


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


class JointMirrorTest(_SpecCase):
    """Joint.mirror は cmds.mirrorJoint と同じチェーンを作り、新しいルートを返す。"""

    def setUp(self):
        super().setUp()
        self.group = cmds.createNode("transform", name=self.name("grp"), skipSelect=True)
        self.joints = self.chain(("L_a", (1, 0, 0)), ("L_b", (3, 1, -1)), ("L_c", (5, 0, 1)))
        cmds.parent(self.joints[0], self.group)
        self.joints = cmds.ls(cmds.listRelatives(self.group, allDescendents=True, fullPath=True), long=True)[::-1]
        Joint(self.joints[0]).orient()

    def matrices(self, root):
        names = [root] + (cmds.listRelatives(root, allDescendents=True, fullPath=True) or [])[::-1]
        return [cmds.xform(name, query=True, worldSpace=True, matrix=True) for name in names]

    def test_matches_cmds(self):
        """全フラグの組み合わせで、新しいルートの名前・親・ワールドマトリクスが cmds と一致する。

        axis はミラー面(``"YZ"``)と反転する軸(``"x"``)のどちらの書き方でも同じ面になる。
        """
        for axis, plane in (("YZ", "YZ"), ("XY", "XY"), ("xz", "XZ"), ("x", "YZ"), ("ZX", "XZ"), (2, "XY")):
            for behavior in (True, False):
                with self.subTest(axis=axis, behavior=behavior):
                    flag = "mirror" + plane
                    expected = cmds.mirrorJoint(self.joints[0], mirrorBehavior=behavior, searchReplace=("L_", "E_"), **{flag: True})
                    expected_root = self.group + "|" + expected[0]
                    root = Joint(self.joints[0]).mirror(axis, behavior, searchReplace=("L_", "R_"))
                    self.assertIs(type(root), Joint)
                    self.assertEqual(root.getParent(), Node(self.group))
                    self.assertEqual(self.leaf(root.getName()), "R_a")
                    self.assertEqual([self.leaf(n.getName()) for n in root.getChainFromHere()], ["R_a", "R_b", "R_c"])
                    for actual, wanted in zip(self.matrices(root.getFullName()), self.matrices(expected_root)):
                        self.assertSequenceAlmostEqual(actual, wanted, places=6)
                    cmds.delete(root.getFullName(), expected_root)

    def test_world_root_and_auto_name(self):
        """親の無いルートでも新しいルートを一意に返す。searchReplace 省略は Maya の自動命名。"""
        cmds.parent(self.joints[0], world=True)
        root_name = cmds.ls(self.name("L_a"), long=True)[0]
        root = Joint(root_name).mirror()
        self.assertIsNone(root.getParent())
        self.assertNotEqual(root, Joint(root_name))
        self.assertEqual(len(root.getChainFromHere()), 3)

    def test_undo_once(self):
        """鏡映は Undo 1回で戻り、選択も元に戻る。新しいルートを選択する。元のチェーンは変わらない。"""
        before = self.matrices(self.joints[0])
        cmds.select(clear=True)
        self.flushUndo()
        root = Joint(self.joints[0]).mirror(searchReplace=("L_", "R_"))
        self.assertEqual(cmds.ls(selection=True, long=True), [root.getFullName()])
        self.assertUndoesInOneStep(
            lambda: self.assertEqual((cmds.ls(self.name("R_*")), cmds.ls(selection=True)), ([], [])),
            lambda: self.assertEqual(len(cmds.ls(self.name("R_*"))), 3),
        )
        self.assertEqual(self.matrices(self.joints[0]), before)

    def test_errors(self):
        """不正な引数は編集前に型付きの例外になる。"""
        joint = Joint(self.joints[0])
        cases = (
            (ValueError, dict(axis="W")),
            (ValueError, dict(axis="xyz")),
            (TypeError, dict(axis=1.5)),
            (TypeError, dict(behavior=1)),
            (TypeError, dict(searchReplace="L_")),
            (TypeError, dict(searchReplace=("L_",))),
            (TypeError, dict(searchReplace=("L_", 1))),
            (ValueError, dict(searchReplace=("", "R_"))),
        )
        before = cmds.ls(type="joint")
        for error, flags in cases:
            with self.subTest(flags=flags):
                with self.assertRaises(error):
                    joint.mirror(**flags)
        self.assertEqual(cmds.ls(type="joint"), before)
        cmds.delete(self.joints[0])
        with self.assertRaises(RuntimeError):
            joint.mirror()


if __name__ == "__main__":
    unittest.main()
