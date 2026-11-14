"""ランプのアトリビュート(位置・値・補間の点を持つマルチアトリビュート)を扱う。"""

import math
import numbers

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import undoChunk
from .multiPlug import MultiPlug

#: 補間の番号(``MRampAttribute.kNone`` 等と同じ)に対応する名前。
_INTERPOLATION_NAMES = ("none", "linear", "smooth", "spline")


def _require_number(value, name):
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
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name}は数値で指定してください")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name}は有限な数値で指定してください: {value!r}")
    return value


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

    def isColorRamp(self):
        """色のランプか判定する。

        Returns:
            bool: 色のランプなら ``True``。float のランプ(カーブのランプ)は ``False``。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        return self._ramp().isColorRamp

    def getEntries(self):
        """ランプの点を、位置の小さい順に取得する。

        Returns:
            list[tuple[float, float | tuple[float, float, float], str]]: (位置, 値, 補間の名前)の新しいリスト。
                値は、float のランプでは float、色のランプでは ``(r, g, b)``。
                位置が同じ点は、論理番号の順に並ぶ。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ramp = self._ramp()
        indices, positions, values, interpolations = ramp.getEntries()
        color = ramp.isColorRamp
        entries = []
        for index, position, value, interpolation in zip(indices, positions, values, interpolations):
            value = (value.r, value.g, value.b) if color else float(value)
            entries.append((float(position), index, value, _INTERPOLATION_NAMES[interpolation]))
        entries.sort(key=lambda entry: (entry[0], entry[1]))
        return [(position, value, interpolation) for position, _, value, interpolation in entries]

    def setEntries(self, entries):
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
        with undoChunk("mlibRampPlugSetEntries"):
            ramp = self._ramp()
            points = self._validated_entries(entries, ramp.isColorRamp)
            if self._mplug.isLocked:
                raise RuntimeError(f"ランプアトリビュートがロックされています: {self.getFullName()}")
            name = self.getFullName()
            for index in self._mplug.getExistingArrayAttributeIndices():
                cmds.removeMultiInstance(f"{name}[{index}]", b=True)
            element = self._mplug.elementByLogicalIndex(0)
            children = [om2.MFnAttribute(element.child(number).attribute()).name for number in range(3)]
            for index, (position, value, interpolation) in enumerate(points):
                prefix = f"{name}[{index}]."
                cmds.setAttr(prefix + children[0], position)
                if isinstance(value, tuple):
                    cmds.setAttr(prefix + children[1], *value, type="double3")
                else:
                    cmds.setAttr(prefix + children[1], value)
                cmds.setAttr(prefix + children[2], interpolation)
            return self

    def getValueAt(self, position):
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
        position = _require_number(position, "position")
        ramp = self._ramp()
        value = ramp.getValueAtPosition(position)
        if ramp.isColorRamp:
            return (value.r, value.g, value.b)
        return float(value)

    def _ramp(self):
        """有効なことを確かめてから、このPlugの ``om2.MRampAttribute`` を作る。

        Returns:
            om2.MRampAttribute: このランプのアトリビュート。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        self._require_valid()
        return om2.MRampAttribute(self._mplug)

    @staticmethod
    def _validated_entries(entries, color):
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
        if isinstance(entries, (str, bytes)):
            raise TypeError("entriesは(position, value, interpolation)の並びで指定してください")
        try:
            entries = list(entries)
        except TypeError:
            raise TypeError("entriesは(position, value, interpolation)の並びで指定してください") from None
        if not entries:
            raise ValueError("entriesは空にできません")
        points = []
        for entry in entries:
            if isinstance(entry, (str, bytes)) or not isinstance(entry, (tuple, list)) or len(entry) != 3:
                raise TypeError("各項目は(position, value, interpolation)のタプルで指定してください")
            position, value, interpolation = entry
            position = _require_number(position, "position")
            if color:
                if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)) or len(value) != 3:
                    raise TypeError("カラーランプのvalueは3つの数値(r, g, b)で指定してください")
                value = tuple(_require_number(item, "value") for item in value)
            else:
                value = _require_number(value, "value")
            if not isinstance(interpolation, str):
                raise TypeError("interpolationは文字列で指定してください")
            if interpolation not in _INTERPOLATION_NAMES:
                raise ValueError(f"interpolationは次のどれかで指定してください: {', '.join(_INTERPOLATION_NAMES)}")
            points.append((position, value, _INTERPOLATION_NAMES.index(interpolation)))
        return points
