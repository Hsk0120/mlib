"""RGB各成分を指定範囲に制限する。"""

from . import _calculation
from .node import Node


class Clamp(Node):
    """RGB各成分を指定範囲に制限する。"""

    def setInput(self, input=None, min=None, max=None):
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            input (Iterable[float] | Plug | str | None): 制限する値(RGB)。
            min (Iterable[float] | Plug | str | None): 下限(RGB)。
            max (Iterable[float] | Plug | str | None): 上限(RGB)。

        Returns:
            Clamp: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書き込みや接続を拒否した場合。それまでの変更は元に戻す。
        """
        return _calculation.set_inputs(self, "setInput", {"input": input, "min": min, "max": max})

    def getResult(self):
        """出力 ``output`` の現在の値を取得する。

        Returns:
            tuple[float, float, float]: 制限した値(RGB)。
        """
        return self.getOutputPlug().get()

    def getOutputPlug(self):
        """出力のアトリビュート ``output`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        return self.getPlug("output")
