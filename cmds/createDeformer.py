"""形状やコンポーネントにcluster・ラティス・wireのデフォーマーを作り、デフォーマーを返す(``cmds.cluster``・``lattice``・``wire`` 相当)。"""

import math

import maya.cmds as cmds

from ..core.object import Object
from ..core.shapeBuild import removing_created_nodes, require_existing, require_name, require_shape_type
from ..decorator import _pick_alias, _require_bool, preservedSelection, undoChunk
from ..util import _UNSET, _require_choice

#: 省略した引数の印(``_pick_alias`` の既定の値に使う。``_UNSET`` は必須の印なので使えない)。
_OMITTED = object()
#: 種類ごとに使える、種類に固有の引数(長い名前)。
_KIND_ARGUMENTS = {"cluster": ("relative",), "lattice": ("divisions", "ldivisions", "objectCentered"), "wire": ("curves", "dropoffDistance")}


def createDeformer(
    kind,
    targets,
    *,
    curves=_OMITTED,
    name=_UNSET,
    relative=_UNSET,
    divisions=_UNSET,
    ldivisions=_UNSET,
    objectCentered=_UNSET,
    dropoffDistance=_UNSET,
    n=_UNSET,
    rel=_UNSET,
    dv=_UNSET,
    ldv=_UNSET,
    oc=_UNSET,
    dds=_UNSET,
):
    """形状またはコンポーネントに、cluster・ラティス・wireのデフォーマーを作る。

    作るものは ``kind`` で選ぶ。Mayaの専用のコマンド(``cmds.cluster``・``cmds.lattice``・``cmds.wire``)で作るので、
    ``cmds.deformer(type=...)`` で作る、そのほかのデフォーマー(``deltaMush`` など)は作れない(ValueError)。
    blendShapeは :func:`~mlib.cmds.createBlendShape.createBlendShape`、skinClusterは :func:`~mlib.cmds.bindSkin.bindSkin` で作る。

    - ``"cluster"``: clusterを作る。ハンドル(clusterHandleを持つtransform)は
      :meth:`Cluster.getWeightedNode <mlib.nodes.cluster.Cluster.getWeightedNode>` で取得する。
      名前を付けると、ハンドルは ``<名前>Handle`` になる。使える引数はrelative。
    - ``"lattice"``: 対象を囲む大きさのラティスを作り、ffdデフォーマーを返す。ラティスの形状は ``deformedLatticePoints`` の入力元に、
      基準のラティスは ``baseLatticeMatrix`` の入力元につながる。名前を付けると、ラティスは ``<名前>Lattice``、
      基準は ``<名前>Base`` になる。使える引数はdivisions・ldivisions・objectCentered。
    - ``"wire"``: カーブで変形するwireを作る。カーブを動かすと、近くの頂点がカーブに沿って動く。カーブごとに、
      基準のカーブ(``<カーブ名>BaseWire``)をMayaが作る。curvesは必須で、使える引数はcurves・dropoffDistance。
      作る前に、ターゲットが変形できる形状(``deformableShape``)を、カーブが ``nurbsCurve`` の形状を持つかを確かめ、
      持たなければ何も作らずにValueErrorにする。それでもMayaが作成に失敗した場合は、作りかけのノード
      (``<カーブ名>BaseWire`` など)を消してから例外を出す。

    その種類で使えない引数を指定するとTypeError。選択状態は使わず、現在の選択は変えない。
    fast引数は無い(OpenMayaにデフォーマーを作る同じ機能が無いため)。Undoが有効なら1回で戻せる
    (Undoチャンク名は ``mlibCreateCluster``・``mlibCreateLattice``・``mlibCreateWire``)。
    name・relative・divisions・ldivisions・objectCentered・dropoffDistanceは、Mayaのコマンドと同じ短縮名
    ``n``・``rel``・``dv``・``ldv``・``oc``・``dds`` でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        kind (str): 作るデフォーマーの種類。``"cluster"``・``"lattice"``・``"wire"`` のどれか。
        targets (str | Node | Component | Iterable): 変形する形状・そのtransform・コンポーネント
            (``"body_geo.vtx[0:20]"``・:class:`~mlib.components.vertex.Vertices` など)。
        curves (str | Node | Iterable[str | Node]): 変形に使うnurbsCurve、またはそのtransform。
            ``cmds.wire`` の ``wire`` フラグに渡す。wireでは必須で、ほかの種類では指定できない。
        name (str | None): デフォーマーに付ける名前。NoneならMayaの既定の名前。既定はNone。
        relative (bool): Trueなら、ハンドルの親の変換を無視し、ハンドル自身の変換だけで変形する。既定はFalse。clusterだけ。
        divisions (Sequence[int]): ラティスのS・T・U方向の点の数。どれも2以上。既定は(2, 5, 2)。latticeだけ。
        ldivisions (Sequence[int]): 変形の計算に使う、局所的な分割数。どれも1以上。既定は(2, 2, 2)。latticeだけ。
        objectCentered (bool): Trueなら対象の中心に置く。Falseなら原点に置く。既定はTrue。latticeだけ。
        dropoffDistance (float | None): カーブからの影響が届く距離(cm)。0より大きい有限な値。
            すべてのカーブに同じ値を設定する。NoneならMayaの既定。既定はNone。wireだけ。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        rel (bool): relativeの短縮名。relativeと同時には指定できない。
        dv (Sequence[int]): divisionsの短縮名。divisionsと同時には指定できない。
        ldv (Sequence[int]): ldivisionsの短縮名。ldivisionsと同時には指定できない。
        oc (bool): objectCenteredの短縮名。objectCenteredと同時には指定できない。
        dds (float | None): dropoffDistanceの短縮名。dropoffDistanceと同時には指定できない。

    Returns:
        GeometryFilter: 作ったデフォーマー。clusterは :class:`~mlib.nodes.cluster.Cluster`、
            latticeはMayaの ``ffd`` 型から作ったクラス(``mlib.nodes.Ffd``)、wireは ``wire`` 型から作ったクラス(``mlib.nodes.Wire``)。

    Raises:
        TypeError: kindが文字列でない場合、その種類で使えない引数を指定した場合、wireでcurvesを省いた場合、
            長い名前と短縮名を同時に指定した場合、nameが文字列でもNoneでもない場合、
            または引数・対象・カーブが対応していない型の場合。
        ValueError: kindが上のどれでもない場合、nameが空文字列か ``|`` を含む場合、分割数の個数や値が正しくない場合、
            dropoffDistanceが0以下か有限でない場合、対象やカーブが空か無効な場合、
            wireでターゲットに変形できる形状が無い場合、またはカーブに ``nurbsCurve`` の形状が無い場合(形状の無いtransformを含む)。
        RuntimeError: 名前からノードが見つからない場合、またはMayaが作成を拒否した場合。

    Note:
        名前空間付きのnameで作ると、Undoのあとの Redo で、Mayaがデフォーマーとハンドルなどを名前空間の外
        (ルート)に作り直す(``cmds.cluster`` などでも同じ、Mayaの動き)。nameから決まるハンドル・ベースの名前を
        保つため、作ったあとの名前の変更では補わない。

    Examples:
        >>> import mlib
        >>> cluster = mlib.createDeformer("cluster", "body_geo.vtx[0:20]", name="chest_cluster")
        >>> handle = cluster.getWeightedNode()

        >>> ffd = mlib.createDeformer("lattice", "head_geo", divisions=(3, 4, 3), name="head_ffd")
        >>> lattice = ffd.getPlug("deformedLatticePoints").getConnections(input=True).getNode()

        >>> wire = mlib.createDeformer("wire", "brow_geo", curves="brow_crv", dropoffDistance=3.0, name="brow_wire")
    """
    kind = _require_choice(kind, "kind", tuple(_KIND_ARGUMENTS))
    given = {
        "curves": curves,
        "relative": _pick_alias(relative, rel, "relative", "rel", default=_OMITTED),
        "divisions": _pick_alias(divisions, dv, "divisions", "dv", default=_OMITTED),
        "ldivisions": _pick_alias(ldivisions, ldv, "ldivisions", "ldv", default=_OMITTED),
        "objectCentered": _pick_alias(objectCentered, oc, "objectCentered", "oc", default=_OMITTED),
        "dropoffDistance": _pick_alias(dropoffDistance, dds, "dropoffDistance", "dds", default=_OMITTED),
    }
    unusable = [key for key, value in given.items() if value is not _OMITTED and key not in _KIND_ARGUMENTS[kind]]
    if unusable:
        raise TypeError(f"kind={kind!r}では{'・'.join(unusable)}を指定できません")
    if kind == "wire" and curves is _OMITTED:
        raise TypeError("kind='wire'ではcurvesを指定してください")
    name = require_name(_pick_alias(name, n, "name", "n", default=None))
    if kind == "cluster":
        return _create_cluster(targets, name, given)
    if kind == "lattice":
        return _create_lattice(targets, name, given)
    return _create_wire(targets, name, given)


