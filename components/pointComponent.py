"""XYZ座標を持つコンポーネントと、その集まりの座標の取得・編集。"""

import math

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core import geometryEdit
from ..decorator import _edit_context, _pick_alias, _require_bool
from ..maths.vector import _vectors_of_points
from ..util import _UNSET, _finite, _world_space, mirrorArguments
from .component import Component, Components, _axis_index, _axis_numbers, _edited_row, _require_single_row


class PointComponent(Component):
    """XYZ座標を持つコンポーネント(頂点・CV・ラティスの点など)1つを表すクラス。

    Shapeと要素の番号を持ち、今のXYZ座標を取得・編集する。

    - 座標は覚えておかず、取得するたびにMayaへ問い合わせる。
    - 距離の単位はcm。既定ではShapeのオブジェクト空間で扱う。
      ワールド空間では、このShapeのオブジェクトが持つDAGパスを使う。
    - CVはAPIの制御点の位置を扱う。カーブ上のパラメータの位置を求めるものではない。
    - 書き込みは、ふだんは ``cmds.xform`` を使い、1回のUndoで戻せるようにまとめる。
      ``fast=True`` ならOpenMayaで1点を書き込み、Undoには記録しない。
    - 共有しているShapeを編集すると、すべてのインスタンスに影響する。
    """

    def getPosition(self, worldSpace=_UNSET, *, ws=_UNSET):
        """頂点またはカーブのCVの、今のXYZ座標をcmで取得する。

        Shapeと番号を確かめてから、OpenMayaへ問い合わせる。UIの距離単位には直さない。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 新しく作ったXYZの値(:class:`~mlib.maths.vector.Vector`)。この値を書き換えても、シーンの座標は変わらない。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            IndexError: 番号が、今の要素数の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが座標の取得を受け付けなかった場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        self._require_valid()
        return _vectors(self.shape, [self.index], ws)[0]

    def setPosition(self, value, worldSpace=_UNSET, *, axis=None, relative=False, fast=False, check=False, ws=_UNSET):
        """頂点/CVの位置を、cmの座標で設定する。

        既定では、移動量ではなく移動先の座標(絶対座標)を指定する。UIの距離単位にかかわらずcmで受け取る。

        - ``axis`` を指定すると、その成分だけを書き込む。ほかの成分は、指定した空間での今の値のまま変えない。
        - ``relative=True`` なら、指定した空間での今の位置にvalueを足す(``axis`` と一緒に使うと、その成分だけに足す)。
        - ふだんは ``cmds.xform`` で書き込み、1回のUndoで戻せるようにまとめる。
        - ``fast=True`` なら ``MFnMesh.setPoint`` / ``MFnNurbsCurve.setCVPosition`` で1点だけを書き込み、Undoには記録しない。
        - CVのウェイト(w)は変えない。周期カーブの末尾で重なっているCVは、先頭側の同じCVと同じ位置になる。

        たくさんの点を設定するときは、:meth:`PointComponents.setPosition` の ``each=True`` で1回にまとめる。
        1成分だけを読むときは ``getPosition().x`` のように書く。

        Args:
            value (Iterable[float] | om2.MPoint | om2.MVector | float): 有限なXYZ(cm)。MPointは、wで割らずにXYZをそのまま使う。
                ``axis`` を指定したときは、その成分の数値1つ。``relative=True`` のときは移動量。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            axis (str | None): 書き込む成分。``"x"``・``"y"``・``"z"`` (大文字でもよい)。Noneなら3成分とも書き込む。既定はNone。
            relative (bool): Trueなら、今の位置にvalueを足す。既定はFalse(絶対座標)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: worldSpace・relative・fast・checkがboolでない場合、axisが文字列でもNoneでもない場合、座標の型が合わない場合
                (axisを指定して数値1つでない場合、axisを指定せずに3成分でない場合を含む)、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 座標が有限な数値でない場合、成分が3つでない場合、axisが ``"x"``・``"y"``・``"z"`` のどれでもない場合、
                またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはロックなどでMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(relative, "relative")
        _require_bool(fast, "fast")
        _require_bool(check, "check")
        ws = _world_space(worldSpace)
        column = None if axis is None else _axis_index(axis, "xyz")
        entered = _point_value(value) if column is None else _finite(value, "value")
        self._require_valid()
        point = entered
        if column is not None or relative:
            point = _edited_row(_positions(self.shape, [self.index], ws)[0], entered, column, relative)
        _write_points([(self.shape, [self.index], [point], ws)], fast, "mlibPointComponentSetPosition", check)


