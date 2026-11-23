"""``SkinCluster`` のウェイトの読み書きの ``geometryIndex``(1つのskinClusterが変形する2つ目以降の形状)を確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """立方体(8頂点)と平面(4頂点)を1つのskinClusterで変形する。平面は geometryIndex=1。"""

    PREFIX = "mlibSkinGeo_"

    def setUp(self):
        super().setUp()
        joints = []
        for index in range(2):
            cmds.select(clear=True)
            joints.append(cmds.joint(name=f"{self.ns}:j{index}", position=(index, 0, 0)))
        self.joints = [mlib.getNode(name) for name in joints]
        self.cube = cmds.polyCube(name=f"{self.ns}:cube", constructionHistory=False)[0]
        self.plane = cmds.polyPlane(name=f"{self.ns}:plane", subdivisionsX=1, subdivisionsY=1, constructionHistory=False)[0]
        self.skinName = cmds.skinCluster(joints, self.cube, toSelectedBones=True, name=f"{self.ns}:skin")[0]
        cmds.skinCluster(self.skinName, edit=True, geometry=self.plane)
        self.skin = mlib.getNode(self.skinName)
        self.index = self.skin.getGeometryIndex(self.plane)
        cmds.select(clear=True)
        cmds.flushUndo()

    def percent(self, shape, vertex):
        """skinPercentで頂点のウェイトを読む(インフルエンスの順)。"""
        return cmds.skinPercent(self.skinName, f"{shape}.vtx[{vertex}]", query=True, value=True)

    def assertListAlmostEqual(self, actual, expected, places=6):
        self.assertEqual(len(actual), len(expected))
        for value, wanted in zip(actual, expected):
            self.assertAlmostEqual(value, wanted, places=places)


class GeometryIndexTest(_Case):
    """2つ目の形状の頂点を、geometryIndexで読み書きできる。"""

    def test_index_of_second_shape(self):
        self.assertEqual(self.index, 1)

    def test_get_weights_matches_skin_percent(self):
        rows = self.skin.getWeights(self.joints, rows=True, geometryIndex=self.index)
        self.assertEqual(len(rows), 4)
        for vertex, row in enumerate(rows):
            self.assertListAlmostEqual(row, self.percent(self.plane, vertex))
        values = self.skin.getVertexWeights(f"{self.plane}.vtx[2]", geometryIndex=self.index)
        self.assertListAlmostEqual(list(values.values()), self.percent(self.plane, 2))

    def test_set_weights_on_second_shape(self):
        vertices = mlib.ls(f"{self.plane}.vtx[1:2]")
        self.skin.setWeights(self.joints, [0.25, 0.75], vertices=vertices, broadcast=True, geometryIndex=self.index)
        for vertex in (1, 2):
            self.assertListAlmostEqual(self.percent(self.plane, vertex), [0.25, 0.75])
        self.skin.setVertexWeights(f"{self.plane}.vtx[3]", {self.joints[0]: 0.4}, geometryIndex=self.index)
        self.assertListAlmostEqual(self.percent(self.plane, 3), [0.4, 0.6])

    def test_weight_list_is_shared(self):
        # Mayaのskinクラスタは形状どうしでweightListを共有するため、同じ番号の頂点は同じウェイトになる。
        self.skin.setVertexWeights(1, {self.joints[0]: 0.1, self.joints[1]: 0.9}, geometryIndex=self.index)
        self.assertListAlmostEqual(self.percent(self.cube, 1), [0.1, 0.9])

    def test_vertices_of_other_shape_are_rejected(self):
        with self.assertRaises(ValueError):
            self.skin.getWeights(self.joints, vertices=mlib.ls(f"{self.cube}.vtx[0]"), geometryIndex=self.index)
        with self.assertRaises(ValueError):
            self.skin.getWeights(self.joints, vertices=mlib.ls(f"{self.plane}.vtx[0]"))
        with self.assertRaises(IndexError):
            self.skin.getWeights(self.joints, vertices=[4], geometryIndex=self.index)

    def test_first_shape_index_is_same_as_default(self):
        first = self.skin.getGeometryIndex(self.cube)
        self.assertEqual(list(self.skin.getWeights(self.joints, geometryIndex=first)), list(self.skin.getWeights(self.joints)))

    def test_invalid_index(self):
        for value, error in ((True, TypeError), (1.0, TypeError), ("1", TypeError), (5, IndexError), (-1, IndexError)):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    self.skin.getWeights(self.joints, geometryIndex=value)
                with self.assertRaises(error):
                    self.skin.setWeights(self.joints, [0.5, 0.5], vertices=[0], geometryIndex=value)
                with self.assertRaises(error):
                    self.skin.smoothWeights(vertices=[0], geometryIndex=value)

    def test_one_undo_and_fast(self):
        before = [self.percent(self.plane, vertex) for vertex in range(4)]
        self.skin.setWeights(self.joints, [0.3, 0.7], vertices=[0, 3], broadcast=True, geometryIndex=self.index)
        self.assertListAlmostEqual(self.percent(self.plane, 3), [0.3, 0.7])
        cmds.undo()
        self.assertEqual([self.percent(self.plane, vertex) for vertex in range(4)], before)
        cmds.flushUndo()
        self.skin.setWeights(self.joints, [0.3, 0.7], vertices=[0, 3], broadcast=True, fast=True, geometryIndex=self.index)
        self.assertListAlmostEqual(self.percent(self.plane, 3), [0.3, 0.7])
        self.assertFalse(cmds.undoInfo(query=True, undoName=True))

    def test_smooth_weights_on_second_shape(self):
        self.skin.setVertexWeights(0, {self.joints[0]: 1.0}, geometryIndex=self.index)
        self.skin.setVertexWeights(1, {self.joints[1]: 1.0}, geometryIndex=self.index)
        selection = cmds.ls(f"{self.cube}.vtx[5]")
        cmds.select(selection, replace=True)
        before = self.percent(self.plane, 0)
        self.skin.smoothWeights(tolerance=0.0, iterations=3, vertices=[0], geometryIndex=self.index)
        self.assertNotEqual(self.percent(self.plane, 0), before)
        self.assertAlmostEqual(sum(self.percent(self.plane, 0)), 1.0, places=5)
        # 選択は元に戻る。
        self.assertEqual(cmds.ls(selection=True), selection)
        cmds.undo()
        self.assertListAlmostEqual(self.percent(self.plane, 0), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
