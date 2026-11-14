"""メッシュの頂点と、頂点の集まり。"""

import maya.api.OpenMaya as om2

from ..decorator import _pick_alias, _require_bool
from ..maths.vector import Vector
from ..util import _UNSET, _world_space
from .pointComponent import PointComponent, PointComponents
from .uv import UVs


class Vertex(PointComponent):
    """メッシュの頂点1つを表すクラス。番号は0から始まる。"""

    shape_type = "mesh"
    component_type = "vtx"
    count_attribute = "getNumVertices"

    def getFaces(self):
        """この頂点に触れている面を取得する。

        :meth:`Vertices.getFaces` と同じ規則。

        Returns:
            Faces: 面。番号の小さい順に並び、重なりは無い。
        """
        return Vertices(self.shape, [self.index]).getFaces()

    def getEdges(self):
        """この頂点に集まるエッジを取得する。

        ``cmds.polyListComponentConversion(toEdge=True)`` と同じエッジになる。

        Returns:
            Edges: エッジ。番号の小さい順に並び、重なりは無い。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        # edge.py が vertex.py を import するため、循環を避けて呼出し時に読む。
        from .edge import Edges

        iterator = self._iterator()
        return Edges(self.shape, sorted(set(iterator.getConnectedEdges())))

    def getConnectedVertices(self):
        """エッジでつながった隣の頂点を取得する。

        自身は含めない。

        Returns:
            Vertices: 頂点。番号の小さい順に並び、重なりは無い。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        iterator = self._iterator()
        return Vertices(self.shape, sorted(set(iterator.getConnectedVertices())))

    def getVertexFaces(self):
        """この頂点の頂点フェースを取得する。

        頂点フェースは、この頂点と、頂点に触れている各フェースとの組。

        Returns:
            VertexFaces: 頂点フェース。フェース番号の小さい順に並ぶ。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        # vertexFace.py が vertex.py を import するため、循環を避けて呼出し時に読む。
        from .vertexFace import VertexFaces

        faces = sorted(self._iterator().getConnectedFaces())
        return VertexFaces(self.shape, [(self.index, face) for face in faces])

    def getUVs(self):
        """この頂点に割り当てられた、現在のUVセットのUVを取得する。

        UVの境界(シーム)の上にある頂点は、UVを複数持つ。

        Returns:
            UVs: UV。番号の小さい順に並び、重なりは無い。UVが無ければ空。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        iterator = self._iterator()
        uv_set = self.shape._geometry_fn().currentUVSetName()
        return UVs(self.shape, sorted(set(iterator.getUVIndices(uv_set))))

    def isOnBoundary(self):
        """メッシュの縁の上にある頂点か調べる。

        縁とは、接する面が1つだけのエッジのこと。``MItMeshVertex.onBoundary`` で調べる。

        Returns:
            bool: 縁の上ならTrue。:meth:`Mesh.getBorderVertices <mlib.nodes.mesh.Mesh.getBorderVertices>` に
                含まれる頂点と同じになる。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return self._iterator().onBoundary()

    def getColor(self, colorSet=None):
        """頂点の色を取得する。

        :meth:`Mesh.getVertexColors <mlib.nodes.mesh.Mesh.getVertexColors>` で得られる、この頂点の値と同じ。
        面ごとに違う色を持つ頂点では、その平均になる。

        Args:
            colorSet (str | None): カラーセットの名前。Noneなら現在のカラーセット。既定はNone。

        Returns:
            tuple[float, float, float, float] | None: (R, G, B, A)。色が無い場合はNone。

        Raises:
            TypeError: colorSetが文字列でもNoneでもない場合。
            ValueError: 指定した名前のカラーセットが無い場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        self._require_valid()
        return self.shape.getVertexColors(colorSet)[self.index]

    def setColor(self, color, colorSet=None, *, fast=False):
        """頂点の色を設定する。

        :meth:`Mesh.setVertexColors <mlib.nodes.mesh.Mesh.setVertexColors>` で、この頂点だけを書き込む。
        この頂点のすべての頂点フェースを、同じ色にする。

        - ふだんは ``cmds.polyColorPerVertex`` で書き込み、1回のUndoで戻せるようにまとめる。
        - ``fast=True`` ならUndoには記録しない。

        Args:
            color (Sequence[float] | om2.MColor): (R, G, B) または (R, G, B, A) の有限な数値。Aを省くと1.0になる。
            colorSet (str | None): カラーセットの名前。Noneなら現在のカラーセット(無ければMayaが ``colorSet1`` を作る)。
                名前を指定する場合は、そのカラーセットがすでにある必要がある。既定はNone。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Vertex: 自身。

        Raises:
            TypeError: fastがboolでない場合、colorSetが文字列でもNoneでもない場合、または色の型が合わない場合。
            ValueError: 成分の数が3でも4でもないか有限でない場合、またはカラーセットが無い場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはロックなどでMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力(コンストラクションヒストリ)がある場合。
        """
        self._require_valid()
        self.shape.setVertexColors([color], [self.index], colorSet=colorSet, fast=fast)
        return self

    def getNormal(self, worldSpace=_UNSET, angleWeighted=False, *, ws=_UNSET):
        """頂点の法線を、長さ1で取得する。

        接する面の法線の平均で、``MFnMesh.getVertexNormal`` で求める。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            angleWeighted (bool): Trueなら面の角度で重みを付けた平均、Falseならそのままの平均にする。既定はFalse。

        Returns:
            Vector: 長さ1の法線。面の法線から計算するので、ロックした法線やハードエッジは反映しない。

        Raises:
            TypeError: worldSpaceかangleWeightedがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        _require_bool(angleWeighted, "angleWeighted")
        self._require_valid()
        return Vector(self.shape._geometry_fn().getVertexNormal(self.index, angleWeighted, space)).normal()

    def _iterator(self):
        """番号を確かめて、この頂点に合わせた ``om2.MItMeshVertex`` を返す。

        Returns:
            om2.MItMeshVertex: この頂点を指す反復子。
        """
        self._require_valid()
        iterator = om2.MItMeshVertex(self.shape.mpath())
        iterator.setIndex(self.index)
        return iterator


class Vertices(PointComponents):
    """同じメッシュにある頂点の集まりを表すクラス。

    座標の取得、一部の取り出し、ミラーができる。
    """

    component_class = Vertex

    def grow(self):
        """エッジでつながった隣の頂点を加えた、頂点の集まりを取得する。

        選択は変えない。

        Returns:
            Vertices: 新しい頂点の集まり。持っている順の頂点のあとに、加えた頂点を番号の小さい順に続ける。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        neighbors = self._neighbor_indices()
        added = sorted({index for indices in neighbors.values() for index in indices}.difference(self._indices))
        return Vertices(self.shape, list(self._indices) + added)

    def shrink(self):
        """縁の頂点を除いた、頂点の集まりを取得する。

        縁の頂点とは、この集まりに無い頂点とエッジでつながっている頂点のこと。選択は変えない。

        Returns:
            Vertices: 新しい頂点の集まり。持っている順を保つ。すべてが縁なら空。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        neighbors = self._neighbor_indices()
        kept = set(self._indices)
        return Vertices(self.shape, [index for index in self._indices if kept.issuperset(neighbors[index])])

    def getFaces(self):
        """持っている頂点のどれかに触れている面を取得する。

        ``cmds.polyListComponentConversion(toFace=True)`` と同じ面になる。選択は変えない。

        Returns:
            Faces: 面。番号の小さい順に並び、重なりは無い。頂点が空なら空。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        # face.py が vertex.py を import するため、循環を避けて呼出し時に読む。
        from .face import Faces

        self._require_valid()
        iterator = om2.MItMeshVertex(self.shape.mpath())
        found = set()
        for index in self._indices:
            iterator.setIndex(index)
            found.update(iterator.getConnectedFaces())
        return Faces(self.shape, sorted(found))

    def _neighbor_indices(self):
        """持っている頂点ごとに、エッジでつながった頂点の番号を返す。

        Returns:
            dict[int, list[int]]: {頂点番号: 隣の頂点番号}。
        """
        self._require_valid()
        iterator = om2.MItMeshVertex(self.shape.mpath())
        neighbors = {}
        for index in self._indices:
            iterator.setIndex(index)
            neighbors[index] = list(iterator.getConnectedVertices())
        return neighbors