def _given(given, key, default):
    """省略した引数を既定の値へ置き換える。

    Args:
        given (dict[str, object]): 引数の名前と値。省略したものは ``_OMITTED``。
        key (str): 引数の名前。
        default (object): 省略したときの値。

    Returns:
        object: 指定した値、または既定の値。
    """
    value = given[key]
    return default if value is _OMITTED else value


def _target_names(targets):
    """変形する対象の名前を確かめる。

    Args:
        targets (str | Node | Component | Iterable): 変形する対象。

    Returns:
        list[str]: 対象の名前。

    Raises:
        ValueError: 対象が空の場合。
    """
    target_names = Object._input_names(targets, allow_plugs=False)
    if not target_names:
        raise ValueError("ターゲットを1つ以上指定してください")
    return target_names


def _create_cluster(targets, name, given):
    """clusterを作る。

    Args:
        targets (str | Node | Component | Iterable): 変形する対象。
        name (str | None): 確かめてある名前。
        given (dict[str, object]): 種類に固有の引数。

    Returns:
        Cluster: 作ったcluster。
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node

    relative = _given(given, "relative", False)
    _require_bool(relative, "relative")
    target_names = _target_names(targets)
    require_existing(target_names)
    flags = {"relative": relative}
    if name is not None:
        flags["name"] = name
    with undoChunk("mlibCreateCluster"), preservedSelection():
        result = cmds.cluster(*target_names, **flags)
        return Node(result[0])


def _create_lattice(targets, name, given):
    """ラティスを作り、ffdデフォーマーを返す。

    Args:
        targets (str | Node | Component | Iterable): 変形する対象。
        name (str | None): 確かめてある名前。
        given (dict[str, object]): 種類に固有の引数。

    Returns:
        GeometryFilter: 作ったffdデフォーマー。
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node

    divisions = _divisions(_given(given, "divisions", (2, 5, 2)), "divisions", 2)
    ldivisions = _divisions(_given(given, "ldivisions", (2, 2, 2)), "ldivisions", 1)
    object_centered = _given(given, "objectCentered", True)
    _require_bool(object_centered, "objectCentered")
    target_names = _target_names(targets)
    require_existing(target_names)
    flags = {"divisions": divisions, "ldivisions": ldivisions, "objectCentered": object_centered}
    if name is not None:
        flags["name"] = name
    with undoChunk("mlibCreateLattice"), preservedSelection():
        result = cmds.lattice(*target_names, **flags)
        return Node(result[0])


