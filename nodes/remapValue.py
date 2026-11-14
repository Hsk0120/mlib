"""ランプで値を再マッピングする。色ランプも操作できる。"""

from . import _calculation
from .node import Node

#: ランプの種類から、ランプ・出力のアトリビュート名。
_RAMPS = {"value": ("value", "outValue"), "color": ("color", "outColor")}


class RemapValue(Node):
    """ランプで値を再マッピングする。色ランプも操作できる。

    どちらのランプを使うかは引数 ``kind`` で選ぶ。

    - ``"value"``: 値のランプ(アトリビュート ``value``)。出力は ``outValue``。
    - ``"color"``: 色のランプ(アトリビュート ``color``)。出力は ``outColor``。

    ランプの点は :class:`~mlib.plugs.rampPlug.RampPlug` で扱う。
    """

    def setInput(self, inputValue=None, inputMin=None, inputMax=None, outputMin=None, outputMax=None):
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
        return _calculation.set_inputs(
            self, "setInput", {"inputValue": inputValue, "inputMin": inputMin, "inputMax": inputMax, "outputMin": outputMin, "outputMax": outputMax}
        )

    def getRampPoints(self, kind="value"):
        """ランプの点を取得する。

        点は位置の小さい順に並ぶ。:meth:`RampPlug.getEntries` と同じ。

        Args:
            kind (str): どのランプか。``"value"`` は値のランプ、``"color"`` は色のランプ。既定は ``"value"``。

        Returns:
            list[tuple[float, float | tuple[float, float, float], str]]: (位置, 値, 補間の名前)の並び。

        Raises:
            ValueError: kindが ``"value"``・``"color"`` 以外の場合。
        """
        return self._ramp(kind).getEntries()

    def setRampPoints(self, points, kind="value"):
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
        self._ramp(kind).setEntries(points)
        return self

    def addRampPoint(self, position, value, interpolation="linear", kind="value"):
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
        ramp = self._ramp(kind)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            value = tuple(value)
        ramp.setEntries(ramp.getEntries() + [(position, value, interpolation)])
        return self

    def getResult(self, kind="value"):
        """出力の現在の値を取得する。

        Args:
            kind (str): どの出力か。``"value"`` は ``outValue``、``"color"`` は ``outColor``。既定は ``"value"``。

        Returns:
            float | tuple[float, float, float]: 再マッピングした値、または色(RGB)。

        Raises:
            ValueError: kindが ``"value"``・``"color"`` 以外の場合。
        """
        return self.getOutputPlug(kind).get()

    def getOutputPlug(self, kind="value"):
        """出力のアトリビュートを取得する。ほかのノードへ接続するときの接続元に使う。

        Args:
            kind (str): どの出力か。``"value"`` は ``outValue``、``"color"`` は ``outColor``。既定は ``"value"``。

        Returns:
            Plug: 出力のアトリビュート。

        Raises:
            ValueError: kindが ``"value"``・``"color"`` 以外の場合。
        """
        return self.getPlug(_RAMPS[_calculation.choice(kind, _RAMPS, "kind")][1])

    def _ramp(self, kind):
        """ランプのアトリビュートを取得する。

        Args:
            kind (str): ``"value"`` または ``"color"``。

        Returns:
            RampPlug: ランプのアトリビュート。

        Raises:
            ValueError: kindが ``"value"``・``"color"`` 以外の場合。
        """
        return self.getPlug(_RAMPS[_calculation.choice(kind, _RAMPS, "kind")][0])
