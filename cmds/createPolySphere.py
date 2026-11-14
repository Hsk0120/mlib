"""ポリゴンの球を作り、シェイプを返す(``cmds.polySphere(constructionHistory=False)`` 相当)。"""

import maya.cmds as cmds

from ..core.shapeBuild import create_poly, positive_size, require_name, resolve_parent, subdivision_counts
from ..decorator import _pick_alias
from ..util import _UNSET, _finite_vector


def createPolySphere(radius=_UNSET, subdivisions=(20, 20), axis=_UNSET, name=_UNSET, parent=None, *, r=_UNSET, ax=_UNSET, n=_UNSET):
    """原点を中心とするポリゴンの球を作り、そのシェイプを返す。

    大きさはMaya APIの内部単位(cm)で指定し、現在のUI単位には左右されない。コンストラクションヒストリは作らない。
    作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。
    fast引数は無い(Mayaのコマンドと同じUV・法線のメッシュをOpenMayaで組み立て直すことになり、同じ結果を保つのが難しいため)。
    radius・axis・nameは ``cmds.polySphere`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。
    subdivisionsは2方向の分割数をまとめたmlib独自の引数のため、短縮名は無い。

    Args:
        radius (float): 半径(cm)。既定は1。
        subdivisions (Sequence[int]): 軸のまわり・軸方向の分割数(``subdivisionsAxis``・``subdivisionsHeight``)。既定は(20, 20)。
        axis (Sequence[float]): 極の方向。0でない有限な3成分。既定は(0, 1, 0)。
        name (str | None): Transformに付けたい名前。シェイプは ``<名前>Shape`` になる。
            NoneならMayaの既定の名前。既定はNone。
        parent (Node | str | None): Transformの親。Noneならワールド直下。
            親のローカル空間に、単位マトリクスで置く。
        r (float): radiusの短縮名。radiusと同時には指定できない。
        ax (Sequence[float]): axisの短縮名。axisと同時には指定できない。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        Mesh: 作ったメッシュのシェイプ。Transformは ``getTransform()`` で取得する。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、または引数の型が正しくない場合。
        ValueError: 大きさが0以下か有限でない場合、または分割数や軸が正しくない場合。
        RuntimeError: 親が無効な場合、またはMayaが作成を拒否した場合。

    Examples:
        >>> import mlib
        >>> shape = mlib.createPolySphere(radius=2.0, subdivisions=(16, 12), name="ball")
        >>> transform = shape.getTransform()
    """
    radius = _pick_alias(radius, r, "radius", "r", default=1.0)
    axis = _pick_alias(axis, ax, "axis", "ax", default=(0, 1, 0))
    name = _pick_alias(name, n, "name", "n", default=None)
    around, along = subdivision_counts(subdivisions, 2)
    axis = _axis(axis)
    flags = {"radius": positive_size(radius, "radius"), "subdivisionsAxis": around, "subdivisionsHeight": along, "axis": axis}
    return create_poly(cmds.polySphere, flags, require_name(name), resolve_parent(parent))


def _axis(value):
    """軸の方向を確かめる。

    Args:
        value (Sequence[float]): 方向。

    Returns:
        tuple[float, float, float]: 確かめた方向。

    Raises:
        TypeError: 数値の並びでない場合。
        ValueError: 成分が3つでない場合、有限でない場合、または0の場合。
    """
    axis = _finite_vector(value, 3, "axis")
    if not any(axis):
        raise ValueError("axisに0のベクトルは指定できません")
    return axis
