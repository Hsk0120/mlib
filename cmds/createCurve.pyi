# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""点の並びからNURBSカーブを作り、シェイプを返す(``cmds.curve`` 相当)。"""

import math
from typing import Any, Dict
import maya.cmds as cmds
from ..core import geometryEdit as geometry_edit
from ..core.shapeBuild import finish_shape, require_name, resolve_parent
from ..decorator import _pick_alias, _require_bool, nativeUnits, preservedSelection, undoTransaction
from ..util import _UNSET
from typing import Iterable, Sequence
from mlib.nodes.node import Node
from mlib.nodes.nurbsCurve import NurbsCurve
import maya.api.OpenMaya as om2


def createCurve(points: Iterable[Sequence[float] | om2.MPoint | om2.MVector], degree: int = ..., closed: bool = ..., knots: Sequence[float] | None = ..., name: str | None = ..., parent: Node | str | None = ..., *, d: int = ..., n: str | None = ...) -> NurbsCurve:
    """点の並びからNURBSカーブを作り、そのシェイプを返す。

    点はそのままCVにする(点を通るように補間するのではない)。距離はMaya APIの内部単位(cm)で指定し、
    現在のUI単位には左右されない。作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。

    - 開いたカーブで ``knots`` を省略すると、``cmds.curve`` の既定のノットにする。
    - ``closed=True`` なら、先頭の ``degree`` 個のCVを末尾へ重ねた周期カーブにする
      (``getForm()`` が ``om2.MFnNurbsCurve.kPeriodic`` になる)。

    fast引数は無い(OpenMayaで作っても約1.4倍にしかならず、効果がほぼ無いため)。
    degree・nameは ``cmds.curve`` と同じ短縮名 ``d``・``n`` でも指定できる(長い名前と短縮名は同時に指定できない)。
    parentの短縮名は無い(``cmds.curve`` の ``p`` はpointのため)。

    Args:
        points (Iterable[Sequence[float] | om2.MPoint | om2.MVector]): CVの位置。各点は3つの
            有限な数値(boolは除く)。MPointはwで割らずにXYZを使う。座標はカーブのTransformの
            ローカル座標(作成時は単位マトリクス)で、単位はcm。
        degree (int): 次数。1・2・3のどれか。既定は1。
        closed (bool): Trueなら閉じたカーブにする。既定はFalse。
        knots (Sequence[float] | None): 開いたカーブのノットの並び(``cmds.curve`` の ``knot``)。
            個数は ``CV数 + degree - 1``。Noneなら既定のノット。``closed=True`` とは同時に指定できない。
        name (str | None): Transformに付けたい名前。シェイプは ``<名前>Shape`` になる。
            NoneならMayaの既定の名前(``curve1`` など)。既定はNone。
        parent (Node | str | None): Transformの親。Noneならワールド直下。親のローカル空間に
            単位マトリクスで置くため、点は親の空間の座標になる。
        d (int): degreeの短縮名。degreeと同時には指定できない。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        NurbsCurve: 作ったカーブのシェイプ。Transformは ``getTransform()`` で取得する。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、
            またはpoints・degree・closed・knots・name・parentの型が正しくない場合。
        ValueError: degreeが1〜3でない場合、点の成分が3つでないか有限でない場合、点の数が足りない場合
            (開いたカーブはdegree+1点以上、閉じたカーブは3点以上かつdegree点以上が必要)、
            knotsの個数や値が正しくない場合、またはclosedとknotsを同時に指定した場合。
        RuntimeError: 親が無効な場合、またはMayaが作成を拒否した場合。

    Examples:
        >>> import mlib
        >>> shape = mlib.createCurve([(0, 0, 0), (1, 0, 0), (1, 1, 0)], degree=1, name="line")
        >>> transform = shape.getTransform()
        >>> loop = mlib.createCurve([(1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)], degree=3, closed=True)
    """
    ...

def _knot_list(knots: Sequence[float], count: int) -> list[float]:
    """ノットの並びを確かめて、floatのリストにする。

    Args:
        knots (Sequence[float]): ノットの並び。
        count (int): 必要な個数。

    Returns:
        list[float]: 確かめたノットの並び。

    Raises:
        TypeError: 順に取り出せない場合、または数値でないものを含む場合。
        ValueError: 個数が違う場合、有限でない場合、または値が途中で減る場合。
    """
    ...
