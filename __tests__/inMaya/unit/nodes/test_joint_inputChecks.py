"""``mlib.nodes.joint`` の入力の検査と、EulerRotateでの優先角度の設定のテスト。"""

import math
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate
from mlib.nodes import Joint, Joints, SkinClusters


class _Case(NamespaceCase):
    """このテストファイルの名前空間の先頭と、ジョイントの作成。"""

    PREFIX = "mlibSpecJointInput_"

    def joint(self, text, position, parent=None):
        """選択を使わずにjointを作ってJointを返す。"""
        cmds.select(clear=True)
        if parent is not None:
            cmds.select(str(parent), replace=True)
        name = cmds.joint(name=self.name(text), position=position)
        cmds.select(clear=True)
        return Joint(name)


class JointInputTest(_Case):
    """Jointの公開メソッドの不正な入力と、境界の結果。"""

    def setUp(self):
        super().setUp()
        self.root = self.joint("root", (0, 0, 0))
        self.middle = self.joint("middle", (1, 0, 0), self.root)
        self.end = self.joint("end", (2, 0, 0), self.middle)
        self.other = self.joint("other", (0, 5, 0))

    def test_set_radius_type(self):
        """数値でないradius(文字列・bool)はTypeErrorで、値は変わらない。"""
        before = cmds.getAttr(str(self.root) + ".radius")
        for value in ("1", True, None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.root.setRadius(value)
        self.assertEqual(cmds.getAttr(str(self.root) + ".radius"), before)

    def test_set_preferred_angle_invalid(self):
        """数値の並びでもEulerRotateでもない値はTypeError、成分の数が違えばValueError。"""
        with self.assertRaises(TypeError):
            self.root.setPreferredAngle(5)
        with self.assertRaises(ValueError):
            self.root.setPreferredAngle((1, 2))
        self.assertEqual(cmds.getAttr(str(self.root) + ".preferredAngle")[0], (0.0, 0.0, 0.0))

    def test_set_preferred_angle_euler(self):
        """EulerRotateはrotateOrderの順に並べ直して書く。通常はUndo1回、fastはUndoなし。"""
        cmds.setAttr(str(self.root) + ".rotateOrder", 3)
        value = EulerRotate(0.1, 0.2, 0.3)
        reordered = value.reorder(3)
        expected = [math.degrees(item) for item in (reordered.x, reordered.y, reordered.z)]
        for fast in (False, True):
            with self.subTest(fast=fast):
                cmds.setAttr(str(self.root) + ".preferredAngle", 0, 0, 0)
                self.flushUndo()
                self.assertIsNone(self.root.setPreferredAngle(value, fast=fast))
                self.assertSequenceAlmostEqual(cmds.getAttr(str(self.root) + ".preferredAngle")[0], expected)
                if fast:
                    self.assertUndoEmpty()
                else:
                    self.assertUndoesInOneStep(lambda: self.assertEqual(cmds.getAttr(str(self.root) + ".preferredAngle")[0], (0.0, 0.0, 0.0)), lambda: None)

    def test_connect_inverse_scale_non_transform(self):
        """sourceがTransformでない(multiplyDivide)ならTypeErrorで、接続しない。"""
        dg = self.make("multiplyDivide", "dg")
        with self.assertRaises(TypeError):
            self.other.connectInverseScale(dg)
        self.assertIsNone(cmds.listConnections(str(self.other) + ".inverseScale", source=True))

    def test_chain_to_non_descendant(self):
        """getChainFromHere(to=)に子孫でないジョイントを渡すとValueError。"""
        self.assertEqual(self.root.getChainFromHere(to=self.end), Joints([self.root, self.middle, self.end]))
        with self.assertRaises(ValueError):
            self.root.getChainFromHere(to=self.other)

    def test_pole_position_collinear(self):
        """3つのジョイントが一直線上か、孫が自身と同じ位置へ折り返しているならValueError。"""
        with self.assertRaises(ValueError):
            self.root.getPolePosition()
        start = self.joint("foldStart", (0, 0, 5))
        middle = self.joint("foldMiddle", (1, 0, 5), start)
        self.joint("foldEnd", (0, 0, 5), middle)
        with self.assertRaises(ValueError):
            start.getPolePosition()

    def test_skin_clusters_of_deleted_joint(self):
        """削除したジョイントのgetSkinClustersは空のSkinClusters。"""
        cmds.delete(str(self.other))
        result = self.other.getSkinClusters()
        self.assertIs(type(result), SkinClusters)
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
