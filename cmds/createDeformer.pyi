# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""形状やコンポーネントにcluster・ラティス・wireのデフォーマーを作り、デフォーマーを返す(``cmds.cluster``・``lattice``・``wire`` 相当)。"""

import math
import maya.cmds as cmds
from ..core.object import Object
from ..core.shapeBuild import removing_created_nodes, require_existing, require_name, require_shape_type
from ..decorator import _pick_alias, _require_bool, preservedSelection, undoChunk
from ..util import _UNSET, _require_choice
from typing import Any, Iterable, Literal, Sequence
from mlib.components.component import Component
from mlib.nodes.cluster import Cluster
from mlib.nodes.geometryFilter import GeometryFilter
from mlib.nodes.node import Node
from typing import overload

_OMITTED: Any
_KIND_ARGUMENTS: dict

@overload
def createDeformer(kind: Literal["cluster"], targets: str | Node | Component | Iterable, *, name: str | None = ..., relative: bool = ..., n: str | None = ..., rel: bool = ...) -> Cluster: ...
@overload
def createDeformer(kind: Literal["lattice"], targets: str | Node | Component | Iterable, *, name: str | None = ..., divisions: Sequence[int] = ..., ldivisions: Sequence[int] = ..., objectCentered: bool = ..., n: str | None = ..., dv: Sequence[int] = ..., ldv: Sequence[int] = ..., oc: bool = ...) -> GeometryFilter: ...
@overload
def createDeformer(kind: Literal["wire"], targets: str | Node | Component | Iterable, *, curves: str | Node | Iterable[str | Node], name: str | None = ..., dropoffDistance: float | None = ..., n: str | None = ..., dds: float | None = ...) -> GeometryFilter: ...
@overload
def createDeformer(kind: str, targets: str | Node | Component | Iterable, *, curves: str | Node | Iterable[str | Node] = ..., name: str | None = ..., relative: bool = ..., divisions: Sequence[int] = ..., ldivisions: Sequence[int] = ..., objectCentered: bool = ..., dropoffDistance: float | None = ..., n: str | None = ..., rel: bool = ..., dv: Sequence[int] = ..., ldv: Sequence[int] = ..., oc: bool = ..., dds: float | None = ...) -> GeometryFilter:
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
    ...

def _given(given: dict[str, object], key: str, default: object) -> Any:
    """省略した引数を既定の値へ置き換える。

    Args:
        given (dict[str, object]): 引数の名前と値。省略したものは ``_OMITTED``。
        key (str): 引数の名前。
        default (object): 省略したときの値。

    Returns:
        object: 指定した値、または既定の値。
    """
    ...

def _target_names(targets: str | Node | Component | Iterable) -> list[str]:
    """変形する対象の名前を確かめる。

    Args:
        targets (str | Node | Component | Iterable): 変形する対象。

    Returns:
        list[str]: 対象の名前。

    Raises:
        ValueError: 対象が空の場合。
    """
    ...

def _create_cluster(targets: str | Node | Component | Iterable, name: str | None, given: dict[str, object]) -> Cluster:
    """clusterを作る。

    Args:
        targets (str | Node | Component | Iterable): 変形する対象。
        name (str | None): 確かめてある名前。
        given (dict[str, object]): 種類に固有の引数。

    Returns:
        Cluster: 作ったcluster。
    """
    ...

def _create_lattice(targets: str | Node | Component | Iterable, name: str | None, given: dict[str, object]) -> GeometryFilter:
    """ラティスを作り、ffdデフォーマーを返す。

    Args:
        targets (str | Node | Component | Iterable): 変形する対象。
        name (str | None): 確かめてある名前。
        given (dict[str, object]): 種類に固有の引数。

    Returns:
        GeometryFilter: 作ったffdデフォーマー。
    """
    ...

def _create_wire(targets: str | Node | Component | Iterable, name: str | None, given: dict[str, object]) -> GeometryFilter:
    """カーブで変形するwireを作る。

    Args:
        targets (str | Node | Component | Iterable): 変形する対象。
        name (str | None): 確かめてある名前。
        given (dict[str, object]): 種類に固有の引数。curvesは必ず入っている。

    Returns:
        GeometryFilter: 作ったwireデフォーマー。
    """
    ...

def _divisions(value: Sequence[int], name: str, minimum: int) -> tuple[int, int, int]:
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
    ...
