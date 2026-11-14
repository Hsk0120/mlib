"""メッシュの、現在のUVセットのUVを扱うクラス。"""

import numbers

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import _edit_context, _require_bool
from ..util import _finite, _finite_vector
from .component import Component, Components


class UV(Component):
    """メッシュのUV1つを表すクラス。

    MeshとUVの番号を持ち、現在のUVセットのU/V座標を取得・編集する。

    - UVセットの名前は覚えておかない。UVセットを切り替えた後は、切り替え先のセットの同じ番号を指す。
    - U/Vには単位が無く、0〜1の範囲に限らない。
    - 書き込みは、ふだんは ``cmds.polyEditUV`` を使い、1回のUndoで戻せるようにまとめる。
      ``fast=True`` なら ``MFnMesh.setUV`` / ``setUVs`` で書き込み、Undoには記録しない。
    """

    shape_type = "mesh"
    component_type = "map"
    count_attribute = "getNumUVs"

    def getPosition(self):
        """現在のUVセットから、このUVのU/V座標を取得する。

        Returns:
            tuple[float, float]: 新しく作った(U, V)の値。単位は無く、UIの距離単位やオブジェクト/ワールド空間とは関係しない。

        Raises:
            IndexError: 持っている番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshまたは現在のUVセットを使えない場合。
        """
        self._require_valid()
        mesh_fn = self.shape._geometry_fn()
        return tuple(mesh_fn.getUV(self._index, uvSet=mesh_fn.currentUVSetName()))

    def setPosition(self, value, *, fast=False):
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
        _require_bool(fast, "fast")
        row = _uv_value(value)
        self._require_valid()
        _write_uvs(self.shape, [self._index], [row], fast, "setPosition", "mlibUVSetPosition")
        return self

    def getU(self):
        """U成分の今の値を取得する。

        Returns:
            float: 座標の値。
        """
        return self._get_coordinate(0)

    def setU(self, value, *, fast=False):
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
        return self._set_coordinate(0, value, fast, "setU", "mlibUVSetU")

    def getV(self):
        """V成分の今の値を取得する。

        Returns:
            float: 座標の値。
        """
        return self._get_coordinate(1)

    def setV(self, value, *, fast=False):
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
        return self._set_coordinate(1, value, fast, "setV", "mlibUVSetV")

    def getVertex(self):
        """このUVが割り当てられた頂点を取得する。

        現在のUVセットで調べる。

        Returns:
            Vertex | None: 頂点。どのフェースにも割り当てられていないUVはNone。

        Raises:
            IndexError: 番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshまたは現在のUVセットを使えない場合。
        """
        # vertex.py が uv.py を import するため、循環を避けて呼出し時に読む。
        from .vertex import Vertex

        self._require_valid()
        mesh_fn = self.shape._geometry_fn()
        uv_counts, uv_ids = mesh_fn.getAssignedUVs(mesh_fn.currentUVSetName())
        counts, vertices = mesh_fn.getVertices()
        uv_offset = vertex_offset = 0
        for uv_count, count in zip(uv_counts, counts):
            # UVの無いフェースは uv_count が0で、uv_ids に項目を持たない。
            for local in range(uv_count):
                if uv_ids[uv_offset + local] == self._index:
                    return Vertex(self.shape, vertices[vertex_offset + local])
            uv_offset += uv_count
            vertex_offset += count
        return None

    def _set_coordinate(self, axis, value, fast, method, chunk):
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
        _require_bool(fast, "fast")
        number = _finite(value, "value")
        row = list(self.getPosition())
        row[axis] = number
        _write_uvs(self.shape, [self._index], [tuple(row)], fast, method, chunk)
        return self


_UV_GET_POSITION = UV.getPosition


