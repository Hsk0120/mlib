"""補間のキャッシュを持つコンストレイント(orientConstraint・parentConstraint)に共通する基底クラス。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..util import _finite, _time_unit
from .constraint import Constraint


class _InterpCacheConstraint(Constraint):
    """回転の補間のキャッシュを作れるコンストレイントの基底クラス。

    Mayaのコマンドに ``createCache``・``deleteCache`` フラグがあるノード型だけが派生する。
    コマンドは、ノード型と同じ名前のもの(``cmds.orientConstraint`` など)を使う。
    """

    def createCache(self, start, end, *, timeUnit="frame"):
        """指定期間の補間キャッシュを作成する。

        2つ以上のターゲットのno-flip補間をキャッシュし、補間モードをcacheへ変更する。
        既存キャッシュは置き換える。fast引数は持たない(cmdsで一括処理するため)。

        Args:
            start (float): 開始時刻。timeUnitの単位。
            end (float): 終了時刻。開始以上。
            timeUnit (str): frame(現在のUI時間単位、既定)またはsec。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 時刻が数値以外の場合。
            ValueError: 時刻が有限でない、範囲が逆、またはtimeUnitが未対応の場合。
            RuntimeError: ノードが無効、キャッシュが不要な単一ターゲット、またはMayaが更新を拒否した場合。
        """
        start, end = _finite(start, "start"), _finite(end, "end")
        if start > end:
            raise ValueError("startはend以下で指定してください")
        if _time_unit(timeUnit) == "sec":
            start = om2.MTime(start, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())
            end = om2.MTime(end, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())
        self._require_valid("キャッシュの作成")
        getattr(cmds, self.getType())(self._full_name(), edit=True, createCache=(start, end))

    def deleteCache(self):
        """補間キャッシュを削除する。

        補間モードの変更もMayaのdeleteCacheに従う。
        fast引数は持たない(cmdsで一括処理するため)。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが無効か、Mayaが更新を拒否した場合。
        """
        self._require_valid("キャッシュの削除")
        getattr(cmds, self.getType())(self._full_name(), edit=True, deleteCache=True)
