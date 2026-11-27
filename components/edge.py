"""メッシュのエッジと、エッジの集まり。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..common.units import convertDistance
from ..decorator import _pick_alias, _require_bool, preservedSelection, undoChunk
from ..maths.vector import _vectors_of_points
from ..util import _UNSET, _world_space
from .component import Component, Components
from .face import Faces
from .vertex import Vertices


class Edge(Component):
    """メッシュのエッジ1つを表すクラス。"""

    shape_type = "mesh"
    component_type = "e"
    count_attribute = "getNumEdges"

    def getVertices(self):
        """エッジの両端の頂点を取得する。

        Returns:
            Vertices: 頂点。Mayaが返すつながりの順に並ぶ。
        """
        self._require_valid()
        return Vertices(self.shape, self.shape._geometry_fn().getEdgeVertices(self.index))

    def getFaces(self):
        """このエッジに接する面を取得する。

        :meth:`Edges.getFaces` と同じ規則。

        Returns:
            Faces: 面。番号の小さい順に並び、重なりは無い。
        """
        return Edges(self.shape, [self.index]).getFaces()

    def getLength(self, worldSpace=_UNSET, *, distanceUnit="cm", ws=_UNSET):
        """エッジの長さを取得する。

        ``MItMeshEdge.length`` で求める。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            distanceUnit (str | None): 返す値の距離の単位。既定はcm。Noneなら、今のUIの距離単位。
                mm/cm/m/km/in/ft/yd/mi、またはMayaのロング名で指定する(:meth:`NurbsCurve.getLength
                <mlib.nodes.nurbsCurve.NurbsCurve.getLength>` と同じ)。

        Returns:
            float: 指定した単位での長さ。単位を省いたときはcm。ワールド空間では、親のスケールも含む。

        Raises:
            TypeError: worldSpaceがboolでない場合、distanceUnitが文字列でもNoneでもない場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: distanceUnitの単位の名前が対応していない場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        factor = convertDistance(1.0, fromUnit="cm", toUnit=distanceUnit)
        self._require_valid()
        it = om2.MItMeshEdge(self.shape.mpath())
        it.setIndex(self.index)
        return it.length(space) * factor

    def getCenter(self, worldSpace=_UNSET, *, ws=_UNSET):
        """エッジの中点を取得する。

        ``MItMeshEdge.center`` で求める。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 中点の位置(cm)。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        self._require_valid()
        it = om2.MItMeshEdge(self.shape.mpath())
        it.setIndex(self.index)
        return _vectors_of_points([it.center(space)])[0]

    def getLoop(self, *, ring=False):
        """このエッジを通るエッジのループ(``ring=True`` ならリング)を取得する。

        :meth:`Edges.getLoop` と同じ規則。

        Args:
            ring (bool): Trueなら、ループでなくリングをたどる。既定はFalse。

        Returns:
            Edges: 自身を先頭に、たどった順のエッジ。

        Raises:
            TypeError: ringがboolでない場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return Edges(self.shape, [self.index]).getLoop(ring=ring)

    def getConnected(self, *, type="edge"):
        """このエッジの隣にあるコンポーネントを取得する。

        ``type`` で、取得する種類を選ぶ。:meth:`Face.getConnected <mlib.components.face.Face.getConnected>` と同じく、
        自身と、自身を形づくる要素(両端の頂点)は含めない。

        - ``"edge"``: このエッジと頂点を共有するエッジ(``MItMeshEdge.getConnectedEdges``)。
        - ``"face"``: このエッジに接する面(``MItMeshEdge.getConnectedFaces``。:meth:`getFaces` と同じ)。
        - ``"vertex"``: 両端の頂点とエッジでつながる、両端以外の頂点(隣のエッジの向こう側の端)。
          両端の頂点は :meth:`getVertices` で取得する。

        Args:
            type (str): 取得する種類。``"edge"``・``"face"``・``"vertex"``。既定は ``"edge"``。

        Returns:
            Edges | Faces | Vertices: ``type`` に合う集まり。番号の小さい順に並び、重なりは無い。

        Raises:
            TypeError: typeが文字列でない場合。
            ValueError: typeが ``"edge"``・``"face"``・``"vertex"`` のどれでもない場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        if not isinstance(type, str):
            raise TypeError(f"typeは文字列で指定してください: {type.__class__.__name__}")
        if type not in ("edge", "face", "vertex"):
            raise ValueError(f'typeは"edge"・"face"・"vertex"のどれかで指定してください: {type!r}')
        iterator = self._iterator()
        if type == "edge":
            return Edges(self.shape, sorted(set(iterator.getConnectedEdges())))
        if type == "face":
            return Faces(self.shape, sorted(set(iterator.getConnectedFaces())))
        fn = self.shape._geometry_fn()
        ends = {iterator.vertexId(0), iterator.vertexId(1)}
        found = set()
        for edge in iterator.getConnectedEdges():
            found.update(fn.getEdgeVertices(edge))
        return Vertices(self.shape, sorted(found - ends))

    def isOnBoundary(self):
        """メッシュの縁のエッジか調べる。

        縁のエッジとは、接する面が1つだけのエッジのこと。

        Returns:
            bool: 縁ならTrue。:meth:`Mesh.getBorder <mlib.nodes.mesh.Mesh.getBorder>` と同じ判定。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return self._iterator().numConnectedFaces() == 1

    def isSmooth(self):
        """ソフトエッジ(スムーズ)か調べる。

        ``MFnMesh.isEdgeSmooth`` で調べる。

        Returns:
            bool: ソフトエッジならTrue、ハードエッジならFalse。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        self._require_valid()
        return self.shape._geometry_fn().isEdgeSmooth(self.index)

    def setSmooth(self, state=True):
        """ソフトエッジかハードエッジかを設定する。

        ``cmds.polySoftEdge`` (角度180または0)で書き込み、1回のUndoで戻せるようにまとめる。選択は変えない。

        - コンストラクションヒストリのあるメッシュでは、``polySoftEdge`` ノードをヒストリへ足す。
        - ヒストリの無いメッシュでは、ヒストリを作らずに直接書き込む。

        Args:
            state (bool): Trueならソフトエッジ、Falseならハードエッジにする。既定はTrue。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでない場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはロックなどでMayaが書き込みを受け付けなかった場合。
        """
        _require_bool(state, "state")
        self._require_valid()
        history = om2.MFnDependencyNode(self.shape.mnode()).findPlug("inMesh", False).isDestination
        # polySoftEdgeは対象のエッジを選択するため、選択を戻す処理も同じUndoに含める(Redoでも選択が変わらない)。
        with undoChunk("mlibEdgeSetSmooth"), preservedSelection():
            cmds.polySoftEdge(self._full_name(), angle=180 if state else 0, constructionHistory=history)

    def _iterator(self):
        """番号を確かめて、このエッジに合わせた ``om2.MItMeshEdge`` を返す。

        Returns:
            om2.MItMeshEdge: このエッジを指す反復子。
        """
        self._require_valid()
        iterator = om2.MItMeshEdge(self.shape.mpath())
        iterator.setIndex(self.index)
        return iterator


_EDGE_GET_VERTICES = Edge.getVertices


class Edges(Components):
    """同じメッシュにあるエッジの集まりを表すクラス。"""

    component_class = Edge

    def getVertices(self):
        """各エッジの両端の頂点を取得する。

        Returns:
            Vertices: 頂点。エッジを持っている順に集め、重なりは除く。
        """
        if not (self._uses_standard_iteration(Edge) and self._uses_standard_vertices() and Edge.getVertices is _EDGE_GET_VERTICES):
            return Vertices(self.shape, (v.index for item in self for v in item.getVertices()))
        indices = self._mesh_vertex_indices("numEdges", "getEdgeVertices")
        return Vertices(self.shape, indices)

    def getFaces(self):
        """持っているエッジのどれかに接する面を取得する。

        ``cmds.polyListComponentConversion(toFace=True)`` と同じ面になる。選択は変えない。

        Returns:
            Faces: 面。番号の小さい順に並び、重なりは無い。エッジが空なら空。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        self._require_valid()
        topology = _Topology(self.shape)
        found = set()
        for edge in self._indices:
            found.update(topology.edge_faces(edge))
        return Faces(self.shape, sorted(found))

    def getLoop(self, *, ring=False):
        """持っているエッジを通る、エッジのループ(``ring=True`` ならリング)を取得する。

        選択は変えない。

        ループ(既定)のたどり方は ``cmds.polySelect(edgeLoop=...)`` と同じ。

        - 4本のエッジが集まる頂点では、今のエッジとフェースを共有しない、向かいのエッジへ進む。
        - それ以外の頂点(極)、メッシュの縁のエッジ、一周して戻った所で止まる。

        リング(``ring=True``)は、ループと直交する向きにたどる。

        - 四角形のフェースを横切って、今のエッジと頂点を共有しない、向かいのエッジへ進む。
        - 四角形でないフェース、メッシュの縁、一周して戻った所で止まる。

        Args:
            ring (bool): Trueなら、ループでなくリングをたどる。既定はFalse。

        Returns:
            Edges: エッジ。持っている順に、各エッジのループ(リング)を両方向へたどった順で並び、重なりは無い。

        Raises:
            TypeError: ringがboolでない場合。
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        _require_bool(ring, "ring")
        self._require_valid()
        topology = _Topology(self.shape)
        follow = topology.ring if ring else topology.loop
        found = []
        for edge in self._indices:
            found.extend(follow(edge))
        return Edges(self.shape, found)


class _Topology:
    """エッジ・頂点・フェースのつながりを調べて覚えておくクラス。

    必要な要素の分だけ、OpenMayaの反復子で調べる。

    Args:
        mesh (Mesh): 調べるメッシュ。
    """

    def __init__(self, mesh):
        path = mesh.mpath()
        self._edge_iterator = om2.MItMeshEdge(path)
        self._vertex_iterator = om2.MItMeshVertex(path)
        self._face_iterator = om2.MItMeshPolygon(path)
        self._edge_vertices = {}
        self._edge_faces = {}
        self._vertex_edges = {}
        self._face_edges = {}

    def edge_vertices(self, edge):
        """エッジの両端の頂点番号を返す。"""
        if edge not in self._edge_vertices:
            self._edge_iterator.setIndex(edge)
            self._edge_vertices[edge] = (self._edge_iterator.vertexId(0), self._edge_iterator.vertexId(1))
        return self._edge_vertices[edge]

    def edge_faces(self, edge):
        """エッジに接するフェース番号を返す。"""
        if edge not in self._edge_faces:
            self._edge_iterator.setIndex(edge)
            self._edge_faces[edge] = tuple(self._edge_iterator.getConnectedFaces())
        return self._edge_faces[edge]

    def vertex_edges(self, vertex):
        """頂点に集まるエッジ番号を返す。"""
        if vertex not in self._vertex_edges:
            self._vertex_iterator.setIndex(vertex)
            self._vertex_edges[vertex] = tuple(self._vertex_iterator.getConnectedEdges())
        return self._vertex_edges[vertex]

    def face_edges(self, face):
        """フェースのエッジ番号を返す。"""
        if face not in self._face_edges:
            self._face_iterator.setIndex(face)
            self._face_edges[face] = tuple(self._face_iterator.getEdges())
        return self._face_edges[face]

    def loop(self, edge):
        """エッジのループを、始めのエッジから両方向へたどった順で返す。

        Args:
            edge (int): 始めのエッジ。

        Returns:
            list[int]: ループのエッジ(始めのエッジを含む)。
        """
        result = [edge]
        seen = {edge}
        for vertex in self.edge_vertices(edge):
            current, pivot = edge, vertex
            while True:
                following = self._loop_next(current, pivot)
                if following is None or following in seen:
                    break
                seen.add(following)
                result.append(following)
                start, end = self.edge_vertices(following)
                current, pivot = following, (end if start == pivot else start)
        return result

    def ring(self, edge):
        """エッジのリングを、始めのエッジから両方向へたどった順で返す。

        Args:
            edge (int): 始めのエッジ。

        Returns:
            list[int]: リングのエッジ(始めのエッジを含む)。
        """
        result = [edge]
        seen = {edge}
        for face in self.edge_faces(edge):
            current, crossing = edge, face
            while True:
                face_edges = self.face_edges(crossing)
                if len(face_edges) != 4:
                    break
                ends = set(self.edge_vertices(current))
                opposite = [other for other in face_edges if not ends.intersection(self.edge_vertices(other))]
                if len(opposite) != 1 or opposite[0] in seen:
                    break
                current = opposite[0]
                seen.add(current)
                result.append(current)
                following = [other for other in self.edge_faces(current) if other != crossing]
                if not following:
                    break
                crossing = following[0]
        return result

    def _loop_next(self, current, pivot):
        """ループで、頂点pivotの先へ続くエッジを返す。続かなければNone。"""
        edges = self.vertex_edges(pivot)
        faces = set(self.edge_faces(current))
        if len(faces) != 2 or len(edges) != 4:
            return None
        # 向かいのエッジは、今のエッジとフェースを共有しないエッジ。
        following = [other for other in edges if other != current and not faces.intersection(self.edge_faces(other))]

        return following[0] if len(following) == 1 else None
