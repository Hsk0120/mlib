"""親への移送、正規化、十進丸め、最大influence数を実Mayaで検証する。"""

import sys
import unittest
import uuid
from decimal import Decimal
from unittest.mock import patch

import maya.cmds as cmds

import mlib

mlib.reload()


class SkinWeightEditingTest(unittest.TestCase):
    def setUp(self):
        self.ns = "mlibWeights_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)
        self.parent = cmds.createNode("joint", name=self.ns + ":parent")
        self.child = cmds.createNode("joint", name=self.ns + ":child", parent=self.parent)
        self.other = cmds.createNode("joint", name=self.ns + ":other")
        self.mesh = cmds.polyCube(name=self.ns + ":mesh", constructionHistory=False)[0]
        self.skin = mlib.getNode(cmds.skinCluster([self.parent, self.child, self.other], self.mesh, toSelectedBones=True, name=self.ns + ":skin")[0])
        pose = self.skin.getBindPose()
        if pose:
            cmds.rename(pose.getName(full=True), self.ns + ":pose")
        self.names = [self.parent, self.child, self.other]
        cmds.setAttr(self.skin.getName(full=True) + ".normalizeWeights", 0)
        self.skin.setWeights(self.names, [0.2, 0.5, 0.3], broadcast=True)

    def tearDown(self):
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def weights(self):
        return list(self.skin.getWeights(self.names))

    def test_joint_remove_without_parent_transfer_matches_skin(self):
        """Joint入口も親移送を無効にでき、SkinCluster入口と同じ値になる。"""
        self.skin.removeInfluences(self.child, transferToParent=False)
        expected = list(self.skin.getWeights([self.parent, self.other]))
        cmds.undo()
        joint = mlib.getNode(self.child)
        joint.removeInfluence(self.skin, transferToParent=False)
        actual = list(self.skin.getWeights([self.parent, self.other]))
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b)
        self.assertTrue(joint.isValid())
        cmds.undo()
        with self.assertRaises(TypeError):
            joint.removeInfluence(self.skin, transferToParent="false")
        self.assertTrue(self.skin.hasInfluence(self.child))

    def test_remove_influence_transfers_and_keeps_joint(self):
        self.skin.removeInfluences(mlib.getNode(self.child), requireAncestor=False)
        self.assertTrue(cmds.objExists(self.child))
        self.assertFalse(self.skin.hasInfluence(self.child))
        values = list(self.skin.getWeights([self.parent, self.other]))
        self.assertAlmostEqual(values[0], 0.7)
        self.assertAlmostEqual(values[1], 0.3)
        cmds.undo()
        self.assertTrue(self.skin.hasInfluence(self.child))
        self.assertAlmostEqual(self.weights()[1], 0.5)
        cmds.redo()
        self.assertFalse(self.skin.hasInfluence(self.child))

    def test_joint_entry_and_last_influence_guard(self):
        joint = mlib.getNode(self.child)
        self.assertIsNone(joint.removeInfluence(self.skin))
        self.assertFalse(self.skin.hasInfluence(self.child))
        cmds.undo()
        joint.removeInfluence()
        self.assertFalse(self.skin.hasInfluence(self.child))
        self.skin.removeInfluences(self.other, requireAncestor=False)
        with self.assertRaises(ValueError):
            self.skin.removeInfluences(self.parent, requireAncestor=False)
        self.assertTrue(cmds.objExists(self.parent))
        self.assertTrue(cmds.objExists(self.skin.getName(full=True)))

    def test_normalize_undo_and_decimal_sum(self):
        self.skin.setWeights(self.names, [1, 1, 1], broadcast=True)
        self.skin.normalizeWeights()
        self.assertAlmostEqual(sum(self.weights()[:3]), 1)
        cmds.undo()
        self.assertEqual(self.weights()[:3], [1, 1, 1])
        self.skin.normalizeWeights(ndigits=2)
        self.assertEqual(self.weights()[:3], [0.34, 0.33, 0.33])
        self.assertEqual(sum(Decimal(str(v)) for v in self.weights()[:3]), Decimal(1))
        self.assertEqual(cmds.getAttr(self.skin.getName(full=True) + ".normalizeWeights"), 0)
        cmds.undo()
        self.assertEqual(self.weights()[:3], [1, 1, 1])
        cmds.redo()
        self.assertEqual(self.weights()[:3], [0.34, 0.33, 0.33])

    def test_zero_and_locked_rejected_before_changes(self):
        self.skin.setWeights(self.names, [0, 0, 0], broadcast=True)
        with self.assertRaises(ValueError):
            self.skin.normalizeWeights()
        self.skin.setWeights(self.names, [0.2, 0.5, 0.3], broadcast=True)
        cmds.setAttr(self.child + ".lockInfluenceWeights", True)
        before = self.weights()
        with self.assertRaises(RuntimeError):
            self.skin.normalizeWeights(ndigits=2)
        self.assertEqual(self.weights(), before)

    def test_max_setting_preserves_weights_and_prune(self):
        before, old_max = self.weights(), self.skin.getMaxInfluences()
        self.skin.setMaxInfluences(2, maintain=True)
        self.assertEqual(self.skin.getMaxInfluences(), 2)
        self.assertEqual(self.weights(), before)
        cmds.undo()
        self.assertEqual(self.skin.getMaxInfluences(), old_max)
        self.skin.setMaxInfluences(2, maintain=True, prune=True)
        row = self.weights()[:3]
        self.assertEqual(row[0], 0)
        self.assertAlmostEqual(row[1], 0.625)
        self.assertAlmostEqual(row[2], 0.375)
        cmds.undo()
        self.assertEqual(self.weights(), before)

    def test_max_influences_maintain_default_keeps_setting(self):
        """setMaxInfluences の maintain は既定 None(変えない)。指定したときだけ maintainMaxInfluences を書く。位置では渡せない。"""
        name = self.skin.getName(full=True)
        cmds.setAttr(name + ".maintainMaxInfluences", False)
        self.skin.setMaxInfluences(3)
        self.assertFalse(cmds.getAttr(name + ".maintainMaxInfluences"))
        self.skin.setMaxInfluences(3, maintain=True)
        self.assertTrue(cmds.getAttr(name + ".maintainMaxInfluences"))
        self.skin.setMaxInfluences(4)
        self.assertTrue(cmds.getAttr(name + ".maintainMaxInfluences"))
        self.assertEqual(self.skin.getMaxInfluences(), 4)
        with self.assertRaises(TypeError):
            self.skin.setMaxInfluences(3, True)
        with self.assertRaises(TypeError):
            self.skin.setMaxInfluences(3, maintain=1)

    def test_invalid_arguments_and_failure_propagation(self):
        before = self.weights()
        for ndigits, error in ((-1, ValueError), (16, ValueError), (1.5, TypeError), (True, TypeError)):
            with self.subTest(ndigits=ndigits), self.assertRaises(error):
                self.skin.normalizeWeights(ndigits)
        for count, error in ((0, ValueError), (-1, ValueError), (1.5, TypeError), (True, TypeError)):
            with self.subTest(count=count), self.assertRaises(error):
                self.skin.setMaxInfluences(count)
        self.assertEqual(self.weights(), before)
        with patch.object(type(self.skin), "_write_weight_entries", side_effect=RuntimeError("transfer failed")):
            with self.assertRaisesRegex(RuntimeError, "transfer failed"):
                mlib.getNode(self.child).removeInfluence()
        self.assertTrue(self.skin.hasInfluence(self.child))

    def test_transfer_preserves_non_normalized_totals(self):
        self.skin.setWeights(self.names, [0.4, 1, 0.6], broadcast=True)
        self.skin.removeInfluences(self.child, requireAncestor=False)
        values = list(self.skin.getWeights([self.parent, self.other]))
        self.assertAlmostEqual(values[0], 1.4)
        self.assertAlmostEqual(values[1], 0.6)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
