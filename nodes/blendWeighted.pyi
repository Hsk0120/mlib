# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ウェイト付き加算ノード。ウェイトの正規化はしない。"""

from . import _calculation
from .node import Node
from mlib.plugs.plug import Plug



class BlendWeighted(Node):
    """input[i] * weight[i]を合計する。weightの既定値は1。"""
    def addInput(self, value: float | Plug | str, weight: float | Plug | str = ...) -> int:
        """入力とウェイトを末尾へ足す。

        足す番号は、今ある入力の最大の番号+1になる。足した番号を返す。1回のUndoで戻せる。

        Args:
            value (float | Plug | str): 入力の値、または接続元。``input[i]`` に入る。
            weight (float | Plug | str): ウェイトの値、または接続元。``weight[i]`` に入る。

        Returns:
            int: 足した入力の論理番号。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込み・接続を拒否した場合。
        """
        ...
    def removeInput(self, index: int) -> BlendWeighted:
        """入力を削除する。

        同じ番号のウェイトも一緒に削除する。つながっている接続も外れる。1回のUndoで戻せる。

        Args:
            index (int): 削除する入力の論理番号。

        Returns:
            BlendWeighted: 自身。

        Raises:
            TypeError: indexがint以外の場合。
            ValueError: indexの番号の入力が無い場合。
            RuntimeError: ノードが無効な場合、またはMayaが削除を拒否した場合。
        """
        ...
    def getInputIndices(self) -> list[int]:
        """今ある入力の論理番号を取得する。

        Returns:
            list[int]: 論理番号。小さい順に並ぶ。
        """
        ...
    def getResult(self) -> float:
        """出力 ``output`` の現在の値を取得する。

        Returns:
            float: input[i] * weight[i] の合計。
        """
        ...
    def getOutputPlug(self) -> Plug:
        """出力のアトリビュート ``output`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        ...
