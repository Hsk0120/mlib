"""XYZ座標を持つコンポーネントと、その集まりの座標の取得・編集。"""

import math
import numbers

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core import geometryEdit as geometry_edit
from ..core.fastWrite import require_writable
from ..decorator import _edit_context, _pick_alias, _require_bool
from ..maths.vector import _vectors_of_points
from ..util import _UNSET, _finite, _world_space, mirrorArguments
from .component import Component, Components


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

    def setPosition(self, value, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """頂点/CVの位置を、cmの絶対座標で設定する。

        移動量ではなく、移動先の座標を指定する。UIの距離単位にかかわらずcmで受け取る。

        - ふだんは ``cmds.xform`` で書き込み、1回のUndoで戻せるようにまとめる。
        - ``fast=True`` なら ``MFnMesh.setPoint`` / ``MFnNurbsCurve.setCVPosition`` で1点だけを書き込み、Undoには記録しない。
        - CVのウェイト(w)は変えない。周期カーブの末尾で重なっているCVは、先頭側の同じCVと同じ位置になる。

        たくさんの点を設定するときは、:meth:`PointComponents.setPositions` で1回にまとめる。

        Args:
            value (Iterable[float] | om2.MPoint | om2.MVector): 有限なXYZ(cm)。MPointは、wで割らずにXYZをそのまま使う。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponent: 自身。

        Raises:
            TypeError: worldSpaceがboolでない場合、座標の型が合わない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 座標が3つの有限な数値でない場合、またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはロックなどでMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        point = _point_value(value)
        self._require_valid()
        _write_points([(self.shape, [self.index], [point], ws)], fast, "mlibPointComponentSetPosition")
        return self

    def getPositionX(self, worldSpace=_UNSET, *, ws=_UNSET):
        """X成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 座標の値。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._get_coordinate(0, worldSpace=_world_space(worldSpace))

    def setPositionX(self, value, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """X成分だけを設定する。

        ほかの成分は、指定した空間での今の値のまま変えない。

        Args:
            value (float): 有限な座標(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponent: 自身。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、valueが数値でない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: valueが有限でない場合、またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._set_coordinate(0, value, worldSpace, fast, "mlibPointComponentSetPositionX")

    def getPositionY(self, worldSpace=_UNSET, *, ws=_UNSET):
        """Y成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 座標の値。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._get_coordinate(1, worldSpace=_world_space(worldSpace))

    def setPositionY(self, value, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """Y成分だけを設定する。

        ほかの成分は、指定した空間での今の値のまま変えない。

        Args:
            value (float): 有限な座標(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponent: 自身。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、valueが数値でない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: valueが有限でない場合、またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._set_coordinate(1, value, worldSpace, fast, "mlibPointComponentSetPositionY")

    def getPositionZ(self, worldSpace=_UNSET, *, ws=_UNSET):
        """Z成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 座標の値。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._get_coordinate(2, worldSpace=_world_space(worldSpace))

    def setPositionZ(self, value, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """Z成分だけを設定する。

        ほかの成分は、指定した空間での今の値のまま変えない。

        Args:
            value (float): 有限な座標(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponent: 自身。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、valueが数値でない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: valueが有限でない場合、またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._set_coordinate(2, value, worldSpace, fast, "mlibPointComponentSetPositionZ")

    def moveBy(self, offset, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """頂点/CVを、今の位置からoffsetだけ動かす。

        指定した空間で今の位置を読み、offsetを足した座標を :meth:`setPosition` と同じ方法で書き込む。

        Args:
            offset (Iterable[float] | om2.MPoint | om2.MVector): 移動量の有限なXYZ(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponent: 自身。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、移動量の型が合わない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 移動量が3つの有限な数値でない場合、またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはロックなどでMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        delta = _point_value(offset)
        self._require_valid()
        point = _positions(self.shape, [self.index], ws)[0]
        moved = tuple(value + step for value, step in zip(point, delta))
        _write_points([(self.shape, [self.index], [moved], ws)], fast, "mlibPointComponentMoveBy")
        return self

    def _set_coordinate(self, axis, value, worldSpace, fast, chunk):
        """1つの成分だけを変えた座標を、同じ空間で書き込む。

        Args:
            axis (int): 成分の番号(0=X、1=Y、2=Z)。
            value (float): 設定する座標(cm)。
            worldSpace (bool): Trueならワールド空間。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            chunk (str): Undoチャンク名。

        Returns:
            PointComponent: 自身。
        """
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        number = _finite(value, "value")
        self._require_valid()
        point = list(_positions(self.shape, [self.index], ws)[0])
        point[axis] = number
        _write_points([(self.shape, [self.index], [tuple(point)], ws)], fast, chunk)
        return self


class PointComponents(Components):
    """同じShapeにある、XYZ座標を持つコンポーネントの集まりを表すクラス。

    頂点/CVの番号を持ち、持っている順にXYZ座標をまとめて取得・編集する。

    - 座標は覚えておかず、getPositionで今の値を取得する。距離の単位はcm。
    - setPositionは全要素を同じ座標に、setPositionsは要素ごとに別の座標にする。
    - 書き込みは、入力をすべて確かめてから行う。ふだんは ``cmds.xform`` を点ごとに呼び、
      1回のUndoで戻せるようにまとめる。Mayaが途中で書き込みを受け付けなかった場合は、先に書いた点を元に戻す。
    - ``fast=True`` なら、OpenMayaで全点を1回で書き込み、Undoには記録しない。
    - 共有しているShapeを編集すると、すべてのインスタンスに影響する。
    """

    def getPositionX(self, worldSpace=_UNSET, *, ws=_UNSET):
        """X成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._get_coordinate(0, worldSpace=_world_space(worldSpace))

    def setPositionX(self, value, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """X成分だけを設定する。

        ほかの成分は、指定した空間での今の値のまま変えない。

        Args:
            value (float | Iterable[float]): 値(cm)。全要素に同じ値を使うなら数値、
                要素ごとに変えるなら、持っている順に並べた値を指定する。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponents: 自身。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、値の型が合わない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 値が有限でない場合、値の並びの数が要素の数と違う場合、または
                worldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._set_coordinates(0, value, worldSpace, fast, "mlibPointComponentsSetPositionX")

    def getPositionY(self, worldSpace=_UNSET, *, ws=_UNSET):
        """Y成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._get_coordinate(1, worldSpace=_world_space(worldSpace))

    def setPositionY(self, value, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """Y成分だけを設定する。

        ほかの成分は、指定した空間での今の値のまま変えない。

        Args:
            value (float | Iterable[float]): 値(cm)。全要素に同じ値を使うなら数値、
                要素ごとに変えるなら、持っている順に並べた値を指定する。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponents: 自身。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、値の型が合わない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 値が有限でない場合、値の並びの数が要素の数と違う場合、または
                worldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._set_coordinates(1, value, worldSpace, fast, "mlibPointComponentsSetPositionY")

    def getPositionZ(self, worldSpace=_UNSET, *, ws=_UNSET):
        """Z成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._get_coordinate(2, worldSpace=_world_space(worldSpace))

    def setPositionZ(self, value, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """Z成分だけを設定する。

        ほかの成分は、指定した空間での今の値のまま変えない。

        Args:
            value (float | Iterable[float]): 値(cm)。全要素に同じ値を使うなら数値、
                要素ごとに変えるなら、持っている順に並べた値を指定する。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponents: 自身。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、値の型が合わない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 値が有限でない場合、値の並びの数が要素の数と違う場合、または
                worldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._set_coordinates(2, value, worldSpace, fast, "mlibPointComponentsSetPositionZ")

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

    def setPosition(self, value, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """持っている頂点/CVをすべて、同じ位置(cmの絶対座標)へ集める。

        移動量を足すのではなく、移動先の座標を指定する。要素ごとに違う座標にするときは :meth:`setPositions` を使う。

        Args:
            value (Iterable[float] | om2.MPoint | om2.MVector): 全要素に使う、有限なXYZ(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponents: 自身。空の集まりでは、入力を確かめるだけで何もしない。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、座標の型が合わない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 座標が3つの有限な数値でない場合、またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        point = _point_value(value)
        return self._write([point] * len(self._indices), ws, fast, "mlibPointComponentsSetPosition")

    def setPositions(self, values, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """持っている順に、要素ごとの位置をcmの絶対座標で設定する。

        座標の数、有限な値か、番号が今の範囲の中にあるかを先にすべて確かめる。問題があればシーンを変えない。

        - ふだんは ``cmds.xform`` を点ごとに呼ぶ(目安は1点あたり約0.2ms)。
        - ``fast=True`` なら、``MFnMesh.setPoints`` / ``MFnNurbsCurve.setCVPositions`` で全点を1回で書き込む。

        Args:
            values (Iterable[Iterable[float] | om2.MPoint | om2.MVector]): 要素と同じ数のXYZ(cm)。
                :meth:`getPosition` の結果をそのまま渡せる。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponents: 自身。空の集まりに空の並びを渡した場合は、Shapeを調べ直さずに何もしない。
                CVのウェイト(w)は変えない。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、座標の型が合わない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 座標の数が要素の数と違う場合、座標が3つの有限な数値でない場合、または
                worldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはロックなどでMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        rows = geometry_edit.point_list(values)
        if len(rows) != len(self._indices):
            raise ValueError(f"点を{len(self._indices)}個指定してください: {len(rows)}個")
        return self._write(rows, ws, fast, "mlibPointComponentsSetPositions")

    def mirror(self, axis="x", worldSpace=_UNSET, pivot=(0.0, 0.0, 0.0), *, fast=False, ws=_UNSET):
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

        Returns:
            PointComponents: 自身。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、axisが文字列でもintでもない場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: axisかpivotの値が正しくない場合、またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはMayaが取得か書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        plan = _mirror_plan(self, axis, ws, pivot, fast)
        _write_points([plan], fast, "mlibPointComponentsMirror")
        return self

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

    def moveBy(self, offset, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
        """持っている頂点/CVをすべて、今の位置から同じoffsetだけ動かす。

        指定した空間で今の位置を読み、offsetを足した座標を :meth:`setPositions` と同じ方法で1回で書き込む。
        ふだんは1回のUndoで戻せる。

        Args:
            offset (Iterable[float] | om2.MPoint | om2.MVector): 移動量の有限なXYZ(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            PointComponents: 自身。空の集まりでは、入力を確かめるだけで何もしない。

        Raises:
            TypeError: worldSpaceかfastがboolでない場合、移動量の型が合わない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 移動量が3つの有限な数値でない場合、またはworldSpace=Trueで、変換マトリクスがほぼ特異な(スケールがほぼ0などで、逆マトリクスを求められない)場合。
            IndexError: 持っている番号が、今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、またはロックなどでMayaが書き込みを受け付けなかった場合。
            NotImplementedError: fast=Trueで、Shapeに入力のヒストリがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        delta = _point_value(offset)
        if not self._indices:
            return self
        self._require_valid()
        rows = [tuple(value + step for value, step in zip(point, delta)) for point in _positions(self._shape, self._indices, ws)]
        return self._write(rows, ws, fast, "mlibPointComponentsMoveBy")

    def _set_coordinates(self, axis, value, worldSpace, fast, chunk):
        """各要素の1つの成分だけを変えた座標を、同じ空間で書き込む。

        Args:
            axis (int): 成分の番号(0=X、1=Y、2=Z)。
            value (float | Iterable[float]): 全要素に同じ値、または持っている順に並べた値。
            worldSpace (bool): Trueならワールド空間。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            chunk (str): Undoチャンク名。

        Returns:
            PointComponents: 自身。
        """
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        values = _axis_values(value, len(self._indices))
        if not self._indices:
            return self
        self._require_valid()
        rows = []
        for point, number in zip(_positions(self._shape, self._indices, ws), values):
            row = list(point)
            row[axis] = number
            rows.append(tuple(row))
        return self._write(rows, ws, fast, chunk)

    def _write(self, rows, ws, fast, chunk):
        """確かめてある座標を、番号の範囲と編集できるかを確かめてから書き込む。

        Args:
            rows (list[tuple[float, float, float]]): 持っている順の座標(cm)。
            ws (bool): Trueならワールド空間。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            chunk (str): Undoチャンク名。

        Returns:
            PointComponents: 自身。
        """
        if not self._indices:
            return self
        self._require_valid()
        _write_points([(self._shape, list(self._indices), rows, ws)], fast, chunk)
        return self


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
    return geometry_edit.point_list([value])[0]


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
        raise ValueError(f"トランスフォームが特異に近いため、ワールド空間では点を編集できません: {shape.getFullName()}")


def _mirror_plan(points, axis, ws, pivot, fast):
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
        _require_editable(shape, indices)
    rows = []
    for point in _positions(shape, indices, ws):
        row = list(point)
        row[flip] = 2.0 * center[flip] - row[flip]
        rows.append(tuple(row))
    if not all(math.isfinite(value) for row in rows for value in row):
        raise ValueError("ミラーした位置が有限な数値になりません")
    return shape, indices, rows, ws


def _write_points(plans, fast, chunk):
    """確かめてある書き込みの計画を、1回のUndoで戻せるようにまとめて書き込む。

    fastの場合はUndoに記録しない。

    Args:
        plans (list[tuple | None]): ``(shape, indices, rows, ws)`` の並び。Noneと、番号が空のものは飛ばす。
        fast (bool): TrueはUndoなしのOpenMaya更新。
        chunk (str): fastでないときのUndoチャンク名。

    Raises:
        ValueError: worldSpaceで、変換マトリクスがほぼ特異な場合。書き込む前に全部の計画を確かめる。
        RuntimeError: Mayaが書き込みを受け付けなかった場合。fastでなければ、先に書いた点を元に戻す。
        NotImplementedError: fastで、Shapeに入力のヒストリがある場合。
    """
    plans = [plan for plan in plans if plan and plan[1]]
    if not plans:
        return
    for shape, _, _, ws in plans:
        if ws:
            _require_invertible(shape)
    # 点ごとのcmds.xformの途中でMayaが書込みを拒否した場合に、先に書いた点を戻すためundoTransactionを使う。
    with _edit_context(chunk, fast, transaction=True):
        for shape, indices, rows, ws in plans:
            if _is_grid(shape):
                _set_grid_positions(shape, indices, rows, ws, fast)
                continue
            if fast and len(indices) == 1:
                # 1点は全点のMPointArrayを読み書きせず、その点だけを書く(大きなMeshで全点の書込みより速い)。
                _set_point_fast(shape, indices[0], rows[0], ws)
                continue
            geometry_edit.set_positions(shape, indices, rows, ws, fast=fast)


def _set_point_fast(shape, index, row, ws):
    """1点をOpenMayaで書き込む。

    CVのウェイト(w)は変えない。周期カーブで重なっているCVも同じ位置にそろえる。

    Args:
        shape (Shape): 入力のヒストリが無いMeshまたはNurbsCurve。
        index (int): 確かめてあるAPIの番号。
        row (tuple[float, float, float]): 設定するXYZ(cm)。
        ws (bool): Trueならワールド座標。マトリクスは確かめてある。

    Raises:
        RuntimeError: ロック・入力の接続・書き込みの禁止がある場合。
        NotImplementedError: Shapeに入力のヒストリがある場合。
    """
    path, fn, mesh = geometry_edit.geometry(shape, [index], edit=True)
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
        return geometry_edit.positions(shape, indices, ws)
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
        return geometry_edit.vectors(shape, indices, ws)
    points = _grid_points(shape.mpath(), ws)
    return _vectors_of_points([points[index] for index in indices])


def _require_editable(shape, indices):
    """fastで、OpenMayaから直接書き込めるか確かめる。

    Args:
        shape (Shape): 番号を確かめてあるシェイプ。
        indices (Sequence[int]): 書き込む点の通し番号。

    Raises:
        RuntimeError: シェイプがロックされている場合、または制御点のアトリビュートにロックか入力の接続がある場合。
        NotImplementedError: 入力のヒストリ(inMesh・create・latticeInputへの入力)がある場合。
    """
    if not _is_grid(shape):
        geometry_edit.geometry(shape, indices, edit=True)
        return
    node = shape.mnode()
    dependency = om2.MFnDependencyNode(node)
    source = "create" if node.hasFn(om2.MFn.kNurbsSurface) else "latticeInput"
    if dependency.findPlug(source, False).isDestination:
        raise NotImplementedError("fastのジオメトリ編集には、入力ヒストリのないシェイプが必要です")
    if dependency.isLocked:
        raise RuntimeError("シェイプノードがロックされています")
    points = dependency.findPlug("controlPoints", False)
    for index in points.getExistingArrayAttributeIndices():
        point = points.elementByLogicalIndex(index)
        require_writable(point)
        for child in range(point.numChildren()):
            require_writable(point.child(child))


def _set_grid_positions(shape, indices, rows, ws, fast):
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
        _require_editable(shape, list(local))
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
    prefix = f"{shape.getFullName()}.{component_class.component_type}"
    numbers = component_class._multi_indices(shape, list(local), command=True)
    unit = om2.MDistance.uiUnit()
    for point, number in zip(local.values(), numbers):
        coordinates = [om2.MDistance(value).asUnits(unit) for value in (point.x, point.y, point.z)]
        name = prefix + "".join(f"[{value}]" for value in number)
        cmds.xform(name, absolute=True, translation=coordinates, objectSpace=True)
