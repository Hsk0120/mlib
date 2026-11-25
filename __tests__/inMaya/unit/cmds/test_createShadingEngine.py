"""``mlib.cmds.createShadingEngine`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class CreateShadingEngineTest(NamespaceCase):
    """mlib.createShadingEngine。"""

    PREFIX = "mlibShadingEngine_"

    def test_matches_sets_command(self):
        """cmds.sets(renderable=True, noSurfaceShader=True, empty=True) と同じつながりになる。"""
        engine = mlib.createShadingEngine(name=self.name("madeSG"))
        expected = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=self.name("refSG"))
        self.assertIsInstance(engine, mlib.ShadingEngine)
        for name in (engine.getName(full=True), expected):
            with self.subTest(name=name):
                partitions = cmds.listConnections(name + ".partition", source=False, destination=True) or []
                self.assertEqual(partitions, ["renderPartition"])
        self.assertIsNone(engine.getShader())

    def test_shader_and_undo(self):
        """shaderを渡すとsurfaceShaderへつなぎ、作成と接続がUndo 1回で戻る。選択は変えない。"""
        shader = mlib.createNode("lambert", name=self.name("mat"), asShader=True, skipSelect=True)
        cmds.select(clear=True)
        self.flushUndo()
        engine = mlib.createShadingEngine(shader, n=self.name("matSG"))
        name = engine.getName(full=True)
        self.assertEqual(engine.getShader(), shader)
        self.assertEqual(cmds.ls(selection=True), [])
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))

    def test_selection_is_not_added_and_no_shader_is_connected(self):
        """選択があっても空のセットとして作り(empty)、surfaceShaderを自動でつながない(noSurfaceShader)。shaderの有無で同じ。"""
        cube = cmds.polyCube(name=self.name("selectedCube"), constructionHistory=False)[0]
        shader = mlib.createNode("lambert", name=self.name("selMat"), asShader=True, skipSelect=True)
        for kwargs in ({"name": self.name("plainSG")}, {"shader": shader, "name": self.name("shadedSG")}):
            with self.subTest(kwargs=sorted(kwargs)):
                cmds.select(cube, replace=True)
                engine = mlib.createShadingEngine(**kwargs)
                name = engine.getName(full=True)
                self.assertEqual(cmds.nodeType(name), "shadingEngine")
                self.assertEqual(cmds.sets(name, query=True) or [], [])
                expected = [shader.getName()] if "shader" in kwargs else []
                self.assertEqual(cmds.listConnections(name + ".surfaceShader", source=True, destination=False) or [], expected)
                self.assertEqual(cmds.ls(selection=True), [cube])

    def test_errors(self):
        """名前の指定と見つからないshaderを、作る前に拒否する。"""
        before = set(cmds.ls(type="shadingEngine"))
        cases = [
            ({"name": "a", "n": "b"}, TypeError),
            ({"name": 1}, TypeError),
            ({"name": ""}, ValueError),
            ({"name": "a|b"}, ValueError),
            ({"shader": self.name("missing")}, RuntimeError),
        ]
        for kwargs, error in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                mlib.createShadingEngine(**kwargs)
        self.assertEqual(set(cmds.ls(type="shadingEngine")), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
