"""マトリクスのアトリビュートの値を読み書きする。ノードの移動・回転などはTransformで扱う。"""

import maya.api.OpenMaya as om2

from ..core.attributeType import _plain_angle_unit, _plain_time_unit, typed_data
from ..core.fastWrite import set_attr, set_plug
from ..decorator import _require_bool
from ..maths import Matrix
from .plug import Plug


class MatrixPlug(Plug):
    """matrix型のアトリビュートを扱うPlug。そのアトリビュートの値だけを扱う。"""

    def get(self, *, unit=None, timeUnit=None, uiUnits=False):
        """アトリビュートのマトリクスの値を取得する。

        Args:
            unit (str | None): Plug共通の角度の単位の指定。正しい指定か確かめるだけで、マトリクスの成分は換算しない。
            timeUnit (str | None): Plug共通の時間の単位の指定。正しい指定か確かめるだけ。
            uiUnits (bool): Plug共通の単位の指定。マトリクスの成分の単位は変換しない。

        Returns:
            Matrix | None: アトリビュートのマトリクスのコピー。uiUnitsにかかわらず、内部単位のまま返す。
                値を一度も設定していない ``dataType="matrix"`` (型付きデータ)はNone。
                ``attributeType="matrix"`` は、未設定でも既定の単位マトリクスを返す。

        Raises:
            TypeError: uiUnitsがboolでない場合、またはunit・timeUnitが文字列でもNoneでもない場合。
            ValueError: unit・timeUnitが対応していない単位名の場合、またはuiUnits=Trueと同時に指定した場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合、または値を読み取れない場合。
        """
        _require_bool(uiUnits, "uiUnits")
        _plain_angle_unit(unit, uiUnits)
        _plain_time_unit(timeUnit, uiUnits)
        self._require_valid()
        # 未初期化の型付きデータはasMObjectがkFailureになるため、nullだけをNoneにする。
        data = typed_data(self._mplug)
        if data.isNull():
            return None
        return Matrix.fromMMatrix(om2.MFnMatrixData(data).matrix())

    def _set_value(self, value, *, uiUnits=False, fast=False):
        """マトリクスのアトリビュートへ値を直接設定する。

        Transformの移動・回転・スケールは操作しない。全体の流れは :meth:`Plug.set` が受け持つ。

        - worldMatrixは計算で求まる出力なので、設定を拒否する。
        - ロックの解除や入力の接続の切断はしない。
        - safe=Trueで失敗したときは、成分ごとに再試行せず1を返す。

        Args:
            value (Matrix | om2.MMatrix | sequence): マトリクスの値。Matrix(value)で変換する。
            uiUnits (bool): Plug共通のフラグとして受け付けるが、マトリクスの成分は換算しない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: worldMatrixに設定しようとした場合、またはuiUnitsや値の型が不正な場合。
            ValueError: 値をマトリクスへ変換できない場合。
            RuntimeError: アトリビュートが無効な場合、またはMayaが書き込みを拒否した場合。
        """
        _require_bool(uiUnits, "uiUnits")
        self._require_valid()
        if self.getLongName() in ("worldMatrix", "wm"):
            raise TypeError("worldMatrixは計算される出力なので設定できません")
        matrix = Matrix(value)
        if fast:
            set_plug(self._mplug, matrix)
        else:
            set_attr(self.getFullName(), *tuple(matrix), type="matrix", fast=False)
