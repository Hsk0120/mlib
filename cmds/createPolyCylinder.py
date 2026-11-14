"""ポリゴンの円柱を作り、シェイプを返す(``cmds.polyCylinder(constructionHistory=False)`` 相当)。

大きさはMaya APIの内部単位(cm)で指定し、現在のUI単位には左右されない。コンストラクションヒストリは作らない。
作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。

.. code-block:: python

    import mlib

    shape = mlib.createPolyCylinder(radius=0.5, height=4.0, axis=(1, 0, 0), name="bone")
    transform = shape.getTransform()
"""

import maya.cmds as cmds

from ..core.shapeBuild import create_poly, positive_size, require_name, resolve_parent, subdivision_counts
from ..decorator import _pick_alias
from ..util import _UNSET, _finite_vector


def createPolyCylinder(
    radius=_UNSET, height=_UNSET, subdivisions=(20, 1, 1), axis=_UNSET, name=_UNSET, parent=None, *, r=_UNSET, h=_UNSET, ax=_UNSET, n=_UNSET
):
    """原点を中心とするポリゴンの円柱を作り、そのシェイプを返す。

    fast引数は無い(Mayaのコマンドと同じUV・法線のメッシュをOpenMayaで組み立て直すことになり、同じ結果を保つのが難しいため)。
    radius・height・axis・nameは ``cmds.polyCylinder`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。
    subdivisionsは ``subdivisionsX/Y/Z`` をまとめたmlib独自の引数のため、短縮名は無い。

    Args:
        radius (float): 半径(cm)。既定は1。
        height (float): 高さ(cm)。既定は2。
        subdivisions (Sequence[int]): 軸のまわり・高さ方向・ふたの分割数(``subdivisionsX/Y/Z``)。既定は(20, 1, 1)。
        axis (Sequence[float]): 円柱の軸の方向。0でない有限な3成分。既定は(0, 1, 0)。
        name (str | None): Transformに付けたい名前。シェイプは ``<名前>Shape`` になる。
            NoneならMayaの既定の名前。既定はNone。
        parent (Node | str | None): Transformの親。Noneならワールド直下。
            親のローカル空間に、単位マトリクスで置く。
        r (float): radiusの短縮名。radiusと同時には指定できない。
        h (float): heightの短縮名。heightと同時には指定できない。
        ax (Sequence[float]): axisの短縮名。axisと同時には指定できない。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        Mesh: 作ったメッシュのシェイプ。Transformは ``getTransform()`` で取得する。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、または引数の型が正しくない場合。
        ValueError: 大きさが0以下か有限でない場合、または分割数や軸が正しくない場合。
        RuntimeError: 親が無効な場合、またはMayaが作成を拒否した場合。
    """
    radius = _pick_alias(radius, r, "radius", "r", default=1.0)
    height = _pick_alias(height, h, "height", "h", default=2.0)
    axis = _pick_alias(axis, ax, "axis", "ax", default=(0, 1, 0))
    name = _pick_alias(name, n, "name", "n", default=None)
    sx, sy, sz = subdivision_counts(subdivisions, 3)
    flags = {
        "radius": positive_size(radius, "radius"),
        "height": positive_size(height, "height"),
        "subdivisionsX": sx,
        "subdivisionsY": sy,
        "subdivisionsZ": sz,
        "axis": _axis(axis),
    }
    return create_poly(cmds.polyCylinder, flags, require_name(name), resolve_parent(parent))


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
