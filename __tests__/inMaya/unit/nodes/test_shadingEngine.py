"""``mlib.nodes.shadingEngine`` のテスト。

- セット・表示レイヤー・シェーディング所属のAPI経路を検証する。
"""

import unittest
from unittest import mock

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

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
        expected = [name.replace(cube.getName(full=True) + ".f[", cube.getShape().getName(full=True) + ".f[") for name in expected]
        self.assertEqual([item.getName(full=True) for item in first.getMembers()], expected)
        cmds.flushUndo()
        second.assign(cube)
        mesh = cube.getShape()
        shaders, indices = om2.MFnMesh(mesh.mpath()).getConnectedShaders(mesh.mpath().instanceNumber())
        self.assertTrue(all(shaders[index] == second.mnode() for index in indices))
        self.assertEqual([item.getName(full=True) for item in first.getMembers()], [other.getShape().getName(full=True)])
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


class ShadingEngineConnectionTest(NamespaceCase):
    """シェーダーの接続・割り当てをcmdsで読み直し、Undo 1回と不正な入力の例外を確かめる。"""

    def engine(self):
        return mlib.ShadingEngine(cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=self.name("SG#")))

    def test_set_shader_kinds_output_and_undo(self):
        """setShaderは種類ごとの接続先へつなぎ(cmds.listConnectionsと一致)、通常はUndo 1回で戻る。outputとPlugの指定も受ける。"""
        engine = self.engine()
        name = engine.getName(full=True)
        material = mlib.createNode("lambert", name=self.name("material#"))
        displacement = mlib.createNode("displacementShader", name=self.name("displacement#"))
        self.flushUndo()
        self.assertIsNone(engine.setShader(material))
        self.assertUndoesInOneStep(
            lambda: self.assertIsNone(engine.getShader()),
            lambda: self.assertEqual(
                cmds.listConnections(name + ".surfaceShader", source=True, destination=False, plugs=True), [material.getName() + ".outColor"]
            ),
        )
        engine.setShader(material, "volume", output="outTransparency")
        self.assertEqual(engine.getShader("volume", plug=True), material.getPlug("outTransparency"))
        self.assertEqual(engine.getShader("volume"), material)
        engine.setShader(displacement, "displacement")
        self.assertEqual(
            cmds.listConnections(name + ".displacementShader", source=True, destination=False, plugs=True), [displacement.getName() + ".displacement"]
        )
        engine.setShader(material.getPlug("outColor"))
        self.assertEqual(engine.getShader(plug=True), material.getPlug("outColor"))
        self.assertEqual(engine.getShader("displacement"), displacement)

    def test_shader_inputs_rejected(self):
        """kindの名前違いはValueError、plugがbool以外はTypeError、自分自身への接続はRuntimeErrorで、接続は変わらない。"""
        engine = self.engine()
        material = mlib.createNode("lambert", name=self.name("material#"))
        engine.setShader(material)
        for label, operation, error in (
            ("get kind", lambda: engine.getShader("color"), ValueError),
            ("get plug type", lambda: engine.getShader(plug=1), TypeError),
            ("set kind", lambda: engine.setShader(material, "color"), ValueError),
            ("self", lambda: engine.setShader(engine.getPlug("surfaceShader")), RuntimeError),
            ("self fast", lambda: engine.setShader(engine.getPlug("surfaceShader"), fast=True), RuntimeError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    operation()
                self.assertEqual(engine.getShader(), material)

    def test_assign_undo_and_empty_targets(self):
        """assignはcmds.setsで読み直した所属と一致し、Undo 1回で戻る。空の対象は何も変えない。"""
        engine = self.engine()
        name = engine.getName(full=True)
        cube = mlib.getNode(cmds.polyCube(name=self.name("cube#"), constructionHistory=False)[0])
        self.flushUndo()
        self.assertIsNone(engine.assign([]))
        self.assertEqual(cmds.sets(name, query=True), None)
        engine.assign(cube.getShape().getFaces([0, 1]))
        self.assertUndoesInOneStep(
            lambda: self.assertIsNone(cmds.sets(name, query=True)), lambda: self.assertEqual(len(cmds.ls(cmds.sets(name, query=True), flatten=True)), 2)
        )
        engine.assign(cube)
        members = engine.getMembers()
        self.assertEqual(members, [cube.getShape()])
        with self.assertRaises(TypeError):
            engine.getMembers(flatten=True)
        if not hasattr(om2.MFnSet, "getMemberPaths"):
            # Maya 2022/2023のAPI2はセットのDAGパス照会を持たない。
            with self.assertRaises(NotImplementedError):
                engine.getMembers(dagOnly=True)
            return
        self.assertEqual([node.getName(full=True) for node in engine.getMembers(dagOnly=True)], cmds.ls(cmds.sets(name, query=True), long=True))
        self.assertEqual(list(engine.getMembers(dagOnly=True, shadingOnly=True)), list(engine.getMembers(dagOnly=True)))


if __name__ == "__main__":
    unittest.main()
