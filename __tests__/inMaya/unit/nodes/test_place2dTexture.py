"""テクスチャ配置のユーティリティノードの仕様を固定する。

担当A。texture2d・place2dTexture の接続の約束を確かめる。
"""

import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib


def _uv_source(texture):
    """テクスチャの uvCoord の入力元ノードの名前を返す。入力が無ければ None。"""
    return cmds.listConnections(texture.getName(full=True) + ".uvCoord", source=True, destination=False)


def _dag(name):
    """名前からMDagPathを返す。"""
    selection = om2.MSelectionList()
    selection.add(name)
    return selection.getDagPath(0)


class _GeometryCase(unittest.TestCase):
    """専用名前空間・cm/rad・Undo有効で実行し、終了時に戻す。"""

    def setUp(self):
        self.units = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True))
        self.undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(state=True)
        cmds.currentUnit(linear="cm", angle="rad")
        self.old_namespace = cmds.namespaceInfo(currentNamespace=True)
        self.namespace = cmds.namespace(add="mlibSpecAGeometry")
        cmds.namespace(set=self.namespace)

    def tearDown(self):
        cmds.namespace(set=self.old_namespace)
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.currentUnit(linear=self.units[0], angle=self.units[1])
        cmds.undoInfo(state=self.undo_state)


class TextureNodesTest(_GeometryCase):
    """file・texture2d・place2dTexture。"""

    def test_place2d_connect_texture(self):
        """標準の配置アトリビュートをすべて接続する。再実行は何もしない。"""
        texture = mlib.createNode("file")
        self.assertIsNone(_uv_source(texture))
        place = mlib.createNode("place2dTexture")
        self.assertIsNone(place.connectTexture(texture))
        names = (
            "coverage",
            "translateFrame",
            "rotateFrame",
            "mirrorU",
            "mirrorV",
            "stagger",
            "wrapU",
            "wrapV",
            "repeatUV",
            "offset",
            "rotateUV",
            "noiseUV",
            "vertexUvOne",
            "vertexUvTwo",
            "vertexUvThree",
            "vertexCameraOne",
        )
        pairs = [(n, n) for n in names] + [("outUV", "uvCoord"), ("outUvFilterSize", "uvFilterSize")]
        expected = [(o, d) for o, d in pairs if cmds.attributeQuery(d, node=texture.getName(full=True), exists=True)]
        for _origin, destination in expected:
            with self.subTest(attr=destination):
                source = cmds.listConnections(f"{texture.getName(full=True)}.{destination}", source=True, destination=False)
                self.assertEqual(source, [place.getName()])
        connections = cmds.listConnections(place.getName(full=True), source=False, destination=True, connections=True)
        self.assertEqual(len(connections) // 2, len(expected))
        # 接続済みの再実行は何も変えず、Undoの記録も残さない。
        undo_name = cmds.undoInfo(query=True, undoName=True)
        place.connectTexture(texture)
        self.assertEqual(len(cmds.listConnections(place.getName(full=True), source=False, destination=True, connections=True)) // 2, len(expected))
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
        cmds.undo()
        self.assertIsNone(_uv_source(texture))
        self.assertIsNone(cmds.listConnections(place.getName(full=True), source=False, destination=True))

    def test_place2d_force_and_errors(self):
        """別の配置ノードの接続はforce/fでだけ置き換える。Texture2d以外はTypeError。"""
        texture = mlib.createNode("checker")
        self.assertIsInstance(texture, mlib.Texture2d)
        first = mlib.createNode("place2dTexture")
        first.connectTexture(texture)
        second = mlib.createNode("place2dTexture")
        with self.assertRaises(RuntimeError):
            second.connectTexture(texture)
        self.assertEqual(_uv_source(texture), [first.getName()])
        second.connectTexture(texture, force=True)
        self.assertEqual(_uv_source(texture), [second.getName()])
        self.assertIsNone(cmds.listConnections(first.getName(full=True), source=False, destination=True))
        for bad in (mlib.createNode("composeMatrix"), cmds.createNode("transform")):
            with self.assertRaisesRegex(TypeError, "textureはTexture2dで指定してください"):
                second.connectTexture(bad)


if __name__ == "__main__":
    unittest.main()