class PointComponents(Components):
    """同じShapeにある、XYZ座標を持つコンポーネントの集まりを表すクラス。

    頂点/CVの番号を持ち、持っている順にXYZ座標をまとめて取得・編集する。

    - 座標は覚えておかず、getPositionで今の値を取得する。距離の単位はcm。
    - setPositionは、既定では全要素を同じ座標にする。``each=True`` で要素ごとに別の座標、``relative=True`` で今の位置からの移動、
      ``axis`` で1成分だけの書き込みになる。
    - 書き込みは、入力をすべて確かめてから行う。ふだんは ``cmds.xform`` を点ごとに呼び、
      1回のUndoで戻せるようにまとめる。Mayaが途中で書き込みを受け付けなかった場合は、先に書いた点を元に戻す。
    - ``fast=True`` なら、OpenMayaで全点を1回で書き込み、Undoには記録しない。
    - 共有しているShapeを編集すると、すべてのインスタンスに影響する。
    """

    def getPosition(self, worldSpace=_UNSET, *, ws=_UNSET):
        """頂点/CVの今のXYZ座標を、持っている順にcmで取得する。

        UIの距離単位には直さない。座標を取得するときに、Mayaがシーンを評価することがある。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[Vector]: 新しく作った座標の値(:class:`~mlib.maths.vector.Vector`)のリスト。
                値を書き換えてもシーンは変わらない。空の集まりなら、Shapeを調べ直さずに空リストを返す。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。空の集まりでも確かめる。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが座標の取得を受け付けなかった場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        if not self._indices:
            return []
        self._require_valid()
        return _vectors(self._shape, self._indices, ws)

    def setPosition(self, value, worldSpace=_UNSET, *, axis=None, relative=False, each=False, fast=False, check=False, ws=_UNSET):
        """持っている頂点/CVの位置を、cmの座標で設定する。

        既定では、**全要素を同じ位置(絶対座標)へ集める**。引数で、値の意味を次のように変える。

        - ``each=True``: valueを、持っている順に並べた要素ごとの値として使う(数は要素と同じにする)。
          :meth:`getPosition` の結果をそのまま渡せる。
        - ``relative=True``: 指定した空間での今の位置にvalueを足す。``each=False`` なら全要素を同じだけ動かす。
        - ``axis``: その成分だけを書き込む。ほかの成分は、指定した空間での今の値のまま変えない。valueは成分の数値
          (``each=True`` なら数値の並び)にする。

        ``setPosition(p)`` は全点を1か所へ集め、``setPosition(p, relative=True)`` は全点を同じだけ動かし、
        ``setPosition(points, each=True)`` は点ごとに別の位置にする。``each`` と値の形が合わないときはTypeErrorになる
        (1点を渡して ``each=True``、点の並びを渡して ``each=False`` のどちらも書き込まない)。

        値の数、有限な値か、番号が今の範囲の中にあるかを先にすべて確かめる。問題があればシーンを変えない。

        - ふだんは ``cmds.xform`` を点ごとに呼び(目安は1点あたり約0.2ms)、1回のUndoで戻せるようにまとめる。
        - ``fast=True`` なら、``MFnMesh.setPoints`` / ``MFnNurbsCurve.setCVPositions`` で全点を1回で書き込み、Undoには記録しない。
        - CVのウェイト(w)は変えない。

        Args:
            value (Iterable[float] | om2.MPoint | om2.MVector | float | Iterable): 有限なXYZ(cm)。
                ``each=True`` なら要素と同じ数のXYZの並び。``axis`` を指定したときは数値1つ(``each=True`` なら要素と同じ数の数値の並び)。
                ``relative=True`` のときは移動量。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            axis (str | None): 書き込む成分。``"x"``・``"y"``・``"z"`` (大文字でもよい)。Noneなら3成分とも書き込む。既定はNone。
            relative (bool): Trueなら、今の位置にvalueを足す。既定はFalse(絶対座標)。
            each (bool): Trueなら、valueを要素ごとの値の並びとして使う。既定はFalse(全要素に同じ値)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。空の集まりでは、入力を確かめるだけで何もしない。

        Raises:
            TypeError: worldSpace・relative・each・fast・checkがboolでない場合、axisが文字列でもNoneでもない場合、
                値の形がaxis・eachの指定と合わない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 値が有限な数値でない場合、成分が3つでない場合、each=Trueで値の数が要素の数と違う場合、
                axisが ``"x"``・``"y"``・``"z"`` のどれでもない場合、または
                worldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはロックなどでMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(relative, "relative")
        _require_bool(each, "each")
        _require_bool(fast, "fast")
        _require_bool(check, "check")
        ws = _world_space(worldSpace)
        count = len(self._indices)
        column = None if axis is None else _axis_index(axis, "xyz")
        if column is not None:
            entered = _axis_numbers(value, count, each)
        elif each:
            entered = geometryEdit.point_list(value)
            if len(entered) != count:
                raise ValueError(f"点を{count}個指定してください: {len(entered)}個")
        else:
            _require_single_row(value)
            entered = [_point_value(value)] * count
        rows = entered
        if column is not None or relative:
            if not self._indices:
                return
            self._require_valid()
            rows = [_edited_row(point, item, column, relative) for point, item in zip(_positions(self._shape, self._indices, ws), entered)]
        self._write(rows, ws, fast, "mlibPointComponentsSetPosition", check)

    def mirror(self, axis="x", worldSpace=_UNSET, *, pivot=(0.0, 0.0, 0.0), fast=False, check=False, ws=_UNSET):
        """持っている頂点/CVを、指定した空間の中心pivotで反転する。

        反転後の座標は ``2 * pivot - 今の座標`` になる。
        Transform・トポロジー・CVのウェイト(w)は変えない。複製・結合・片側からの対称化・法線の反転もしない。
        全点の座標を先に読んでから書くので、周期カーブで重なっているCVを2回反転することはない。

        Args:
            axis (str | int): 反転する軸。``"x"``・``"y"``・``"z"``、ミラー面の ``"YZ"``・``"XZ"``・``"XY"``、
                または0/1/2で指定する。軸と面は x⇔YZ、y⇔XZ、z⇔XY が同じ意味になる。
                面の文字の順と、大文字・小文字は問わない。既定は ``"x"``。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            pivot (Iterable[float]): 反転の中心のXYZ(cm)。指定した空間で表す。既定は原点。
                Transformのピボットとは関係しない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: worldSpace・fast・checkがboolでない場合、axisが文字列でもintでもない場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: axisかpivotの値が正しくない場合、またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが取得か書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        _require_bool(check, "check")
        ws = _world_space(worldSpace)
        plan = _mirror_plan(self, axis, ws, pivot, fast, check)
        _write_points([plan], fast, "mlibPointComponentsMirror", check)

    def getCenter(self, worldSpace=_UNSET, *, ws=_UNSET):
        """持っている頂点/CVの、位置の平均(重心)を取得する。

        選んだ頂点やエッジループの中心に、ジョイントやコントローラーを置くときに使う。
        バウンディングボックスの中心ではない。
        面やエッジは、``getVertices().getCenter()`` で、それを作る頂点の重心を求められる。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 平均の位置(cm)。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 空の集まりの場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが座標の取得を受け付けなかった場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        if not self._indices:
            raise ValueError("空のコンポーネントの集まりでは中心を計算できません")
        points = self.getPosition(worldSpace=ws)
        count = float(len(points))
        center = points[0]
        for point in points[1:]:
            center += point
        return center / count

    def _write(self, rows, ws, fast, chunk, check=False):
        """確かめてある座標を、番号の範囲と編集できるかを確かめてから書き込む。

        Args:
            rows (list[tuple[float, float, float]]): 持っている順の座標(cm)。
            ws (bool): Trueならワールド空間。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            chunk (str): Undoチャンク名。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

        Returns:
            None: 値を返さない。
        """
        if not self._indices:
            return
        self._require_valid()
        _write_points([(self._shape, list(self._indices), rows, ws)], fast, chunk, check)


