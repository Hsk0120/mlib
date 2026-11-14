"""アトリビュートの動きを、フレームごとのキーへ焼き込む(``cmds.bakeResults`` 相当)。

コンストレイント・エクスプレッション・ドリブンキーなどで動いているアトリビュートを、
指定した範囲でフレームごとに評価し、キーにする。戻り値はそのアニメーションカーブ。
焼き込みの間に動かした現在時刻は、終わったら元へ戻す。

.. code-block:: python

    import mlib

    curves = mlib.bakeResults(["arm_CTRL", "leg_CTRL"], time=(1, 120), simulation=True)
    curves = mlib.bakeResults("arm_CTRL", at=["tx", "ty"], t=(1, 24), sb=2)  # cmds.bakeResults と同じ短縮名
"""

import math
import numbers
import re

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _pick_alias, undoChunk
from ..util import _UNSET

#: ``**kwargs`` では受け付けないフラグ。``attribute`` は ``attributes``(短縮名 ``at``)で指定し、
#: query・editは焼き込み専用のため受け付けない。
_REJECTED_FLAGS = frozenset(("attribute", "query", "q", "edit", "e"))


def bakeResults(nodes, attributes=_UNSET, time=_UNSET, sampleBy=_UNSET, *, at=_UNSET, t=_UNSET, sb=_UNSET, **kwargs):
    """アトリビュートの動きをキーへ焼き込み、そのアニメーションカーブを返す。

    選択状態は使わない。

    - timeを省略すると、再生範囲(``mlib.Time.getPlaybackRange()``)を焼き込む。
    - attributesを省略すると、Mayaの既定(各ノードのキー設定可能なアトリビュート)を焼き込む。
    - Mayaの既定(``simulation=False``)では、入力を持たない静的なアトリビュートにはキーを作らない。
      ダイナミクスなど、すべてのフレームを順に評価する必要があるときは ``simulation=True`` を渡す。

    焼き込みで現在時刻が動いた場合は、終わったあと元の時刻へ戻す。
    fast引数は無い(OpenMayaに同じ機能が無いため)。Undoが有効なら1回で戻せる。
    専用の引数は ``cmds.bakeResults`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        nodes (Node | str | Sequence[Node | str]): 焼き込むノード、またはその並び。
        attributes (str | Sequence[str] | None): 焼き込むアトリビュート名。``"translateX"``・``"tx"`` や、
            コンパウンドアトリビュートの ``"translate"`` も指定できる。
            NoneならMayaの既定(キー設定可能なもの)。既定はNone。
        time (tuple[float, float] | None): 焼き込む範囲 (開始, 終了)。現在のUI時間単位のフレームで、両端を含む。
            Noneなら再生範囲。既定はNone。
        sampleBy (float): キーを作る間隔(フレーム)。正の数。既定は1。
        at (str | Sequence[str] | None): attributesの短縮名(Mayaの ``attribute``)。attributesと同時には指定できない。
        t (tuple[float, float] | None): timeの短縮名。timeと同時には指定できない。
        sb (float): sampleByの短縮名。sampleByと同時には指定できない。
        **kwargs (object): ``cmds.bakeResults`` のそのほかのフラグ。長い名前・短い名前のどちらでもよい。
            ``simulation``・``preserveOutsideKeys``・``sparseAnimCurveBake``・``disableImplicitControl``・
            ``minimizeRotation``・``shape``・``hierarchy`` など。
            ``attribute`` は ``attributes`` で指定するため受け付けない。query・editも受け付けない。

    Returns:
        list[AnimCurve]: 焼き込んだアトリビュートを動かすアニメーションカーブ(新しく作ったものと書き換えたもの)。
            対象はnodesのアトリビュートで、``shape`` が有効なら直下のShapeのアトリビュートも含む。
            ``hierarchy`` で増えた子孫のカーブは含まない。焼き込むものが無ければ空リスト。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、``**kwargs`` で受け付けないフラグを渡した場合、
            attributesが文字列・文字列の並び・Noneのどれでもない場合、またはtimeかsampleByが数値でない場合。
        ValueError: nodesが空の場合、timeが2つの有限な数値でない場合、timeの開始が終了より後の場合、
            またはsampleByが正の有限な数でない場合。
        RuntimeError: 名前からノードが見つからない場合、またはMayaが焼き込みを拒否した場合。
    """
    # nodes・common はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..common.sceneTime import Time
    from ..nodes.animCurve import AnimCurve
    from ..nodes.node import Node

    attributes = _pick_alias(attributes, at, "attributes", "at", default=None)
    time = _pick_alias(time, t, "time", "t", default=None)
    sampleBy = _pick_alias(sampleBy, sb, "sampleBy", "sb", default=1)
    rejected = sorted(_REJECTED_FLAGS.intersection(kwargs))
    if rejected:
        raise TypeError(f"bakeResultsは次の引数を受け付けません: {', '.join(rejected)}")
    items = [nodes] if isinstance(nodes, (str, Object)) or not hasattr(nodes, "__iter__") else list(nodes)
    if not items:
        raise ValueError("bakeResultsにはノードを1つ以上指定してください")
    targets = [Node(Object._input_name(item)) for item in items]
    names = _attribute_names(attributes)
    start, end = Time.getPlaybackRange() if time is None else _time_range(time)
    if isinstance(sampleBy, bool) or not isinstance(sampleBy, numbers.Real):
        raise TypeError("sampleByは数値で指定してください")
    if not math.isfinite(sampleBy) or sampleBy <= 0:
        raise ValueError(f"sampleByは正の有限な数値で指定してください: {sampleBy}")
    flags = dict(kwargs, time=(start, end), sampleBy=sampleBy)
    if names is not None:
        flags["attribute"] = names
    full_names = [node.getFullName() for node in targets]
    current = cmds.currentTime(query=True)
    try:
        with undoChunk("mlibBakeResults"):
            cmds.bakeResults(full_names, **flags)
    finally:
        if cmds.currentTime(query=True) != current:
            cmds.currentTime(current, update=True)
    # 結果の照会はUndoのまとまりの外で行う。
    with_shapes = kwargs.get("shape", kwargs.get("s", True))
    result = []
    for node in targets:
        owners = [node.getFullName()]
        if with_shapes and node.hasFn(om2.MFn.kTransform):
            owners += cmds.listRelatives(owners[0], shapes=True, noIntermediate=True, fullPath=True) or []
        for owner in owners:
            for curve in _driving_curves(owner, names):
                if curve not in result:
                    result.append(curve)
    return [AnimCurve(curve) for curve in result]


