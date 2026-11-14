# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ランプのアトリビュート(位置・値・補間の点を持つマルチアトリビュート)を扱う。"""

import math
import numbers
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import undoChunk
from .multiPlug import MultiPlug

_INTERPOLATION_NAMES: tuple

def _require_number(value: float, name: str) -> float:
    """有限の実数を検証し、floatで返す。

    Args:
        value (float): 検証する値。
        name (str): 例外の文言に使う引数名。

    Returns:
        float: 検証済みの値。

    Raises:
        TypeError: boolまたは実数以外の場合。
        ValueError: 有限でない場合。
    """
    ...


class RampPlug(MultiPlug):
    """ランプのアトリビュートを、点(位置・値・補間)の並びとして扱うPlug。

    remapValueの ``value``・``color`` などが対象になる。``om2.MRampAttribute`` で扱えるマルチアトリビュートを
    取得すると、この型になる。

    - 値は、float のランプ(カーブのランプ)では float、色のランプでは ``(r, g, b)`` の tuple。
    - 補間は ``"none"``・``"linear"``・``"smooth"``・``"spline"`` の名前で扱う。

    要素の番号や値を直接編集するときは、:class:`MultiPlug` の機能を使う。

    Note:
        ``ramp`` テクスチャノードの ``colorEntryList`` は、MRampAttribute で扱えない形をしている。
        そのため、この型ではなく :class:`MultiPlug` になる。
    """
    def isColorRamp(self) -> bool:
        """色のランプか判定する。

        Returns:
            bool: 色のランプなら ``True``。float のランプ(カーブのランプ)は ``False``。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    def getEntries(self) -> list[tuple[float, float | tuple[float, float, float], str]]:
        """ランプの点を、位置の小さい順に取得する。

        Returns:
            list[tuple[float, float | tuple[float, float, float], str]]: (位置, 値, 補間の名前)の新しいリスト。
                値は、float のランプでは float、色のランプでは ``(r, g, b)``。
                位置が同じ点は、論理番号の順に並ぶ。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    def setEntries(self, entries: list[tuple[float, float | tuple[float, float, float], str]]) -> RampPlug:
        """ランプの点を設定する。すでにある点はすべて置き換える。

        すでにある要素を ``cmds.removeMultiInstance`` で外してから、渡した順に論理番号0から設定する。
        1回のUndoで戻せる。

        Args:
            entries (list[tuple[float, float | tuple[float, float, float], str]]): (位置, 値, 補間の名前)の並び。
                値は、float のランプでは実数、色のランプでは3つの実数。補間は ``"none"``・``"linear"``・
                ``"smooth"``・``"spline"``。:meth:`getEntries` の結果をそのまま渡せる。

        Returns:
            RampPlug: 自身。

        Raises:
            TypeError: 次のどれかの場合。entriesや各点が3つの組でない。位置・値が実数でない
                (色のランプでは3つの実数でない)。補間が文字列でない。
            ValueError: entriesが空の場合、数値が有限でない場合、または補間が対応していない名前の場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合、またはロックや入力の接続があって
                Mayaが設定を拒否した場合。
        """
        ...
    def getValueAt(self, position: float) -> float | tuple[float, float, float]:
        """ランプ上の位置での値を取得する。

        点と点の間は、補間した値になる。

        Args:
            position (float): ランプ上の位置。

        Returns:
            float | tuple[float, float, float]: float のランプでは float、色のランプでは ``(r, g, b)``。

        Raises:
            TypeError: positionが実数でない場合。
            ValueError: positionが有限でない場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    def _ramp(self) -> om2.MRampAttribute:
        """有効なことを確かめてから、このPlugの ``om2.MRampAttribute`` を作る。

        Returns:
            om2.MRampAttribute: このランプのアトリビュート。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    @staticmethod
    def _validated_entries(entries: list[tuple[float, float | tuple[float, float, float], str]], color: bool) -> list[tuple[float, float | tuple[float, float, float], int]]:
        """setEntriesの点を検証し、(位置, 値, 補間の番号)のリストで返す。

        Args:
            entries (list[tuple[float, float | tuple[float, float, float], str]]): 検証する点の並び。
            color (bool): 色のランプならTrue。

        Returns:
            list[tuple[float, float | tuple[float, float, float], int]]: 検証済みの点。

        Raises:
            TypeError: 並び・点・値・補間の型が違う場合。
            ValueError: 空、有限でない数値、または未対応の補間の名前の場合。
        """
        ...
