"""マルチアトリビュートの入力の加算・減算・平均を計算する。"""

from . import _calculation
from .shadingDependNode import ShadingDependNode

#: 演算の種類の名前(Mayaの ``operation`` の番号順)。
_OPERATIONS = ("noOperation", "sum", "subtract", "average")
#: 入力の次元から、入力・出力のアトリビュート名。
_ATTRIBUTES = {1: ("input1D", "output1D"), 2: ("input2D", "output2D"), 3: ("input3D", "output3D")}


def _attributes(dimension):
    """入力の次元を検証し、(入力, 出力)のアトリビュート名を返す。

    Args:
        dimension (int): 1・2・3。

    Returns:
        tuple[str, str]: 入力のマルチアトリビュート名と出力のアトリビュート名。

    Raises:
        TypeError: dimensionがハッシュできない型(list等)の場合。
        ValueError: dimensionが1・2・3以外の場合。
    """
    try:
        attributes = None if isinstance(dimension, bool) else _ATTRIBUTES.get(dimension)
    except TypeError:
        raise TypeError(f"dimensionは1・2・3のどれかで指定してください: ハッシュできない{type(dimension).__name__}") from None
    if attributes is None:
        raise ValueError(f"dimensionは1・2・3のどれかで指定してください: {dimension!r}")
    return attributes


class PlusMinusAverage(ShadingDependNode):
    """マルチアトリビュートの入力の加算・減算・平均を計算するplusMinusAverageを扱うクラス。

    入力は1次元(``input1D``)・2次元(``input2D``)・3次元(``input3D``)の3組がある。
    どれを使うかは、各メソッドの ``dimension`` で選ぶ(既定は1)。
    """

    def getOperation(self):
        """演算の種類を名前で取得する(``operation``)。

        Returns:
            str: ``"noOperation"``・``"sum"``・``"subtract"``・``"average"`` のいずれか。
        """
        return _calculation.get_enum(self, "operation", _OPERATIONS)

    def setOperation(self, operation):
        """演算の種類を設定する(``operation``)。

        名前か番号で指定する。1回のUndoで戻せる。

        Args:
            operation (str | int): ``"noOperation"``・``"sum"``・``"subtract"``・``"average"`` のいずれか、
                Mayaの番号(0から)でもよい。

        Returns:
            PlusMinusAverage: 自身。

        Raises:
            TypeError: operationが文字列・int以外の場合。
            ValueError: 対応していない名前、または範囲外の番号の場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込みを拒否した場合。
        """
        return _calculation.set_enum(self, "setOperation", "operation", operation, _OPERATIONS, "operation")

    def addInput(self, value, dimension=1):
        """入力を末尾へ足す。

        足す位置の論理番号は、すでにある番号の最大値+1になる。1回のUndoで戻せる。

        Args:
            value (float | Iterable[float] | Plug | str): 書き込む値、または接続元。2・3次元では成分を並べて渡す。
            dimension (int): 入力の次元。1・2・3。

        Returns:
            int: 足した入力の論理番号。

        Raises:
            TypeError: 接続元の型が不正な場合、またはdimensionがハッシュできない型(list等)の場合。
            ValueError: dimensionが1・2・3以外の場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込み・接続を拒否した場合。
        """
        attribute = _attributes(dimension)[0]
        return _calculation.add_element(self, "addInput", attribute, {attribute + "[{index}]": value})

    def removeInput(self, index, dimension=1):
        """入力の要素を削除する。

        接続されていれば、接続ごと取り除く。1回のUndoで戻せる。

        Args:
            index (int): 入力の論理番号。
            dimension (int): 入力の次元。1・2・3。

        Returns:
            PlusMinusAverage: 自身。

        Raises:
            TypeError: indexがint以外の場合、またはdimensionがハッシュできない型(list等)の場合。
            ValueError: dimensionが1・2・3以外の場合、またはindexの入力が無い場合。
            RuntimeError: ノードが無効な場合、またはMayaが削除を拒否した場合。
        """
        return _calculation.remove_elements(self, "removeInput", (_attributes(dimension)[0],), index)

    def getInputIndices(self, dimension=1):
        """すでにある入力の論理番号を、小さい順に取得する。

        Args:
            dimension (int): 入力の次元。1・2・3。

        Returns:
            list[int]: 論理番号。

        Raises:
            TypeError: dimensionがハッシュできない型(list等)の場合。
            ValueError: dimensionが1・2・3以外の場合。
        """
        return _calculation.element_indices(self, _attributes(dimension)[0])

    def getResult(self, dimension=1):
        """出力の現在の値を取得する。

        Args:
            dimension (int): 出力の次元。1・2・3。

        Returns:
            float | tuple: 1次元はfloat、2・3次元は成分のtuple。

        Raises:
            TypeError: dimensionがハッシュできない型(list等)の場合。
            ValueError: dimensionが1・2・3以外の場合。
        """
        return self.getOutputPlug(dimension).get()

    def getOutputPlug(self, dimension=1):
        """出力のアトリビュートを取得する(接続元に使う)。

        Args:
            dimension (int): 出力の次元。1・2・3。

        Returns:
            Plug: ``output1D``・``output2D``・``output3D`` のいずれか。

        Raises:
            TypeError: dimensionがハッシュできない型(list等)の場合。
            ValueError: dimensionが1・2・3以外の場合。
        """
        return self.getPlug(_attributes(dimension)[1])
