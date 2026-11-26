# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""エクスプレッションのノードを作り、そのノードを返す(``cmds.expression`` 相当)。"""

import maya.cmds as cmds
from ..core.shapeBuild import require_name
from ..decorator import _pick_alias, _require_bool
from ..util import _UNSET
from mlib.nodes.node import Node

_UNIT_CONVERSIONS: tuple

def createExpression(string: str, *, name: str | None = ..., alwaysEvaluate: bool = ..., unitConversion: str = ..., n: str | None = ..., ae: bool = ..., uc: str = ...) -> Node:
    """エクスプレッション(expressionノード)を作り、そのノードを返す。

    ``cmds.expression(string=...)`` で作る。式の中のアトリビュートへの代入は、Mayaがexpressionノードとの接続に変える。
    省略した指定はMayaへ渡さず、Mayaの既定のままにする。現在の選択は変えない。
    Mayaのコマンドの1回なので、Undoが有効なら1回で戻せる。fast引数は無い(OpenMayaに式を解釈して接続する機能が無いため)。
    name・alwaysEvaluate・unitConversionは ``cmds.expression`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        string (str): 式(MELのエクスプレッションの文)。空でない文字列。
        name (str | None): 付けたい名前。NoneならMayaの既定の名前(``expression1`` など)。既定はNone。
        alwaysEvaluate (bool): Trueなら、入力が変わらなくても毎回評価する。省略するとMayaの既定(True)。
        unitConversion (str): 単位の換算。``"all"``・``"none"``・``"angularOnly"`` のどれか。省略するとMayaの既定(``"all"``)。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        ae (bool): alwaysEvaluateの短縮名。alwaysEvaluateと同時には指定できない。
        uc (str): unitConversionの短縮名。unitConversionと同時には指定できない。

    Returns:
        Node: 作ったexpressionノード。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、stringかnameが文字列でない場合、
            またはalwaysEvaluateがboolでない場合。
        ValueError: stringが空文字列の場合、nameが空文字列か ``|`` を含む場合、またはunitConversionが対応していない値の場合。
        RuntimeError: 式に誤りがある場合など、Mayaが作成を拒否した場合。

    Examples:
        >>> import mlib
        >>> node = mlib.createExpression("pCube1.ty = sin(frame);", name="bounce_EXP", alwaysEvaluate=False)
    """
    ...
