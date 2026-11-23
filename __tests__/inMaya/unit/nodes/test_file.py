"""``mlib.nodes.file`` のテスト。

- Reference・Container・DagPose・マテリアル系・Constraint・AnimCurve の参照の少ないAPIの約束を固定する(担当C)。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import File, Node, Place2dTexture


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeMisc_"
    CLEAR_SELECTION = True


class TextureTest(_SpecCase):
    """File・Texture2d・Place2dTexture。"""

    def setUp(self):
        super().setUp()
        self.file = Node(cmds.shadingNode("file", asTexture=True, name=self.name("tex")))
        self.place = Node(cmds.shadingNode("place2dTexture", asUtility=True, name=self.name("place")))

    def test_connect_texture_and_placement(self):
        """標準の配置アトリビュートをつなぐ。同じ接続の繰り返しは何もしない。"""
        self.assertIsInstance(self.file, File)
        self.assertIsNone(cmds.listConnections(self.file.getName() + ".uvCoord", source=True, destination=False))
        self.assertIsInstance(self.place, Place2dTexture)
        self.assertIsNone(self.place.connectTexture(self.file))
        self.assertEqual(cmds.listConnections(self.file.getName() + ".uvCoord", source=True, plugs=True), [self.place.getName() + ".outUV"])
        count = len(cmds.listConnections(self.place.getName(), source=False, destination=True) or [])
        self.place.connectTexture(self.file)
        self.assertEqual(len(cmds.listConnections(self.place.getName(), source=False, destination=True) or []), count)

    def test_connect_texture_force_and_errors(self):
        """別の配置ノードからは force=True で置き換え、既定は RuntimeError。Texture2d 以外は TypeError。"""
        self.place.connectTexture(self.file)
        other = Node(cmds.shadingNode("place2dTexture", asUtility=True, name=self.name("other")))
        with self.assertRaises(RuntimeError):
            other.connectTexture(self.file)
        self.assertIsNone(other.connectTexture(self.file, force=True))
        self.assertEqual(cmds.listConnections(self.file.getName() + ".uvCoord", source=True, plugs=True), [other.getName() + ".outUV"])
        material = cmds.shadingNode("lambert", asShader=True, name=self.name("notTexture"))
        with self.assertRaisesRegex(TypeError, "textureはTexture2dで指定してください"):
            other.connectTexture(material)


if __name__ == "__main__":
    unittest.main()
