"""Maya の aimConstraint を扱う。"""

import math

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
        destinations = root.getDestinations()
        result = [(root, destination) for destination in destinations]
        for axis in "XYZ":
            source = self.getPlug("constraintRotate" + axis)
            for destination in source.getDestinations():
                if destination.isChild() and destination.getParent() in destinations:
                    continue
                result.append((source, destination))
        return result

    def getRestRotate(self, *, unit="deg"):
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
        angle_unit = _angle_unit(unit)
        return tuple(self.getPlug("restRotate" + axis).get(unit=angle_unit) for axis in "XYZ")

    def setRestRotate(self, value, *, unit="deg", fast=False):
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
        return self._set_angles("restRotate", value, unit=unit, fast=fast)

    def getOffset(self, *, unit="deg"):
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
        angle_unit = _angle_unit(unit)
        return tuple(self.getPlug("offset" + axis).get(unit=angle_unit) for axis in "XYZ")

    def setOffset(self, value, *, unit="deg", fast=False):
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
        return self._set_angles("offset", value, unit=unit, fast=fast)

    def getOutputRotate(self):
        """出力のconstraintRotateを、constraintRotateOrderの回転順序で取得する。

        Returns:
            EulerRotate: 評価した出力(ラジアン)。このノード自身のTransformの回転や、ワールドの回転ではない。
        """
        values = [self.getPlug("constraintRotate" + axis).get(unit="rad") for axis in "XYZ"]
        return EulerRotate(*values, order=int(self.getPlug("constraintRotateOrder").get()))

    def _set_angles(self, attribute, value, unit="deg", fast=False):
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
        with _edit_context("mlibAimConstraintSetAngles", fast):
            angle_unit = _angle_unit(unit)
            values = tuple(float(component) for component in value)
            if len(values) != 3 or not all(math.isfinite(component) for component in values):
                raise ValueError("anglesは3つの有限な値で指定してください")
            values = tuple(_to_radians(component, angle_unit) for component in values)
            parent = self.getPlug(attribute)
            children = [self.getPlug(attribute + axis) for axis in "XYZ"]
            require_editable(self.mnode())
            if any(plug.isLocked() or plug.getSource() is not None for plug in [parent] + children):
                raise RuntimeError(f"アトリビュートがロックされているか、接続されています: {parent.getFullName()}")
            for plug, component in zip(children, values):
                plug.set(component, unit="rad", fast=fast)
            return self
