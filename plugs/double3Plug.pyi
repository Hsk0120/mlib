# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""double3のアトリビュートを、意味に合った3成分の値(移動・回転など)として読み書きする。"""

import math
import maya.api.OpenMaya as om2
from ..core.attributeType import _convert_angles, _convert_units, _plain_angle_unit, _plain_time_unit
from ..core.fastWrite import set_plug
from ..decorator import _require_bool
from ..maths import EulerRotate, Scale, Shear, Translate, Vector
from .compoundPlug import CompoundPlug
from typing import Iterable
from mlib.maths.quaternion import Quaternion



class Double3Plug(CompoundPlug):
    """3成分のアトリビュートを扱うPlug。チャンネルの値を読み書きし、マトリクスでの変換はしない。"""
    def get(self, *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ...) -> Vector | Translate | EulerRotate | Scale | Shear | tuple[float, float, float]:
        """3成分のチャンネルの値を取得する。

        このアトリビュートの値だけを返し、jointOrientなどほかのアトリビュートとは合成しない。

        Args:
            unit (str | None): 角度の子の数値の単位。None(既定)は度(rotateはEulerRotateで返す)。
                rotateでunitを指定すると、EulerRotateではなく、指定した単位の数値のtupleを返す。
                ``"deg"`` / ``"rad"`` と、``"degree"`` などの別名を受け付ける。uiUnits=Trueとは同時に指定できない。
            timeUnit (str | None): Plug共通の時間の単位の指定。3成分の子は時間を持たないので、正しい指定か確かめるだけ。
            uiUnits (bool): Trueなら、現在のUIの単位の数値のtupleを返す。既定はFalseで、数学の値の型で返す。

        Returns:
            Vector | Translate | EulerRotate | Scale | Shear | tuple[float, float, float]:
                アトリビュートごとに次の型で返す。

                - translateはTranslate。距離はcm。
                - rotateはEulerRotate。回転順序はノードのrotateOrder、中身はrad。
                - scaleはScale、shearはShear。
                - それ以外はVector。jointOrient・rotateAxisなどの角度の子は度(unit="rad"ならrad)。

                どれも、ほかとは独立した値になる。

                uiUnits=Trueの場合と、rotateでunitを指定した場合は、数値のtupleを返す。

        Raises:
            TypeError: uiUnitsがboolでない場合、またはunit・timeUnitが文字列でもNoneでもない場合。
            ValueError: unit・timeUnitが対応していない単位名の場合、またはuiUnits=Trueと同時に指定した場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    def set(self, value: Iterable[float] | EulerRotate | Quaternion, safe: bool = ..., *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., fast: bool = ...) -> Double3Plug | int:
        """このアトリビュートの3成分だけを書き込む。

        マトリクスを通して姿勢を変えることはしない。3成分の値と、書き込めるかどうかを確かめてから
        CompoundPlug.setへ渡す。safeで子ごとに再試行したときは、成功した子の変更は残る。
        通常はUndoが有効なら記録し、fastでは記録しない。

        Args:
            value (Iterable[float] | EulerRotate | Quaternion): 3成分の値。
                rotateでは、OpenMayaの基底の型の回転も受け付け、ノードのrotateOrderへ揃える。
                数値の並びは、ノードのrotateOrderの回転として読む。角度の子の数値は既定で度。
                EulerRotate・Quaternionは自分の単位(rad)を持つので、unitにかかわらず換算しない。
            safe (bool): Trueなら、書き込みの失敗を例外にせず数える(数える失敗の種類はRaisesを参照)。
            unit (str | None): 角度の子(rotate・jointOrient・rotateAxisなど)の数値の単位。
                None(既定)は度、``"rad"`` はラジアン(``"degree"`` などの別名も使える)。角度以外の子では使わない。
            timeUnit (str | None): Plug共通の時間の単位の指定。3成分の子は時間を持たないので、正しい指定か確かめるだけ。
            uiUnits (bool): Trueなら、UIの単位の数値の並びを指定する。数学の値の型やunitとは同時に指定できない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Double3Plug | int: safe=Falseなら自身。safe=Trueなら、成功は0、失敗は子の失敗数、
                値の変換に失敗した場合は1。CompoundPlug.setの再試行の決まりに従い、
                途中まで変えた値は自動では戻さない。

        Raises:
            TypeError: fastがboolでない場合、またはマルチアトリビュート全体に設定しようとした場合。
                safe=Trueでも例外にする。safe=Falseなら、値の型が不正な場合にも送出する。
            ValueError: unit・timeUnitが対応していない場合、またはuiUnits=Trueと同時に指定した場合
                (safe=Trueでは1を返す)。safe=Falseなら、成分の数が違う場合や有限でない値の場合にも送出する。
            RuntimeError: safe=Falseで、アトリビュートが無効な場合、ロックや入力の接続がある場合、
                またはMayaでの編集に失敗した場合。
            NotImplementedError: fastで、対応していない型の場合。safe=Trueでも例外にする。
        """
        ...
    def _set_value(self, value: Iterable[float] | EulerRotate | Quaternion, *, uiUnits: bool = ..., fast: bool = ...) -> None:
        """3成分の値と、書き込めるかどうかを確かめてから書き込む。

        全体の流れは :meth:`Plug.set` が受け持つ。

        Args:
            value (Iterable[float] | EulerRotate | Quaternion): 3成分の値。角度の数値は
                :meth:`Plug._set_template` でradへ換算済み。
            uiUnits (bool): Trueなら、UIの単位の数値の並び。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 値の型が不正な場合。
            ValueError: 成分の数が違う場合、または有限でない値の場合。
            RuntimeError: アトリビュートが無効な場合、ロックや入力の接続がある場合、
                またはMayaでの編集に失敗した場合。
        """
        ...
    def _set_children_safely(self, value: object, *, uiUnits: bool = ..., fast: bool = ...) -> int:
        """回転順序と単位を揃えてから、子ごとにsafeで設定を試す。

        uiUnits=Trueで数学の値の型を渡した場合のように、成分への変換そのものが失敗したときは、子を変更しない。

        Args:
            value (object): 最初の設定へ渡した値(角度の数値はradへ換算済み)。
            uiUnits (bool): Trueなら、UIの単位の数値を一度、内部単位へ変換する。
            fast (bool): 子のsetへ渡す、更新の方法。

        Returns:
            int: 子の失敗数。値の変換に失敗した場合は1。
        """
        ...
    def _ui_components(self, value: Iterable[float]) -> tuple:
        """UIの単位の数値の並びを、内部単位へ変換する。

        数学の値の型は、もともと内部単位を持つので受け付けない。

        Args:
            value (Iterable[float]): UI単位の数値3成分。

        Returns:
            tuple: 内部単位の数値3成分。

        Raises:
            TypeError: OpenMayaの数学値をUI数値として指定した場合。
        """
        ...
    def _set_components(self, value: Iterable[float] | om2.MEulerRotation | om2.MQuaternion) -> tuple[float, float, float]:
        """3成分の値を確かめる。rotateでは回転順序をノードに揃える。

        シーンへは書き込まない。角度の数値は、呼び出し元でradへ換算済みのものを受け取る。

        Args:
            value (Iterable[float] | om2.MEulerRotation | om2.MQuaternion): 値。

        Returns:
            tuple[float, float, float]: rotateなら、ノードのrotateOrderに合わせたラジアンの成分。
                それ以外は渡された3成分。

        Raises:
            TypeError: 値を数値の並びへ変換できない場合。
            ValueError: 成分の数が違う場合、または有限でない値の場合。
        """
        ...
