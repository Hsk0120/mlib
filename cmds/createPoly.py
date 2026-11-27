"""ポリゴンの立方体・球・円柱・平面を作り、シェイプを返す(``cmds.polyCube``・``polySphere``・``polyCylinder``・``polyPlane`` 相当)。"""

import maya.cmds as cmds

from ..core.shapeBuild import create_poly, poly_history_flags, positive_size, require_name, resolve_parent, subdivision_counts
from ..decorator import _pick_alias, _require_bool
from ..util import _UNSET, _finite_vector, _require_choice

#: 省略した引数の印(``_pick_alias`` の既定の値に使う。``_UNSET`` は必須の印なので使えない)。
_OMITTED = object()
#: 形ごとの、Mayaのコマンド名・大きさの引数と既定値・分割数のフラグ名と既定値・axisとroundCapを受けるか。
_SHAPES = {
    "cube": ("polyCube", {"width": 1.0, "height": 1.0, "depth": 1.0}, ("subdivisionsX", "subdivisionsY", "subdivisionsZ"), (1, 1, 1), False, False),
    "sphere": ("polySphere", {"radius": 1.0}, ("subdivisionsAxis", "subdivisionsHeight"), (20, 20), True, False),
    "cylinder": ("polyCylinder", {"radius": 1.0, "height": 2.0}, ("subdivisionsX", "subdivisionsY", "subdivisionsZ"), (20, 1, 1), True, True),
    "plane": ("polyPlane", {"width": 1.0, "height": 1.0}, ("subdivisionsX", "subdivisionsY"), (10, 10), True, False),
}


