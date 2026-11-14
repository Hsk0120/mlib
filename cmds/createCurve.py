"""点の並びからNURBSカーブを作り、シェイプを返す(``cmds.curve`` 相当)。

点はそのままCVにする(点を通るように補間するのではない)。距離はMaya APIの内部単位(cm)で指定し、
現在のUI単位には左右されない。作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。

.. code-block:: python

    import mlib

    shape = mlib.createCurve([(0, 0, 0), (1, 0, 0), (1, 1, 0)], degree=1, name="line")
    transform = shape.getTransform()
    loop = mlib.createCurve([(1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)], degree=3, closed=True)
"""

import math
from typing import Any, Dict

import maya.cmds as cmds

from ..core import geometryEdit as geometry_edit
from ..core.shapeBuild import finish_shape, require_name, resolve_parent
from ..decorator import _pick_alias, _require_bool, nativeUnits, preservedSelection, undoTransaction
from ..util import _UNSET


def createCurve(points, degree=_UNSET, closed=False, knots=None, name=_UNSET, parent=None, *, d=_UNSET, n=_UNSET):
    """点の並びからNURBSカーブを作り、そのシェイプを返す。

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
    """
    degree = _pick_alias(degree, d, "degree", "d", default=1)
    name = _pick_alias(name, n, "name", "n", default=None)
    values = geometry_edit.point_list(points)
    if isinstance(degree, bool) or not isinstance(degree, int):
        raise TypeError("degreeはintで指定してください")
    if degree not in (1, 2, 3):
        raise ValueError(f"degreeは1・2・3のどれかで指定してください: {degree}")
    _require_bool(closed, "closed")
    name = require_name(name)
    if closed:
        if knots is not None:
            raise ValueError("knotsはclosed=Trueと同時に指定できません")
        if len(values) < max(3, degree):
            raise ValueError(f"degree {degree}の閉じたカーブには、点が{max(3, degree)}個以上必要です")
    elif len(values) < degree + 1:
        raise ValueError(f"degree {degree}の開いたカーブには、点が{degree + 1}個以上必要です")
    flags: Dict[str, Any] = {"degree": degree}
    if knots is not None:
        flags["knot"] = _knot_list(knots, len(values) + degree - 1)
    parent_node = resolve_parent(parent)
    if closed:
        count = len(values)
        values = values + values[:degree]
        # 周期カーブのノットは重なるCVの数だけ両端へはみ出す一様な列(CV数 + degree - 1 個)。
        flags["periodic"] = True
        flags["knot"] = [float(knot) for knot in range(-(degree - 1), count + degree)]
    if name:
        flags["name"] = name
    with undoTransaction("mlibCreateCurve"), preservedSelection():
        # cmds.curveの座標は現在のUI単位で解釈されるため、内部単位(cm)へ切り替えて渡す。
        with nativeUnits():
            transform = cmds.curve(point=values, **flags)
        return finish_shape(transform, "nurbsCurve", name, parent_node)


def _knot_list(knots, count):
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
    if isinstance(knots, (str, bytes)):
        raise TypeError("knotsは数値の並びで指定してください")
    try:
        items = list(knots)
    except TypeError:
        raise TypeError("knotsは数値の並びで指定してください") from None
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in items):
        raise TypeError("knotsの要素は数値で指定してください")
    values = [float(value) for value in items]
    if len(values) != count:
        raise ValueError(f"knotsは{count}個の値(CVの数 + degree - 1)で指定してください: {len(values)}個")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("knotsは有限な数値で指定してください")
    if any(b < a for a, b in zip(values, values[1:])):
        raise ValueError("knotsは減少しない並びで指定してください")
    return values
