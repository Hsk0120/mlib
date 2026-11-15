# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の aimConstraint を扱う。"""

import math
import maya.api.OpenMaya as om2
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
    def getRestRotate(self) -> EulerRotate:
        """Rest Rotateの設定値を取得する。

        Returns:
            EulerRotate: 評価した設定値(ラジアン)。回転順序はconstraintRotateOrder。コンストレイントされる側の回転ではない。
                度の3つの値は ``getRestRotate().asDegrees()`` で取得する。
        """
        ...
    def setRestRotate(self, value: Sequence[float] | EulerRotate, *, unit: str = ..., fast: bool = ..., check: bool = ...) -> None:
        """Rest Rotateだけを設定する。

        追従の状態や、コンストレイントされる側の回転は直接変えない。

        Args:
            value (Sequence[float] | EulerRotate): XYZの3つの値。EulerRotateの代わりに、元になっているOpenMayaの型も
                受け付ける。EulerRotateは自分の単位(rad)を持つので、unitに関係なく換算しない。回転順序が
                constraintRotateOrderと違う場合は、同じ回転になる値へ直して書く。
            unit (str): 3つの数値の角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: 値またはunitが不正な場合。
            RuntimeError: ノードがリファレンスされているかロックされている場合、またはアトリビュートがロックされているか入力が接続されている場合。
        """
        ...
    def getOffset(self) -> EulerRotate:
        """Offsetの設定値を取得する。

        Returns:
            EulerRotate: 評価したOffsetの値(ラジアン)。回転順序はconstraintRotateOrder。
                度の3つの値は ``getOffset().asDegrees()`` で取得する。
        """
        ...
    def setOffset(self, value: Sequence[float] | EulerRotate, *, unit: str = ..., fast: bool = ..., check: bool = ...) -> None:
        """Offsetだけを設定する。

        Maintain Offsetのように、今の姿勢からオフセットを計算し直すことはしない。

        Args:
            value (Sequence[float] | EulerRotate): XYZの3つの値。EulerRotateの代わりに、元になっているOpenMayaの型も
                受け付ける。EulerRotateは自分の単位(rad)を持つので、unitに関係なく換算しない。回転順序が
                constraintRotateOrderと違う場合は、同じ回転になる値へ直して書く。
            unit (str): 3つの数値の角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

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
    def _get_angles(self, attribute: str) -> EulerRotate:
        """3つの角度を、constraintRotateOrderの回転順序のEulerRotateで取得する。

        Args:
            attribute (str): 読み取るコンパウンドアトリビュート。

        Returns:
            EulerRotate: 評価した値(ラジアン)。
        """
        ...
    def _set_angles(self, attribute: str, value: Sequence[float] | EulerRotate, unit: str = ..., fast: bool = ..., check: bool = ...) -> None:
        """3つの角度をまとめて書き込む。

        通常は1回のUndoで戻せるようにまとめる。fast=TrueならOpenMayaで直接書き込む(Undoなし)。

        Args:
            attribute (str): 書き込むコンパウンドアトリビュート。
            value (Sequence[float] | EulerRotate): unitの単位の3つの値、またはEulerRotate。
            unit (str): 角度の単位(deg/rad)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、入力の接続とロックをすべて確かめる。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: 値またはunitが不正な場合。
            RuntimeError: ノードがリファレンスされているかロックされている場合、またはアトリビュートがロックされているか入力が接続されている場合。
        """
        ...