class UVs(Components):
    """同じメッシュにあるUVの集まりを表すクラス。

    UVの番号を持ち、現在のUVセットの座標を、持っている順にまとめて取得・編集する。

    - UVセットの名前や座標は覚えておかない。UVセットを切り替えた後は、切り替え先のセットの同じ番号を使う。
    - setPositionは全要素を同じU/Vに、setPositionsは要素ごとに別のU/Vにする。
    - 書き込みは、入力をすべて確かめてから行う。ふだんは ``cmds.polyEditUV`` をUVごとに呼び、
      1回のUndoで戻せるようにまとめる。Mayaが途中で書き込みを受け付けなかった場合は、先に書いたUVを元に戻す。
    - ``fast=True`` なら ``MFnMesh.setUVs`` で全UVを1回で書き込み、Undoには記録しない。
    """

    component_class = UV

    def getU(self):
        """U成分の今の値を取得する。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。
        """
        return self._get_coordinate(0)

    def setU(self, value, *, fast=False):
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
        return self._set_coordinates(0, value, fast, "setU", "mlibUVsSetU")

    def getV(self):
        """V成分の今の値を取得する。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。
        """
        return self._get_coordinate(1)

    def setV(self, value, *, fast=False):
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
        return self._set_coordinates(1, value, fast, "setV", "mlibUVsSetV")

    def getPosition(self):
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
        if not (self._uses_standard_iteration(UV) and UV.getPosition is _UV_GET_POSITION):
            return [item.getPosition() for item in self]
        if not self._indices:
            return []
        Component._require_shape(self._shape, UV.shape_type)
        mesh_fn = self._shape._geometry_fn()
        count = mesh_fn.numUVs()
        uv_set = mesh_fn.currentUVSetName()
        result = []
        for index in self._indices:
            Component._require_index_range(index, count)
            result.append(tuple(mesh_fn.getUV(index, uvSet=uv_set)))
        return result

    def setPosition(self, value, *, fast=False):
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
        _require_bool(fast, "fast")
        row = _uv_value(value)
        return self._write([row] * len(self._indices), fast, "setPosition", "mlibUVsSetPosition")

    def setPositions(self, values, *, fast=False):
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
        _require_bool(fast, "fast")
        if isinstance(values, (str, bytes)):
            raise TypeError("valuesは(u, v)の組の並びで指定してください")
        try:
            items = list(values)
        except TypeError:
            raise TypeError("valuesは(u, v)の組の並びで指定してください") from None
        rows = [_uv_value(item) for item in items]
        if len(rows) != len(self._indices):
            raise ValueError(f"UVを{len(self._indices)}個指定してください: {len(rows)}個")
        return self._write(rows, fast, "setPositions", "mlibUVsSetPositions")

    def _set_coordinates(self, axis, value, fast, method, chunk):
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
        _require_bool(fast, "fast")
        values = _axis_values(value, len(self._indices))
        if not self._indices:
            return self
        rows = []
        for row, number in zip(self.getPosition(), values):
            row = list(row)
            row[axis] = number
            rows.append(tuple(row))
        return self._write(rows, fast, method, chunk)

    def _write(self, rows, fast, method, chunk):
        """確かめてあるU/Vを、番号の範囲を確かめてから書き込む。

        Args:
            rows (list[tuple[float, float]]): 持っている順のU/V。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            method (str): 例外のメッセージに使う、公開メソッドの名前。
            chunk (str): Undoチャンク名。

        Returns:
            UVs: 自身。
        """
        if not self._indices:
            return self
        self._require_valid()
        _write_uvs(self._shape, list(self._indices), rows, fast, method, chunk)
        return self


def _uv_value(value):
    """1つのU/Vを確かめて、floatのtupleへ変換する。

    Args:
        value (Iterable[float]): U/Vの2つの値。

    Returns:
        tuple[float, float]: 変換したU/V。

    Raises:
        TypeError: 反復できない場合、文字列の場合、または成分が数値でない場合。
        ValueError: 成分が2つでない場合、または有限でない場合。
    """
    if isinstance(value, (str, bytes)):
        raise TypeError("uvは2つの数値の並びで指定してください")
    return _finite_vector(value, 2, "uv")


def _axis_values(value, count):
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
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        return [_finite(value, "value")] * count
    if isinstance(value, (str, bytes)):
        raise TypeError("valueは数値か数値の並びで指定してください")
    try:
        items = list(value)
    except TypeError:
        raise TypeError("valueは数値か数値の並びで指定してください") from None
    if len(items) != count:
        raise ValueError(f"値を{count}個指定してください: {len(items)}個")
    return [_finite(item, "value") for item in items]


def _write_uvs(shape, indices, rows, fast, method, chunk):
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
    path = shape.mpath()
    dependency = om2.MFnDependencyNode(path.node())
    if dependency.isLocked:
        raise RuntimeError(f"メッシュがロックされています: {shape.getFullName()}")
    if fast and dependency.findPlug("inMesh", False).isDestination:
        # 入力履歴のあるMeshはinMeshの再評価でUVが上書きされるため、直接は書かない。
        raise NotImplementedError(f"fastの{method}は入力ヒストリのあるメッシュに対応していません: {shape.getFullName()}")
    mesh_fn = om2.MFnMesh(path)
    uv_set = mesh_fn.currentUVSetName()
    # polyEditUVの途中でMayaが書込みを拒否した場合に、先に書いたUVを戻すためundoTransactionを使う。
    with _edit_context(chunk, fast, transaction=True):
        if fast:
            _write_uvs_fast(mesh_fn, uv_set, indices, rows)
            return
        name = shape.getFullName()
        for index, (u, v) in zip(indices, rows):
            cmds.polyEditUV(f"{name}.map[{index}]", relative=False, uValue=u, vValue=v, uvSetName=uv_set)


def _write_uvs_fast(mesh_fn, uv_set, indices, rows):
    """U/VをOpenMayaで書き込む。

    1点なら ``setUV`` で書き、複数なら全UVを ``setUVs`` で1回で書く。

    Args:
        mesh_fn (om2.MFnMesh): 書き込むMeshのfunction set。
        uv_set (str): 書き込むUVセットの名前。
        indices (list[int]): UVの番号。同じ番号があれば、後の値を使う。
        rows (list[tuple[float, float]]): 番号と同じ数のU/V。
    """
    if len(indices) == 1:
        mesh_fn.setUV(indices[0], rows[0][0], rows[0][1], uv_set)
        return
    us, vs = mesh_fn.getUVs(uv_set)
    for index, (u, v) in zip(indices, rows):
        us[index] = u
        vs[index] = v
    mesh_fn.setUVs(us, vs, uv_set)
