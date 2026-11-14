# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""メッシュの、現在のUVセットのUVを扱うクラス。"""

import numbers
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import _edit_context, _require_bool
from ..util import _finite, _finite_vector
from .component import Component, Components
from typing import Any, Iterable, Iterator
from mlib.components.vertex import Vertex
from mlib.nodes.mesh import Mesh
from typing import overload



class UV(Component):
    """メッシュのUV1つを表すクラス。

    MeshとUVの番号を持ち、現在のUVセットのU/V座標を取得・編集する。

    - UVセットの名前は覚えておかない。UVセットを切り替えた後は、切り替え先のセットの同じ番号を指す。
    - U/Vには単位が無く、0〜1の範囲に限らない。
    - 書き込みは、ふだんは ``cmds.polyEditUV`` を使い、1回のUndoで戻せるようにまとめる。
      ``fast=True`` なら ``MFnMesh.setUV`` / ``setUVs`` で書き込み、Undoには記録しない。
    """
    shape_type: str
    component_type: str
    count_attribute: str
    def getPosition(self) -> tuple[float, float]:
        """現在のUVセットから、このUVのU/V座標を取得する。

        Returns:
            tuple[float, float]: 新しく作った(U, V)の値。単位は無く、UIの距離単位やオブジェクト/ワールド空間とは関係しない。

        Raises:
            IndexError: 持っている番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshまたは現在のUVセットを使えない場合。
        """
        ...
    def setPosition(self, value: Iterable[float], *, fast: bool = ...) -> UV:
        """現在のUVセットで、このUVの位置をU/Vの絶対座標で設定する。

        移動量ではなく、移動先の座標を指定する。

        - ふだんは ``cmds.polyEditUV(relative=False)`` で書き込み、1回のUndoで戻せるようにまとめる。
        - ``fast=True`` なら ``MFnMesh.setUV`` で書き込み、Undoには記録しない(1点で約5倍速い)。

        Args:
            value (Iterable[float]): 有限なU/Vの2つの値。単位は無く、0〜1の範囲に限らない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            UV: 自身。UVセットや割り当ては作らない。

        Raises:
            TypeError: fastがboolでない場合、または座標の型が合わない場合。
            ValueError: 座標が2つの有限な数値でない場合。
            IndexError: 番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力(コンストラクションヒストリ)がある場合。
        """
        ...
    def getU(self) -> float:
        """U成分の今の値を取得する。

        Returns:
            float: 座標の値。
        """
        ...
    def setU(self, value: float, *, fast: bool = ...) -> UV:
        """U成分だけを設定する。Vは今の値のまま変えない。

        Args:
            value (float): 有限なU。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            UV: 自身。

        Raises:
            TypeError: fastがboolでない場合、またはvalueが数値でない場合。
            ValueError: valueが有限でない場合。
            IndexError: 番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力がある場合。
        """
        ...
    def getV(self) -> float:
        """V成分の今の値を取得する。

        Returns:
            float: 座標の値。
        """
        ...
    def setV(self, value: float, *, fast: bool = ...) -> UV:
        """V成分だけを設定する。Uは今の値のまま変えない。

        Args:
            value (float): 有限なV。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            UV: 自身。

        Raises:
            TypeError: fastがboolでない場合、またはvalueが数値でない場合。
            ValueError: valueが有限でない場合。
            IndexError: 番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力がある場合。
        """
        ...
    def getVertex(self) -> Vertex | None:
        """このUVが割り当てられた頂点を取得する。

        現在のUVセットで調べる。

        Returns:
            Vertex | None: 頂点。どのフェースにも割り当てられていないUVはNone。

        Raises:
            IndexError: 番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshまたは現在のUVセットを使えない場合。
        """
        ...
    def _set_coordinate(self, axis: int, value: float, fast: bool, method: str, chunk: str) -> UV:
        """1つの成分だけを変えたU/Vを書き込む。

        Args:
            axis (int): 成分の番号(0=U、1=V)。
            value (float): 設定する値。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            method (str): 例外のメッセージに使う、公開メソッドの名前。
            chunk (str): Undoチャンク名。

        Returns:
            UV: 自身。
        """
        ...
_UV_GET_POSITION: Any