def createPoly(
    kind,
    *,
    width=_UNSET,
    w=_UNSET,
    height=_UNSET,
    h=_UNSET,
    depth=_UNSET,
    d=_UNSET,
    radius=_UNSET,
    r=_UNSET,
    subdivisions=_UNSET,
    axis=_UNSET,
    ax=_UNSET,
    roundCap=_UNSET,
    rcp=_UNSET,
    name=_UNSET,
    n=_UNSET,
    parent=None,
    constructionHistory=_UNSET,
    ch=_UNSET,
    createUVs=_UNSET,
    cuv=_UNSET,
):
    """原点を中心とするポリゴンの立方体・球・円柱・平面を作り、そのシェイプを返す。

    作る形は ``kind`` で選ぶ。形ごとに使える引数と既定値は次のとおり。その形で使えない引数を指定するとTypeError。

    - ``"cube"``(``cmds.polyCube``): width・height・depth(既定はどれも1)、subdivisionsはX・Y・Zの分割数
      (``subdivisionsX/Y/Z``。既定は(1, 1, 1))。axisは無い。
    - ``"sphere"``(``cmds.polySphere``): radius(既定は1)、subdivisionsは軸のまわり・軸方向の分割数
      (``subdivisionsAxis``・``subdivisionsHeight``。既定は(20, 20))、axisは極の方向。
    - ``"cylinder"``(``cmds.polyCylinder``): radius(既定は1)・height(既定は2)、subdivisionsは軸のまわり・高さ方向・ふたの分割数
      (``subdivisionsX/Y/Z``。既定は(20, 1, 1))、axisは円柱の軸の方向、roundCap。
    - ``"plane"``(``cmds.polyPlane``): width・height(高さは奥行き方向の長さ。既定はどちらも1)、subdivisionsは幅・高さ方向の分割数
      (``subdivisionsX/Y``。既定は(10, 10))、axisは面の法線。

    大きさはMaya APIの内部単位(cm)で指定し、現在のUI単位には左右されない。
    既定ではコンストラクションヒストリを作らない。``constructionHistory=True`` なら作成ノード(``polyCube`` などのノード)を残し、
    ``shape.getHistory(type="polyCube")`` のように取得できる(作成ノードの大きさのアトリビュートもcm)。
    作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。Undoチャンク名は形ごとに ``mlibCreatePolyCube`` などになる。
    fast引数は無い(Mayaのコマンドと同じUV・法線のメッシュをOpenMayaで組み立て直すことになり、同じ結果を保つのが難しいため)。
    width・height・depth・radius・axis・roundCap・nameは、Mayaのコマンドと同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。
    subdivisionsは複数の分割数をまとめたmlib独自の引数のため、短縮名は無い。

    Args:
        kind (str): 作る形。``"cube"``・``"sphere"``・``"cylinder"``・``"plane"`` のどれか。
        width (float): 幅(cm)。cube・planeだけ。
        w (float): widthの短縮名。widthと同時には指定できない。
        height (float): 高さ(cm)。cube・cylinder・planeだけ。
        h (float): heightの短縮名。heightと同時には指定できない。
        depth (float): 奥行き(cm)。cubeだけ。
        d (float): depthの短縮名。depthと同時には指定できない。
        radius (float): 半径(cm)。sphere・cylinderだけ。
        r (float): radiusの短縮名。radiusと同時には指定できない。
        subdivisions (Sequence[int]): 分割数。数と意味は形ごとに違う(上の一覧)。
        axis (Sequence[float]): 形の向き。0でない有限な3成分。既定は(0, 1, 0)。cube以外。
        ax (Sequence[float]): axisの短縮名。axisと同時には指定できない。
        roundCap (bool): Trueなら、ふたを丸くする(丸みの分割数はsubdivisionsの3つ目)。既定はFalse。cylinderだけ。
        rcp (bool): roundCapの短縮名。roundCapと同時には指定できない。
        name (str | None): Transformに付けたい名前。シェイプは ``<名前>Shape`` になる。
            NoneならMayaの既定の名前。既定はNone。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        parent (Node | str | None): Transformの親。Noneならワールド直下。
            親のローカル空間に、単位マトリクスで置く。既定はNone。
        constructionHistory (bool): Trueなら、コンストラクションヒストリ(作成ノード)を残す。既定はFalse。
        ch (bool): constructionHistoryの短縮名。constructionHistoryと同時には指定できない。
        createUVs (int): UVの作り方。Mayaのコマンドの ``createUVs`` と同じ番号(0はUVを作らない)。省略するとMayaの既定。
        cuv (int): createUVsの短縮名。createUVsと同時には指定できない。

    Returns:
        Mesh: 作ったメッシュのシェイプ。Transformは ``getTransform()`` で取得する。

    Raises:
        TypeError: kindが文字列でない場合、その形で使えない引数を指定した場合、長い名前と短縮名を同時に指定した場合、
            または引数の型が正しくない場合。
        ValueError: kindが上のどれでもない場合、大きさが0以下か有限でない場合、分割数や軸が正しくない場合、
            またはcreateUVsが負の場合。
        RuntimeError: 親が無効な場合、またはMayaが作成を拒否した場合。

    Examples:
        >>> import mlib
        >>> box = mlib.createPoly("cube", width=2.0, height=1.0, depth=1.0, subdivisions=(4, 1, 1), name="box")
        >>> ball = mlib.createPoly("sphere", radius=2.0, subdivisions=(16, 12), name="ball")
        >>> bone = mlib.createPoly("cylinder", radius=0.5, height=4.0, axis=(1, 0, 0), name="bone")
        >>> floor = mlib.createPoly("plane", width=10.0, height=10.0, subdivisions=(4, 4), name="floor")
        >>> transform = box.getTransform()
    """
    kind = _require_choice(kind, "kind", tuple(_SHAPES))
    command, sizes, subdivision_flags, subdivision_default, has_axis, has_round_cap = _SHAPES[kind]
    given = {
        "width": _pick_alias(width, w, "width", "w", default=_OMITTED),
        "height": _pick_alias(height, h, "height", "h", default=_OMITTED),
        "depth": _pick_alias(depth, d, "depth", "d", default=_OMITTED),
        "radius": _pick_alias(radius, r, "radius", "r", default=_OMITTED),
        "axis": _pick_alias(axis, ax, "axis", "ax", default=_OMITTED),
        "roundCap": _pick_alias(roundCap, rcp, "roundCap", "rcp", default=_OMITTED),
    }
    allowed = set(sizes)
    if has_axis:
        allowed.add("axis")
    if has_round_cap:
        allowed.add("roundCap")
    unusable = [key for key, value in given.items() if value is not _OMITTED and key not in allowed]
    if unusable:
        raise TypeError(f"kind={kind!r}では{'・'.join(unusable)}を指定できません")
    name = _pick_alias(name, n, "name", "n", default=None)
    counts = subdivision_counts(subdivision_default if subdivisions is _UNSET else subdivisions, len(subdivision_flags))
    flags = {key: positive_size(default if given[key] is _OMITTED else given[key], key) for key, default in sizes.items()}
    flags.update(zip(subdivision_flags, counts))
    if has_axis:
        flags["axis"] = _axis((0, 1, 0) if given["axis"] is _OMITTED else given["axis"])
    if has_round_cap:
        round_cap = False if given["roundCap"] is _OMITTED else given["roundCap"]
        _require_bool(round_cap, "roundCap")
        if round_cap:
            flags["roundCap"] = True
    flags.update(poly_history_flags(constructionHistory, ch, createUVs, cuv))
    return create_poly(getattr(cmds, command), flags, require_name(name), resolve_parent(parent))


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
