"""influence 解除(cmds.skinCluster -removeInfluence)の通常経路の契約を固定する。

- ウェイトのロックは一時的に外して解除し、元へ戻す。
- Closest in hierarchy の連続解除も処理でき、Undo 1 回でウェイトと登録が戻る。
- fast 引数は持たない(OpenMaya で書いても速くならないため)。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.nodes import SkinCluster


class _Rig:
    """root→mid→tip の chain と、別階層の other(子 otherEnd を持つ)にバインドした円柱。

    Args:
        case (NamespaceCase): 名前を作るテスト。
        tag (str): 名前の接頭辞。
        meshes (int): 同じ joint にバインドする円柱の数。
        bind_method (int): skinCluster.bindMethod。
        max_influences (int): skinCluster の maximumInfluences。
    """

    def __init__(self, case, tag, meshes=1, bind_method=0, max_influences=2):
        name = case.name
        cmds.select(clear=True)
        self.root = cmds.joint(name=name(tag + "root"), position=(0, 0, 0))
        self.mid = cmds.joint(name=name(tag + "mid"), position=(0.2, 1, 0))
        self.tip = cmds.joint(name=name(tag + "tip"), position=(0, 2, 0.1))
        cmds.select(clear=True)
        self.other = cmds.joint(name=name(tag + "other"), position=(1.5, 0.3, 0))
        self.other_end = cmds.joint(name=name(tag + "otherEnd"), position=(2.5, 1.5, 0))
        cmds.select(clear=True)
        self.joints = [self.root, self.mid, self.tip, self.other]
        self.skins = []
        for _ in range(meshes):
            mesh = cmds.polyCylinder(name=name(tag + "mesh#"), height=2, subdivisionsHeight=4)[0]
            cmds.move(0, 1, 0, mesh)
            skin = cmds.skinCluster(self.joints, mesh, toSelectedBones=True, maximumInfluences=max_influences)[0]
            cmds.setAttr(skin + ".bindMethod", bind_method)
            self.skins.append(SkinCluster(skin))
        cmds.select(clear=True)

    def configure(self, normalize=1, locked=False, dropoff=None):
        """normalizeWeights・ロック・dropoff を設定する。"""
        for skin in self.skins:
            cmds.setAttr(skin.getFullName() + ".normalizeWeights", normalize)
            if dropoff is not None:
                cmds.setAttr(skin.getFullName() + ".dropoff[0]", dropoff)
        cmds.setAttr(self.other + ".liw", locked)
        return self

    def raw(self):
        """全 skinCluster の weightList を {頂点: {論理番号: 値}} で返す(存在しない要素は 0 扱い)。"""
        result = []
        for skin in self.skins:
            name = skin.getFullName()
            rows = {}
            for vertex in cmds.getAttr(name + ".weightList", multiIndices=True) or []:
                prefix = f"{name}.weightList[{vertex}].weights"
                indices = cmds.getAttr(prefix, multiIndices=True) or []
                rows[vertex] = {index: cmds.getAttr(f"{prefix}[{index}]") for index in indices}
            influences = [node.getName().rsplit(":", 1)[-1][1:] for node in skin.getInfluences()]
            result.append((influences, rows))
        return result


class RemoveInfluenceTest(NamespaceCase):
    """通常経路の influence 解除。"""

    PREFIX = "mlibSpecSkinRemove_"

    def setUp(self):
        super().setUp()
        self.selection = cmds.ls(selection=True, long=True)

    def tearDown(self):
        if self.selection:
            cmds.select(self.selection, replace=True)
        else:
            cmds.select(clear=True)
        super().tearDown()

    def test_locked_influence_is_restored(self):
        """ウェイトのロックがあっても解除でき、ロックは元へ戻り、Undo 1 回で全て戻る。"""
        rig = _Rig(self, "n").configure(locked=True)
        before = rig.raw()
        cmds.flushUndo()
        rig.skins[0].removeInfluences(rig.tip, transferToParent=True, requireAncestor=False)
        self.assertFalse(rig.skins[0].hasInfluence(rig.tip))
        self.assertTrue(cmds.getAttr(rig.other + ".liw"))
        cmds.undo()
        self.assertEqual(rig.raw(), before)
        self.assertTrue(cmds.getAttr(rig.other + ".liw"))

    def test_closest_in_hierarchy_consecutive(self):
        """Closest in hierarchy の連続解除も処理できる。"""
        rig = _Rig(self, "n", bind_method=1)
        for skin in rig.skins:
            for joint in (rig.tip, rig.mid):
                skin.removeInfluences(joint, transferToParent=False)
        self.assertEqual(len(rig.skins[0].getInfluences()), 2)

    def test_normal_undo_once(self):
        """通常経路は Undo 1 回でウェイトと登録が戻る。"""
        rig = _Rig(self, "n")
        before = rig.raw()
        cmds.flushUndo()
        rig.skins[0].removeInfluences(rig.tip, transferToParent=False)
        cmds.undo()
        self.assertEqual(rig.raw(), before)


class RemoveInfluencesArgumentsTest(NamespaceCase):
    """removeInfluences の requireAncestor・戻り値・unused と同時に指定できない引数。"""

    PREFIX = "mlibSpecSkinRemoveArgs_"

    def tearDown(self):
        cmds.select(clear=True)
        super().tearDown()

    def test_require_ancestor_default_rejects_without_change(self):
        """既定(requireAncestor=True)は、ウェイトを受け取る祖先のインフルエンスが残らないと ValueError で、何も変えない。"""
        rig = _Rig(self, "a")
        skin = rig.skins[0]
        cases = (("root", [rig.root]), ("other", rig.other), ("tip and root", [rig.tip, rig.root]), ("whole chain", [rig.root, rig.mid, rig.tip]))
        for label, joints in cases:
            with self.subTest(label):
                before = rig.raw()
                cmds.flushUndo()
                with self.assertRaisesRegex(ValueError, "ウェイトを受け取る祖先のインフルエンスが残っていません"):
                    skin.removeInfluences(joints)
                self.assertEqual(rig.raw(), before)
                self.assertEqual(len(skin.getInfluences()), 4)
                with self.assertRaises(ValueError):
                    skin.removeInfluences(joints, requireAncestor=True)
                self.assertEqual(rig.raw(), before)

    def test_require_ancestor_false_matches_native_redistribution(self):
        """requireAncestor=False は、祖先が無いインフルエンスを Maya 標準の配り直し(skinCluster -removeInfluence)で外す。"""
        for normalize in (1, 0, 2):
            with self.subTest(normalize=normalize):
                rig = _Rig(self, f"b{normalize}").configure(normalize=normalize)
                skin = rig.skins[0]
                before = rig.raw()
                cmds.skinCluster(skin.getFullName(), edit=True, removeInfluence=rig.root)
                native = rig.raw()
                cmds.undo()
                self.assertEqual(rig.raw(), before)
                cmds.flushUndo()
                removed = skin.removeInfluences(rig.root, requireAncestor=False)
                self.assertEqual([node.getName() for node in removed], [rig.root])
                self.assertFalse(skin.hasInfluence(rig.root))
                self.assertEqual(rig.raw(), native)
                cmds.undo()
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
                self.assertEqual(rig.raw(), before)

    def test_require_ancestor_false_still_transfers_when_ancestor_exists(self):
        """requireAncestor=False でも、祖先があるインフルエンスは祖先へ移す(既定で1本ずつ外した結果と同じ)。"""
        rig = _Rig(self, "c")
        skin = rig.skins[0]
        before = rig.raw()
        skin.removeInfluences(rig.tip)
        skin.removeInfluences(rig.root, requireAncestor=False)
        expected = rig.raw()
        cmds.undo()
        cmds.undo()
        self.assertEqual(rig.raw(), before)
        cmds.flushUndo()
        removed = skin.removeInfluences([rig.root, rig.tip], requireAncestor=False)
        self.assertEqual([node.getName() for node in removed], [rig.root, rig.tip])
        self.assertEqual(rig.raw(), expected)
        # まとめて外しても Undo は1回。
        cmds.undo()
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertEqual(rig.raw(), before)

    def test_transfer_to_parent_false_ignores_require_ancestor(self):
        """transferToParent=False は祖先を探さないので、祖先が無くても既定の requireAncestor のまま外せる。"""
        rig = _Rig(self, "d")
        skin = rig.skins[0]
        before = rig.raw()
        cmds.skinCluster(skin.getFullName(), edit=True, removeInfluence=rig.root)
        native = rig.raw()
        cmds.undo()
        self.assertEqual(rig.raw(), before)
        for flags in ({}, {"requireAncestor": True}, {"requireAncestor": False}):
            with self.subTest(flags=flags):
                cmds.flushUndo()
                skin.removeInfluences(rig.root, transferToParent=False, **flags)
                self.assertEqual(rig.raw(), native)
                cmds.undo()
                self.assertEqual(rig.raw(), before)

    def test_returns_removed_nodes_in_given_order(self):
        """戻り値は外したノードの Nodes(すべて joint なら Joints)。渡した順に並び、名前でも Node でも1つでも同じ。"""
        cases = (
            ("deep first given shallow first", lambda rig: [rig.mid, rig.tip], lambda rig: [rig.mid, rig.tip]),
            ("single name", lambda rig: rig.tip, lambda rig: [rig.tip]),
            ("single node", lambda rig: mlib.getNode(rig.tip), lambda rig: [rig.tip]),
            ("nodes", lambda rig: mlib.Joints([rig.tip, rig.mid]), lambda rig: [rig.tip, rig.mid]),
        )
        for index, (label, joints, expected) in enumerate(cases):
            with self.subTest(label):
                rig = _Rig(self, f"e{index}")
                skin = rig.skins[0]
                removed = skin.removeInfluences(joints(rig))
                self.assertIsInstance(removed, mlib.Nodes)
                self.assertIsInstance(removed, mlib.Joints)
                self.assertEqual([node.getName() for node in removed], expected(rig))
                # 外したのは登録だけで、ノードは残る。
                self.assertTrue(all(node.isValid() for node in removed))
                self.assertEqual([skin.hasInfluence(node) for node in removed], [False] * len(removed))

    def test_unused_returns_nodes_and_rejects_other_arguments(self):
        """unused=True は外したノードの Nodes を返し、joints・transferToParent・requireAncestor と同時に指定できない(TypeError)。"""
        rig = _Rig(self, "f")
        skin = rig.skins[0]
        skin.setWeights(rig.joints, [1.0, 0.0, 0.0, 0.0], broadcast=True)
        before = rig.raw()
        cases = (
            ("nothing", lambda: skin.removeInfluences()),
            ("unused False only", lambda: skin.removeInfluences(unused=False)),
            ("joints", lambda: skin.removeInfluences(rig.tip, unused=True)),
            ("transferToParent True", lambda: skin.removeInfluences(unused=True, transferToParent=True)),
            ("transferToParent False", lambda: skin.removeInfluences(unused=True, transferToParent=False)),
            ("requireAncestor True", lambda: skin.removeInfluences(unused=True, requireAncestor=True)),
            ("requireAncestor False", lambda: skin.removeInfluences(unused=True, requireAncestor=False)),
            ("unused int", lambda: skin.removeInfluences(unused=1)),
            ("positional flag", lambda: skin.removeInfluences(rig.tip, True)),
        )
        for label, call in cases:
            with self.subTest(label), self.assertRaises(TypeError):
                call()
            self.assertEqual(rig.raw(), before)
        expected = [node.getName() for node in skin.getInfluences(unused=True)]
        self.assertEqual(expected, [rig.mid, rig.tip, rig.other])
        cmds.flushUndo()
        removed = skin.removeInfluences(unused=True)
        self.assertIsInstance(removed, mlib.Nodes)
        self.assertEqual([node.getName() for node in removed], expected)
        self.assertEqual([node.getName() for node in skin.getInfluences()], [rig.root])
        cmds.undo()
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        # Undo で登録は戻る。0 のウェイトの要素は Maya が作り直さないことがあるので、0 でない値だけを比べる。
        self.assertEqual([influences for influences, _rows in rig.raw()], [influences for influences, _rows in before])

        def nonzero(raw):
            """0 でないウェイトだけを残す。"""
            return [{vertex: {index: value for index, value in row.items() if value} for vertex, row in rows.items()} for _names, rows in raw]

        self.assertEqual(nonzero(rig.raw()), nonzero(before))
        # 使っていないものが無ければ空の集まり。
        skin.removeInfluences(unused=True)
        again = skin.removeInfluences(unused=True)
        self.assertIsInstance(again, mlib.Nodes)
        self.assertEqual(list(again), [])

    def test_all_influences_and_invalid_input(self):
        """すべて外す指定・未登録・重複・空は ValueError で、登録は変わらない。"""
        rig = _Rig(self, "g")
        skin = rig.skins[0]
        before = rig.raw()
        with self.assertRaisesRegex(ValueError, "すべてのインフルエンスを削除することはできません"):
            skin.removeInfluences(rig.joints, requireAncestor=False)
        for joints in ([rig.other_end], [rig.tip, rig.tip], []):
            with self.subTest(joints=joints), self.assertRaises(ValueError):
                skin.removeInfluences(joints, requireAncestor=False)
        self.assertEqual(rig.raw(), before)

    def test_influence_filters_and_force_normalize_arguments(self):
        """getInfluences(locked=, unused=) は True・False・None で絞り、normalizeWeights(force=True) は decimals と同時に指定できない。"""
        rig = _Rig(self, "h").configure(normalize=0, locked=True)
        skin = rig.skins[0]
        skin.setWeights(rig.joints, [0.5, 0.25, 0.0, 0.75], broadcast=True)
        names = lambda nodes: [node.getName() for node in nodes]  # noqa: E731  # この関数の中だけで使う短い変換。
        self.assertEqual(names(skin.getInfluences()), rig.joints)
        self.assertEqual(names(skin.getInfluences(locked=True)), [rig.other])
        self.assertEqual(names(skin.getInfluences(locked=False)), [rig.root, rig.mid, rig.tip])
        self.assertEqual(names(skin.getInfluences(unused=True)), [rig.tip])
        self.assertEqual(names(skin.getInfluences(unused=False)), [rig.root, rig.mid, rig.other])
        self.assertEqual(names(skin.getInfluences(locked=False, unused=False)), [rig.root, rig.mid])
        self.assertEqual(names(skin.getInfluences(locked=True, unused=True)), [])
        self.assertEqual(names(skin.getInfluences(locked=None, unused=None)), rig.joints)
        self.assertIsInstance(skin.getInfluences(locked=True), mlib.Nodes)
        before = rig.raw()
        for call in (
            lambda: skin.normalizeWeights(3, force=True),
            lambda: skin.normalizeWeights(decimals=0, force=True),
            lambda: skin.normalizeWeights(force=1),
        ):
            with self.assertRaises(TypeError):
                call()
            self.assertEqual(rig.raw(), before)
        # force=True は、正規化の設定(none)とウェイトのロックがあっても合計を1にする(通常は Undo 1回、fast は Undo なし)。
        for fast in (False, True):
            with self.subTest(fast=fast):
                cmds.flushUndo()
                self.assertIsNone(skin.normalizeWeights(force=True, fast=fast))
                rows = skin.getWeights(rig.joints, rows=True)
                for row in rows:
                    self.assertAlmostEqual(sum(row), 1.0)
                    self.assertAlmostEqual(row[0], 0.5 / 1.5)
                self.assertEqual(cmds.getAttr(skin.getFullName() + ".normalizeWeights"), 0)
                self.assertTrue(cmds.getAttr(rig.other + ".liw"))
                if fast:
                    self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
                else:
                    cmds.undo()
                    self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
                    self.assertEqual(rig.raw(), before)


if __name__ == "__main__":
    unittest.main()
