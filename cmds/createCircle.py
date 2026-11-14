"""NURBSの円を作り、シェイプを返す(``cmds.circle(constructionHistory=False)`` 相当)。"""

import maya.cmds as cmds

from ..core.shapeBuild import finish_shape, require_name, resolve_parent
from ..decorator import _pick_alias, nativeUnits, preservedSelection, undoTransaction
from ..util import _UNSET, _finite, _finite_vector


def createCircle(radius=_UNSET, normal=_UNSET, sections=_UNSET, degree=_UNSET, name=_UNSET, parent=None, *, r=_UNSET, nr=_UNSET, s=_UNSET, d=_UNSET, n=_UNSET):
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
    radius = _pick_alias(radius, r, "radius", "r", default=1.0)
    normal = _pick_alias(normal, nr, "normal", "nr", default=(0, 0, 1))
    sections = _pick_alias(sections, s, "sections", "s", default=8)
    degree = _pick_alias(degree, d, "degree", "d", default=3)
    name = _pick_alias(name, n, "name", "n", default=None)
    radius = _finite(radius, "radius")
    if radius <= 0:
        raise ValueError("radiusは正の値で指定してください")
    normal = _finite_vector(normal, 3, "normal")
    if not any(normal):
        raise ValueError("normalに0のベクトルは指定できません")
    if isinstance(degree, bool) or degree not in (1, 3):
        raise ValueError("degreeは1か3で指定してください")
    if isinstance(sections, bool) or not isinstance(sections, int):
        raise TypeError("sectionsはintで指定してください")
    if sections < (3 if degree == 1 else 4):
        raise ValueError(f"degree {degree}のsectionsは{3 if degree == 1 else 4}以上で指定してください")
    name = require_name(name)
    parent_node = resolve_parent(parent)
    flags = {"radius": radius, "normal": tuple(normal), "sections": sections, "degree": degree, "constructionHistory": False}
    if name:
        flags["name"] = name
    with undoTransaction("mlibCreateCircle"), preservedSelection():
        with nativeUnits():
            transform = cmds.circle(**flags)[0]
        return finish_shape(transform, "nurbsCurve", name, parent_node)
