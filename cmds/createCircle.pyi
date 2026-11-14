# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""NURBSの円を作り、シェイプを返す(``cmds.circle(constructionHistory=False)`` 相当)。"""

import maya.cmds as cmds
from ..core.shapeBuild import finish_shape, require_name, resolve_parent
from ..decorator import _pick_alias, nativeUnits, preservedSelection, undoTransaction
from ..util import _UNSET, _finite, _finite_vector
from typing import Sequence
from mlib.nodes.node import Node
from mlib.nodes.nurbsCurve import NurbsCurve


def createCircle(radius: float = ..., normal: Sequence[float] = ..., sections: int = ..., degree: int = ..., name: str | None = ..., parent: Node | str | None = ..., *, r: float = ..., nr: Sequence[float] = ..., s: int = ..., d: int = ..., n: str | None = ...) -> NurbsCurve:
    """原点を中心とするNURBSの円を作り、そのシェイプを返す。

    半径はMaya APIの内部単位(cm)で指定し、現在のUI単位には左右されない。コンストラクションヒストリは作らない。
    作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。
    fast引数は無い(OpenMayaに円を作る同じ機能が無いため)。
    parent以外は ``cmds.circle`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        radius (float): 半径(cm)。正の有限な値。既定は1。
        normal (Sequence[float]): 円の面の法線。0でない有限な3成分。既定は(0, 0, 1)。
        sections (int): 区間の数。degree=1なら3以上、degree=3なら4以上。既定は8。
        degree (int): 1(直線)または3(曲線)。既定は3。
        name (str | None): Transformに付けたい名前。シェイプは ``<名前>Shape`` になる。
            NoneならMayaの既定の名前(``nurbsCircle1`` など)。既定はNone。
        parent (Node | str | None): Transformの親。Noneならワールド直下。
            親のローカル空間に、単位マトリクスで置く。
        r (float): radiusの短縮名。radiusと同時には指定できない。
        nr (Sequence[float]): normalの短縮名。normalと同時には指定できない。
        s (int): sectionsの短縮名。sectionsと同時には指定できない。
        d (int): degreeの短縮名。degreeと同時には指定できない。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        NurbsCurve: 作った円のシェイプ。Transformは ``getTransform()`` で取得する。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、または引数の型が正しくない場合。
        ValueError: 半径・法線・区間の数・次数が正しくない場合。
        RuntimeError: 親が無効な場合、またはMayaが作成を拒否した場合。

    Examples:
        >>> import mlib
        >>> shape = mlib.createCircle(radius=2.0, normal=(0, 1, 0), name="ring")
        >>> shape = mlib.createCircle(r=2.0, nr=(0, 1, 0), n="ring")  # cmds.circle と同じ短縮名
    """
    ...
