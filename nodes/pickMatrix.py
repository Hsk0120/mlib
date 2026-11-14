"""マトリクスから移動・回転・スケール・せん断の一部だけを取り出す。"""

from . import _calculation
from .node import Node


class PickMatrix(Node):
    """マトリクスの成分の一部だけを取り出すpickMatrixを扱うクラス。

    入力のマトリクスの移動・回転・スケール・せん断のうち、使うものだけを残したマトリクスを出力する。
    """

    def setInput(self, inputMatrix=None, useTranslate=None, useRotate=None, useScale=None, useShear=None):
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            inputMatrix (Matrix | Iterable[float] | Plug | str | None): 元のマトリクス。
            useTranslate (bool | Plug | str | None): Trueなら移動を残す。
            useRotate (bool | Plug | str | None): Trueなら回転を残す。
            useScale (bool | Plug | str | None): Trueならスケールを残す。
            useShear (bool | Plug | str | None): Trueならせん断を残す。

        Returns:
            PickMatrix: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込み・接続を拒否した場合(それまでの変更は戻す)。
        """
        return _calculation.set_inputs(
            self, "setInput", {"inputMatrix": inputMatrix, "useTranslate": useTranslate, "useRotate": useRotate, "useScale": useScale, "useShear": useShear}
        )

    def getResult(self):
        """出力 ``outputMatrix`` の現在の値を取得する。

        Returns:
            Matrix: 取り出したマトリクス。
        """
        return self.getOutputPlug().get()

    def getOutputPlug(self):
        """出力のアトリビュート ``outputMatrix`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        return self.getPlug("outputMatrix")
