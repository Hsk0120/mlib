# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の aimConstraint を扱う。"""

import math
from ..core.nodeEdit import require_editable
from ..decorator import _edit_context
from ..maths import EulerRotate
from ..util import _angle_unit, _to_radians
from .constraint import Constraint
from typing import Sequence
from mlib.plugs.plug import Plug



class AimConstraint(Constraint):
    """オブジェクトをターゲットの方向へ向ける、aimConstraintのクラス。"""
    def getRotateConnections(self) -> list[tuple[Plug, Plug]]:
        """回転の出力から直接つながっている接続を取得する。

        直接の接続だけを返す。その先をたどったり、接続先の種類で絞ったりはしない。

        Returns:
            list[tuple[Plug, Plug]]: 接続元と接続先の組。コンパウンドアトリビュートごと接続している場合は、親どうしの組だけを返す。
        """
        ...
    def getRestRotate(self, *, unit: str = ...) -> tuple[float, float, float]:
        """Rest RotateのXYZの設定値を取得する。

        Args:
            unit (str): 戻り値の角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
                ``"degree"`` などの別名も使える。

        Returns:
            tuple[float, float, float]: 評価した設定値。コンストレイントされる側の回転ではない。

        Raises:
            TypeError: unitが文字列・None以外の場合。
            ValueError: unitが未対応の単位名の場合。
        """
        ...
    def setRestRotate(self, value: Sequence[float], *, unit: str = ..., fast: bool = ...) -> AimConstraint:
        """Rest Rotateだけを設定する。

        追従の状態や、コンストレイントされる側の回転は直接変えない。

        Args:
            value (Sequence[float]): XYZの3つの値。どれも有限な数値にする。
            unit (str): valueの角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            AimConstraint: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: 値またはunitが不正な場合。
            RuntimeError: ノードがリファレンスされているかロックされている場合、またはアトリビュートがロックされているか入力が接続されている場合。
        """
        ...
    def getOffset(self, *, unit: str = ...) -> tuple[float, float, float]:
        """OffsetのXYZの設定値を取得する。

        Args:
            unit (str): 戻り値の角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
                ``"degree"`` などの別名も使える。

        Returns:
            tuple[float, float, float]: 評価したOffsetの値。

        Raises:
            TypeError: unitが文字列・None以外の場合。
            ValueError: unitが未対応の単位名の場合。
        """
        ...
    def setOffset(self, value: Sequence[float], *, unit: str = ..., fast: bool = ...) -> AimConstraint:
        """Offsetだけを設定する。

        Maintain Offsetのように、今の姿勢からオフセットを計算し直すことはしない。

        Args:
            value (Sequence[float]): XYZの3つの値。どれも有限な数値にする。
            unit (str): valueの角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            AimConstraint: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: 値またはunitが不正な場合。
            RuntimeError: ノードがリファレンスされているかロックされている場合、またはアトリビュートがロックされているか入力が接続されている場合。
        """
        ...
    def getOutputRotate(self) -> EulerRotate:
        """出力のconstraintRotateを、constraintRotateOrderの回転順序で取得する。

        Returns:
            EulerRotate: 評価した出力(ラジアン)。このノード自身のTransformの回転や、ワールドの回転ではない。
        """
        ...
    def _set_angles(self, attribute: str, value: Sequence[float], unit: str = ..., fast: bool = ...) -> AimConstraint:
        """3つの角度をまとめて書き込む。

        入力の接続とロックは、書き込む前にすべて確かめる。
        通常は1回のUndoで戻せるようにまとめる。fast=TrueならOpenMayaで直接書き込む(Undoなし)。

        Args:
            attribute (str): 書き込むコンパウンドアトリビュート。
            value (Sequence[float]): unitの単位の3つの値。
            unit (str): 角度の単位(deg/rad)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            AimConstraint: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: 値またはunitが不正な場合。
            RuntimeError: ノードがリファレンスされているかロックされている場合、またはアトリビュートがロックされているか入力が接続されている場合。
        """
        ...
