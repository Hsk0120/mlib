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

    def test_file_path(self):
        """トークンを展開せずに保持し、文字列以外は TypeError。1回の Undo で戻る。"""
        self.assertIsInstance(self.file, File)
        self.assertEqual(self.file.getFilePath(), "")
        cmds.flushUndo()
        self.assertIs(self.file.setFilePath("C:/textures/a.<UDIM>.png"), self.file)
        self.assertEqual(self.file.getFilePath(), "C:/textures/a.<UDIM>.png")
        cmds.undo()
        self.assertEqual(self.file.getFilePath(), "")
        with self.assertRaisesRegex(TypeError, "pathは文字列で指定してください"):
            self.file.setFilePath(5)

    def test_color_space(self):
        """色空間名を設定・取得する。名前は検証せずに保存し、str 以外は何も変えず TypeError。"""
        self.assertEqual(self.file.getColorSpace(), cmds.getAttr(self.file.getName() + ".colorSpace"))
        self.assertIs(self.file.setColorSpace("Raw"), self.file)
        self.assertEqual(self.file.getColorSpace(), "Raw")
        self.file.setColorSpace("mlibNoSuchColorSpace")
        self.assertEqual(self.file.getColorSpace(), "mlibNoSuchColorSpace")
        for value in (5, None, b"Raw", ["Raw"]):
            with self.assertRaises(TypeError):
                self.file.setColorSpace(value)
            self.assertEqual(self.file.getColorSpace(), "mlibNoSuchColorSpace")

    def test_connect_texture_and_placement(self):
        """標準の配置アトリビュートをつなぎ、getPlacement はその配置ノード。同じ接続の繰り返しは何もしない。"""
        self.assertIsNone(self.file.getPlacement())
        self.assertIsInstance(self.place, Place2dTexture)
        self.assertIs(self.place.connectTexture(self.file), self.place)
        self.assertEqual(self.file.getPlacement(), self.place)
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
        self.assertIs(other.connectTexture(self.file, force=True), other)
        self.assertEqual(self.file.getPlacement(), other)
        material = cmds.shadingNode("lambert", asShader=True, name=self.name("notTexture"))
        with self.assertRaisesRegex(TypeError, "textureはTexture2dで指定してください"):
            other.connectTexture(material)


if __name__ == "__main__":
    unittest.main()