def _point_value(value):
    """1点の座標を確かめて、XYZのfloatのtupleへ変換する。

    Args:
        value (Iterable[float] | om2.MPoint | om2.MVector): 座標。

    Returns:
        tuple[float, float, float]: 変換した座標。

    Raises:
        TypeError: 反復できない場合、または成分が数値でない場合。
        ValueError: 成分が3つでない場合、または有限でない場合。
    """
    return geometryEdit.point_list([value])[0]


def _require_invertible(shape):
    """Shapeのワールドマトリクスが、ほぼ特異でないことを確かめる。

    ワールド空間で編集するには、逆マトリクスが必要なため確かめる。
    Mayaはスケールの0をとても小さい値に置き換えるので、マトリクスの大きさも考えて判定する
    (:meth:`~mlib.nodes.shape.Shape.scaleGeometry` と同じ基準)。

    Args:
        shape (Shape): MeshまたはNurbsCurve。

    Raises:
        ValueError: ワールドマトリクスがほぼ特異な場合。
    """
    matrix = shape.mpath().inclusiveMatrix()
    magnitude = max(1.0, *(sum(abs(matrix[row * 4 + col]) for col in range(3)) for row in range(3)))
    if abs(matrix.det4x4()) <= 1e-12 * magnitude**3:
        raise ValueError(f"トランスフォームが特異に近いため、ワールド空間では点を編集できません: {shape._full_name()}")


