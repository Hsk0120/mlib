# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
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
from typing import Iterable, Iterator, Sequence
from mlib.maths.vector import Vector
from mlib.nodes.shape import Shape
from typing import overload



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
    def getPosition(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def setPosition(self, value: Iterable[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponent:
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
        ...
    def getPositionX(self, worldSpace: bool = ..., *, ws: bool = ...) -> float:
        """X成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 座標の値。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def setPositionX(self, value: float, worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponent:
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
        ...
    def getPositionY(self, worldSpace: bool = ..., *, ws: bool = ...) -> float:
        """Y成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 座標の値。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def setPositionY(self, value: float, worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponent:
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
        ...
    def getPositionZ(self, worldSpace: bool = ..., *, ws: bool = ...) -> float:
        """Z成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 座標の値。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def setPositionZ(self, value: float, worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponent:
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
        ...
    def moveBy(self, offset: Iterable[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponent:
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
        ...
    def _set_coordinate(self, axis: int, value: float, worldSpace: bool, fast: bool, chunk: str) -> PointComponent:
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
        ...


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
    def __iter__(self) -> Iterator[PointComponent]: ...
    @overload
    def __getitem__(self, index: int) -> PointComponent: ...
    @overload
    def __getitem__(self, index: slice) -> PointComponents: ...
    def getPositionX(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[float]:
        """X成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def setPositionX(self, value: float | Iterable[float], worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponents:
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
        ...
    def getPositionY(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[float]:
        """Y成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def setPositionY(self, value: float | Iterable[float], worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponents:
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
        ...
    def getPositionZ(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[float]:
        """Z成分の今の値を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[float]: 座標の値。持っている順に並ぶ。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def setPositionZ(self, value: float | Iterable[float], worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponents:
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
        ...
    def getPosition(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
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
        ...
    def setPosition(self, value: Iterable[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponents:
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
        ...
    def setPositions(self, values: Iterable[Iterable[float] | om2.MPoint | om2.MVector], worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponents:
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
        ...
    def mirror(self, axis: str | int = ..., worldSpace: bool = ..., pivot: Iterable[float] = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponents:
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
        ...
    def getCenter(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def moveBy(self, offset: Iterable[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> PointComponents:
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
        ...
    def _set_coordinates(self, axis: int, value: float | Iterable[float], worldSpace: bool, fast: bool, chunk: str) -> PointComponents:
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
        ...
    def _write(self, rows: list[tuple[float, float, float]], ws: bool, fast: bool, chunk: str) -> PointComponents:
        """確かめてある座標を、番号の範囲と編集できるかを確かめてから書き込む。

        Args:
            rows (list[tuple[float, float, float]]): 持っている順の座標(cm)。
            ws (bool): Trueならワールド空間。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            chunk (str): Undoチャンク名。

        Returns:
            PointComponents: 自身。
        """
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.components.component.Component.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...

def _point_value(value: Iterable[float] | om2.MPoint | om2.MVector) -> tuple[float, float, float]:
    """1点の座標を確かめて、XYZのfloatのtupleへ変換する。

    Args:
        value (Iterable[float] | om2.MPoint | om2.MVector): 座標。

    Returns:
        tuple[float, float, float]: 変換した座標。

    Raises:
        TypeError: 反復できない場合、または成分が数値でない場合。
        ValueError: 成分が3つでない場合、または有限でない場合。
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

def _require_invertible(shape: Shape):
    """Shapeのワールドマトリクスが、ほぼ特異でないことを確かめる。

    ワールド空間で編集するには、逆マトリクスが必要なため確かめる。
    Mayaはスケールの0をとても小さい値に置き換えるので、マトリクスの大きさも考えて判定する
    (:meth:`~mlib.nodes.shape.Shape.scaleGeometry` と同じ基準)。

    Args:
        shape (Shape): MeshまたはNurbsCurve。

    Raises:
        ValueError: ワールドマトリクスがほぼ特異な場合。
    """
    ...

def _mirror_plan(points: PointComponents, axis: str | int, ws: bool, pivot: Iterable[float], fast: bool) -> tuple | None:
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
    ...

def _write_points(plans: list[tuple | None], fast: bool, chunk: str):
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
    ...

def _set_point_fast(shape: Shape, index: int, row: tuple[float, float, float], ws: bool):
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
    ...

def _is_grid(shape: Shape) -> bool:
    """NURBS曲面かラティス(番号を複数持つ制御点)のシェイプか調べる。

    Args:
        shape (Shape): 型を確かめてあるシェイプ。

    Returns:
        bool: MeshとNurbsCurve以外ならTrue。
    """
    ...

def _grid_points(path: om2.MDagPath, ws: bool) -> om2.MPointArray:
    """NURBS曲面のCVかラティスの点の今の位置を、通し番号の順に返す。

    Args:
        path (om2.MDagPath): NURBS曲面またはラティスのシェイプのパス。
        ws (bool): Trueならワールド空間。

    Returns:
        om2.MPointArray: 全部の制御点(cm)。曲面では ``MFnNurbsSurface.cvPositions`` と同じ並びとウェイト(w)になる。
    """
    ...

def _positions(shape: Shape, indices: Sequence[int], ws: bool) -> list[tuple[float, float, float]]:
    """指定した点の座標を、cmのtupleで取得する。

    Mesh・NurbsCurveは :mod:`geometryEdit` に任せる。

    Args:
        shape (Shape): 番号を確かめてあるシェイプ。
        indices (Sequence[int]): 通し番号。
        ws (bool): Trueならワールド空間。

    Returns:
        list[tuple[float, float, float]]: 指定順の座標。
    """
    ...

def _vectors(shape: Shape, indices: Sequence[int], ws: bool) -> list[Vector]:
    """指定した点の座標を、:class:`~mlib.maths.vector.Vector` で取得する。

    Args:
        shape (Shape): 番号を確かめてあるシェイプ。
        indices (Sequence[int]): 通し番号。
        ws (bool): Trueならワールド空間。

    Returns:
        list[Vector]: 新しく作った座標の値。指定した順に並ぶ。CVのwでは割らない。
    """
    ...

def _require_editable(shape: Shape, indices: Sequence[int]):
    """fastで、OpenMayaから直接書き込めるか確かめる。

    Args:
        shape (Shape): 番号を確かめてあるシェイプ。
        indices (Sequence[int]): 書き込む点の通し番号。

    Raises:
        RuntimeError: シェイプがロックされている場合、または制御点のアトリビュートにロックか入力の接続がある場合。
        NotImplementedError: 入力のヒストリ(inMesh・create・latticeInputへの入力)がある場合。
    """
    ...

def _set_grid_positions(shape: Shape, indices: Sequence[int], rows: Sequence[Sequence[float]], ws: bool, fast: bool):
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
    ...
