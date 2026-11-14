"""サーフェス上の点の位置・法線・接線を取得する。"""

from . import _calculation
from .node import Node

#: 出力の種類からMayaの出力アトリビュート名。
_OUTPUTS = {
    "position": "position",
    "normal": "normal",
    "normalizedNormal": "normalizedNormal",
    "tangentU": "tangentU",
    "normalizedTangentU": "normalizedTangentU",
    "tangentV": "tangentV",
    "normalizedTangentV": "normalizedTangentV",
}
#: ジオメトリの入力のアトリビュート名からシェイプのMaya型名。
_GEOMETRY = {"inputSurface": "nurbsSurface"}


class PointOnSurfaceInfo(Node):
    """サーフェス上の点の情報を出力するpointOnSurfaceInfoを扱うクラス。

    UVのパラメーターで指定した点の位置・法線・接線を出力する。
    """

    def setInput(self, inputSurface=None, parameterU=None, parameterV=None, turnOnPercentage=None):
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            inputSurface (NurbsSurface | Transform | Plug | str | None): 対象のサーフェス。シェイプを渡すと、そのworldSpaceを接続する。
                シェイプを1つだけ持つTransformを渡した場合も同じ。
            parameterU (float | Plug | str | None): Uパラメーター。
            parameterV (float | Plug | str | None): Vパラメーター。
            turnOnPercentage (bool | Plug | str | None): Trueなら、パラメーターを割合(0〜1)として扱う。

        Returns:
            PointOnSurfaceInfo: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            ValueError: inputSurfaceにTransformを渡し、対応するシェイプが1つだけではない場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込み・接続を拒否した場合(それまでの変更は戻す)。
        """
        return _calculation.set_inputs(
            self,
            "setInput",
            {"inputSurface": inputSurface, "parameterU": parameterU, "parameterV": parameterV, "turnOnPercentage": turnOnPercentage},
            _GEOMETRY,
        )

    def getResult(self, kind="position"):
        """出力の現在の値を取得する。

        Args:
            kind (str): 出力の種類。``"position"`` は ``position``、``"normal"`` は ``normal``、
                ``"normalizedNormal"`` は ``normalizedNormal``、``"tangentU"`` は ``tangentU``、
                ``"normalizedTangentU"`` は ``normalizedTangentU``、``"tangentV"`` は ``tangentV``、
                ``"normalizedTangentV"`` は ``normalizedTangentV``。

        Returns:
            Vector: 計算した値。

        Raises:
            ValueError: kindが未対応の名前の場合。
        """
        return self.getOutputPlug(kind).get()

    def getOutputPlug(self, kind="position"):
        """出力のアトリビュートを取得する(接続元に使う)。

        Args:
            kind (str): 出力の種類。:meth:`getResult` と同じ。

        Returns:
            Plug: 出力のアトリビュート。

        Raises:
            ValueError: kindが未対応の名前の場合。
        """
        return self.getPlug(_OUTPUTS[_calculation.choice(kind, _OUTPUTS, "kind")])
