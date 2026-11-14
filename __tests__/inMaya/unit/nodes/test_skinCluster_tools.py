"""``mlib.nodes.skinCluster`` のテスト。

- リグ・スキン向けの API の契約を固定する。
- スキンのウェイト編集向けの照会・編集の契約を固定する。
"""

import math
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Joint, Mesh, SkinCluster


def _distance(first, second):
    """2点の距離(Python 3.7 には math.dist が無いため)。"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _world_points(name):
    selection = om2.MSelectionList()
    selection.add(name)
    path = selection.getDagPath(0)
    path.extendToShape()
    return [(p.x, p.y, p.z) for p in om2.MFnMesh(path).getPoints(om2.MSpace.kObject)]


class _RigCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, offset=(0, 0, 0)):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        cmds.move(offset[0], offset[1], offset[2], self.mesh)
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True, maximumInfluences=3)[0])
        cmds.select(clear=True)
        return self.skin


class UnlockedInfluencesTest(_RigCase):
    def test_unlock_and_restore(self):
        """ロックしていたものだけを外し、抜けると戻す。中で書いたウェイトは残る。"""
        skin = self.skinned()
        skin.setInfluencesLocked([self.root, self.tip], True)
        with skin.unlockedInfluences() as value:
            self.assertIs(value, skin)
            self.assertEqual(skin.getLockedInfluences(), [])
            skin.setWeights([self.root], [1.0], vertices=[0], normalize=True)
        self.assertEqual(sorted(n.getName() for n in skin.getLockedInfluences()), sorted(mlib.getNode(n).getName() for n in (self.root, self.tip)))
        self.assertAlmostEqual(skin.getWeights([self.root], vertices=[0])[0], 1.0, places=6)

    def test_subset_and_exception(self):
        """指定したものだけを外し、例外でも戻す。"""
        skin = self.skinned()
        skin.setInfluencesLocked([self.root, self.tip], True)
        with self.assertRaises(KeyError):
            with skin.unlockedInfluences([self.root]):
                self.assertFalse(cmds.getAttr(self.root + ".lockInfluenceWeights"))
                self.assertTrue(cmds.getAttr(self.tip + ".lockInfluenceWeights"))
                raise KeyError("test")
        self.assertTrue(cmds.getAttr(self.root + ".lockInfluenceWeights"))
        self.assertTrue(cmds.getAttr(self.tip + ".lockInfluenceWeights"))

    def test_undo_once(self):
        """抜けた後の Undo 1回で、ロックしたまま元のウェイトへ戻る。"""
        skin = self.skinned()
        skin.setInfluencesLocked([self.tip], True)
        before = skin.getWeights([self.root, self.mid, self.tip])
        self.flushUndo()
        with skin.unlockedInfluences():
            skin.setWeights([self.tip], [1.0], vertices=[0], normalize=True)
        self.assertTrue(cmds.getAttr(self.tip + ".lockInfluenceWeights"))
        cmds.undo()
        self.assertTrue(cmds.getAttr(self.tip + ".lockInfluenceWeights"))
        self.assertSequenceAlmostEqual(skin.getWeights([self.root, self.mid, self.tip]), before, places=6)
        self.assertUndoEmpty()

    def test_undo_inside(self):
        """with の中で Undo しても(ロックの解除まで戻しても)、抜けるとロックへ戻る。"""
        skin = self.skinned()
        skin.setInfluencesLocked([self.tip], True)
        with skin.unlockedInfluences():
            cmds.undo()
            self.assertTrue(cmds.getAttr(self.tip + ".lockInfluenceWeights"))
        self.assertTrue(cmds.getAttr(self.tip + ".lockInfluenceWeights"))
        with skin.unlockedInfluences():
            skin.setWeights([self.tip], [1.0], vertices=[0], normalize=True)
            cmds.undo()
        self.assertTrue(cmds.getAttr(self.tip + ".lockInfluenceWeights"))

    def test_errors(self):
        skin = self.skinned()
        cmds.select(clear=True)
        other = cmds.joint(name=self.name("other"))

        def enter(joints):
            with skin.unlockedInfluences(joints):
                pass

        self.assertRaises(ValueError, enter, [other])
        self.assertRaises(ValueError, enter, [])


class InvertShapeTest(_RigCase):
    def posed_and_sculpted(self, offset=(0, 0, 0)):
        skin = self.skinned(offset)
        cmds.setAttr(self.mid + ".rotateZ", 40)
        cmds.setAttr(self.root + ".rotateX", 10)
        sculpt = cmds.duplicate(self.mesh, name=self.name("sculpt"))[0]
        for shape in cmds.listRelatives(sculpt, shapes=True, fullPath=True):
            if cmds.getAttr(shape + ".intermediateObject"):
                cmds.delete(shape)
        cmds.move(5, 0, 0, sculpt, relative=True)
        for index in (3, 12, 20, 33):
            cmds.move(0.3, 0.2, -0.4, f"{sculpt}.vtx[{index}]", relative=True, objectSpace=True)
        return skin, sculpt

    def check_matches(self, offset=(0, 0, 0), front=None):
        skin, sculpt = self.posed_and_sculpted(offset)
        if front is not None:
            front()
        result = skin.invertShape(sculpt)
        self.assertIsInstance(result, Mesh)
        blend = cmds.blendShape(result.getParent().getFullName(), self.mesh, frontOfChain=True, name=self.name("corrective"))[0]
        cmds.setAttr(blend + ".weight[0]", 1.0)
        for actual, expected in zip(_world_points(self.mesh), _world_points(sculpt)):
            self.assertLess(_distance(actual, expected), 1e-3)
        return result

    def test_matches_sculpted(self):
        """補正形状を blendShape で足すと、現在のポーズで sculpted と一致する。"""
        result = self.check_matches()
        self.assertTrue(result.getParent().getName().endswith("sculpt_inverted"))

    def test_moved_mesh(self):
        """メッシュを動かしてからバインドした(geomMatrix が単位でない)場合も一致する。"""
        self.check_matches(offset=(1.5, 0.5, -2))

    def test_existing_blend_shape(self):
        """skinCluster より前に、値の入った blendShape(ターゲットの形状は削除済み)があっても一致する。"""

        def front():
            target = cmds.polyCylinder(name=self.name("bump"), height=4, subdivisionsHeight=8)[0]
            cmds.move(0, 0, 0.5, target + ".vtx[0:20]", relative=True)
            blend = cmds.blendShape(target, self.mesh, frontOfChain=True, name=self.name("bumpBlend"))[0]
            cmds.setAttr(blend + ".weight[0]", 0.7)
            # ターゲットの形状を残すと blendShape は入力に対する絶対位置として働くため、差分だけにする。
            cmds.delete(target)

        self.check_matches(front=front)

    def test_undo_once(self):
        skin, sculpt = self.posed_and_sculpted()
        before = set(cmds.ls(self.ns + ":*"))
        self.flushUndo()
        skin.invertShape(sculpt, name=self.name("fix"))
        self.assertTrue(cmds.objExists(self.name("fix")))
        cmds.undo()
        self.assertEqual(set(cmds.ls(self.ns + ":*")), before)
        self.assertUndoEmpty()

    def test_errors(self):
        skin, sculpt = self.posed_and_sculpted()
        other = cmds.polyCube(name=self.name("cube"))[0]
        self.assertRaises(ValueError, skin.invertShape, other)
        self.assertRaises(TypeError, skin.invertShape, self.root)
        self.assertRaises(TypeError, skin.invertShape, sculpt, name=1)
        self.assertRaises(ValueError, skin.invertShape, sculpt, name="")


class _SkinCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, max_influences=3):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True, maximumInfluences=max_influences)[0])
        cmds.select(clear=True)
        return self.skin

    def raw(self, skin=None):
        skin = skin or self.skin
        return [round(value, 6) for value in skin.getWeights([self.root, self.mid, self.tip])]


class SkinLockTest(_SkinCase):
    def test_lock_roundtrip(self):
        """SkinCluster と Joint のどちらからもロックを読み書きでき、cmds の値と一致する。"""
        skin = self.skinned()
        self.assertEqual(skin.getLockedInfluences(), [])
        self.assertIs(skin.setInfluencesLocked([self.root, self.tip]), skin)
        self.assertEqual([node.getName() for node in skin.getLockedInfluences()], [mlib.getNode(self.root).getName(), mlib.getNode(self.tip).getName()])
        self.assertTrue(cmds.getAttr(self.root + ".liw"))
        mid = Joint(self.mid)
        self.assertFalse(mid.isInfluenceLocked())
        self.assertIs(mid.setInfluenceLocked(), mid)
        self.assertTrue(cmds.getAttr(self.mid + ".liw"))
        skin.setInfluencesLocked([self.root, self.mid, self.tip], state=False)
        self.assertEqual(skin.getLockedInfluences(), [])

    def test_lock_errors_and_undo(self):
        """未登録・bool 以外は例外。バインドしていない joint は isInfluenceLocked が False で set は RuntimeError。"""
        skin = self.skinned()
        cmds.select(clear=True)
        loose = Joint(cmds.joint(name=self.name("loose")))
        self.assertFalse(loose.isInfluenceLocked())
        self.assertRaises(RuntimeError, loose.setInfluenceLocked)
        self.assertRaises(ValueError, skin.setInfluencesLocked, [loose])
        self.assertRaises(TypeError, skin.setInfluencesLocked, [self.root], state=1)
        cmds.flushUndo()
        skin.setInfluencesLocked([self.root, self.mid])
        cmds.undo()
        self.assertFalse(cmds.getAttr(self.root + ".liw") or cmds.getAttr(self.mid + ".liw"))


class SkinRowsTest(_SkinCase):
    def test_rows_match_flat(self):
        """rows=True は平坦な値を頂点ごとに分けたもの。指定頂点も同じ。"""
        skin = self.skinned()
        joints = [self.root, self.mid, self.tip]
        flat = list(skin.getWeights(joints))
        rows = skin.getWeights(joints, rows=True)
        self.assertEqual(len(rows), cmds.polyEvaluate(self.mesh, vertex=True))
        self.assertEqual([value for row in rows for value in row], flat)
        part = skin.getWeights(joints, vertices=[5, 2], rows=True)
        self.assertEqual(part, [rows[5], rows[2]])

    def test_set_rows(self):
        """rows=True で書いた行を読み戻す。行の長さ違い・broadcast 併用は ValueError。"""
        skin = self.skinned()
        joints = [self.root, self.mid, self.tip]
        for fast in (False, True):
            with self.subTest(fast=fast):
                skin.setWeights(joints, [[0.5, 0.5, 0.0], [0.0, 0.25, 0.75]], vertices=[0, 1], rows=True, fast=fast)
                self.assertEqual(skin.getWeights(joints, vertices=[0, 1], rows=True), [[0.5, 0.5, 0.0], [0.0, 0.25, 0.75]])
        self.assertRaises(ValueError, skin.setWeights, joints, [[1.0, 0.0]], vertices=[0], rows=True)
        self.assertRaises(ValueError, skin.setWeights, joints, [[1.0, 0.0, 0.0]], vertices=[0], rows=True, broadcast=True)
        self.assertRaises(TypeError, skin.setWeights, joints, [1.0, 0.0, 0.0], vertices=[0], rows=True)
        self.assertRaises(TypeError, skin.getWeights, joints, rows=1)


class SkinRemoveInfluencesTest(_SkinCase):
    def test_parent_and_child_move_to_remaining_ancestor(self):
        """mid と tip を同時に外すと、両方のウェイトが root へ集まる(Undo 1回で戻る)。"""
        skin = self.skinned()
        before = skin.getWeights([self.root, self.mid, self.tip], rows=True)
        cmds.flushUndo()
        self.assertIs(skin.removeInfluences([self.mid, self.tip]), skin)
        self.assertEqual([node.getName() for node in skin.getInfluences()], [mlib.getNode(self.root).getName()])
        for value in skin.getWeights([self.root]):
            self.assertAlmostEqual(value, 1.0, places=6)
        cmds.undo()
        self.assertEqual(len(skin.getInfluences()), 3)
        after = skin.getWeights([self.root, self.mid, self.tip], rows=True)
        for row, original in zip(after, before):
            for value, expected in zip(row, original):
                self.assertAlmostEqual(value, expected, places=6)

    def test_errors_before_change(self):
        """残る祖先が無い・全部・未登録・重複は変更前に ValueError。"""
        skin = self.skinned()
        before = self.raw()
        cases = (
            lambda: skin.removeInfluences([self.root]),
            lambda: skin.removeInfluences([self.root, self.mid, self.tip], transferToParent=False),
            lambda: skin.removeInfluences([self.name("missing_joint")]),
            lambda: skin.removeInfluences([self.mid, self.mid]),
        )
        for index, call in enumerate(cases):
            with self.subTest(case=index):
                self.assertRaises((ValueError, RuntimeError), call)
        self.assertEqual(len(skin.getInfluences()), 3)
        self.assertEqual(self.raw(), before)
        self.assertRaises(TypeError, skin.removeInfluences, [self.tip], transferToParent=1)

    def test_without_transfer_root_allowed(self):
        """transferToParent=False なら root も外せる。"""
        skin = self.skinned()
        skin.removeInfluences([self.root], transferToParent=False)
        self.assertEqual(len(skin.getInfluences()), 2)


class SkinSettingsTest(_SkinCase):
    def test_settings_by_name(self):
        """名前で読み書きし、cmds の値と一致する。不正な名前は ValueError、型違いは TypeError。"""
        skin = self.skinned()
        self.assertEqual(skin.getSkinningMethod(), "classicLinear")
        self.assertIs(skin.setSkinningMethod("dualQuaternion"), skin)
        self.assertEqual(cmds.getAttr(skin.getFullName() + ".skinningMethod"), 1)
        self.assertEqual(skin.getNormalizeMode(), "interactive")
        skin.setNormalizeMode("post")
        self.assertEqual(cmds.getAttr(skin.getFullName() + ".normalizeWeights"), 2)
        self.assertEqual(skin.isMaintainingMaxInfluences(), bool(cmds.getAttr(skin.getFullName() + ".maintainMaxInfluences")))
        self.assertRaises(ValueError, skin.setSkinningMethod, "linear")
        self.assertRaises(TypeError, skin.setNormalizeMode, 1)
        cmds.flushUndo()
        skin.setSkinningMethod("weightBlended")
        cmds.undo()
        self.assertEqual(skin.getSkinningMethod(), "dualQuaternion")


if __name__ == "__main__":
    unittest.main()
