# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""2値の比較により出力を切り替える。"""

from . import _calculation
from .node import Node
from typing import Iterable
from mlib.plugs.plug import Plug

_OPERATIONS: tuple


class Condition(Node):
    """2つの値を比べ、その結果で出力を切り替える。"""
    def setInput(self, firstTerm: float | Plug | str | None = ..., secondTerm: float | Plug | str | None = ..., colorIfTrue: Iterable[float] | Plug | str | None = ..., colorIfFalse: Iterable[float] | Plug | str | None = ...) -> Condition:
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            firstTerm (float | Plug | str | None): 比較する1つ目の値。
            secondTerm (float | Plug | str | None): 比較する2つ目の値。
            colorIfTrue (Iterable[float] | Plug | str | None): 比較が成り立つときの出力(RGB)。
            colorIfFalse (Iterable[float] | Plug | str | None): 比較が成り立たないときの出力(RGB)。

        Returns:
            Condition: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書き込みや接続を拒否した場合。それまでの変更は元に戻す。
        """
        ...
    def getOperation(self) -> str:
        """比較の種類を名前で取得する。

        ``operation`` の値を名前に直して返す。

        Returns:
            str: ``"equal"``・``"notEqual"``・``"greaterThan"``・``"greaterOrEqual"``・``"lessThan"``・
                ``"lessOrEqual"`` のいずれか。
        """
        ...
    def setOperation(self, operation: str | int) -> Condition:
        """比較の種類を設定する。

        ``operation`` へ書き込む。名前でも番号でも指定できる。1回のUndoで戻せる。

        Args:
            operation (str | int): ``"equal"``・``"notEqual"``・``"greaterThan"``・``"greaterOrEqual"``・``"lessThan"``・
                ``"lessOrEqual"`` のいずれか。またはMayaの番号(0から)。

        Returns:
            Condition: 自身。

        Raises:
            TypeError: operationが文字列・int以外の場合。
            ValueError: 使えない名前、または範囲外の番号を指定した場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込みを拒否した場合。
        """
        ...
    def getResult(self) -> tuple[float, float, float]:
        """出力 ``outColor`` の現在の値を取得する。

        Returns:
            tuple[float, float, float]: 比較の結果の色(RGB)。
        """
        ...
    def getOutputPlug(self) -> Plug:
        """出力のアトリビュート ``outColor`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        ...
