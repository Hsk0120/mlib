# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の parentConstraint を扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..util import _finite, _time_unit
from .constraint import Constraint



class ParentConstraint(Constraint):
    """位置と回転をコンストレイントするparentConstraintを扱うクラス。"""
    def createCache(self, start: float, end: float, *, timeUnit: str = ...) -> None:
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
        ...
    def deleteCache(self) -> None:
        """補間キャッシュを削除する。

        補間モードの変更もMayaのdeleteCacheに従う。
        fast引数は持たない(cmdsで一括処理するため)。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが無効か、Mayaが更新を拒否した場合。
        """
        ...
