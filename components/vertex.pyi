# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""メッシュの頂点と、頂点の集まり。"""

import maya.api.OpenMaya as om2
from ..decorator import _pick_alias, _require_bool
from ..maths.vector import Vector
from ..util import _UNSET, _world_space
from .pointComponent import PointComponent, PointComponents
from .uv import UVs
from typing import Any, Iterator, Sequence
from mlib.components.edge import Edges
from mlib.components.face import Faces
from mlib.components.vertexFace import VertexFaces
from typing import overload



class Vertex(PointComponent):
    """メッシュの頂点1つを表すクラス。番号は0から始まる。"""
    shape_type: str
    component_type: str
    count_attribute: str
    def getFaces(self) -> Faces:
        """この頂点に触れている面を取得する。

        :meth:`Vertices.getFaces` と同じ規則。

        Returns:
            Faces: 面。番号の小さい順に並び、重なりは無い。
        """
        ...
    def getEdges(self) -> Edges:
        """この頂点に集まるエッジを取得する。

        ``cmds.polyListComponentConversion(toEdge=True)`` と同じエッジになる。

        Returns:
            Edges: エッジ。番号の小さい順に並び、重なりは無い。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getConnectedVertices(self) -> Vertices:
        """エッジでつながった隣の頂点を取得する。

        自身は含めない。

        Returns:
            Vertices: 頂点。番号の小さい順に並び、重なりは無い。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getVertexFaces(self) -> VertexFaces:
        """この頂点の頂点フェースを取得する。

        頂点フェースは、この頂点と、頂点に触れている各フェースとの組。

        Returns:
            VertexFaces: 頂点フェース。フェース番号の小さい順に並ぶ。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getUVs(self) -> UVs:
        """この頂点に割り当てられた、現在のUVセットのUVを取得する。

        UVの境界(シーム)の上にある頂点は、UVを複数持つ。

        Returns:
            UVs: UV。番号の小さい順に並び、重なりは無い。UVが無ければ空。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def isOnBoundary(self) -> bool:
        """メッシュの縁の上にある頂点か調べる。

        縁とは、接する面が1つだけのエッジのこと。``MItMeshVertex.onBoundary`` で調べる。

        Returns:
            bool: 縁の上ならTrue。:meth:`Mesh.getBorderVertices <mlib.nodes.mesh.Mesh.getBorderVertices>` に
                含まれる頂点と同じになる。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getColor(self, colorSet: str | None = ...) -> tuple[float, float, float, float] | None:
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
        ...
    def setColor(self, color: Sequence[float] | om2.MColor, colorSet: str | None = ..., *, fast: bool = ...) -> Vertex:
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
        ...
    def getNormal(self, worldSpace: bool = ..., angleWeighted: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def _iterator(self) -> om2.MItMeshVertex:
        """番号を確かめて、この頂点に合わせた ``om2.MItMeshVertex`` を返す。

        Returns:
            om2.MItMeshVertex: この頂点を指す反復子。
        """
        ...


class Vertices(PointComponents):
    """同じメッシュにある頂点の集まりを表すクラス。

    座標の取得、一部の取り出し、ミラーができる。
    """
    def __iter__(self) -> Iterator[Vertex]: ...
    @overload
    def __getitem__(self, index: int) -> Vertex: ...
    @overload
    def __getitem__(self, index: slice) -> Vertices: ...
    component_class: Any
    def grow(self) -> Vertices:
        """エッジでつながった隣の頂点を加えた、頂点の集まりを取得する。

        選択は変えない。

        Returns:
            Vertices: 新しい頂点の集まり。持っている順の頂点のあとに、加えた頂点を番号の小さい順に続ける。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def shrink(self) -> Vertices:
        """縁の頂点を除いた、頂点の集まりを取得する。

        縁の頂点とは、この集まりに無い頂点とエッジでつながっている頂点のこと。選択は変えない。

        Returns:
            Vertices: 新しい頂点の集まり。持っている順を保つ。すべてが縁なら空。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def getFaces(self) -> Faces:
        """持っている頂点のどれかに触れている面を取得する。

        ``cmds.polyListComponentConversion(toFace=True)`` と同じ面になる。選択は変えない。

        Returns:
            Faces: 面。番号の小さい順に並び、重なりは無い。頂点が空なら空。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def _neighbor_indices(self) -> dict[int, list[int]]:
        """持っている頂点ごとに、エッジでつながった頂点の番号を返す。

        Returns:
            dict[int, list[int]]: {頂点番号: 隣の頂点番号}。
        """
        ...
    def getEdges(self) -> list[Edges]:
        """各要素の :meth:`~mlib.components.vertex.Vertex.getEdges` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getConnectedVertices(self) -> list[Vertices]:
        """各要素の :meth:`~mlib.components.vertex.Vertex.getConnectedVertices` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getVertexFaces(self) -> list[VertexFaces]:
        """各要素の :meth:`~mlib.components.vertex.Vertex.getVertexFaces` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUVs(self) -> list[UVs]:
        """各要素の :meth:`~mlib.components.vertex.Vertex.getUVs` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isOnBoundary(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.vertex.Vertex.isOnBoundary` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getColor(self, colorSet: str | None = ...) -> list[tuple[float, float, float, float] | None]:
        """各要素の :meth:`~mlib.components.vertex.Vertex.getColor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setColor(self, color: Sequence[float] | om2.MColor, colorSet: str | None = ..., *, fast: bool = ...) -> list[Vertex]:
        """各要素の :meth:`~mlib.components.vertex.Vertex.setColor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getNormal(self, worldSpace: bool = ..., angleWeighted: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.vertex.Vertex.getNormal` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.components.component.Component.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
