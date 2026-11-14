# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""マトリクスを移動・回転・スケール・せん断へ分解する。"""

from . import _calculation
from .node import Node
from typing import Iterable
from mlib.maths.matrix import Matrix
from mlib.maths.vector import Vector
from mlib.plugs.plug import Plug

_ROTATE_ORDERS: tuple
_OUTPUTS: dict


class DecomposeMatrix(Node):
    """マトリクスを移動・回転・スケール・せん断・クォータニオンへ分解する。

    親の空間やjointOrientに合わせた補正はしない。
    """
    def setInput(self, inputMatrix: Matrix | Iterable[float] | Plug | str | None = ...) -> DecomposeMatrix:
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            inputMatrix (Matrix | Iterable[float] | Plug | str | None): 分解するマトリクス。

        Returns:
            DecomposeMatrix: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            RuntimeError: ノードが無効な場合、またはMayaが書き込みや接続を拒否した場合。それまでの変更は元に戻す。
        """
        ...
    def getRotateOrder(self) -> str:
        """出力する回転の回転順を名前で取得する。

        ``inputRotateOrder`` の値を名前に直して返す。

        Returns:
            str: ``"xyz"``・``"yzx"``・``"zxy"``・``"xzy"``・``"yxz"``・``"zyx"`` のいずれか。
        """
        ...
    def setRotateOrder(self, order: str | int) -> DecomposeMatrix:
        """出力する回転の回転順を設定する。

        ``inputRotateOrder`` へ書き込む。名前でも番号でも指定できる。1回のUndoで戻せる。

        Args:
            order (str | int): ``"xyz"``・``"yzx"``・``"zxy"``・``"xzy"``・``"yxz"``・``"zyx"`` のいずれか。
                またはMayaの番号(0から)。

        Returns:
            DecomposeMatrix: 自身。

        Raises:
            TypeError: orderが文字列・int以外の場合。
            ValueError: 使えない名前、または範囲外の番号を指定した場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込みを拒否した場合。
        """
        ...
    def getResult(self, kind: str = ...) -> Vector | tuple[float, float, float, float]:
        """出力の現在の値を取得する。

        Args:
            kind (str): 出力の種類。既定は ``"translate"``。

                - ``"translate"``: ``outputTranslate``
                - ``"rotate"``: ``outputRotate``
                - ``"scale"``: ``outputScale``
                - ``"shear"``: ``outputShear``
                - ``"quaternion"``: ``outputQuat``

        Returns:
            Vector | tuple[float, float, float, float]: 分解した値。
                回転は度の ``Vector`` で、回転順は ``inputRotateOrder`` に従う。クォータニオンは ``(x, y, z, w)``。

        Raises:
            ValueError: kindに使えない名前を指定した場合。
        """
        ...
    def getOutputPlug(self, kind: str = ...) -> Plug:
        """出力のアトリビュートを取得する(接続元に使う)。

        Args:
            kind (str): 出力の種類。:meth:`getResult` と同じ。

        Returns:
            Plug: 出力のアトリビュート。

        Raises:
            ValueError: kindに使えない名前を指定した場合。
        """
        ...
