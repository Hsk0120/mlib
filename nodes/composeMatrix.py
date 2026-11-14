"""移動・回転・スケール・せん断からマトリクスを作る。"""

from . import _calculation
from .node import Node

#: 回転の回転順の名前(Mayaの ``inputRotateOrder`` の番号順)。
_ROTATE_ORDERS = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")


class ComposeMatrix(Node):
    """移動・回転(オイラー角またはクォータニオン)・スケール・せん断からマトリクスを作る。"""

    def setInput(self, inputTranslate=None, inputRotate=None, inputScale=None, inputShear=None, inputQuat=None, useEulerRotation=None):
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            inputTranslate (Iterable[float] | Plug | str | None): 移動(cm)。
            inputRotate (Iterable[float] | Plug | str | None): 回転(度)。
            inputScale (Iterable[float] | Plug | str | None): スケール。
            inputShear (Iterable[float] | Plug | str | None): せん断。
            inputQuat (Iterable[float] | Plug | str | None): 回転のクォータニオン(XYZW)。useEulerRotationがFalseのときに使われる。
            useEulerRotation (bool | Plug | str | None): 回転の与え方。Trueならオイラー角(inputRotate)、
                Falseならクォータニオン(inputQuat)を使う。

        Returns:
            ComposeMatrix: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書き込みや接続を拒否した場合。それまでの変更は元に戻す。
        """
        return _calculation.set_inputs(
            self,
            "setInput",
            {
                "inputTranslate": inputTranslate,
                "inputRotate": inputRotate,
                "inputScale": inputScale,
                "inputShear": inputShear,
                "inputQuat": inputQuat,
                "useEulerRotation": useEulerRotation,
            },
        )

    def getRotateOrder(self):
        """回転順を名前で取得する。

        ``inputRotateOrder`` の値を名前に直して返す。

        Returns:
            str: ``"xyz"``・``"yzx"``・``"zxy"``・``"xzy"``・``"yxz"``・``"zyx"`` のいずれか。
        """
        return _calculation.get_enum(self, "inputRotateOrder", _ROTATE_ORDERS)

    def setRotateOrder(self, order):
        """回転順を設定する。

        ``inputRotateOrder`` へ書き込む。名前でも番号でも指定できる。1回のUndoで戻せる。

        Args:
            order (str | int): ``"xyz"``・``"yzx"``・``"zxy"``・``"xzy"``・``"yxz"``・``"zyx"`` のいずれか。
                またはMayaの番号(0から)。

        Returns:
            ComposeMatrix: 自身。

        Raises:
            TypeError: orderが文字列・int以外の場合。
            ValueError: 使えない名前、または範囲外の番号を指定した場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込みを拒否した場合。
        """
        return _calculation.set_enum(self, "setRotateOrder", "inputRotateOrder", order, _ROTATE_ORDERS, "order")

    def getResult(self):
        """出力 ``outputMatrix`` の現在の値を取得する。

        Returns:
            Matrix: 作ったマトリクス。
        """
        return self.getOutputPlug().get()

    def getOutputPlug(self):
        """出力のアトリビュート ``outputMatrix`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        return self.getPlug("outputMatrix")
