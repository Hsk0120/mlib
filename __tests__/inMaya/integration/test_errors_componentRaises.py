"""components の公開APIが docstring の Raises に書いた例外のうち、ほかのテストで確かめていないものを固定する。

- Face・Edge・Vertex の照会・設定: トポロジーを変えて番号が範囲の外になると IndexError、Shape を削除すると RuntimeError。
- Face の UV の照会: uvSet・tolerance の型は TypeError、無い UV セットは ValueError。
- VertexFace.setNormalLocked・removeColor: 引数の型は TypeError、ロックしたメッシュは RuntimeError、
  fast と入力ヒストリは NotImplementedError、無いカラーセットは ValueError。getBinormal は UV が無いと RuntimeError。
- PointComponent(s) の getPositionY・getPositionZ の空間指定は TypeError、moveBy の fast と入力ヒストリは NotImplementedError。
- Components.getFullNames・isComplete・CVs.getFullNames: 範囲の外は IndexError、Shape の削除後は RuntimeError。

例外の後は、可能なものについて座標・法線・色・ノード数が変わっていないことも確かめる。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.components import CVs, Edge, Face, Vertex, VertexFace, Vertices


class _ComponentCase(NamespaceCase):
    """テスト用のメッシュの作成と、シーンの比較を共通にする。"""

    PREFIX = "mlibSpecCompRaises_"
    UNLOCK_NODES = True

    def nodes(self):
        """シーン全体のノードの完全名の集合を返す。"""
        return set(cmds.ls(long=True) or [])

    def plane(self, text="plane", history=False):
        """2x2 分割の平面(頂点9・辺12・面4・UV9)を作り、(transform, Mesh) を返す。"""
        transform = cmds.polyPlane(name=self.name(text), width=2, height=2, subdivisionsX=2, subdivisionsY=2, constructionHistory=history)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return transform, mlib.getNode(shape)

    def shrinkPlane(self, transform):
        """角の面(3番)を消し、頂点8番・辺10/11番・面3番を範囲外にする。"""
        cmds.delete(transform + ".f[3]")

    def points(self, mesh):
        """全頂点のオブジェクト空間の座標を返す。"""
        return cmds.xform(mesh.getFullName() + ".vtx[*]", query=True, translation=True, objectSpace=True)


#: 面3番(縮めた平面で範囲外になる)に対する照会。(名前, Face を受けて呼ぶ関数)。
_FACE_CALLS = (
    ("getConnectedFaces", lambda face: face.getConnectedFaces()),
    ("getConnectedEdges", lambda face: face.getConnectedEdges()),
    ("getConnectedVertices", lambda face: face.getConnectedVertices()),
    ("getVertexFaces", lambda face: face.getVertexFaces()),
    ("getUVSetNames", lambda face: face.getUVSetNames()),
    ("getPointAtUV", lambda face: face.getPointAtUV(0.9, 0.9)),
    ("getUVAtPoint", lambda face: face.getUVAtPoint((0.5, 0.0, 0.5))),
    ("isOnBoundary", lambda face: face.isOnBoundary()),
    ("isPlanar", lambda face: face.isPlanar()),
    ("isConvex", lambda face: face.isConvex()),
    ("isStarlike", lambda face: face.isStarlike()),
    ("isLamina", lambda face: face.isLamina()),
    ("isHoled", lambda face: face.isHoled()),
    ("isZeroArea", lambda face: face.isZeroArea()),
    ("getTriangleCount", lambda face: face.getTriangleCount()),
)

#: 辺11番に対する照会と設定。
_EDGE_CALLS = (
    ("getConnectedEdges", lambda edge: edge.getConnectedEdges()),
    ("isOnBoundary", lambda edge: edge.isOnBoundary()),
    ("isSmooth", lambda edge: edge.isSmooth()),
    ("setSmooth", lambda edge: edge.setSmooth(False)),
)

#: 頂点8番に対する照会と設定。
_VERTEX_CALLS = (
    ("getEdges", lambda vertex: vertex.getEdges()),
    ("getConnectedVertices", lambda vertex: vertex.getConnectedVertices()),
    ("getVertexFaces", lambda vertex: vertex.getVertexFaces()),
    ("isOnBoundary", lambda vertex: vertex.isOnBoundary()),
    ("getColor", lambda vertex: vertex.getColor()),
    ("setColor", lambda vertex: vertex.setColor((1.0, 0.0, 0.0))),
    ("getNormal", lambda vertex: vertex.getNormal()),
)


class TopologyRangeErrorTest(_ComponentCase):
    """番号が範囲の外なら IndexError、Shape を削除したら RuntimeError。"""

    def _check(self, factory, calls, index_error=True):
        """縮めた平面と削除後の平面で、各呼出しの例外を確かめる。

        Args:
            factory (Callable[[Mesh], Component]): メッシュから対象のコンポーネントを作る関数。
            calls (tuple): (名前, 関数) の並び。
            index_error (bool): 縮めた状態で IndexError を確かめるか。
        """
        transform, mesh = self.plane()
        cmds.polyColorPerVertex(mesh.getFullName() + ".vtx[*]", rgb=(0.0, 0.0, 0.0), colorDisplayOption=True)
        target = factory(mesh)
        for name, call in calls:
            with self.subTest(method=name, state="valid"):
                call(target)
        self.shrinkPlane(transform)
        if index_error:
            before = (self.points(mesh), self.nodes())
            for name, call in calls:
                with self.subTest(method=name, state="shrunk"):
                    with self.assertRaises(IndexError):
                        call(target)
                    self.assertEqual((self.points(mesh), self.nodes()), before)
        cmds.delete(transform)
        before = self.nodes()
        for name, call in calls:
            with self.subTest(method=name, state="deleted"):
                with self.assertRaises(RuntimeError):
                    call(target)
                self.assertEqual(self.nodes(), before)

    def test_face(self):
        """Face の照会。"""
        self._check(lambda mesh: Face(mesh, 3), _FACE_CALLS)

    def test_edge(self):
        """Edge の照会と setSmooth。"""
        self._check(lambda mesh: Edge(mesh, 11), _EDGE_CALLS)

    def test_vertex(self):
        """Vertex の照会と setColor。"""
        self._check(lambda mesh: Vertex(mesh, 8), _VERTEX_CALLS)

    def test_components_names_and_complete(self):
        """Components.getFullNames・isComplete。"""
        calls = (("getFullNames", lambda vertices: vertices.getFullNames()), ("isComplete", lambda vertices: vertices.isComplete()))
        self._check(lambda mesh: Vertices(mesh, [0, 8]), calls)

    def test_cvs_full_names(self):
        """CVs.getFullNames: CV数を減らすと IndexError、カーブの削除後は RuntimeError。"""
        transform = cmds.curve(name=self.name("curve"), degree=1, point=[(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0)])
        shape = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        cvs = CVs(shape, [3, 4])
        self.assertEqual(len(cvs.getFullNames()), 2)
        cmds.rebuildCurve(transform, constructionHistory=False, replaceOriginal=True, rebuildType=0, spans=1, degree=1, keepRange=0)
        with self.assertRaises(IndexError):
            cvs.getFullNames()
        cmds.delete(transform)
        with self.assertRaises(RuntimeError):
            cvs.getFullNames()


class FaceUVArgumentErrorTest(_ComponentCase):
    """Face の UV の照会の引数の拒否。"""

    def test_uv_set_type_and_missing(self):
        """uvSet が文字列・None 以外なら TypeError、無い UV セットなら ValueError。"""
        _, mesh = self.plane()
        face = Face(mesh, 0)
        calls = (
            ("getUVArea", lambda **kwargs: face.getUVArea(**kwargs)),
            ("isUVReversed", lambda **kwargs: face.isUVReversed(**kwargs)),
            ("isZeroUVArea", lambda **kwargs: face.isZeroUVArea(**kwargs)),
        )
        for name, call in calls:
            with self.subTest(method=name, state="valid"):
                call()
            for error, kwargs in ((TypeError, {"uvSet": 5}), (TypeError, {"uvSet": ["map1"]}), (ValueError, {"uvSet": "noSuchUVSet"})):
                if name == "isZeroUVArea" and error is ValueError:
                    continue
                with self.subTest(method=name, kwargs=kwargs):
                    with self.assertRaises(error):
                        call(**kwargs)

    def test_tolerance_type(self):
        """isZeroUVArea・isZeroArea の tolerance が数値でなければ TypeError。"""
        _, mesh = self.plane()
        face = Face(mesh, 0)
        for name, call in (("isZeroUVArea", face.isZeroUVArea), ("isZeroArea", face.isZeroArea)):
            for value in ("0.1", None, [0.1]):
                with self.subTest(method=name, tolerance=value):
                    with self.assertRaises(TypeError):
                        call(tolerance=value)


class VertexFaceErrorTest(_ComponentCase):
    """VertexFace.setNormalLocked・removeColor・getBinormal の拒否。"""

    def locks(self, mesh):
        """全頂点フェースの法線のロック状態を返す。"""
        return cmds.polyNormalPerVertex(mesh.getFullName() + ".vtxFace[*][*]", query=True, freezeNormal=True)

    def test_set_normal_locked_type(self):
        """state・fast が bool 以外なら TypeError で、ロック状態を変えない。"""
        _, mesh = self.plane()
        target = VertexFace(mesh, 0)
        before = self.locks(mesh)
        for kwargs in ({"state": "yes"}, {"state": 1}, {"fast": "yes"}, {"fast": None}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(TypeError):
                    target.setNormalLocked(**kwargs)
                self.assertEqual(self.locks(mesh), before)

    def test_set_normal_locked_locked_mesh(self):
        """lockNode したメッシュは RuntimeError で、ロック状態を変えない。"""
        _, mesh = self.plane()
        target = VertexFace(mesh, 0)
        before = self.locks(mesh)
        cmds.lockNode(mesh.getFullName(), lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    target.setNormalLocked(True, fast=fast)
        cmds.lockNode(mesh.getFullName(), lock=False)
        self.assertEqual(self.locks(mesh), before)

    def test_fast_with_history(self):
        """fast=True で入力ヒストリのあるメッシュなら NotImplementedError で、ノードを増やさない。"""
        _, mesh = self.plane(history=True)
        cmds.polyColorPerVertex(mesh.getFullName() + ".vtx[*]", rgb=(0.0, 0.0, 0.0), colorDisplayOption=True)
        target = VertexFace(mesh, 0)
        before = (self.locks(mesh), self.nodes())
        for name, call in (("setNormalLocked", lambda: target.setNormalLocked(True, fast=True)), ("removeColor", lambda: target.removeColor(fast=True))):
            with self.subTest(method=name):
                with self.assertRaises(NotImplementedError):
                    call()
                self.assertEqual((self.locks(mesh), self.nodes()), before)

    def test_remove_color_arguments(self):
        """removeColor: fast・colorSet の型は TypeError、無いカラーセットは ValueError。色は変えない。"""
        _, mesh = self.plane()
        target = VertexFace(mesh, 0)
        target.setColor((1.0, 0.0, 0.0))
        before = target.getColor()
        for error, kwargs in ((TypeError, {"fast": "yes"}), (TypeError, {"colorSet": 5}), (ValueError, {"colorSet": "noSuchColorSet"})):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(error):
                    target.removeColor(**kwargs)
                self.assertEqual(target.getColor(), before)

    def test_binormal_without_uv(self):
        """UV を割り当てていないメッシュでは getBinormal が RuntimeError。"""
        transform = cmds.polyPlane(name=self.name("noUV"), subdivisionsX=1, subdivisionsY=1, createUVs=0, constructionHistory=False)[0]
        mesh = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        self.assertEqual(cmds.polyEvaluate(mesh.getFullName(), uvcoord=True), 0)
        with self.assertRaises(RuntimeError):
            VertexFace(mesh, 0).getBinormal()


class PointComponentArgumentErrorTest(_ComponentCase):
    """PointComponent(s).getPositionY・getPositionZ の空間指定と、moveBy の fast の拒否。"""

    def test_get_position_space_type(self):
        """worldSpace が bool 以外、worldSpace と ws の同時指定は TypeError。"""
        _, mesh = self.plane()
        vertex = Vertex(mesh, 4)
        vertices = Vertices(mesh, [0, 4])
        calls = (
            ("Vertex.getPositionY", vertex.getPositionY),
            ("Vertex.getPositionZ", vertex.getPositionZ),
            ("Vertices.getPositionY", vertices.getPositionY),
            ("Vertices.getPositionZ", vertices.getPositionZ),
        )
        for name, call in calls:
            for args, kwargs in (((), {"worldSpace": "yes"}), ((1,), {}), ((), {"ws": 1}), ((True,), {"ws": True}), ((), {"worldSpace": True, "ws": True})):
                with self.subTest(method=name, args=args, kwargs=kwargs):
                    with self.assertRaises(TypeError):
                        call(*args, **kwargs)

    def test_move_by_fast_with_history(self):
        """fast=True で入力ヒストリのある Shape なら NotImplementedError で、座標を変えない。"""
        _, mesh = self.plane(history=True)
        before = self.points(mesh)
        for name, call in (("Vertex.moveBy", Vertex(mesh, 4).moveBy), ("Vertices.moveBy", Vertices(mesh, [0, 4]).moveBy)):
            with self.subTest(method=name):
                with self.assertRaises(NotImplementedError):
                    call((1.0, 0.0, 0.0), fast=True)
                self.assertEqual(self.points(mesh), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