def _mirror_plan(points, axis, ws, pivot, fast, check=False):
    """頂点/CVの集まりを反転した座標を求め、書き込みの計画を返す。

    シーンは変えない。書き込む前に、軸・中心・番号の範囲・ワールドマトリクス・fastで編集できるかをすべて確かめる。
    :meth:`Transform.mirrorGeometry <mlib.nodes.transform.Transform.mirrorGeometry>` が、
    複数のShapeをまとめて確かめてから書き込むために使う。

    Args:
        points (PointComponents): 反転する頂点/CVの集まり。
        axis (str | int): 反転する軸、またはミラー面。
        ws (bool): Trueならワールド空間。確かめてある値。
        pivot (Iterable[float]): 反転の中心のXYZ(cm)。指定した空間で表す。
        fast (bool): TrueならOpenMayaで直接書けるかも確かめる。
        check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

    Returns:
        tuple | None: ``(shape, indices, rows, ws)``。空の集まりならNone。

    Raises:
        TypeError: axisが文字列でもintでもない場合。
        ValueError: axisかpivotの値が正しくない場合、またはワールドマトリクスがほぼ特異な場合。
        IndexError: 持っている番号が、今の範囲の外にある場合。
        RuntimeError: Shapeが無効な場合、またはfastで、ロックなどのために書き込めない場合。
        NotImplementedError: fastで、Shapeに入力のヒストリがある場合。
    """
    (flip,), center = mirrorArguments(axis, pivot)
    indices = list(points.indices)
    if not indices:
        return None
    points._require_valid()
    shape = points.shape
    if ws:
        _require_invertible(shape)
    if fast:
        _require_editable(shape, indices, check)
    rows = []
    for point in _positions(shape, indices, ws):
        row = list(point)
        row[flip] = 2.0 * center[flip] - row[flip]
        rows.append(tuple(row))
    if not all(math.isfinite(value) for row in rows for value in row):
        raise ValueError("ミラーした位置が有限な数値になりません")
    return shape, indices, rows, ws


def _write_points(plans, fast, chunk, check=False):
    """確かめてある書き込みの計画を、1回のUndoで戻せるようにまとめて書き込む。

    fastの場合はUndoに記録しない。

    Args:
        plans (list[tuple | None]): ``(shape, indices, rows, ws)`` の並び。Noneと、番号が空のものは飛ばす。
        fast (bool): TrueはUndoなしのOpenMaya更新。
        chunk (str): fastでないときのUndoチャンク名。
        check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

    Raises:
        ValueError: worldSpaceで、変換マトリクスがほぼ特異な場合。書き込む前に全部の計画を確かめる。
        RuntimeError: Mayaが書き込みを受け付けなかった場合。fastでなければ、先に書いた点を元に戻す。
        NotImplementedError: fastで、Shapeに入力のヒストリがある場合。
    """
    plans = [plan for plan in plans if plan and plan[1]]
    if not plans:
        return
    for shape, indices, _, ws in plans:
        if ws:
            _require_invertible(shape)
        if check and fast:
            # 途中の形状で止まって一部だけ書き換わらないよう、書く前に全部の形状を確かめる
            # (通常の経路は、失敗すると下のundoTransactionが先に書いた点を戻す)。
            _require_editable(shape, indices, check)
    # 点ごとのcmds.xformの途中でMayaが書込みを拒否した場合に、先に書いた点を戻すためundoTransactionを使う。
    with _edit_context(chunk, fast, transaction=True):
        for shape, indices, rows, ws in plans:
            if _is_grid(shape):
                _set_grid_positions(shape, indices, rows, ws, fast, check)
                continue
            if fast and len(indices) == 1:
                # 1点は全点のMPointArrayを読み書きせず、その点だけを書く(大きなMeshで全点の書込みより速い)。
                _set_point_fast(shape, indices[0], rows[0], ws, check)
                continue
            geometryEdit.set_positions(shape, indices, rows, ws, fast=fast, check=check)