class UVs(Components):
    """同じメッシュにあるUVの集まりを表すクラス。

    UVの番号を持ち、現在のUVセットの座標を、持っている順にまとめて取得・編集する。

    - UVセットの名前や座標は覚えておかない。UVセットを切り替えた後は、切り替え先のセットの同じ番号を使う。
    - setPositionは全要素を同じU/Vに、setPositionsは要素ごとに別のU/Vにする。
    - 書き込みは、入力をすべて確かめてから行う。ふだんは ``cmds.polyEditUV`` をUVごとに呼び、
      1回のUndoで戻せるようにまとめる。Mayaが途中で書き込みを受け付けなかった場合は、先に書いたUVを元に戻す。
    - ``fast=True`` なら ``MFnMesh.setUVs`` で全UVを1回で書き込み、Undoには記録しない。
    """
    def __iter__(self) -> Iterator[UV]: ...
    @overload
    def __getitem__(self, index: int) -> UV: ...
    @overload
    def __getitem__(self, index: slice) -> UVs: ...
    component_class: Any
    def getU(self) -> list[float]:
        """U成分の今の値を取得する。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。
        """
        ...
    def setU(self, value: float | Iterable[float], *, fast: bool = ...) -> UVs:
        """U成分だけを設定する。Vは今の値のまま変えない。

        Args:
            value (float | Iterable[float]): 全要素に同じ値を使うなら数値、
                要素ごとに変えるなら、持っている順に並べた値を指定する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            UVs: 自身。

        Raises:
            TypeError: fastがboolでない場合、または値の型が合わない場合。
            ValueError: 値が有限でない場合、または値の並びの数が要素の数と違う場合。
            IndexError: 持っている番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力がある場合。
        """
        ...
    def getV(self) -> list[float]:
        """V成分の今の値を取得する。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。
        """
        ...
    def setV(self, value: float | Iterable[float], *, fast: bool = ...) -> UVs:
        """V成分だけを設定する。Uは今の値のまま変えない。

        Args:
            value (float | Iterable[float]): 全要素に同じ値を使うなら数値、
                要素ごとに変えるなら、持っている順に並べた値を指定する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            UVs: 自身。

        Raises:
            TypeError: fastがboolでない場合、または値の型が合わない場合。
            ValueError: 値が有限でない場合、または値の並びの数が要素の数と違う場合。
            IndexError: 持っている番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力がある場合。
        """
        ...
    def getPosition(self) -> list[tuple[float, float]]:
        """現在のUVセットのU/V座標を、持っている順に取得する。

        ふだんは、同じMFnMeshと現在のUVセットの名前を使って、各番号を問い合わせる。
        UVのクラスや反復が拡張されている場合は、各要素のgetPositionに任せる。

        Returns:
            list[tuple[float, float]]: 新しく作ったU/Vの値のリスト。単位は無い。値を書き換えても座標は変わらない。
                ふだんの処理では、空の集まりならShapeを調べ直さずに空リストを返す。

        Raises:
            IndexError: 持っている番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshまたは現在のUVセットを使えない場合。
        """
        ...
    def setPosition(self, value: Iterable[float], *, fast: bool = ...) -> UVs:
        """持っているUVをすべて、現在のUVセットで同じ位置(U/Vの絶対座標)へ集める。

        要素ごとに違う座標にするときは :meth:`setPositions` を使う。

        Args:
            value (Iterable[float]): 全要素に使う、有限なU/V。単位は無い。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            UVs: 自身。空の集まりでは、入力を確かめるだけで何もしない。

        Raises:
            TypeError: fastがboolでない場合、または座標の型が合わない場合。
            ValueError: 座標が2つの有限な数値でない場合。
            IndexError: 持っている番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力がある場合。
        """
        ...
    def setPositions(self, values: Iterable[Iterable[float]], *, fast: bool = ...) -> UVs:
        """現在のUVセットで、要素ごとの位置を(U, V)の絶対座標で設定する。

        座標の数、有限な値か、番号が今の範囲の中にあるかを先にすべて確かめる。問題があればシーンを変えない。

        - ふだんは ``cmds.polyEditUV`` をUVごとに呼ぶ(目安は1UVあたり約1ms)。
        - ``fast=True`` なら ``MFnMesh.setUVs`` で全UVを1回で書き込む。

        Args:
            values (Iterable[Iterable[float]]): 要素と同じ数の、有限な(U, V)。単位は無い。
                :meth:`getPosition` の結果をそのまま渡せる。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            UVs: 自身。空の集まりに空の並びを渡した場合は、Shapeを調べ直さずに何もしない。

        Raises:
            TypeError: fastがboolでない場合、または座標の型が合わない場合。
            ValueError: 座標の数が要素の数と違う場合、または座標が2つの有限な数値でない場合。
            IndexError: 持っている番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力がある場合。

        Note:
            UVセットや割り当ては作らない。
        """
        ...
    def _set_coordinates(self, axis: int, value: float | Iterable[float], fast: bool, method: str, chunk: str) -> UVs:
        """各要素の1つの成分だけを変えたU/Vを書き込む。

        Args:
            axis (int): 成分の番号(0=U、1=V)。
            value (float | Iterable[float]): 全要素に同じ値、または持っている順に並べた値。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            method (str): 例外のメッセージに使う、公開メソッドの名前。
            chunk (str): Undoチャンク名。

        Returns:
            UVs: 自身。
        """
        ...
    def _write(self, rows: list[tuple[float, float]], fast: bool, method: str, chunk: str) -> UVs:
        """確かめてあるU/Vを、番号の範囲を確かめてから書き込む。

        Args:
            rows (list[tuple[float, float]]): 持っている順のU/V。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            method (str): 例外のメッセージに使う、公開メソッドの名前。
            chunk (str): Undoチャンク名。

        Returns:
            UVs: 自身。
        """
        ...
    def getVertex(self) -> list[Vertex | None]:
        """各要素の :meth:`~mlib.components.uv.UV.getVertex` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.components.component.Component.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...

def _uv_value(value: Iterable[float]) -> tuple[float, float]:
    """1つのU/Vを確かめて、floatのtupleへ変換する。

    Args:
        value (Iterable[float]): U/Vの2つの値。

    Returns:
        tuple[float, float]: 変換したU/V。

    Raises:
        TypeError: 反復できない場合、文字列の場合、または成分が数値でない場合。
        ValueError: 成分が2つでない場合、または有限でない場合。
    """
    ...

def _axis_values(value: float | Iterable[float], count: int) -> list[float]:
    """1つの成分の値を確かめて、要素の数だけの値のリストにする。

    Args:
        value (float | Iterable[float]): 全要素に同じ値、またはcount個の値の並び。
        count (int): 持っている要素の数。

    Returns:
        list[float]: count個の有限な値。

    Raises:
        TypeError: 数値でも数値の並びでもない場合(文字列も含む)。
        ValueError: 有限でない場合、または値の並びの数がcountと違う場合。
    """
    ...

def _write_uvs(shape: Mesh, indices: list[int], rows: list[tuple[float, float]], fast: bool, method: str, chunk: str):
    """確かめてあるU/Vを、現在のUVセットへ書き込む。

    Args:
        shape (Mesh): 書き込むMesh。番号は確かめてある。
        indices (list[int]): UVの番号。
        rows (list[tuple[float, float]]): 番号と同じ数のU/V。
        fast (bool): TrueはUndoなしのOpenMaya更新。
        method (str): 例外の文言に使う公開メソッド名。
        chunk (str): fastでないときのUndoチャンク名。

    Raises:
        RuntimeError: Meshがロックされている場合、またはMayaが書き込みを受け付けなかった場合。
        NotImplementedError: fastで、inMeshへの入力がある場合。
    """
    ...

def _write_uvs_fast(mesh_fn: om2.MFnMesh, uv_set: str, indices: list[int], rows: list[tuple[float, float]]):
    """U/VをOpenMayaで書き込む。

    1点なら ``setUV`` で書き、複数なら全UVを ``setUVs`` で1回で書く。

    Args:
        mesh_fn (om2.MFnMesh): 書き込むMeshのfunction set。
        uv_set (str): 書き込むUVセットの名前。
        indices (list[int]): UVの番号。同じ番号があれば、後の値を使う。
        rows (list[tuple[float, float]]): 番号と同じ数のU/V。
    """
    ...
