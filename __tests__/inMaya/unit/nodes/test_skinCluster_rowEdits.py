"""``SkinCluster.limitInfluences``・``roundWeights`` と、``transferWeights`` の ``vertices``・``add`` を確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

ROWS = [[0.5, 0.3, 0.2], [0.123456, 0.654321, 0.222223], [0.0, 0.6, 0.4], [0.1, 0.1, 0.8]]


class _Case(unittest.TestCase):
    """3本のインフルエンスでバインドした立方体(頂点0〜3に決まった値)を用意する。"""

    def setUp(self):
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)
        joints = []
        for index in range(3):
            cmds.select(clear=True)
            joints.append(cmds.joint(name=f"rowEdit{index}", position=(index, 0, 0)))
        self.joints = [mlib.getNode(name) for name in joints]
        mesh = cmds.polyCube(name="rowEditMesh", constructionHistory=False)[0]
        self.skin = mlib.getNode(cmds.skinCluster(joints, mesh, toSelectedBones=True)[0])
        self.skin.setWeights(self.joints, ROWS, vertices=[0, 1, 2, 3], rows=True)
        self.others = self.rows([4, 5, 6, 7])
        cmds.flushUndo()

    def rows(self, vertices):
        return self.skin.getWeights(self.joints, vertices=vertices, rows=True)

    def assertRowsAlmostEqual(self, actual, expected, places=6):
        for row, wanted in zip(actual, expected):
            for value, target in zip(row, wanted):
                self.assertAlmostEqual(value, target, places=places)

    def assertNormalized(self, vertices):
        for row in self.rows(vertices):
            self.assertAlmostEqual(sum(row), 1.0, places=5)


class LimitInfluencesTest(_Case):
    """頂点ごとのインフルエンス数の制限。"""

    def test_limits_count_and_normalizes(self):
        self.skin.limitInfluences(1)
        for row in self.rows([0, 1, 2, 3]):
            self.assertEqual(sum(1 for value in row if value > 0.0), 1)
        self.assertRowsAlmostEqual(self.rows([0, 1, 2, 3]), [[1, 0, 0], [0, 1, 0], [0, 1, 0], [0, 0, 1]])

    def test_keeps_ratio_of_remaining(self):
        self.skin.limitInfluences(2)
        self.assertRowsAlmostEqual(self.rows([0]), [[0.5 / 0.8, 0.3 / 0.8, 0.0]])
        # 2本以下の頂点は変えない。
        self.assertRowsAlmostEqual(self.rows([2]), [[0.0, 0.6, 0.4]])

    def test_locked_influence_is_kept_and_counted_first(self):
        self.skin.setInfluencesLocked([self.joints[2]], True)
        self.skin.limitInfluences(1, vertices=[0])
        # ロックした0.2が先に数に入るので、残りは0になり、ロックしていない値が全部0なら変えない。
        self.assertRowsAlmostEqual(self.rows([0]), [ROWS[0]])
        self.skin.limitInfluences(2, vertices=[0])
        self.assertRowsAlmostEqual(self.rows([0]), [[0.8, 0.0, 0.2]])

    def test_vertices_limit_the_target(self):
        self.skin.limitInfluences(1, vertices=[0])
        self.assertRowsAlmostEqual(self.rows([0]), [[1, 0, 0]])
        self.assertRowsAlmostEqual(self.rows([1, 3]), [ROWS[1], ROWS[3]])
        self.assertRowsAlmostEqual(self.rows([4, 5, 6, 7]), self.others)

    def test_one_undo_and_fast(self):
        self.skin.limitInfluences(1)
        expected = self.rows([0, 1, 2, 3])
        cmds.undo()
        self.assertRowsAlmostEqual(self.rows([0, 1, 2, 3]), ROWS)
        cmds.flushUndo()
        self.skin.limitInfluences(1, fast=True)
        self.assertRowsAlmostEqual(self.rows([0, 1, 2, 3]), expected)
        self.assertFalse(cmds.undoInfo(query=True, undoName=True))

    def test_invalid_count(self):
        for value, error in ((True, TypeError), (1.0, TypeError), ("2", TypeError), (0, ValueError), (-1, ValueError)):
            with self.subTest(value=value), self.assertRaises(error):
                self.skin.limitInfluences(value)
        self.assertRowsAlmostEqual(self.rows([0, 1, 2, 3]), ROWS)


class RoundWeightsTest(_Case):
    """ウェイトの丸め。"""

    def test_rounds_and_keeps_sum(self):
        self.skin.roundWeights(2)
        self.assertRowsAlmostEqual(self.rows([1]), [[0.12, 0.66, 0.22]])
        self.assertNormalized([0, 1, 2, 3])

    def test_locked_influence_is_not_rounded(self):
        self.skin.setInfluencesLocked([self.joints[0]], True)
        self.skin.roundWeights(2, vertices=[1])
        row = self.rows([1])[0]
        self.assertAlmostEqual(row[0], 0.123456, places=6)
        self.assertAlmostEqual(row[2], 0.22, places=6)
        self.assertAlmostEqual(sum(row), 1.0, places=5)

    def test_one_undo_and_fast(self):
        self.skin.roundWeights(1)
        expected = self.rows([0, 1, 2, 3])
        cmds.undo()
        self.assertRowsAlmostEqual(self.rows([0, 1, 2, 3]), ROWS)
        cmds.flushUndo()
        self.skin.roundWeights(1, fast=True)
        self.assertRowsAlmostEqual(self.rows([0, 1, 2, 3]), expected)
        self.assertFalse(cmds.undoInfo(query=True, undoName=True))

    def test_invalid_ndigits(self):
        for value, error in ((True, TypeError), (2.0, TypeError), (0, ValueError)):
            with self.subTest(value=value), self.assertRaises(error):
                self.skin.roundWeights(value)


class TransferWeightsOptionsTest(_Case):
    """transferWeights の vertices と add。"""

    def test_add_on_vertices(self):
        self.skin.transferWeights([(self.joints[0], self.joints[1])], vertices=[0, 1], add=True)
        self.assertRowsAlmostEqual(self.rows([0, 1]), [[0.0, 0.8, 0.2], [0.0, 0.777777, 0.222223]])
        self.assertRowsAlmostEqual(self.rows([3]), [ROWS[3]])

    def test_replace_on_vertices(self):
        self.skin.transferWeights([(self.joints[0], self.joints[1])], vertices=[0])
        self.assertRowsAlmostEqual(self.rows([0]), [[0.0, 0.5, 0.2]])
        self.assertRowsAlmostEqual(self.rows([1]), [ROWS[1]])

    def test_add_on_all_vertices_keeps_sum(self):
        self.skin.transferWeights([(self.joints[2], self.joints[0])], add=True)
        self.assertNormalized([0, 1, 2, 3, 4, 5, 6, 7])
        for row in self.rows([0, 1, 2, 3]):
            self.assertAlmostEqual(row[2], 0.0)

    def test_one_undo_and_fast(self):
        self.skin.transferWeights([(self.joints[0], self.joints[1])], vertices=[0, 1], add=True)
        expected = self.rows([0, 1, 2, 3])
        cmds.undo()
        self.assertRowsAlmostEqual(self.rows([0, 1, 2, 3]), ROWS)
        cmds.flushUndo()
        self.skin.transferWeights([(self.joints[0], self.joints[1])], vertices=[0, 1], add=True, fast=True)
        self.assertRowsAlmostEqual(self.rows([0, 1, 2, 3]), expected)
        self.assertFalse(cmds.undoInfo(query=True, undoName=True))

    def test_locked_influence_raises(self):
        self.skin.setInfluencesLocked([self.joints[1]], True)
        with self.assertRaises(RuntimeError):
            self.skin.transferWeights([(self.joints[0], self.joints[1])], vertices=[0], add=True)
        self.assertRowsAlmostEqual(self.rows([0]), [ROWS[0]])

    def test_invalid_arguments(self):
        with self.assertRaises(TypeError):
            self.skin.transferWeights([(self.joints[0], self.joints[1])], add=1)
        with self.assertRaises(IndexError):
            self.skin.transferWeights([(self.joints[0], self.joints[1])], vertices=[100])
        self.assertRowsAlmostEqual(self.rows([0, 1, 2, 3]), ROWS)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
