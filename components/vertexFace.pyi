# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""メッシュの頂点フェース(フェースごとの頂点)と、頂点フェースの集まり。"""

import bisect
import maya.api.OpenMaya as om2
from ..decorator import _pick_alias, _require_bool
from ..maths.vector import Vector
from ..util import _UNSET, _world_space
from .component import Component, Components, _MultiIndexComponent, _MultiIndexComponents
from .face import Face
from .vertex import Vertex
from typing import Any, Iterable, Iterator, Sequence
from mlib.nodes.mesh import Mesh
from typing import overload


def _face_vertex_layout(shape: Mesh) -> tuple[list[int], list[int], list[int]]:
    """フェースごとの頂点の並びを取得する。

    Args:
        shape (Mesh): 型を確かめてあるメッシュ。

    Returns:
        tuple[list[int], list[int], list[int]]: (各フェースの先頭の通し番号, 各フェースの頂点数,
            通し番号の順に並べた頂点番号)。通し番号は、フェース番号の順、同じフェースの中では頂点の順に数える。
    """
    ...


class VertexFace(_MultiIndexComponent, Component):
    """メッシュの頂点フェース(``vtxFace[頂点][フェース]``)1つを表すクラス。

    頂点フェースは、フェースごとに法線や色を持たせるときの単位。

    持っている :attr:`index` は通し番号。フェース番号の順、同じフェースの中では頂点の順に数える
    (``om2.MFnMesh.getVertices`` の頂点の並び、``MItMeshFaceVertex`` の順と同じ)。
    ``(頂点, フェース)`` は :meth:`getMultiIndex` で取得する。
    """
    shape_type: str
    component_type: str
    index_size: int
    def getVertex(self) -> Vertex:
        """この頂点フェースの頂点を取得する。

        Returns:
            Vertex: 頂点。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getFace(self) -> Face:
        """この頂点フェースのフェースを取得する。

        Returns:
            Face: フェース。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getNormal(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
        """頂点フェースの法線を、長さ1で取得する。

        ``MFnMesh.getFaceVertexNormal`` で求める。ハードエッジやロックした法線を反映した、表示に使う法線になる
        (``polyNormalPerVertex`` で取得した値と同じ)。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 長さ1の法線。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def setNormal(self, normal: Sequence[float] | Vector, worldSpace: bool = ..., *, fast: bool = ..., check: bool = ..., ws: bool = ...) -> None:
        """この面頂点の法線を設定し、ロックする。

        通常はpolyNormalPerVertexでUndoに記録する。fastは入力ヒストリの無いメッシュに限る。

        Args:
            normal (Sequence[float] | Vector): 長さが0でないXYZ。正規化して設定する。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら有限な数値か書き込み前に確認する。既定FalseはMayaの受理に任せる。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fast・check・空間指定・法線の型が不正な場合。
            ValueError: 法線の成分が不正、長さ0、またはワールド変換が特異な場合。
            RuntimeError: メッシュがロックされているか、Mayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        ...
    def isNormalLocked(self) -> bool:
        """この面頂点の法線がロックされているか調べる。

        Returns:
            bool: 法線がロックされていればTrue。
        """
        ...
    def setNormalLocked(self, state: bool = ..., *, fast: bool = ...) -> None:
        """この面頂点の法線をロック、またはロック解除する。

        Args:
            state (bool): Trueはロック、Falseは解除。既定True。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。入力ヒストリの無いメッシュに限る。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: state・fastがbool以外の場合。
            RuntimeError: メッシュがロックされているか、Mayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        ...
    def getTangent(self, worldSpace: bool = ..., *, uvSet: str | None = ..., ws: bool = ...) -> Vector:
        """この面頂点のUVのU方向に沿う接線を取得する。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            uvSet (str | None): UVセット。Noneは現在のセット。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            Vector: 独立した正規化済み接線。

        Raises:
            RuntimeError: UVが未割当・縮退しているか、接線を求められない場合。
        """
        ...
    def getBinormal(self, worldSpace: bool = ..., *, uvSet: str | None = ..., ws: bool = ...) -> Vector:
        """この面頂点のUVに基づく従法線を取得する。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            uvSet (str | None): UVセット。Noneは現在のセット。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            Vector: 独立した正規化済み従法線。

        Raises:
            RuntimeError: UVが未割当・縮退しているか、従法線を求められない場合。
        """
        ...
    def getColor(self, *, colorSet: str | None = ...) -> tuple[float, float, float, float] | None:
        """この面頂点の色を取得する。

        Args:
            colorSet (str | None): カラーセット。Noneは現在のセット。

        Returns:
            tuple[float, float, float, float] | None: RGBA。色が未設定ならNone。
        """
        ...
    def setColor(self, color: Sequence[float] | om2.MColor, *, fast: bool = ..., colorSet: str | None = ...) -> None:
        """この面頂点の色を設定する。

        通常はpolyColorPerVertexでUndoに記録する。fastは入力ヒストリの無いメッシュに限る。

        Args:
            color (Sequence[float] | om2.MColor): RGBまたはRGBAの有限値。RGBのAは1。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            colorSet (str | None): 既存のカラーセット。Noneは現在のセット(無ければcolorSet1を作る)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合、または色・セットの型が不正な場合。
            ValueError: 色の成分が不正、またはセットが無い場合。
            RuntimeError: メッシュがロックされているか、Mayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        ...
    @classmethod
    def _element_count(cls, shape: Mesh) -> int:
        """頂点フェースの数(全フェースの頂点数の合計)を返す。

        Args:
            shape (Mesh): 型を確かめてあるメッシュ。

        Returns:
            int: 頂点フェースの数。
        """
        ...
    @classmethod
    def _multi_indices(cls, shape: Mesh, indices: Iterable[int], command: bool = ...) -> list[tuple[int, int]]:
        """通し番号を ``(頂点, フェース)`` へ変換する。

        Args:
            shape (Mesh): 型を確かめてあるメッシュ。
            indices (Iterable[int]): 範囲を確かめてある通し番号。
            command (bool): Trueならcmdsで使う番号にする。頂点フェースではどちらも同じ番号になる。

        Returns:
            list[tuple[int, int]]: ``(頂点, フェース)``。指定した順に並ぶ。
        """
        ...
    @classmethod
    def _flat_indices(cls, shape: Mesh, numbers: Iterable[tuple[int, int]]) -> list[int]:
        """``(頂点, フェース)`` を通し番号へ変換する。

        Args:
            shape (Mesh): 型を確かめてあるメッシュ。
            numbers (Iterable[tuple[int, int]]): 0以上の ``(頂点, フェース)``。

        Returns:
            list[int]: 通し番号。指定した順に並ぶ。

        Raises:
            IndexError: フェース番号が範囲の外にある場合、または頂点がそのフェースに無い場合。
        """
        ...


class VertexFaces(_MultiIndexComponents, Components):
    """同じメッシュにある頂点フェースの集まりを表すクラス。

    番号の指定には、通し番号と ``(頂点, フェース)`` を混ぜて使える。名前は範囲にまとめない。
    """
    def __iter__(self) -> Iterator[VertexFace]: ...
    @overload
    def __getitem__(self, index: int) -> VertexFace: ...
    @overload
    def __getitem__(self, index: slice) -> VertexFaces: ...
    component_class: Any
    def getVertex(self) -> list[Vertex]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.getVertex` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getFace(self) -> list[Face]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.getFace` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getNormal(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.getNormal` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setNormal(self, normal: Sequence[float] | Vector, worldSpace: bool = ..., *, fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.setNormal` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isNormalLocked(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.isNormalLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setNormalLocked(self, state: bool = ..., *, fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.setNormalLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTangent(self, worldSpace: bool = ..., *, uvSet: str | None = ..., ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.getTangent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getBinormal(self, worldSpace: bool = ..., *, uvSet: str | None = ..., ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.getBinormal` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getColor(self, *, colorSet: str | None = ...) -> list[tuple[float, float, float, float] | None]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.getColor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setColor(self, color: Sequence[float] | om2.MColor, *, fast: bool = ..., colorSet: str | None = ...) -> list[None]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.setColor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.components.component.Component.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
