"""エクスプレッションのノードを作り、そのノードを返す(``cmds.expression`` 相当)。"""

import maya.cmds as cmds

from ..core.shapeBuild import require_name
from ..decorator import _edit_context, _pick_alias, _require_bool
from ..util import _UNSET

#: unitConversionに指定できる値。
_UNIT_CONVERSIONS = ("all", "none", "angularOnly")


def createExpression(string, *, name=_UNSET, alwaysEvaluate=_UNSET, unitConversion=_UNSET, n=_UNSET, ae=_UNSET, uc=_UNSET):
    """エクスプレッション(expressionノード)を作り、そのノードを返す。

    ``cmds.expression(string=...)`` で作る。式の中のアトリビュートへの代入は、Mayaがexpressionノードとの接続に変える。
    省略した指定はMayaへ渡さず、Mayaの既定のままにする。現在の選択は変えない。
    Undoが有効なら1回で戻せる。名前は作ったあとに付ける(Mayaのコマンドのnameフラグは、Redoで名前空間を失うため)。fast引数は無い(OpenMayaに式を解釈して接続する機能が無いため)。
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
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node

    if not isinstance(string, str):
        raise TypeError(f"stringはstrで指定してください: {type(string).__name__}")
    if not string.strip():
        raise ValueError("stringは空でない式で指定してください")
    name = require_name(_pick_alias(name, n, "name", "n", default=None))
    flags = {"string": string}
    always = _pick_alias(alwaysEvaluate, ae, "alwaysEvaluate", "ae", default=None)
    if always is not None:
        _require_bool(always, "alwaysEvaluate")
        flags["alwaysEvaluate"] = always
    conversion = _pick_alias(unitConversion, uc, "unitConversion", "uc", default=None)
    if conversion is not None:
        if conversion not in _UNIT_CONVERSIONS:
            raise ValueError(f"unitConversionは{'・'.join(_UNIT_CONVERSIONS)}のどれかで指定してください: {conversion!r}")
        flags["unitConversion"] = conversion
    # 名前を付けるときは作成と改名の2回になるので、1回のUndoにまとめる。
    with _edit_context("mlibCreateExpression", False, single=not name):
        try:
            created = cmds.expression(**flags)
        except RuntimeError as exc:
            raise RuntimeError(f"Mayaがエクスプレッションの作成を拒否しました: {exc}") from exc
        if name:
            # expressionのnameフラグはRedo時に名前空間を失うため、renameに任せる。
            created = cmds.rename(created, name)
        return Node(created)
