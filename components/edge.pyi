# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""メッシュのエッジと、エッジの集まり。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import _pick_alias, _require_bool, preservedSelection, undoChunk
from ..maths.vector import _vectors_of_points
from ..util import _UNSET, _world_space
from .component import Component, Components
from .face import Faces
from .vertex import Vertices
from typing import Any, Iterator
from mlib.maths.vector import Vector
from typing import overload



class Edge(Component):
    """メッシュのエッジ1つを表すクラス。"""
    shape_type: str
    component_type: str
    count_attribute: str
    def getVertices(self) -> Vertices:
        """エッジの両端の頂点を取得する。

        Returns:
            Vertices: 頂点。Mayaが返すつながりの順に並ぶ。
        """
        ...
    def getFaces(self) -> Faces:
        """このエッジに接する面を取得する。

        :meth:`Edges.getFaces` と同じ規則。

        Returns:
            Faces: 面。番号の小さい順に並び、重なりは無い。
        """
        ...
    def getLength(self, worldSpace: bool = ..., *, ws: bool = ...) -> float:
        """エッジの長さを、cmで取得する。

        ``MItMeshEdge.length`` で求める。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 長さ(cm)。ワールド空間では、親のスケールも含む。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getCenter(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def getLoop(self) -> Edges:
        """このエッジを通るエッジのループを取得する。

        :meth:`Edges.getLoop` と同じ規則。

        Returns:
            Edges: 自身を先頭に、たどった順のエッジ。
        """
        ...
    def getRing(self) -> Edges:
        """このエッジを通るエッジのリングを取得する。

        :meth:`Edges.getRing` と同じ規則。

        Returns:
            Edges: 自身を先頭に、たどった順のエッジ。
        """
        ...
    def getConnectedEdges(self) -> Edges:
        """このエッジと頂点を共有するエッジを取得する。

        自身は含めない。``MItMeshEdge.getConnectedEdges`` で求める。

        Returns:
            Edges: エッジ。番号の小さい順に並び、重なりは無い。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def isOnBoundary(self) -> bool:
        """メッシュの縁のエッジか調べる。

        縁のエッジとは、接する面が1つだけのエッジのこと。

        Returns:
            bool: 縁ならTrue。:meth:`Mesh.getBorderEdges <mlib.nodes.mesh.Mesh.getBorderEdges>` と同じ判定。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def isSmooth(self) -> bool:
        """ソフトエッジ(スムーズ)か調べる。

        ``MFnMesh.isEdgeSmooth`` で調べる。

        Returns:
            bool: ソフトエッジならTrue、ハードエッジならFalse。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def setSmooth(self, value: bool = ...) -> Edge:
        """ソフトエッジかハードエッジかを設定する。

        ``cmds.polySoftEdge`` (角度180または0)で書き込み、1回のUndoで戻せるようにまとめる。選択は変えない。

        - コンストラクションヒストリのあるメッシュでは、``polySoftEdge`` ノードをヒストリへ足す。
        - ヒストリの無いメッシュでは、ヒストリを作らずに直接書き込む。

        Args:
            value (bool): Trueならソフトエッジ、Falseならハードエッジにする。既定はTrue。

        Returns:
            Edge: 自身。

        Raises:
            TypeError: valueがboolでない場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはロックなどでMayaが書き込みを受け付けなかった場合。
        """
        ...
    def _iterator(self) -> om2.MItMeshEdge:
        """番号を確かめて、このエッジに合わせた ``om2.MItMeshEdge`` を返す。

        Returns:
            om2.MItMeshEdge: このエッジを指す反復子。
        """
        ...
_EDGE_GET_VERTICES: Any


class Edges(Components):
    """同じメッシュにあるエッジの集まりを表すクラス。"""
    def __iter__(self) -> Iterator[Edge]: ...
    @overload
    def __getitem__(self, index: int) -> Edge: ...
    @overload
    def __getitem__(self, index: slice) -> Edges: ...
    component_class: Any
    def getVertices(self) -> Vertices:
        """各エッジの両端の頂点を取得する。

        Returns:
            Vertices: 頂点。エッジを持っている順に集め、重なりは除く。
        """
        ...
    def getFaces(self) -> Faces:
        """持っているエッジのどれかに接する面を取得する。

        ``cmds.polyListComponentConversion(toFace=True)`` と同じ面になる。選択は変えない。

        Returns:
            Faces: 面。番号の小さい順に並び、重なりは無い。エッジが空なら空。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def getLoop(self) -> Edges:
        """持っているエッジを通る、エッジのループを取得する。

        選択は変えない。たどり方は ``cmds.polySelect(edgeLoop=...)`` と同じ。

        - 4本のエッジが集まる頂点では、今のエッジとフェースを共有しない、向かいのエッジへ進む。
        - それ以外の頂点(極)、メッシュの縁のエッジ、一周して戻った所で止まる。

        Returns:
            Edges: エッジ。持っている順に、各エッジのループを両方向へたどった順で並び、重なりは無い。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def getRing(self) -> Edges:
        """持っているエッジを通る、エッジのリングを取得する。

        選択は変えない。

        - 四角形のフェースを横切って、今のエッジと頂点を共有しない、向かいのエッジへ進む。
        - 四角形でないフェース、メッシュの縁、一周して戻った所で止まる。

        Returns:
            Edges: エッジ。持っている順に、各エッジのリングを両方向へたどった順で並び、重なりは無い。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def getLength(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[float]:
        """各要素の :meth:`~mlib.components.edge.Edge.getLength` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getCenter(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.edge.Edge.getCenter` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getConnectedEdges(self) -> list[Edges]:
        """各要素の :meth:`~mlib.components.edge.Edge.getConnectedEdges` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isOnBoundary(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.edge.Edge.isOnBoundary` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isSmooth(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.edge.Edge.isSmooth` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setSmooth(self, value: bool = ...) -> list[Edge]:
        """各要素の :meth:`~mlib.components.edge.Edge.setSmooth` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.components.component.Component.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...


class _Topology:
    """エッジ・頂点・フェースのつながりを調べて覚えておくクラス。

    必要な要素の分だけ、OpenMayaの反復子で調べる。

    Args:
        mesh (Mesh): 調べるメッシュ。
    """
    def __init__(self, mesh) -> None: ...
    def edge_vertices(self, edge):
        """エッジの両端の頂点番号を返す。"""
        ...
    def edge_faces(self, edge):
        """エッジに接するフェース番号を返す。"""
        ...
    def vertex_edges(self, vertex):
        """頂点に集まるエッジ番号を返す。"""
        ...
    def face_edges(self, face):
        """フェースのエッジ番号を返す。"""
        ...
    def loop(self, edge: int) -> list[int]:
        """エッジのループを、始めのエッジから両方向へたどった順で返す。

        Args:
            edge (int): 始めのエッジ。

        Returns:
            list[int]: ループのエッジ(始めのエッジを含む)。
        """
        ...
    def ring(self, edge: int) -> list[int]:
        """エッジのリングを、始めのエッジから両方向へたどった順で返す。

        Args:
            edge (int): 始めのエッジ。

        Returns:
            list[int]: リングのエッジ(始めのエッジを含む)。
        """
        ...
    def _loop_next(self, current, pivot):
        """ループで、頂点pivotの先へ続くエッジを返す。続かなければNone。"""
        ...
