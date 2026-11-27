# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""メッシュの頂点フェース(フェースごとの頂点)と、頂点フェースの集まり。"""

import bisect
import maya.api.OpenMaya as om2
from ..decorator import _pick_alias, _require_bool
from ..maths.vector import Vector
from ..util import _UNSET, _world_space
from .component import Component, Components
from .face import Face
from .vertex import Vertex
from typing import Any, Iterable, Iterator, Literal, Sequence
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


class VertexFace(Component):
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
    @overload
    def getNormal(self, worldSpace: bool = ..., *, lockedOnly: Literal[True], ws: bool = ...) -> bool: ...
    @overload
    def getNormal(self, worldSpace: bool = ..., *, lockedOnly: Literal[False] = ..., ws: bool = ...) -> Vector: ...
    @overload
    def getNormal(self, worldSpace: bool = ..., *, lockedOnly: bool = ..., ws: bool = ...) -> Vector | bool:
        """頂点フェースの法線を、長さ1で取得する。``lockedOnly=True`` なら、法線がロックされているかを調べる。

        法線は ``MFnMesh.getFaceVertexNormal`` で求める。ハードエッジやロックした法線を反映した、表示に使う法線になる
        (``polyNormalPerVertex`` で取得した値と同じ)。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。``lockedOnly=True`` とは同時に指定できない。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            lockedOnly (bool): Trueなら、法線の値ではなく、法線がロックされているかを返す。既定はFalse。

        Returns:
            Vector | bool: 長さ1の法線。``lockedOnly=True`` なら、法線がロックされていればTrue。

        Raises:
            TypeError: worldSpaceかlockedOnlyがboolでない場合、worldSpaceとwsを同時に指定した場合、
                または ``lockedOnly=True`` とworldSpace(ws)を同時に指定した場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def setNormal(self, normal: Sequence[float] | Vector | None = ..., worldSpace: bool = ..., *, locked: bool | None = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> None:
        """この面頂点の法線を設定してロックする。または、法線のロックだけを切り替える。

        - ``normal`` を渡すと、法線を設定してロックする(``locked`` はNoneかTrue)。
        - ``normal`` を省いて ``locked=True`` / ``locked=False`` を渡すと、法線の値は書かずに、ロックだけを掛ける/外す。
          外した後は、Mayaが形状とエッジの硬軟から法線を計算し直す。
        - ``normal`` と ``locked=False`` は同時に指定できない(外すとMayaが法線を計算し直し、設定した値が消えるため)。

        通常はpolyNormalPerVertexでUndoに記録する。fastは入力ヒストリの無いメッシュに限る。

        Args:
            normal (Sequence[float] | Vector | None): 長さが0でないXYZ。正規化して設定する。Noneなら値は書かない。既定はNone。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。``normal`` を渡したときだけ指定できる。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            locked (bool | None): Trueはロック、Falseは解除。Noneは ``normal`` を渡したときのロック(Trueと同じ)。既定はNone。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、有限な数値か。``normal`` を渡したときだけ指定できる。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fast・check・locked・空間指定・法線の型が不正な場合、normalとlockedをどちらも指定しない場合、
                normalとlocked=Falseを同時に指定した場合、またはnormalを渡さずにworldSpace(ws)・checkを指定した場合。
            ValueError: 法線の成分の数が3でない・成分が不正・長さ0の場合、またはワールド変換が特異な場合。
            RuntimeError: メッシュがロックされているか、Mayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        ...
    def getTangent(self, worldSpace: bool = ..., *, binormal: bool = ..., uvSet: str | None = ..., ws: bool = ...) -> Vector:
        """この面頂点の、UVのU方向に沿う接線を取得する。``binormal=True`` なら、UVに基づく従法線を取得する。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            binormal (bool): Trueなら、接線でなく従法線を返す。既定はFalse。
            uvSet (str | None): UVセット。Noneは現在のセット。既定はNone。

        Returns:
            Vector: 独立した正規化済みの接線(``binormal=True`` なら従法線)。

        Raises:
            TypeError: binormalがboolでない場合、空間指定・uvSetの型が不正な場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 指定した名前のUVセットが無い場合。
            RuntimeError: UVが未割当・縮退しているか、接線(従法線)を求められない場合。
        """
        ...
    def getColor(self, *, colorSet: str | None = ...) -> tuple[float, float, float, float] | None:
        """この面頂点の色を取得する。

        Args:
            colorSet (str | None): カラーセット。Noneは現在のセット。既定はNone。

        Returns:
            tuple[float, float, float, float] | None: RGBA。色が未設定ならNone。

        Raises:
            TypeError: colorSetが文字列でもNoneでもない場合。
            ValueError: 指定した名前のカラーセットが無い場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def setColor(self, color: Sequence[float] | om2.MColor, *, colorSet: str | None = ..., fast: bool = ..., check: bool = ...) -> None:
        """この面頂点の色を設定する。

        通常はpolyColorPerVertexでUndoに記録する。fastは入力ヒストリの無いメッシュに限る。

        Args:
            color (Sequence[float] | om2.MColor): RGBまたはRGBAの有限値。RGBのAは1。
            colorSet (str | None): 既存のカラーセット。Noneは現在のセット(無ければcolorSet1を作る)。既定はNone。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合、または色・セットの型が不正な場合。
            ValueError: 色の成分が不正、またはセットが無い場合。
            RuntimeError: メッシュがロックされているか、Mayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        ...
    def removeColor(self, *, colorSet: str | None = ..., fast: bool = ...) -> None:
        """この面頂点のカラー割り当てを解除する。

        カラーセットは残し、getColorでNoneになる状態へ戻す。
        ヒストリの制限はMesh.removeFaceVertexColorsと同じ。通常はUndoに記録する。

        Args:
            colorSet (str | None): 既存のカラーセット。Noneは現在のセット。既定はNone。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合、またはcolorSetの型が不正な場合。
            ValueError: 指定したカラーセットが無い場合。
            RuntimeError: メッシュが編集不可か、通常経路で未対応のヒストリがある場合。
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


class VertexFaces(Components):
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
    def getNormal(self, worldSpace: bool = ..., *, lockedOnly: bool = ..., ws: bool = ...) -> list[Vector | bool]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.getNormal` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setNormal(self, normal: Sequence[float] | Vector | None = ..., worldSpace: bool = ..., *, locked: bool | None = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.setNormal` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTangent(self, worldSpace: bool = ..., *, binormal: bool = ..., uvSet: str | None = ..., ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.getTangent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getColor(self, *, colorSet: str | None = ...) -> list[tuple[float, float, float, float] | None]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.getColor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setColor(self, color: Sequence[float] | om2.MColor, *, colorSet: str | None = ..., fast: bool = ..., check: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.setColor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def removeColor(self, *, colorSet: str | None = ..., fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.components.vertexFace.VertexFace.removeColor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getName(self, *, full: bool = ..., removeNamespace: bool = ...) -> list[str]:
        """各要素の :meth:`~mlib.components.component.Component.getName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getMultiIndex(self) -> list[tuple[int, ...]]:
        """各要素の :meth:`~mlib.components.component.Component.getMultiIndex` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
