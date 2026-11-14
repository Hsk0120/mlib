"""単位変換のノード(unitConversion)を扱う。"""

from . import _calculation
from .node import Node


class UnitConversion(Node):
    """単位変換のノード(unitConversion)を扱うクラス。入力に係数を掛けて出力する。"""

    def setInput(self, input=None, conversionFactor=None):
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            input (float | Plug | str | None): 変換する値。
            conversionFactor (float | Plug | str | None): 掛ける係数。

        Returns:
            UnitConversion: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書き込み・接続を拒否した場合。
                拒否されたときは、それまでの変更を戻す。
        """
        return _calculation.set_inputs(self, "setInput", {"input": input, "conversionFactor": conversionFactor})

    def getResult(self):
        """出力 ``output`` の現在の値を取得する。

        Returns:
            object: 変換した値。
        """
        return self.getOutputPlug().get()

    def getOutputPlug(self):
        """出力のアトリビュート ``output`` を取得する。

        ほかのノードへつなぐときの接続元に使う。

        Returns:
            Plug: 出力のアトリビュート。
        """
        return self.getPlug("output")
