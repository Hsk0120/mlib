# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""カーブの長さ等を取得する。"""

from . import _calculation
from .node import Node
from mlib.nodes.nurbsCurve import NurbsCurve
from mlib.nodes.transform import Transform
from mlib.plugs.plug import Plug

_GEOMETRY: dict


class CurveInfo(Node):
    """カーブの長さ・CVの位置・ノット等を出力する。"""
    def setInput(self, inputCurve: NurbsCurve | Transform | Plug | str | None = ...) -> CurveInfo:
        """主な入力をまとめて設定する。値は書き込み、Plugは接続する。

        各入力は、渡したものの種類で扱いが変わる。

        - Plug・MPlug・``"node.attr"`` の文字列: 接続元として接続する。すでにある入力の接続は置き換える。
        - それ以外: 値として書き込む。入力が接続されていれば、先に接続を外す。
        - None: その入力は変更しない。

        まとめて1回のUndoで戻せる。

        Args:
            inputCurve (NurbsCurve | Transform | Plug | str | None): 対象のカーブ。シェイプを渡すと、そのworldSpaceを接続する。
                シェイプを1つだけ持つTransformを渡してもよい。

        Returns:
            CurveInfo: 自身。

        Raises:
            TypeError: 接続元の型が不正な場合。
            ValueError: inputCurveに渡したTransformが、対応するシェイプをちょうど1つ持っていない場合。
            RuntimeError: ノードが無効な場合、またはMayaが書き込みや接続を拒否した場合。それまでの変更は元に戻す。
        """
        ...
    def getResult(self) -> float:
        """出力 ``arcLength`` の現在の値を取得する。

        Returns:
            float: カーブの長さ(cm)。
        """
        ...
    def getOutputPlug(self) -> Plug:
        """出力のアトリビュート ``arcLength`` を取得する(接続元に使う)。

        Returns:
            Plug: 出力のアトリビュート。
        """
        ...