def _create_wire(targets, name, given):
    """カーブで変形するwireを作る。

    Args:
        targets (str | Node | Component | Iterable): 変形する対象。
        name (str | None): 確かめてある名前。
        given (dict[str, object]): 種類に固有の引数。curvesは必ず入っている。

    Returns:
        GeometryFilter: 作ったwireデフォーマー。
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node

    dropoff_distance = _given(given, "dropoffDistance", None)
    if dropoff_distance is not None:
        if isinstance(dropoff_distance, bool) or not isinstance(dropoff_distance, (int, float)):
            raise TypeError(f"dropoffDistanceは数値かNoneで指定してください: {type(dropoff_distance).__name__}")
        if not math.isfinite(dropoff_distance) or dropoff_distance <= 0.0:
            raise ValueError(f"dropoffDistanceは正の有限な数値で指定してください: {dropoff_distance}")
    target_names = _target_names(targets)
    curve_names = Object._input_names(given["curves"], allow_plugs=False)
    if not curve_names:
        raise ValueError("カーブを1つ以上指定してください")
    require_existing(target_names + curve_names)
    require_shape_type(target_names, "deformableShape", "ターゲット")
    require_shape_type(curve_names, "nurbsCurve", "カーブ")
    flags = {"wire": curve_names}
    if name is not None:
        flags["name"] = name
    if dropoff_distance is not None:
        flags["dropoffDistance"] = [(index, float(dropoff_distance)) for index in range(len(curve_names))]
    with undoChunk("mlibCreateWire"), preservedSelection():
        with removing_created_nodes():
            result = cmds.wire(*target_names, **flags)
        return Node(result[0])


def _divisions(value, name, minimum):
    """3つの整数の分割数を確かめる。

    Args:
        value (Sequence[int]): S・T・U方向の分割数。
        name (str): 例外メッセージに使う引数名。
        minimum (int): 各値の下限。

    Returns:
        tuple[int, int, int]: 確かめた分割数。

    Raises:
        TypeError: 並びでない場合、または値がintでない場合(boolもintとして扱わない)。
        ValueError: 値の数が3でない場合、または下限より小さい場合。
    """
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name}は3つのintの並びで指定してください")
    try:
        values = tuple(value)
    except TypeError:
        raise TypeError(f"{name}は3つのintの並びで指定してください: {type(value).__name__}") from None
    if len(values) != 3:
        raise ValueError(f"{name}は3つの値で指定してください: {len(values)}個")
    for item in values:
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(f"{name}の要素はintで指定してください: {type(item).__name__}")
        if item < minimum:
            raise ValueError(f"{name}の値は{minimum}以上で指定してください: {item}")
    return values
