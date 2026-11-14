"""Mayaの継承・シェーダー接続・面割り当てを検証する。

あわせて次も確かめる。

- Reference・Container・DagPose・マテリアル系・Constraint・AnimCurve の参照の少ないAPIの約束を固定する(担当C)。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import Face
from mlib.nodes import Blinn, File, Lambert, Node, Reflect, ShadingEngine, StandardSurface


class MaterialNodesTest(unittest.TestCase):
    """専用namespace内で割り当てを検証する。"""

    def setUp(self):
        self.old = cmds.namespaceInfo(currentNamespace=True)
        self.ns = cmds.namespace(add="mlibMaterialTest")
        cmds.namespace(set=self.ns)

    def tearDown(self):
        cmds.namespace(set=self.old)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_maya_inheritance(self):
        for kind in ("lambert", "blinn", "phong", "phongE", "standardSurface", "surfaceShader", "file", "place2dTexture", "place3dTexture"):
            node = mlib.createNode(kind)
            native = cmds.nodeType(kind, isTypeName=True, inherited=True)
            declared = {cls: name for name, cls in mlib.nodes._WRAPPER_CLASSES.items()}
            for cls in type(node).__mro__:
                key = declared.get(cls)
                if key and key != "dependNode":
                    self.assertIn(key, native)
        self.assertTrue(issubclass(Blinn, Reflect))
        self.assertTrue(issubclass(Reflect, Lambert))
        self.assertFalse(issubclass(StandardSurface, Lambert))

    def test_assignment_faces_and_undo(self):
        mesh = Node(cmds.polyCube()[0]).getShape()
        material = mlib.getNode(cmds.shadingNode("lambert", asShader=True))
        second = mlib.getNode(cmds.shadingNode("standardSurface", asShader=True))
        group = mlib.getNode(cmds.sets(renderable=True, noSurfaceShader=True, empty=True))
        group.setShader(material)
        other = mlib.getNode(cmds.sets(renderable=True, noSurfaceShader=True, empty=True))
        other.setShader(second)
        self.assertIsInstance(group, ShadingEngine)
        group.assign(mesh)
        self.assertEqual([engine.getShader() for engine in mesh.getShadingEngines()], [material])
        other.assign(mesh.getFaces([0, 1]))
        self.assertEqual(mesh.getFace(0).getMaterial(), second)
        self.assertEqual(mesh.getFace(2).getMaterial(), material)
        self.assertEqual(mesh.getFaces([0, 1]).getMaterials(), [second])
        self.assertTrue(all(member.shape == mesh for member in other.getMembers()))
        self.assertEqual(material.getShadingEngines(), [group])
        self.assertTrue(any(engine.getMembers() for engine in material.getShadingEngines()))
        cmds.undo()
        self.assertEqual(mesh.getFace(0).getMaterial(), material)

    def test_instance_assignments(self):
        transform = Node(cmds.polyCube()[0])
        instance = Node(cmds.instance(transform.getFullName())[0])
        a = mlib.getNode(cmds.sets(renderable=True, noSurfaceShader=True, empty=True))
        a.setShader(mlib.getNode(cmds.shadingNode("lambert", asShader=True)))
        b = mlib.getNode(cmds.sets(renderable=True, noSurfaceShader=True, empty=True))
        b.setShader(mlib.getNode(cmds.shadingNode("blinn", asShader=True)))
        a.assign(transform)
        b.assign(instance)
        self.assertEqual(transform.getShape().getShadingEngines(), [a])
        self.assertEqual(instance.getShape().getShadingEngines(), [b])

    def test_texture_connections(self):
        texture = mlib.createNode("file")
        place = mlib.createNode("place2dTexture")
        self.assertIsInstance(texture, File)
        texture.setFilePath("test.<UDIM>.exr")
        self.assertEqual(texture.getFilePath(), "test.<UDIM>.exr")
        place.connectTexture(texture)
        self.assertEqual(texture.getPlacement(), place)
        place.connectTexture(texture)

    def test_shader_ports_and_aliases(self):
        material = mlib.getNode(cmds.shadingNode("surfaceShader", n="surface", asShader=True))
        group = mlib.getNode(cmds.sets(renderable=True, noSurfaceShader=True, empty=True, n="surfaceSG"))
        self.assertIsNone(group.getShader())
        group.setShader(material.getPlug("outColor"))
        self.assertEqual(group.getShaderPlug(), material.getPlug("outColor"))
        replacement = mlib.getNode(cmds.shadingNode("lambert", asShader=True))
        group.setShader(replacement)
        self.assertEqual(group.getShader(), replacement)
        cmds.undo()
        self.assertEqual(group.getShader(), material)
        group.setShader(material, kind="volume")
        self.assertEqual(group.getShader("volume"), material)
        with self.assertRaises(ValueError):
            group.getShader("invalid")


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeMisc_"
    CLEAR_SELECTION = True


class MaterialTest(_SpecCase):
    """ShadingEngine.getShaderPlug と、マテリアル・割り当ての照会。"""

    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=self.name("cube"))[0]
        self.material = cmds.shadingNode("lambert", asShader=True, name=self.name("mat"))
        self.group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=self.name("matSG"))
        cmds.connectAttr(self.material + ".outColor", self.group + ".surfaceShader")
        cmds.sets(self.cube, edit=True, forceElement=self.group)

    def test_shader_plug(self):
        """接続元の出力 Plug、未接続は None、不正な種類は ValueError。"""
        group = Node(self.group)
        self.assertEqual(group.getShaderPlug().getFullName(), self.material + ".outColor")
        self.assertIsNone(group.getShaderPlug("volume"))
        self.assertIsNone(group.getShaderPlug("displacement"))
        with self.assertRaisesRegex(ValueError, "kindは"):
            group.getShaderPlug("light")
        empty = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=self.name("emptySG"))
        self.assertIsNone(Node(empty).getShaderPlug())

    @staticmethod
    def assigned(node):
        """node に繋がる ShadingEngine の割り当て先を保持順に集める。"""
        return [member for engine in node.getShadingEngines() for member in engine.getMembers()]

    @staticmethod
    def materials(node):
        """node に繋がる ShadingEngine のサーフェスシェーダーを重複なしで集める。"""
        result = []
        for engine in node.getShadingEngines():
            shader = engine.getShader()
            if shader is not None and shader not in result:
                result.append(shader)
        return result

    def test_assigned_objects_and_materials(self):
        """割り当て先は ShadingEngine.getMembers()、マテリアルは getShader() を getShadingEngines() ごとに集める。"""
        shape = Node(self.cube).getShape()
        self.assertEqual(self.assigned(Node(self.material)), [shape])
        self.assertEqual(self.materials(shape), [Node(self.material)])

    def test_face_assignment(self):
        """フェース単位の割り当てでは Face を返し、Shape のマテリアルは重複なしで両方。"""
        cmds.sets(self.cube + ".f[0]", edit=True, forceElement="initialShadingGroup")
        assigned = self.assigned(Node(self.material))
        self.assertTrue(assigned)
        self.assertTrue(all(isinstance(item, Face) for item in assigned))
        materials = self.materials(Node(self.cube).getShape())
        self.assertIn(Node(self.material), materials)
        self.assertEqual(len(materials), 2)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
