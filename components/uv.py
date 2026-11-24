"""メッシュの、現在のUVセットのUVを扱うクラス。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import _edit_context, _require_bool
from ..util import _finite, _finite_vector
from .component import Component, Components, _axis_index, _axis_numbers, _edited_row, _require_single_row


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

    def setPosition(self, value, *, axis=None, fast=False):
        """現在のUVセットで、このUVの位置をU/Vの絶対座標で設定する。

        移動量ではなく、移動先の座標を指定する。
        ``axis`` を指定すると、その成分だけを書き込む(もう一方は今の値のまま変えない)。
        1成分だけを読むときは ``getPosition()[0]`` (U)・``getPosition()[1]`` (V)のように書く。

        - ふだんは ``cmds.polyEditUV(relative=False)`` で書き込み、1回のUndoで戻せるようにまとめる。
        - ``fast=True`` なら ``MFnMesh.setUV`` で書き込み、Undoには記録しない(1点で約5倍速い)。

        Args:
            value (Iterable[float] | float): 有限なU/Vの2つの値。単位は無く、0〜1の範囲に限らない。
                ``axis`` を指定したときは、その成分の数値1つ。
            axis (str | None): 書き込む成分。``"u"``・``"v"`` (大文字でもよい)。Noneなら両方を書き込む。既定はNone。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。UVセットや割り当ては作らない。

        Raises:
            TypeError: fastがboolでない場合、axisが文字列でもNoneでもない場合、または座標の型が合わない場合
                (axisを指定して数値1つでない場合、axisを指定せずに2成分でない場合を含む)。
            ValueError: 座標が有限な数値でない場合、成分が2つでない場合、またはaxisが ``"u"``・``"v"`` のどちらでもない場合。
            IndexError: 番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力(コンストラクションヒストリ)がある場合。
        """
        _require_bool(fast, "fast")
        column = None if axis is None else _axis_index(axis, "uv")
        row = _uv_value(value) if column is None else _finite(value, "value")
        if column is not None:
            row = _edited_row(self.getPosition(), row, column, False)
        self._require_valid()
        _write_uvs(self.shape, [self._index], [row], fast, "mlibUVSetPosition")

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


_UV_GET_POSITION = UV.getPosition


class UVs(Components):
    """同じメッシュにあるUVの集まりを表すクラス。

    UVの番号を持ち、現在のUVセットの座標を、持っている順にまとめて取得・編集する。

    - UVセットの名前や座標は覚えておかない。UVセットを切り替えた後は、切り替え先のセットの同じ番号を使う。
    - setPositionは、既定では全要素を同じU/Vにする。``each=True`` で要素ごとに別のU/V、``axis`` で1成分だけの書き込みになる。
    - 書き込みは、入力をすべて確かめてから行う。ふだんは ``cmds.polyEditUV`` をUVごとに呼び、
      1回のUndoで戻せるようにまとめる。Mayaが途中で書き込みを受け付けなかった場合は、先に書いたUVを元に戻す。
    - ``fast=True`` なら ``MFnMesh.setUVs`` で全UVを1回で書き込み、Undoには記録しない。
    """

    component_class = UV

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

    def setPosition(self, value, *, axis=None, each=False, fast=False):
        """持っているUVの位置を、現在のUVセットのU/Vの絶対座標で設定する。

        既定では、**全要素を同じ位置へ集める**。引数で、値の意味を次のように変える。

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
            each (bool): Trueなら、valueを要素ごとの値の並びとして使う。既定はFalse(全要素に同じ値)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。空の集まりでは、入力を確かめるだけで何もしない。UVセットや割り当ては作らない。

        Raises:
            TypeError: eachかfastがboolでない場合、axisが文字列でもNoneでもない場合、または値の形がaxis・eachの指定と合わない場合。
            ValueError: 値が有限な数値でない場合、成分が2つでない場合、each=Trueで値の数が要素の数と違う場合、
                またはaxisが ``"u"``・``"v"`` のどちらでもない場合。
            IndexError: 持っている番号が、現在のUVセットの範囲の外にある場合。
            RuntimeError: Meshが無効かロックされている場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、inMeshへの入力がある場合。
        """
        _require_bool(each, "each")
        _require_bool(fast, "fast")
        count = len(self._indices)
        column = None if axis is None else _axis_index(axis, "uv")
        if column is not None:
            numbers = _axis_numbers(value, count, each)
            if not self._indices:
                return
            rows = [_edited_row(current, number, column, False) for current, number in zip(self.getPosition(), numbers)]
        elif each:
            if isinstance(value, (str, bytes)):
                raise TypeError("each=Trueのvalueは(u, v)の組の並びで指定してください")
            try:
                items = list(value)
            except TypeError:
                raise TypeError("each=Trueのvalueは(u, v)の組の並びで指定してください") from None
            rows = [_uv_value(item) for item in items]
            if len(rows) != count:
                raise ValueError(f"UVを{count}個指定してください: {len(rows)}個")
        else:
            _require_single_row(value)
            rows = [_uv_value(value)] * count
        self._write(rows, fast, "mlibUVsSetPosition")

    def _write(self, rows, fast, chunk):
        """確かめてあるU/Vを、番号の範囲を確かめてから書き込む。

        Args:
            rows (list[tuple[float, float]]): 持っている順のU/V。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            chunk (str): Undoチャンク名。

        Returns:
            None: 値を返さない。
        """
        if not self._indices:
            return
        self._require_valid()
        _write_uvs(self._shape, list(self._indices), rows, fast, chunk)


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


def _write_uvs(shape, indices, rows, fast, chunk):
    """確かめてあるU/Vを、現在のUVセットへ書き込む。

    Args:
        shape (Mesh): 書き込むMesh。番号は確かめてある。
        indices (list[int]): UVの番号。
        rows (list[tuple[float, float]]): 番号と同じ数のU/V。
        fast (bool): TrueはUndoなしのOpenMaya更新。
        chunk (str): fastでないときのUndoチャンク名。

    Raises:
        RuntimeError: Meshがロックされている場合、またはMayaが書き込みを受け付けなかった場合。
        NotImplementedError: fastで、inMeshへの入力がある場合。
    """
    path = shape.mpath()
    dependency = om2.MFnDependencyNode(path.node())
    if dependency.isLocked:
        raise RuntimeError(f"メッシュがロックされています: {shape._full_name()}")
    if fast and dependency.findPlug("inMesh", False).isDestination:
        # 入力履歴のあるMeshはinMeshの再評価でUVが上書きされるため、直接は書かない。
        raise NotImplementedError(f"fastのsetPositionは入力ヒストリのあるメッシュに対応していません: {shape._full_name()}")
    mesh_fn = om2.MFnMesh(path)
    uv_set = mesh_fn.currentUVSetName()
    # polyEditUVの途中でMayaが書込みを拒否した場合に、先に書いたUVを戻すためundoTransactionを使う。
    with _edit_context(chunk, fast, transaction=True):
        if fast:
            _write_uvs_fast(mesh_fn, uv_set, indices, rows)
            return
        name = shape._full_name()
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