def _set_point_fast(shape, index, row, ws, check=False):
    """1点をOpenMayaで書き込む。

    CVのウェイト(w)は変えない。周期カーブで重なっているCVも同じ位置にそろえる。

    Args:
        shape (Shape): 入力のヒストリが無いMeshまたはNurbsCurve。
        index (int): 確かめてあるAPIの番号。
        row (tuple[float, float, float]): 設定するXYZ(cm)。
        ws (bool): Trueならワールド座標。マトリクスは確かめてある。
        check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

    Raises:
        RuntimeError: ロック・入力の接続・書き込みの禁止がある場合。
        NotImplementedError: Shapeに入力のヒストリがある場合。
    """
    path, fn, mesh = geometryEdit.geometry(shape, [index], edit=True, check=check)
    inverse = path.inclusiveMatrixInverse() if ws else om2.MMatrix()
    if mesh:
        fn.setPoint(index, om2.MPoint(row[0], row[1], row[2]) * inverse)
        fn.updateSurface()
        return
    independent = fn.numCVs - fn.degree if fn.form == om2.MFnNurbsCurve.kPeriodic else fn.numCVs
    index %= independent
    weight = fn.cvPosition(index).w
    # _set_positions_fastと同じく、CVのwを掛けた点を逆変換してからwを戻す。
    point = om2.MPoint(row[0], row[1], row[2], weight) * inverse
    point.w = weight
    # 周期カーブはsetCVPositionが独立CVの番号だけを受け付け、末尾の重複CVも同じ位置へ揃える。
    fn.setCVPosition(index, point)
    fn.updateCurve()


def _is_grid(shape):
    """NURBS曲面かラティス(番号を複数持つ制御点)のシェイプか調べる。

    Args:
        shape (Shape): 型を確かめてあるシェイプ。

    Returns:
        bool: MeshとNurbsCurve以外ならTrue。
    """
    node = shape.mnode()
    return not (node.hasFn(om2.MFn.kMesh) or node.hasFn(om2.MFn.kNurbsCurve))


def _grid_points(path, ws):
    """NURBS曲面のCVかラティスの点の今の位置を、通し番号の順に返す。

    Args:
        path (om2.MDagPath): NURBS曲面またはラティスのシェイプのパス。
        ws (bool): Trueならワールド空間。

    Returns:
        om2.MPointArray: 全部の制御点(cm)。曲面では ``MFnNurbsSurface.cvPositions`` と同じ並びとウェイト(w)になる。
    """
    space = om2.MSpace.kWorld if ws else om2.MSpace.kObject
    if path.node().hasFn(om2.MFn.kNurbsSurface):
        return om2.MFnNurbsSurface(path).cvPositions(space)
    return om2.MItGeometry(path).allPositions(space)


def _positions(shape, indices, ws):
    """指定した点の座標を、cmのtupleで取得する。

    Mesh・NurbsCurveは :mod:`geometryEdit` に任せる。

    Args:
        shape (Shape): 番号を確かめてあるシェイプ。
        indices (Sequence[int]): 通し番号。
        ws (bool): Trueならワールド空間。

    Returns:
        list[tuple[float, float, float]]: 指定順の座標。
    """
    if not _is_grid(shape):
        return geometryEdit.positions(shape, indices, ws)
    points = _grid_points(shape.mpath(), ws)
    return [(points[index].x, points[index].y, points[index].z) for index in indices]


def _vectors(shape, indices, ws):
    """指定した点の座標を、:class:`~mlib.maths.vector.Vector` で取得する。

    Args:
        shape (Shape): 番号を確かめてあるシェイプ。
        indices (Sequence[int]): 通し番号。
        ws (bool): Trueならワールド空間。

    Returns:
        list[Vector]: 新しく作った座標の値。指定した順に並ぶ。CVのwでは割らない。
    """
    if not _is_grid(shape):
        return geometryEdit.vectors(shape, indices, ws)
    points = _grid_points(shape.mpath(), ws)
    return _vectors_of_points([points[index] for index in indices])


