# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""距離型の2入力を乗算する(Maya 2026以降の型名は ``multDL``)。"""

from . import _calculation
from .node import Node
from mlib.plugs.plug import Plug



class MultDoubleLinear(Node):
    """距離型の2入力を乗算する。

    Maya 2026で ``multDoubleLinear`` は ``multDL`` へ名前が変わった。mlibはどの版でも、
    両方の型名を受け付ける(``createNode``・``ls(type=)``・``isType``)。どちらの型のノードも
    このクラスで扱う。``getType()`` は、その版での実際の型名を返す。
    ``MultDL`` は同じクラスの別名。
    """
    def setInput(self, input1: float | Plug | str | None = ..., input2: float | Plug | str | None = ...) -> MultDoubleLinear:
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            input1 (float | Plug | str | None): 1つ目の値。
            input2 (float | Plug | str | None): 2つ目の値。

        Returns:
            MultDoubleLinear: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込み・接続を拒否した場合(それまでの変更は戻す)。
        """
        ...
    def getResult(self) -> float:
        """出力 ``output`` の現在の値を取得する。

        Returns:
            float: input1 * input2。
        """
        ...
    def getOutputPlug(self) -> Plug:
        """出力のアトリビュート ``output`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        ...
MultDL = MultDoubleLinear