def _attribute_names(attributes):
    """attributesの指定を、cmds.bakeResultsへ渡すアトリビュート名のリストに揃える。

    Args:
        attributes (str | Sequence[str] | None): アトリビュート名、その並び、またはNone。

    Returns:
        list[str] | None: アトリビュート名。NoneはMayaの既定。

    Raises:
        TypeError: 文字列・文字列の並び・Noneのどれでもない場合。
        ValueError: 並びが空の場合、または空文字列を含む場合。
    """
    if attributes is None:
        return None
    names = [attributes] if isinstance(attributes, str) else list(attributes) if isinstance(attributes, (list, tuple)) else None
    if names is None or not all(isinstance(name, str) for name in names):
        raise TypeError("attributesはアトリビュート名か、名前の並びか、Noneで指定してください")
    if not names or not all(names):
        raise ValueError("attributesは空にできません。空の名前も指定できません")
    return names


def _time_range(time):
    """timeの指定 (開始, 終了) を確かめる。

    Args:
        time (Sequence[float]): 開始と終了のフレーム。

    Returns:
        tuple[float, float]: (開始, 終了)。

    Raises:
        TypeError: 数値の並びでない場合。
        ValueError: 値が2つでない場合、有限でない場合、または開始が終了より後の場合。
    """
    if isinstance(time, (str, bytes)) or not isinstance(time, (list, tuple)):
        raise TypeError("timeは(start, end)のフレームの組かNoneで指定してください")
    if len(time) != 2:
        raise ValueError(f"timeは2つの値(start, end)で指定してください: {len(time)}個")
    if not all(isinstance(value, numbers.Real) and not isinstance(value, bool) for value in time):
        raise TypeError("timeの要素は数値で指定してください")
    start, end = float(time[0]), float(time[1])
    if not (math.isfinite(start) and math.isfinite(end)):
        raise ValueError("timeは有限な数値で指定してください")
    if start > end:
        raise ValueError(f"timeのstartはend以下にしてください: {start} > {end}")
    return start, end


def _driving_curves(owner, names):
    """対象のアトリビュートへ直接つながるアニメーションカーブを返す。

    間にある単位変換ノードは飛ばしてたどる。

    Args:
        owner (str): ノードのフルパス。
        names (list[str] | None): 焼き込んだアトリビュート名。Noneはキー設定可能なアトリビュート。

    Returns:
        list[str]: アニメーションカーブの名前。接続の順に並び、同じものは1回だけ含む。
    """
    if names is None:
        wanted = {_attribute_base(name) for name in cmds.listAttr(owner, keyable=True) or []}
    else:
        wanted = set()
        for name in names:
            if not cmds.attributeQuery(_attribute_base(name), node=owner, exists=True):
                continue
            wanted.add(cmds.attributeQuery(_attribute_base(name), node=owner, longName=True))
            wanted.update(cmds.attributeQuery(_attribute_base(name), node=owner, listChildren=True) or [])
    pairs = cmds.listConnections(owner, source=True, destination=False, type="animCurve", connections=True, skipConversionNodes=True) or []
    curves = []
    for destination, curve in zip(pairs[::2], pairs[1::2]):
        if _attribute_base(destination.split(".", 1)[1]) in wanted and curve not in curves:
            curves.append(curve)
    return curves


def _attribute_base(name):
    """アトリビュートのパスから、末尾のアトリビュート名を返す。

    論理番号は除く(``"weight[0]"`` は ``"weight"`` になる)。

    Args:
        name (str): アトリビュート名またはパス。

    Returns:
        str: 論理番号を除いた末尾のアトリビュート名。
    """
    return re.sub(r"\[\d+\]", "", name).rsplit(".", 1)[-1]
