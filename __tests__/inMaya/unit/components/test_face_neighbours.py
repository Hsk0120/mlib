"""Maya標準の照会と、既存の取得対象との違いを検証する。

- ``Face.getConnected`` の3種類(``type``)と、自身のエッジ・頂点を含めないこと。
- ``Face.isKind`` の9種類を ``om2.MItMeshPolygon`` と突き合わせる。
- ``Face.getArea`` の ``uv=True`` と、同時に指定できない引数。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class FaceNeighboursTest(NamespaceCase):
    def test_cube_neighbours_exclude_face_members(self):
        node = cmds.polyCube(name=self.ns + ":cube")[0]
        shape = mlib.getNode(node).getShape()
        face = shape.getFaces(0)
        iterator = om2.MItMeshPolygon(shape.mpath())
        iterator.setIndex(0)
        edges = [x.index for x in face.getConnected(type="edge")]
        vertices = [x.index for x in face.getConnected(type="vertex")]
        self.assertEqual(edges, sorted(iterator.getConnectedEdges()))
        self.assertEqual(vertices, sorted(iterator.getConnectedVertices()))
        self.assertTrue(edges)
        self.assertTrue(vertices)
        self.assertFalse(set(edges) & {x.index for x in face.getEdges()})
        self.assertFalse(set(vertices) & {x.index for x in face.getVertices()})
        self.assertEqual(face.isKind("starlike"), iterator.isStarlike())

    def test_isolated_face_has_no_external_neighbours(self):
        node = cmds.polyCreateFacet(point=[(0, 0, 0), (2, 0, 0), (1, 0, 1)], name=self.ns + ":triangle")[0]
        face = mlib.getNode(node).getShape().getFaces(0)
        self.assertEqual(len(face.getConnected(type="edge")), 0)
        self.assertEqual(len(face.getConnected(type="vertex")), 0)
        self.assertEqual(len(face.getConnected()), 0)
        self.assertTrue(face.isKind("starlike"))
        cmds.delete(node)
        for kind in ("face", "edge", "vertex"):
            with self.subTest(type=kind):
                with self.assertRaises(RuntimeError):
                    face.getConnected(type=kind)

    def test_connected_types_match_openmaya(self):
        """type ごとに Faces・Edges・Vertices を返し、番号は MItMeshPolygon の結果を小さい順に並べたものと同じ。"""
        node = cmds.polyPlane(name=self.ns + ":plane", subdivisionsX=3, subdivisionsY=3, constructionHistory=False)[0]
        shape = mlib.getNode(node).getShape()
        iterator = om2.MItMeshPolygon(shape.mpath())
        cases = (
            ("face", mlib.Faces, lambda: iterator.getConnectedFaces()),
            ("edge", mlib.Edges, lambda: iterator.getConnectedEdges()),
            ("vertex", mlib.Vertices, lambda: iterator.getConnectedVertices()),
        )
        for index in (0, 4, 8):
            face = shape.getFaces(index)
            iterator.setIndex(index)
            for kind, cls, native in cases:
                with self.subTest(face=index, type=kind):
                    result = face.getConnected(type=kind)
                    self.assertIs(type(result), cls)
                    self.assertEqual(list(result.indices), sorted(set(native())))
            self.assertEqual(face.getConnected().indices, face.getConnected(type="face").indices)
        # 複数形は各要素へ転送し、要素ごとの集まりの list を返す。
        many = shape.getFaces([0, 4]).getConnected(type="vertex")
        self.assertEqual([list(item.indices) for item in many], [list(shape.getFaces(i).getConnected(type="vertex").indices) for i in (0, 4)])
        # エッジ・頂点は引数なし。
        self.assertIs(type(shape.getEdges(0).getConnected()), mlib.Edges)
        self.assertIs(type(shape.getVertices(0).getConnected()), mlib.Vertices)

    def test_connected_rejects_invalid_type(self):
        """type が文字列でなければ TypeError、決まった名前でなければ ValueError。位置引数では渡せない。"""
        node = cmds.polyCube(name=self.ns + ":cube")[0]
        face = mlib.getNode(node).getShape().getFaces(0)
        for value in (None, 1, True, ["face"], b"face"):
            with self.subTest(type=value):
                with self.assertRaises(TypeError):
                    face.getConnected(type=value)
        for value in ("faces", "Face", "uv", ""):
            with self.subTest(type=value):
                with self.assertRaises(ValueError):
                    face.getConnected(type=value)
        with self.assertRaises(TypeError):
            face.getConnected("edge")

    def _kind_meshes(self):
        """種類の判定が分かれるメッシュ(立方体・凹んだ5角形・ねじれた4角形・つぶれた面・穴のある面)のシェイプを返す。"""
        cube = cmds.polyCube(name=self.ns + ":kindCube", constructionHistory=False)[0]
        concave = cmds.polyCreateFacet(point=[(0, 0, 0), (4, 0, 0), (4, 0, 4), (2, 0, 1), (0, 0, 4)], name=self.ns + ":concave", constructionHistory=False)[0]
        twisted = cmds.polyCreateFacet(point=[(0, 0, 0), (2, 0, 0), (2, 1.5, 2), (0, 0, 2)], name=self.ns + ":twisted", constructionHistory=False)[0]
        flat = cmds.polyCreateFacet(point=[(0, 0, 0), (1, 0, 0), (2, 0, 0)], name=self.ns + ":flat", constructionHistory=False)[0]
        holed = cmds.polyCreateFacet(
            point=[(0, 0, 0), (6, 0, 0), (6, 0, 6), (0, 0, 6), (), (2, 0, 2), (2, 0, 4), (4, 0, 4), (4, 0, 2)],
            name=self.ns + ":holed",
            constructionHistory=False,
        )[0]
        return [mlib.getNode(name).getShape() for name in (cube, concave, twisted, flat, holed)]

    def test_kinds_match_openmaya(self):
        """isKind の9種類は、MItMeshPolygon の同じ照会(面積は getArea・getUVArea、UVの向きは巻き方向)と一致する。"""
        natives = {
            "planar": lambda it: it.isPlanar(),
            "convex": lambda it: it.isConvex(),
            "starlike": lambda it: it.isStarlike(),
            "lamina": lambda it: it.isLamina(),
            "holed": lambda it: it.isHoled(),
            "validTriangulation": lambda it: it.hasValidTriangulation(),
            "zeroArea": lambda it: it.getArea() <= 1e-10,
            "zeroUVArea": lambda it: it.getUVArea() <= 1e-10,
        }
        seen = {kind: set() for kind in natives}
        meshes = self._kind_meshes()
        for shape in meshes:
            iterator = om2.MItMeshPolygon(shape.mpath())
            for index in range(shape.getNumPolygons()):
                iterator.setIndex(index)
                face = shape.getFaces(index)
                for kind, native in natives.items():
                    if kind == "zeroUVArea" and not iterator.hasUVs():
                        continue
                    with self.subTest(mesh=shape.getName(), face=index, kind=kind):
                        result = face.isKind(kind)
                        self.assertIsInstance(result, bool)
                        self.assertEqual(result, native(iterator))
                        seen[kind].add(result)
        # 用意したメッシュで、True と False の両方を確かめられた種類(結果が片方だけなら判定を見ていないのと同じ)。
        for kind in ("planar", "convex", "holed", "zeroArea"):
            with self.subTest(kind=kind, state="both"):
                self.assertEqual(seen[kind], {True, False})
        # 複数形は各要素の結果の list。
        self.assertEqual(meshes[0].getFaces().isKind("planar"), [True] * 6)

    def test_kind_uv_reversed_and_tolerance(self):
        """uvReversed は UV の巻き方向、zeroArea・zeroUVArea は tolerance 以下かで決まり、uvSet を選べる。"""
        node = cmds.polyPlane(name=self.ns + ":uvPlane", subdivisionsX=1, subdivisionsY=1, width=2, height=2, constructionHistory=False)[0]
        shape = mlib.getNode(node).getShape()
        face = shape.getFaces(0)
        self.assertFalse(face.isKind("uvReversed"))
        self.assertFalse(face.isKind("zeroUVArea"))
        self.assertAlmostEqual(face.getArea(uv=True), 1.0)
        self.assertTrue(face.isKind("zeroUVArea", tolerance=1.0))
        self.assertFalse(face.isKind("zeroUVArea", tolerance=0.5))
        self.assertTrue(face.isKind("zeroArea", tolerance=4.0))
        self.assertFalse(face.isKind("zeroArea", tolerance=3.9))
        # 別のUVセットを左右反転すると、そのセットだけ裏返る。
        cmds.polyUVSet(shape.getFullName(), copy=True, uvSet="map1", newUVSet="flipped")
        cmds.polyUVSet(shape.getFullName(), currentUVSet=True, uvSet="flipped")
        cmds.polyEditUV(shape.getFullName() + ".map[*]", pivotU=0.5, pivotV=0.5, scaleU=-0.5, scaleV=0.5)
        cmds.polyUVSet(shape.getFullName(), currentUVSet=True, uvSet="map1")
        self.assertTrue(face.isKind("uvReversed", uvSet="flipped"))
        self.assertFalse(face.isKind("uvReversed", uvSet="map1"))
        self.assertAlmostEqual(face.getArea(uv=True, uvSet="flipped"), 0.25)
        self.assertTrue(face.isKind("zeroUVArea", uvSet="flipped", tolerance=0.25))
        self.assertFalse(face.isKind("zeroUVArea", uvSet="map1", tolerance=0.25))
        self.assertEqual(cmds.polyUVSet(shape.getFullName(), query=True, currentUVSet=True), ["map1"])

    def test_kind_rejects_invalid_arguments(self):
        """kind が文字列でなければ TypeError、知らない名前は ValueError、その種類で使わない uvSet・tolerance は TypeError。"""
        node = cmds.polyCube(name=self.ns + ":cube")[0]
        face = mlib.getNode(node).getShape().getFaces(0)
        for value in (None, 1, True, ["planar"], b"planar"):
            with self.subTest(kind=value):
                with self.assertRaises(TypeError):
                    face.isKind(value)
        for value in ("Planar", "isPlanar", "flat", "", "onBoundary"):
            with self.subTest(kind=value):
                with self.assertRaises(ValueError):
                    face.isKind(value)
        for kind in ("planar", "convex", "starlike", "lamina", "holed", "validTriangulation"):
            for flags in ({"uvSet": "map1"}, {"tolerance": 0.1}):
                with self.subTest(kind=kind, flags=flags):
                    with self.assertRaises(TypeError):
                        face.isKind(kind, **flags)
        with self.subTest(kind="zeroArea", flags="uvSet"):
            with self.assertRaises(TypeError):
                face.isKind("zeroArea", uvSet="map1")
        with self.subTest(kind="uvReversed", flags="tolerance"):
            with self.assertRaises(TypeError):
                face.isKind("uvReversed", tolerance=0.1)
        with self.assertRaises(TypeError):
            face.isKind()
        with self.assertRaises(TypeError):
            face.isKind("zeroArea", 0.1)

    def test_area_uv_and_exclusive_arguments(self):
        """getArea(uv=True) は MItMeshPolygon.getUVArea と同じ。uv=True と空間指定、uv=True でない uvSet は TypeError。"""
        node = cmds.polyCube(name=self.ns + ":cube", width=2, height=3, depth=4, constructionHistory=False)[0]
        shape = mlib.getNode(node).getShape()
        cmds.setAttr(node + ".scale", 2, 2, 2)
        iterator = om2.MItMeshPolygon(shape.mpath())
        for index in range(shape.getNumPolygons()):
            iterator.setIndex(index)
            face = shape.getFaces(index)
            with self.subTest(face=index):
                self.assertAlmostEqual(face.getArea(uv=True), iterator.getUVArea("map1"))
                self.assertAlmostEqual(face.getArea(uv=True, uvSet="map1"), iterator.getUVArea("map1"))
                self.assertAlmostEqual(face.getArea(), iterator.getArea(om2.MSpace.kObject))
                self.assertAlmostEqual(face.getArea(uv=False, ws=True), iterator.getArea(om2.MSpace.kWorld), places=5)
        face = shape.getFaces(0)
        self.assertEqual(shape.getFaces([0, 1]).getArea(uv=True), [shape.getFaces(0).getArea(uv=True), shape.getFaces(1).getArea(uv=True)])
        rejected = (
            {"uv": True, "worldSpace": True},
            {"uv": True, "worldSpace": False},
            {"uv": True, "ws": True},
            {"uvSet": "map1"},
            {"uv": False, "uvSet": "map1"},
            {"uv": 1},
            {"uv": None},
            {"uv": True, "uvSet": 5},
        )
        for flags in rejected:
            with self.subTest(flags=flags):
                with self.assertRaises(TypeError):
                    face.getArea(**flags)
        with self.assertRaises(ValueError):
            face.getArea(uv=True, uvSet="noSuchUVSet")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