def _require_editable(shape, indices, check=False):
    """fastで、OpenMayaから直接書き込めるか確かめる。

    Args:
        shape (Shape): 番号を確かめてあるシェイプ。
        indices (Sequence[int]): 書き込む点の通し番号。
        check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

    Raises:
        RuntimeError: シェイプがロックされている場合、または制御点のアトリビュートにロックか入力の接続がある場合。
        NotImplementedError: 入力のヒストリ(inMesh・create・latticeInputへの入力)がある場合。
    """
    if not _is_grid(shape):
        geometryEdit.geometry(shape, indices, edit=True, check=check)
        return
    node = shape.mnode()
    dependency = om2.MFnDependencyNode(node)
    source = "create" if node.hasFn(om2.MFn.kNurbsSurface) else "latticeInput"
    if dependency.findPlug(source, False).isDestination:
        raise NotImplementedError("fastのジオメトリ編集には、入力ヒストリのないシェイプが必要です")
    if dependency.isLocked:
        raise RuntimeError("シェイプノードがロックされています")
    if check:
        geometryEdit._require_control_points_writable(shape)


def _set_grid_positions(shape, indices, rows, ws, fast, check=False):
    """NURBS曲面のCVやラティスの点へ、確かめてあるcmの座標を書き込む。

    Undoのまとめ方は、呼び出し元が決める。

    - ふだんは点ごとに ``cmds.xform`` (オブジェクト空間)で書き込む。
    - fastなら ``MFnNurbsSurface.setCVPositions`` / ``MItGeometry.setAllPositions`` で全点を1回で書き込む。
    - 曲面のCVのウェイト(w)は変えない。周期曲面で重なっているCVは、
      対応するCVと同じ位置にそろえる(cmdsのCV名で書いた場合と同じ結果)。

    Args:
        shape (Shape): NURBS曲面またはラティスのシェイプ。番号は確かめてある。
        indices (Sequence[int]): 通し番号。同じ番号があれば、後の値を使う。
        rows (Sequence[Sequence[float]]): 番号と同じ数の、有限なXYZ(cm)。
        ws (bool): Trueならワールド座標。マトリクスは確かめてある。
        fast (bool): TrueはUndoなしのOpenMaya更新。
        check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

    Raises:
        RuntimeError: Mayaが書き込みを受け付けなかった場合。
        NotImplementedError: fastで、シェイプに入力のヒストリがある場合。
    """
    # 単数型はこのモジュールを継承するため、循環を避けて使う時点で読み込む。
    from .latticePoint import LatticePoint
    from .surfaceCV import SurfaceCV

    path = shape.mpath()
    surface = path.node().hasFn(om2.MFn.kNurbsSurface)
    component_class = SurfaceCV if surface else LatticePoint
    current = _grid_points(path, False)
    inverse = path.inclusiveMatrixInverse() if ws else om2.MMatrix()
    local = {}
    for index, row in zip(indices, rows):
        # 曲面のcvPositions(kWorld)はCVのwもマトリクスの積に使うため、同じwで逆変換してローカルのXYZにする。
        weight = current[index].w
        point = om2.MPoint(row[0], row[1], row[2], weight) * inverse
        point.w = weight
        local[index] = point
    if fast:
        _require_editable(shape, list(local), check)
        if surface:
            keys = component_class._multi_indices(shape, range(len(current)), command=True)
            targets = {keys[index]: point for index, point in local.items()}
            for index, key in enumerate(keys):
                if key in targets:
                    current[index] = targets[key]
            fn = om2.MFnNurbsSurface(path)
            fn.setCVPositions(current)
            fn.updateSurface()
            return
        for index, point in local.items():
            current[index] = point
        om2.MItGeometry(path).setAllPositions(current)
        return
    if check:
        geometryEdit._require_control_points_writable(shape)
    else:
        # cmds.xformはロックした点へ書かずに警告だけを出すので、ロックはcheckに関係なく書く前に確かめる。
        geometryEdit.require_control_points_unlocked(shape, local)
    prefix = f"{shape._full_name()}.{component_class.component_type}"
    numbers = component_class._multi_indices(shape, list(local), command=True)
    unit = om2.MDistance.uiUnit()
    for point, number in zip(local.values(), numbers):
        coordinates = [om2.MDistance(value).asUnits(unit) for value in (point.x, point.y, point.z)]
        name = prefix + "".join(f"[{value}]" for value in number)
        cmds.xform(name, absolute=True, translation=coordinates, objectSpace=True)
