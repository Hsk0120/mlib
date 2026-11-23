"""BlendShapeのbaseWeightsの値・疎番号・版別の評価とUndoを検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class BlendShapeBaseWeightsTest(NamespaceCase):
    def setup_blend(self):
        base = cmds.polyCube(name=self.name("base"), constructionHistory=False)[0]
        target = cmds.duplicate(base, name=self.name("target"))[0]
        cmds.move(0, 2, 0, target + ".vtx[0]", relative=True)
        blend = mlib.Node(cmds.blendShape(target, base, name=self.name("blend"))[0])
        return blend, base, target

    def test_defaults_do_not_materialize_elements(self):
        blend, base, _target = self.setup_blend()
        path = blend.getFullName() + ".inputTarget[0].baseWeights"
        before = cmds.getAttr(path, multiIndices=True)
        values = blend.getTargetWeights(base=base)
        self.assertEqual(values, [1.0] * 8)
        self.assertEqual(cmds.getAttr(path, multiIndices=True), before)
        values[0] = 99
        self.assertEqual(blend.getTargetWeights()[0], 1.0)
        # target=None(省略)がベースのウェイト。位置引数でも同じで、ターゲットのウェイトとは別の値。
        self.assertEqual(blend.getTargetWeights(None, base), [1.0] * 8)
        self.assertEqual(blend.getTargetWeights(None), blend.getTargetWeights())
        blend.setTargetWeights(None, {2: 0.5})
        blend.setTargetWeights(0, {2: 0.25})
        self.assertEqual(blend.getTargetWeights()[2], 0.5)
        self.assertEqual(blend.getTargetWeights(0)[2], 0.25)
        self.assertEqual(cmds.getAttr(path + "[2]"), 0.5)

    def test_dense_sparse_undo_redo_and_fast(self):
        blend, _base, _target = self.setup_blend()
        self.flushUndo()
        self.assertIsNone(blend.setTargetWeights(None, [0.25] * 8))
        self.assertEqual(blend.getTargetWeights(), [0.25] * 8)
        cmds.undo()
        self.assertEqual(blend.getTargetWeights(), [1.0] * 8)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        cmds.redo()
        self.assertEqual(blend.getTargetWeights(), [0.25] * 8)
        self.flushUndo()
        blend.setTargetWeights(None, {0: -2.0, 7: 3.0})
        # 複数回の setAttr に分かれる書き込みは、今までどおりの名前の Undo チャンクにまとめる。
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "mlibBlendShapeSetBaseWeights")
        self.assertEqual(blend.getTargetWeights(), [-2.0] + [0.25] * 6 + [3.0])
        cmds.undo()
        self.assertEqual(blend.getTargetWeights(), [0.25] * 8)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.flushUndo()
        state = cmds.undoInfo(query=True, state=True)
        self.assertIsNone(blend.setTargetWeights(None, {0: 0.75, 7: 0.5}, fast=True))
        self.assertEqual(blend.getTargetWeights(), [0.75] + [0.25] * 6 + [0.5])
        self.assertEqual(cmds.undoInfo(query=True, state=True), state)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_preflight_lock_and_connection(self):
        blend, _base, _target = self.setup_blend()
        path = blend.getFullName() + ".inputTarget[0].baseWeights[7]"
        cmds.setAttr(path, lock=True)
        try:
            for fast in (False, True):
                self.flushUndo()
                with self.assertRaises(RuntimeError):
                    blend.setTargetWeights(None, {0: 0.2, 7: 0.4}, fast=fast)
                self.assertEqual(blend.getTargetWeights(), [1.0] * 8)
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        finally:
            cmds.setAttr(path, lock=False)
        driver = self.make(text="driver")
        cmds.setAttr(driver + ".translateX", 1)
        cmds.connectAttr(driver + ".translateX", path)
        for fast in (False, True):
            with self.assertRaises(RuntimeError):
                blend.setTargetWeights(None, [0.2] * 8, fast=fast, check=True)
            self.assertEqual(blend.getTargetWeights(), [1.0] * 8)

    def test_values_and_flags_are_validated_before_update(self):
        blend, _base, _target = self.setup_blend()
        for weights, exception in [([1.0], ValueError), ({8: 0.0}, IndexError), ({True: 0.5}, TypeError), ({0: "bad"}, TypeError), ("bad", TypeError)]:
            with self.subTest(weights=weights), self.assertRaises(exception):
                blend.setTargetWeights(None, weights)
            self.assertEqual(blend.getTargetWeights(), [1.0] * 8)
        for flags in ({"fast": 1}, {"check": 1}):
            with self.assertRaises(TypeError):
                blend.setTargetWeights(None, {}, **flags)
        with self.assertRaises(ValueError):
            blend.setTargetWeights(None, {0: float("nan")}, check=True)
        self.flushUndo()
        self.assertIsNone(blend.setTargetWeights(None, {}))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_multiple_bases_and_generic_mask_are_separate(self):
        blend, base, target = self.setup_blend()
        second = cmds.polyCube(name=self.name("second"), constructionHistory=False)[0]
        blend.addBaseGeometry(second)
        blend.setTargetWeights(None, {1: 0.25}, base=second)
        self.assertEqual(blend.getTargetWeights(base=base), [1.0] * 8)
        self.assertEqual(blend.getTargetWeights(base=second), [1.0, 0.25] + [1.0] * 6)
        with self.assertRaises(ValueError):
            blend.setTargetWeights(None, {0: 0.5}, base=target)
        name = blend.getFullName()
        cmds.setAttr(name + ".weight[0]", 1)
        blend.setTargetWeights(None, {0: 0.5}, base)
        has_generic = cmds.attributeQuery("weightList", node=name, exists=True)
        if has_generic:
            self.assertAlmostEqual(cmds.pointPosition(base + ".vtx[0]", local=True)[1], 1.5)
            cmds.setAttr(name + ".weightList[0].weights[0]", 0.25)
            self.assertAlmostEqual(cmds.pointPosition(base + ".vtx[0]", local=True)[1], 0.0)
            self.assertEqual(blend.getTargetWeights(base=base)[0], 0.5)
            self.assertEqual(blend.getDeformerWeights()[0], 0.25)
        else:
            self.assertAlmostEqual(cmds.pointPosition(base + ".vtx[0]", local=True)[1], 0.5)
        blend.setTargetWeights(0, {0: 0.5})
        expected = -0.25 if has_generic else 0.0
        self.assertAlmostEqual(cmds.pointPosition(base + ".vtx[0]", local=True)[1], expected)

    def test_plural_updates_share_one_undo(self):
        first, _base, _target = self.setup_blend()
        second, _other_base, _other_target = self.setup_blend()
        blends = mlib.Nodes([first, second])
        self.flushUndo()
        self.assertEqual(blends.setTargetWeights(None, {0: 0.25, 7: 0.5}), [None, None])
        for blend in blends:
            self.assertEqual(blend.getTargetWeights(), [0.25] + [1.0] * 6 + [0.5])
        cmds.undo()
        for blend in blends:
            self.assertEqual(blend.getTargetWeights(), [1.0] * 8)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
