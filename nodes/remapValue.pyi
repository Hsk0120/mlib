# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ランプで値を再マッピングする。色ランプも操作できる。"""

from . import _calculation
from .node import Node
from typing import Iterable
from mlib.plugs.plug import Plug
from mlib.plugs.rampPlug import RampPlug

_RAMPS: dict


class RemapValue(Node):
    """ランプで値を再マッピングする。色ランプも操作できる。

    どちらのランプを使うかは引数 ``kind`` で選ぶ。

    - ``"value"``: 値のランプ(アトリビュート ``value``)。出力は ``outValue``。
    - ``"color"``: 色のランプ(アトリビュート ``color``)。出力は ``outColor``。

    ランプの点は :class:`~mlib.plugs.rampPlug.RampPlug` で扱う。
    """
    def setInput(self, inputValue: float | Plug | str | None = ..., inputMin: float | Plug | str | None = ..., inputMax: float | Plug | str | None = ..., outputMin: float | Plug | str | None = ..., outputMax: float | Plug | str | None = ...) -> RemapValue:
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            inputValue (float | Plug | str | None): 再マッピングする値。
            inputMin (float | Plug | str | None): 入力の範囲の下限(ランプの位置0)。
            inputMax (float | Plug | str | None): 入力の範囲の上限(ランプの位置1)。
            outputMin (float | Plug | str | None): 出力の範囲の下限(ランプの値0)。
            outputMax (float | Plug | str | None): 出力の範囲の上限(ランプの値1)。

        Returns:
            RemapValue: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書き込みや接続を拒否した場合。
                拒否された場合は、それまでの変更を戻す。
        """
        ...
    def getRampPoints(self, kind: str = ...) -> list[tuple[float, float | tuple[float, float, float], str]]:
        """ランプの点を取得する。

        点は位置の小さい順に並ぶ。:meth:`RampPlug.getEntries` と同じ。

        Args:
            kind (str): どのランプか。``"value"`` は値のランプ、``"color"`` は色のランプ。既定は ``"value"``。

        Returns:
            list[tuple[float, float | tuple[float, float, float], str]]: (位置, 値, 補間の名前)の並び。

        Raises:
            ValueError: kindが ``"value"``・``"color"`` 以外の場合。
        """
        ...
    def setRampPoints(self, points: list[tuple[float, float | tuple[float, float, float], str]], kind: str = ...) -> RemapValue:
        """ランプの点を設定する。

        すでにある点はすべて消え、指定した点に置き換わる。:meth:`RampPlug.setEntries` と同じ。
        1回のUndoで戻せる。

        Args:
            points (list[tuple[float, float | tuple[float, float, float], str]]): (位置, 値, 補間の名前)の並び。
                補間は ``"none"``・``"linear"``・``"smooth"``・``"spline"`` のどれか。
            kind (str): どのランプか。``"value"`` は値のランプ、``"color"`` は色のランプ。既定は ``"value"``。

        Returns:
            RemapValue: 自身。

        Raises:
            TypeError: 点の形・型が不正な場合。
            ValueError: kindが対応していない値の場合、pointsが空の場合、数値が有限でない場合、
                または補間の名前が対応していない場合。
            RuntimeError: ノードが無効な場合、またはMayaが設定を拒否した場合。
        """
        ...
    def addRampPoint(self, position: float, value: float | Iterable[float], interpolation: str = ..., kind: str = ...) -> RemapValue:
        """ランプへ点を1つ足す。

        すでにある点はそのまま残る。1回のUndoで戻せる。

        Args:
            position (float): ランプ上の位置。
            value (float | Iterable[float]): 点の値。色のランプでは ``(r, g, b)``。
            interpolation (str): 補間の名前。``"none"``・``"linear"``・``"smooth"``・``"spline"`` のどれか。
                既定は ``"linear"``。
            kind (str): どのランプか。``"value"`` は値のランプ、``"color"`` は色のランプ。既定は ``"value"``。

        Returns:
            RemapValue: 自身。

        Raises:
            TypeError: 位置・値・補間の型が不正な場合。
            ValueError: kindか補間の名前が対応していない場合、または数値が有限でない場合。
            RuntimeError: ノードが無効な場合、またはMayaが設定を拒否した場合。
        """
        ...
    def getResult(self, kind: str = ...) -> float | tuple[float, float, float]:
        """出力の現在の値を取得する。

        Args:
            kind (str): どの出力か。``"value"`` は ``outValue``、``"color"`` は ``outColor``。既定は ``"value"``。

        Returns:
            float | tuple[float, float, float]: 再マッピングした値、または色(RGB)。

        Raises:
            ValueError: kindが ``"value"``・``"color"`` 以外の場合。
        """
        ...
    def getOutputPlug(self, kind: str = ...) -> Plug:
        """出力のアトリビュートを取得する。ほかのノードへ接続するときの接続元に使う。

        Args:
            kind (str): どの出力か。``"value"`` は ``outValue``、``"color"`` は ``outColor``。既定は ``"value"``。

        Returns:
            Plug: 出力のアトリビュート。

        Raises:
            ValueError: kindが ``"value"``・``"color"`` 以外の場合。
        """
        ...
    def _ramp(self, kind: str) -> RampPlug:
        """ランプのアトリビュートを取得する。

        Args:
            kind (str): ``"value"`` または ``"color"``。

        Returns:
            RampPlug: ランプのアトリビュート。

        Raises:
            ValueError: kindが ``"value"``・``"color"`` 以外の場合。
        """
        ...
