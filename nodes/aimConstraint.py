"""Maya の aimConstraint を扱う。"""

import math

import maya.api.OpenMaya as om2

from ..core.nodeEdit import require_editable
from ..decorator import _edit_context
from ..maths import EulerRotate
from ..util import _angle_unit, _to_radians
from .constraint import Constraint


class AimConstraint(Constraint):
    """オブジェクトをターゲットの方向へ向ける、aimConstraintのクラス。"""

    def getRotateConnections(self):
        """回転の出力から直接つながっている接続を取得する。

        直接の接続だけを返す。その先をたどったり、接続先の種類で絞ったりはしない。

        Returns:
            list[tuple[Plug, Plug]]: 接続元と接続先の組。コンパウンドアトリビュートごと接続している場合は、親どうしの組だけを返す。
        """
        root = self.getPlug("constraintRotate")
        destinations = root.getConnections(outputs=True)
        result = [(root, destination) for destination in destinations]
        for axis in "XYZ":
            source = self.getPlug("constraintRotate" + axis)
            for destination in source.getConnections(outputs=True):
                if destination.isCompound(child=True) and destination.getParent() in destinations:
                    continue
                result.append((source, destination))
        return result

    def getRestRotate(self):
        """Rest Rotateの設定値を取得する。

        Returns:
            EulerRotate: 評価した設定値(ラジアン)。回転順序はconstraintRotateOrder。コンストレイントされる側の回転ではない。
                度の3つの値は ``getRestRotate().asDegrees()`` で取得する。
        """
        return self._get_angles("restRotate")

    def setRestRotate(self, value, *, unit="deg", fast=False, check=False):
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
        self._set_angles("restRotate", value, unit=unit, fast=fast, check=check)

    def _get_angles(self, attribute):
        """3つの角度を、constraintRotateOrderの回転順序のEulerRotateで取得する。

        Args:
            attribute (str): 読み取るコンパウンドアトリビュート。

        Returns:
            EulerRotate: 評価した値(ラジアン)。
        """
        values = [self.getPlug(attribute + axis).get(unit="rad") for axis in "XYZ"]
        return EulerRotate(*values, order=int(self.getPlug("constraintRotateOrder").get()))

    def _set_angles(self, attribute, value, unit="deg", fast=False, check=False):
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
        with _edit_context("mlibAimConstraintSetAngles", fast):
            angle_unit = _angle_unit(unit)
            if isinstance(value, om2.MEulerRotation):
                order = int(self.getPlug("constraintRotateOrder").get())
                euler = value if value.order == order else value.reorder(order)
                values = (euler.x, euler.y, euler.z)
            else:
                values = tuple(float(component) for component in value)
                if len(values) != 3 or not all(math.isfinite(component) for component in values):
                    raise ValueError("anglesは3つの有限な値で指定してください")
                values = tuple(_to_radians(component, angle_unit) for component in values)
            parent = self.getPlug(attribute)
            children = [self.getPlug(attribute + axis) for axis in "XYZ"]
            require_editable(self.mnode())
            if check and any(plug.isLocked() or plug.getConnections(input=True) is not None for plug in [parent, *children]):
                raise RuntimeError(f"アトリビュートがロックされているか、接続されています: {parent._full_name()}")
            for plug, component in zip(children, values):
                plug.set(component, unit="rad", fast=fast)
