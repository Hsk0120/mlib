# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""XYZ成分ごとの乗算・除算・累乗。"""

from . import _calculation
from .shadingDependNode import ShadingDependNode
from typing import Iterable
from mlib.plugs.plug import Plug

_OPERATIONS: tuple


class MultiplyDivide(ShadingDependNode):
    """XYZの成分ごとに、乗算・除算・累乗を計算するmultiplyDivideを扱うクラス。"""
    def setInput(self, input1: Iterable[float] | Plug | str | None = ..., input2: Iterable[float] | Plug | str | None = ...) -> MultiplyDivide:
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            input1 (Iterable[float] | Plug | str | None): 1つ目の入力(XYZ)。
            input2 (Iterable[float] | Plug | str | None): 2つ目の入力(XYZ)。

        Returns:
            MultiplyDivide: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込み・接続を拒否した場合(それまでの変更は戻す)。
        """
        ...
    def getOperation(self) -> str:
        """演算の種類を名前で取得する(``operation``)。

        Returns:
            str: ``"noOperation"``・``"multiply"``・``"divide"``・``"power"`` のいずれか。
        """
        ...
    def setOperation(self, operation: str | int) -> MultiplyDivide:
        """演算の種類を設定する(``operation``)。

        名前か番号で指定する。1回のUndoで戻せる。

        Args:
            operation (str | int): ``"noOperation"``・``"multiply"``・``"divide"``・``"power"`` のいずれか。
                Mayaの番号(0から)でもよい。

        Returns:
            MultiplyDivide: 自身。

        Raises:
            TypeError: operationが文字列・int以外の場合。
            ValueError: 対応していない名前、または範囲外の番号の場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込みを拒否した場合。
        """
        ...
    def getResult(self) -> tuple[float, float, float]:
        """出力 ``output`` の現在の値を取得する。

        Returns:
            tuple[float, float, float]: 演算の結果(XYZ)。
        """
        ...
    def getOutputPlug(self) -> Plug:
        """出力のアトリビュート ``output`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        ...
