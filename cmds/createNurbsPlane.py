"""NURBSの平面を作り、シェイプを返す(``cmds.nurbsPlane(constructionHistory=False)`` 相当)。

幅はMaya APIの内部単位(cm)で指定し、現在のUI単位には左右されない。コンストラクションヒストリは作らない。
作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。リボンの元になる面などに使う。

.. code-block:: python

    import mlib

    shape = mlib.createNurbsPlane(width=10.0, lengthRatio=0.1, patchesU=5, name="ribbon")
    shape = mlib.createNurbsPlane(w=10.0, lr=0.1, u=5, n="ribbon")  # cmds.nurbsPlane と同じ短縮名
"""

import maya.cmds as cmds

from ..core.shapeBuild import finish_shape, positive_size, require_name, resolve_parent
from ..decorator import _pick_alias, nativeUnits, preservedSelection, undoTransaction
from ..util import _UNSET, _finite_vector


def createNurbsPlane(
    width=_UNSET,
    lengthRatio=_UNSET,
    patchesU=_UNSET,
    patchesV=_UNSET,
    axis=_UNSET,
    degree=_UNSET,
    name=_UNSET,
    parent=None,
    *,
    w=_UNSET,
    lr=_UNSET,
    u=_UNSET,
    v=_UNSET,
    ax=_UNSET,
    d=_UNSET,
    n=_UNSET,
):
    """原点を中心とするNURBSの平面を作り、そのシェイプを返す。

    fast引数は無い(OpenMayaでは同じノット・CVの面を組み立て直すことになり、同じ結果を保つのが難しいため)。
    parent以外は ``cmds.nurbsPlane`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。
    U方向が幅(width)、V方向が長さ(``width * lengthRatio``)になる。

    Args:
        width (float): 幅(cm)。正の有限な値。既定は1。
        lengthRatio (float): 幅に対する長さの比。正の有限な値。既定は1。
        patchesU (int): U方向のパッチ(スパン)の数。1以上。既定は1。
        patchesV (int): V方向のパッチ(スパン)の数。1以上。既定は1。
        axis (Sequence[float]): 面の法線。0でない有限な3成分。既定は(0, 1, 0)。
            ``cmds.nurbsPlane`` の既定とは違い、:func:`createPolyPlane <mlib.cmds.createPolyPlane.createPolyPlane>`
            と同じ上向きにしている。
        degree (int): U・V方向の次数。1(直線)または3(曲線)。既定は3。
        name (str | None): Transformに付けたい名前。シェイプは ``<名前>Shape`` になる。
            NoneならMayaの既定の名前(``nurbsPlane1`` など)。既定はNone。
        parent (Node | str | None): Transformの親。Noneならワールド直下。
            親のローカル空間に、単位マトリクスで置く。
        w (float): widthの短縮名。widthと同時には指定できない。
        lr (float): lengthRatioの短縮名。lengthRatioと同時には指定できない。
        u (int): patchesUの短縮名。patchesUと同時には指定できない。
        v (int): patchesVの短縮名。patchesVと同時には指定できない。
        ax (Sequence[float]): axisの短縮名。axisと同時には指定できない。
        d (int): degreeの短縮名。degreeと同時には指定できない。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        NurbsSurface: 作った平面のシェイプ。Transformは ``getTransform()`` で取得する。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、または引数の型が正しくない場合。
        ValueError: 幅や比が0以下か有限でない場合、またはパッチの数・軸・次数が正しくない場合。
        RuntimeError: 親が無効な場合、またはMayaが作成を拒否した場合。
    """
    width = _pick_alias(width, w, "width", "w", default=1.0)
    lengthRatio = _pick_alias(lengthRatio, lr, "lengthRatio", "lr", default=1.0)
    patchesU = _pick_alias(patchesU, u, "patchesU", "u", default=1)
    patchesV = _pick_alias(patchesV, v, "patchesV", "v", default=1)
    axis = _pick_alias(axis, ax, "axis", "ax", default=(0, 1, 0))
    degree = _pick_alias(degree, d, "degree", "d", default=3)
    name = _pick_alias(name, n, "name", "n", default=None)
    width = positive_size(width, "width")
    lengthRatio = positive_size(lengthRatio, "lengthRatio")
    patchesU = _patch_count(patchesU, "patchesU")
    patchesV = _patch_count(patchesV, "patchesV")
    axis = _finite_vector(axis, 3, "axis")
    if not any(axis):
        raise ValueError("axisに0のベクトルは指定できません")
    if isinstance(degree, bool) or not isinstance(degree, int):
        raise TypeError("degreeはintで指定してください")
    if degree not in (1, 3):
        raise ValueError("degreeは1か3で指定してください")
    name = require_name(name)
    parent_node = resolve_parent(parent)
    flags = {
        "width": width,
        "lengthRatio": lengthRatio,
        "patchesU": patchesU,
        "patchesV": patchesV,
        "axis": tuple(axis),
        "degree": degree,
        "constructionHistory": False,
    }
    if name:
        flags["name"] = name
    with undoTransaction("mlibCreateNurbsPlane"), preservedSelection():
        # nurbsPlaneの幅は現在のUI単位で解釈されるため、内部単位(cm)へ切り替えて渡す。
        with nativeUnits():
            transform = cmds.nurbsPlane(**flags)[0]
        return finish_shape(transform, "nurbsSurface", name, parent_node)


def _patch_count(value, name):
    """パッチの数を確かめる。

    Args:
        value (int): パッチの数。boolは受け付けない。
        name (str): 例外メッセージに使う引数名。

    Returns:
        int: 確かめたパッチの数。

    Raises:
        TypeError: intでない場合。
        ValueError: 1より小さい場合。
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name}はintで指定してください")
    if value < 1:
        raise ValueError(f"{name}は1以上で指定してください")
    return value
