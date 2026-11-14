# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""16個の値からマトリクスを作る。"""

from . import _calculation
from .node import Node
from typing import Iterable
from mlib.maths.matrix import Matrix
from mlib.plugs.plug import Plug

_ELEMENTS: tuple


class FourByFourMatrix(Node):
    """``in00``〜``in33`` の16個の値(行優先)からマトリクスを作り、``output`` へ出力する。"""
    def setInput(self, matrix: Matrix | Iterable[float] | None = ..., **elements: float | Plug | str) -> FourByFourMatrix:
        """成分をまとめて設定する。

        値を渡した成分は書き込み、Plugを渡した成分は接続する。1回のUndoで戻せる。

        Args:
            matrix (Matrix | Iterable[float] | None): 16個の値(行優先)。Noneなら変更しない。
            **elements (float | Plug | str): 成分を1つずつ指定する(``in03=5.0`` や ``in30=node.tx`` など)。
                matrixを書き込んだ後に反映する。

        Returns:
            FourByFourMatrix: 自身。

        Raises:
            TypeError: elementsに ``in00``〜``in33`` 以外の名前がある場合、または接続元の型が不正な場合。
            ValueError: matrixの値が16個でない場合。
            RuntimeError: ノードが無効な場合、またはMayaが書き込みや接続を拒否した場合。それまでの変更は元に戻す。
        """
        ...
    def getResult(self) -> Matrix:
        """出力 ``output`` の現在の値を取得する。

        Returns:
            Matrix: 作ったマトリクス。
        """
        ...
    def getOutputPlug(self) -> Plug:
        """出力のアトリビュート ``output`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        ...
