"""複数のマトリクスを順に掛け合わせる。"""

from ..decorator import _edit_context
from . import _calculation
from .node import Node


class MultMatrix(Node):
    """複数のマトリクスを掛け合わせるmultMatrixを扱うクラス。

    ``matrixIn`` のマトリクスを論理番号の順に掛け合わせ、``matrixSum`` へ出力する。
    先頭のマトリクスが最初に適用される。
    """

    def setInput(self, matrices):
        """入力のマトリクスを設定する。

        すでにある入力はすべて取り除き、渡したものに置き換える。渡した順に、論理番号0から設定する。

        - マトリクス: 値として書き込む。
        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。

        1回のUndoで戻せる。

        Args:
            matrices (Iterable[Matrix | Iterable[float] | Plug | str]): 掛け合わせるマトリクスの並び。

        Returns:
            MultMatrix: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込み・接続を拒否した場合(それまでの変更は戻す)。
        """
        matrices = list(matrices)
        self._require_valid("setInput")
        with _edit_context(_calculation.chunk_name(self, "setInput"), False, transaction=True):
            for index in reversed(_calculation.element_indices(self, "matrixIn")):
                _calculation.remove_elements(self, "setInput", ("matrixIn",), index)
            _calculation.set_inputs(self, "setInput", {f"matrixIn[{index}]": matrix for index, matrix in enumerate(matrices)})
        return self

    def addInput(self, matrix):
        """入力のマトリクスを末尾へ足す。

        足す位置の論理番号は、すでにある番号の最大値+1になる。1回のUndoで戻せる。

        Args:
            matrix (Matrix | Iterable[float] | Plug | str): マトリクスの値、または接続元。

        Returns:
            int: 足した入力の論理番号。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込み・接続を拒否した場合。
        """
        return _calculation.add_element(self, "addInput", "matrixIn", {"matrixIn[{index}]": matrix})

    def removeInput(self, index):
        """入力のマトリクスを削除する。

        接続されていれば、接続ごと取り除く。1回のUndoで戻せる。

        Args:
            index (int): 入力の論理番号。

        Returns:
            MultMatrix: 自身。

        Raises:
            TypeError: indexがint以外の場合。
            ValueError: indexの入力が無い場合。
            RuntimeError: ノードが無効な場合、またはMayaが削除を拒否した場合。
        """
        return _calculation.remove_elements(self, "removeInput", ("matrixIn",), index)

    def getInputIndices(self):
        """すでにある入力の論理番号を、小さい順に取得する。

        Returns:
            list[int]: 論理番号。
        """
        return _calculation.element_indices(self, "matrixIn")

    def getResult(self):
        """出力 ``matrixSum`` の現在の値を取得する。

        Returns:
            Matrix: 掛け合わせたマトリクス。
        """
        return self.getOutputPlug().get()

    def getOutputPlug(self):
        """出力のアトリビュート ``matrixSum`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        return self.getPlug("matrixSum")
