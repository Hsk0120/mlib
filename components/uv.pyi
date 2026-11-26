# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""メッシュの、現在のUVセットのUVを扱うクラス。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.fastWrite import require_writable
from ..decorator import _edit_context, _require_bool
from ..util import _finite, _finite_vector
from .component import Component, Components, _axis_index, _axis_numbers, _edited_row, _require_single_row
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
    def setPosition(self, value: Iterable[float] | float, *, axis: str | None = ..., relative: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """現在のUVセットで、このUVの位置をU/Vの座標で設定する。

        既定では移動量ではなく、移動先の絶対座標を指定する。``relative=True`` なら、今の位置にvalueを足す
        (:meth:`PointComponent.setPosition <mlib.components.pointComponent.PointComponent.setPosition>` と同じ)。
        ``axis`` を指定すると、その成分だけを書き込む(もう一方は今の値のまま変えない)。
        1成分だけを読むときは ``getPosition()[0]`` (U)・``getPosition()[1]`` (V)のように書く。

        - ふだんは ``cmds.polyEditUV(relative=False)`` で書き込み、1回のUndoで戻せるようにまとめる。
        - ``fast=True`` なら ``MFnMesh.setUV`` で書き込み、Undoには記録しない(1点で約5倍速い)。

        Args:
            value (Iterable[float] | float): 有限なU/Vの2つの値。単位は無く、0〜1の範囲に限らない。
                ``axis`` を指定したときは、その成分の数値1つ。
            axis (str | None): 書き込む成分。``"u"``・``"v"`` (大文字でもよい)。Noneなら両方を書き込む。既定はNone。
            relative (bool): Trueなら、今の位置にvalueを足す。既定はFalse(絶対座標)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。UVセットや割り当ては作らない。

        Raises:
            TypeError: relative・fast・checkがboolでない場合、axisが文字列でもNoneでもない場合、または座標の型が合わない場合
                (axisを指定して数値1つでない場合、axisを指定せずに2成分でない場合を含む)。
            ValueError: 座標が有限な数値でない場合、成分が2つでない場合、またはaxisが ``"u"``・``"v"`` のどちらでもない場合。
            IndexError: 番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、check=TrueでUVのアトリビュートがロック・入力の接続などで
                書き込めない場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力(コンストラクションヒストリ)がある場合。
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
_UV_GET_POSITION: Any


class UVs(Components):
    """同じメッシュにあるUVの集まりを表すクラス。

    UVの番号を持ち、現在のUVセットの座標を、持っている順にまとめて取得・編集する。

    - UVセットの名前や座標は覚えておかない。UVセットを切り替えた後は、切り替え先のセットの同じ番号を使う。
    - setPositionは、既定では全要素を同じU/Vにする。``each=True`` で要素ごとに別のU/V、``axis`` で1成分だけの書き込みになる。
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
    def setPosition(self, value: Iterable[float] | float | Iterable, *, axis: str | None = ..., relative: bool = ..., each: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """持っているUVの位置を、現在のUVセットのU/Vの座標で設定する。

        既定では、**全要素を同じ位置へ集める**。引数で、値の意味を次のように変える。

        - ``relative=True``: 今の位置にvalueを足す。``each=False`` なら全要素を同じだけ動かす。

        - ``each=True``: valueを、持っている順に並べた要素ごとの値として使う(数は要素と同じにする)。
          :meth:`getPosition` の結果をそのまま渡せる。
        - ``axis``: その成分だけを書き込む。もう一方は今の値のまま変えない。valueは成分の数値
          (``each=True`` なら数値の並び)にする。

        ``each`` と値の形が合わないときはTypeErrorになる(1つの(U, V)を渡して ``each=True``、
        (U, V)の並びを渡して ``each=False`` のどちらも書き込まない)。
        値の数、有限な値か、番号が今の範囲の中にあるかを先にすべて確かめる。問題があればシーンを変えない。

        - ふだんは ``cmds.polyEditUV`` をUVごとに呼び(目安は1UVあたり約1ms)、1回のUndoで戻せるようにまとめる。
        - ``fast=True`` なら ``MFnMesh.setUVs`` で全UVを1回で書き込み、Undoには記録しない。

        Args:
            value (Iterable[float] | float | Iterable): 有限な(U, V)。単位は無い。
                ``each=True`` なら要素と同じ数の(U, V)の並び。``axis`` を指定したときは数値1つ(``each=True`` なら要素と同じ数の数値の並び)。
            axis (str | None): 書き込む成分。``"u"``・``"v"`` (大文字でもよい)。Noneなら両方を書き込む。既定はNone。
            relative (bool): Trueなら、今の位置にvalueを足す。既定はFalse(絶対座標)。
            each (bool): Trueなら、valueを要素ごとの値の並びとして使う。既定はFalse(全要素に同じ値)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。空の集まりでは、入力を確かめるだけで何もしない。UVセットや割り当ては作らない。

        Raises:
            TypeError: relative・each・fast・checkがboolでない場合、axisが文字列でもNoneでもない場合、または値の形がaxis・eachの指定と合わない場合。
            ValueError: 値が有限な数値でない場合、成分が2つでない場合、each=Trueで値の数が要素の数と違う場合、
                またはaxisが ``"u"``・``"v"`` のどちらでもない場合。
            IndexError: 持っている番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、check=TrueでUVのアトリビュートがロック・入力の接続などで
                書き込めない場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力がある場合。
        """
        ...
    def _write(self, rows: list[tuple[float, float]], fast: bool, chunk: str, check: bool = ...) -> None:
        """確かめてあるU/Vを、番号の範囲を確かめてから書き込む。

        Args:
            rows (list[tuple[float, float]]): 持っている順のU/V。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            chunk (str): Undoチャンク名。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

        Returns:
            None: 値を返さない。
        """
        ...
    def getVertex(self) -> list[Vertex | None]:
        """各要素の :meth:`~mlib.components.uv.UV.getVertex` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
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

def _write_uvs(shape: Mesh, indices: list[int], rows: list[tuple[float, float]], fast: bool, chunk: str, check: bool = ...):
    """確かめてあるU/Vを、現在のUVセットへ書き込む。

    Args:
        shape (Mesh): 書き込むMesh。番号は確かめてある。
        indices (list[int]): UVの番号。
        rows (list[tuple[float, float]]): 番号と同じ数のU/V。
        fast (bool): TrueはUndoなしのOpenMaya更新。
        chunk (str): fastでないときのUndoチャンク名。
        check (bool): Trueなら、書き込む前に、UVのアトリビュートへ書き込めるかを確かめる。

    Raises:
        RuntimeError: Meshがロックされている場合、check=TrueでUVのアトリビュートへ書き込めない場合、
            またはMayaが書き込みを受け付けなかった場合。
        NotImplementedError: fastで、inMeshへの入力がある場合。
    """
    ...

def _require_uvs_writable(dependency: om2.MFnDependencyNode, uv_set: str, indices: Iterable[int]):
    """現在のUVセットの、指定したUVのアトリビュート(uvSetPoints)とその子へ書き込めるかを確かめる。シーンは変えない。

    すでにある要素だけを調べ、要素を作らない。

    Args:
        dependency (om2.MFnDependencyNode): Meshのfunction set。
        uv_set (str): 現在のUVセットの名前。
        indices (Iterable[int]): 範囲を確かめてあるUVの番号。

    Raises:
        RuntimeError: ロック・入力接続・書き込み禁止がある場合。
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
