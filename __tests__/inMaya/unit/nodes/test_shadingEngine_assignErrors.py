"""``mlib.nodes.shadingEngine`` の ShadingEngine.assign が割り当てられない対象を受けたときの動きを確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class ShadingEngineAssignErrorTest(NamespaceCase):
    """割り当てできない対象への assign。"""

    PREFIX = "mlibSpecShadingAssign_"

    def setUp(self):
        super().setUp()
        self.engine = mlib.getNode(cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=self.name("engine")))
        self.cube = cmds.polyCube(constructionHistory=False, name=self.name("cube"))[0]

    def test_vertex_assignment_is_rejected(self):
        """頂点は割り当てられないので RuntimeError(Mayaは警告だけで飛ばす)。"""
        with self.assertRaises(RuntimeError):
            self.engine.assign(self.cube + ".vtx[0]")
        self.assertFalse(cmds.sets(self.engine.getName(full=True), query=True))

    def test_rejected_target_rolls_back_the_others(self):
        """割り当てられない対象が混ざると、割り当てた分も戻して RuntimeError。"""
        shape = cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0]
        before = cmds.listConnections(shape + ".instObjGroups[0]", source=False, destination=True) or []
        empty = cmds.group(empty=True, name=self.name("empty"))
        with self.assertRaises(RuntimeError):
            self.engine.assign([self.cube, empty])
        self.assertFalse(cmds.sets(self.engine.getName(full=True), query=True))
        self.assertEqual(cmds.listConnections(shape + ".instObjGroups[0]", source=False, destination=True) or [], before)

    def test_dg_node_and_set_are_type_errors(self):
        """DGノードやシェーディングエンジン自身は、割り当てる前に TypeError で何も変えない。"""
        calc = cmds.createNode("multiplyDivide", name=self.name("calc"))
        for target in (calc, self.engine, [self.cube, calc]):
            with self.subTest(target=target), self.assertRaises(TypeError):
                self.engine.assign(target)
            self.assertFalse(cmds.sets(self.engine.getName(full=True), query=True))

    def test_transform_and_faces_are_assigned_in_one_undo(self):
        """Transform(形状へ割り当てる)とフェースは成功し、1回の Undo で戻る。"""
        other = cmds.polyCube(constructionHistory=False, name=self.name("other"))[0]
        self.engine.assign([self.cube, other + ".f[0:1]"])
        engine = self.engine.getName(full=True)
        shape = cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0]
        self.assertTrue(cmds.sets(shape, isMember=engine))
        self.assertTrue(cmds.sets(other + ".f[0:1]", isMember=engine))
        cmds.undo()
        self.assertFalse(cmds.sets(engine, query=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
