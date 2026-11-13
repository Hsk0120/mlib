"""``mlib.cmds`` のテスト。

- デフォーマー・AnimCurve・ObjectSet のメソッドと作成関数を確かめる。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibDeformAdd_"

    def cube(self, subdivisionsY=1):
        """1辺2cm の polyCube を作り、(transform 名, shape 名) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, subdivisionsY=subdivisionsY,
                                  constructionHistory=False)[0]
        transform = cmds.ls(transform, long=True)[0]
        return transform, cmds.listRelatives(transform, shapes=True, fullPath=True)[0]

    def skinned(self):
        """2段の cube を2本の joint へバインドし、(skin, mesh 名, joints, 未登録 joint) を返す。"""
        mesh, _ = self.cube(subdivisionsY=2)
        cmds.select(clear=True)
        j0 = cmds.joint(name=self.name("j0"), position=(0, -1, 0))
        j1 = cmds.joint(name=self.name("j1"), position=(0, 1, 0))
        cmds.select(clear=True)
        stranger = cmds.joint(name=self.name("stranger"))
        cmds.select(clear=True)
        name = cmds.skinCluster(j0, j1, mesh, toSelectedBones=True, name=self.name("skin"))[0]
        cmds.select(clear=True)
        return mlib.getNode(name), mesh, (j0, j1), stranger

    def keyed(self):
        """translateX の frame 1 に 0、frame 10 に 5 のキーを打ったカーブを返す。"""
        node = self.make("transform", "keyed#")
        cmds.setKeyframe(node, attribute="translateX", time=1, value=0.0)
        cmds.setKeyframe(node, attribute="translateX", time=10, value=5.0)
        return mlib.getNode(cmds.listConnections(node + ".tx", type="animCurve")[0])


class CreateDeformerTest(_Case):
    """createCluster・createLattice・createWire。"""

    CLEAR_SELECTION = True

    def test_create_cluster(self):
        """cluster を作り、ハンドルを取れる。relative・短縮名・選択を変えないこと・Undo 1回。"""
        cube, _ = self.cube()
        cmds.select(clear=True)
        self.flushUndo()
        cluster = mlib.createCluster(cube + ".vtx[0:3]", n=self.name("made"), rel=True)
        self.assertEqual(cluster.getType(), "cluster")
        self.assertEqual(cluster.getName(), self.name("made"))
        self.assertTrue(cmds.getAttr(cluster.getFullName() + ".relative"))
        self.assertTrue(cmds.listRelatives(cluster.getWeightedNode().getFullName(), shapes=True,
                                           type="clusterHandle"))
        self.assertEqual(cmds.ls(selection=True), [])
        name = cluster.getFullName()
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)),
                                   lambda: self.assertTrue(cmds.objExists(name)))
        self.assertFalse(cmds.getAttr(mlib.createCluster(cube).getFullName() + ".relative"))

    def test_create_lattice(self):
        """ffd を作り、分割数がラティスに設定される。"""
        cube, _ = self.cube()
        cmds.select(clear=True)
        self.flushUndo()
        ffd = mlib.createLattice(cube, name=self.name("made"), dv=(3, 4, 2), ldv=(2, 3, 2))
        self.assertEqual(ffd.getType(), "ffd")
        lattice = ffd.getPlug("deformedLatticePoints").getSource().getNode().getFullName()
        self.assertEqual([cmds.getAttr(lattice + "." + axis + "Divisions") for axis in "stu"], [3, 4, 2])
        self.assertEqual([cmds.getAttr(ffd.getFullName() + ".localInfluence" + axis) for axis in "STU"],
                         [2, 3, 2])
        self.assertEqual(cmds.ls(selection=True), [])
        name = ffd.getFullName()
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)),
                                   lambda: self.assertTrue(cmds.objExists(name)))

    def test_create_wire(self):
        """wire を作り、dropoffDistance を全カーブに設定する。"""
        cube, _ = self.cube()
        curves = [cmds.curve(degree=1, point=[(-2, y, 1), (2, y, 1)], name=self.name("crv#")) for y in (0.5, -0.5)]
        cmds.select(clear=True)
        self.flushUndo()
        wire = mlib.createWire(cube, curves, name=self.name("made"), dds=2.5)
        self.assertEqual(wire.getType(), "wire")
        self.assertEqual([cmds.getAttr(f"{wire.getFullName()}.dropoffDistance[{i}]") for i in (0, 1)], [2.5, 2.5])
        self.assertEqual(cmds.ls(selection=True), [])
        name = wire.getFullName()
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)),
                                   lambda: self.assertTrue(cmds.objExists(name)))

    def test_invalid_arguments(self):
        """不正な引数はシーンを変えずに例外。"""
        cube, _ = self.cube()
        curve = cmds.curve(degree=1, point=[(-2, 0, 1), (2, 0, 1)], name=self.name("crv#"))
        before = set(cmds.ls())
        cases = (
            (mlib.createCluster, ([],), {}, ValueError),
            (mlib.createCluster, (cube,), {"name": "a", "n": "b"}, TypeError),
            (mlib.createCluster, (cube,), {"relative": "yes"}, TypeError),
            (mlib.createCluster, (cube,), {"name": ""}, ValueError),
            (mlib.createLattice, (cube,), {"divisions": (1, 2, 2)}, ValueError),
            (mlib.createLattice, (cube,), {"divisions": (2, 2)}, ValueError),
            (mlib.createLattice, (cube,), {"divisions": (2.0, 2, 2)}, TypeError),
            (mlib.createLattice, (cube,), {"divisions": (2, 2, 2), "dv": (2, 2, 2)}, TypeError),
            (mlib.createLattice, (cube,), {"objectCentered": 1}, TypeError),
            (mlib.createWire, (cube, []), {}, ValueError),
            (mlib.createWire, (cube, curve), {"dropoffDistance": 0}, ValueError),
            (mlib.createWire, (cube, curve), {"dropoffDistance": "1"}, TypeError),
            (mlib.createWire, (cube, curve), {"dropoffDistance": 1.0, "dds": 1.0}, TypeError),
        )
        for function, args, kwargs, error in cases:
            with self.subTest(function=function.__name__, kwargs=kwargs):
                with self.assertRaises(error):
                    function(*args, **kwargs)
                self.assertEqual(set(cmds.ls()), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
