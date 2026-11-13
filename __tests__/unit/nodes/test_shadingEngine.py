"""``mlib.nodes.shadingEngine`` のテスト。

- セット・表示レイヤー・シェーディング所属のAPI経路を検証する。
"""

from unittest import mock
import unittest

from maya import cmds
import maya.api.OpenMaya as om2

import mlib


class ConsolidatedSetsLayersTests(unittest.TestCase):
    """Maya標準の所属表現と通常Undoを確認する。"""

    def setUp(self):
        """隔離した新規シーンを用意する。"""
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)

    def tearDown(self):
        """既定レイヤーへ戻して検証シーンを破棄する。"""
        cmds.editDisplayLayerGlobals(currentDisplayLayer="defaultLayer")
        cmds.file(new=True, force=True)

    def test_shading_members_and_whole_mesh_assignment(self):
        """既存のフェース別割り当てを全体へ置換し、他のメッシュは保持する。"""
        cube = mlib.getNode(cmds.polyCube(name="shadeCube")[0])
        other = mlib.getNode(cmds.polyCube(name="shadeOther")[0])
        first = mlib.ShadingEngine(cmds.sets(renderable=True, noSurfaceShader=True, empty=True))
        second = mlib.ShadingEngine(cmds.sets(renderable=True, noSurfaceShader=True, empty=True))
        first.assign([cube.getName() + ".f[0:2]", other.getName()])
        expected = cmds.ls(cmds.sets(first.getName(), query=True), long=True, flatten=True)
        expected = [name.replace(cube.getFullName() + ".f[", cube.getShape().getFullName() + ".f[")
                    for name in expected]
        self.assertEqual([item.getFullName() for item in first.getMembers()], expected)
        cmds.flushUndo()
        second.assign(cube)
        mesh = cube.getShape()
        shaders, indices = om2.MFnMesh(mesh.mpath()).getConnectedShaders(mesh.mpath().instanceNumber())
        self.assertTrue(all(shaders[index] == second.mnode() for index in indices))
        self.assertEqual([item.getFullName() for item in first.getMembers()], [other.getShape().getFullName()])
        with mock.patch.object(cmds, "sets", side_effect=AssertionError("cmds set read used")):
            second.getMembers()

    def test_shading_fast_shader_connection(self):
        """シェーダー接続はfastでUndoに記録しない。assignはfastを持たない。"""
        cube = cmds.polyCube()[0]
        shading = mlib.ShadingEngine(cmds.sets(renderable=True, noSurfaceShader=True, empty=True))
        with self.assertRaises(TypeError):
            shading.assign(cube + ".f[0]", fast=True)
        material = mlib.createNode("lambert")
        cmds.flushUndo()
        shading.setShader(material, fast=True)
        self.assertEqual(shading.getShader(), material)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))


if __name__ == "__main__":
    unittest.main()
