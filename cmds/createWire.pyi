# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""形状をカーブで変形するwireデフォーマーを作り、wireを返す(``cmds.wire`` 相当)。

カーブを動かすと、近くの頂点がカーブに沿って動く。作成は1回のUndoにまとめ、現在の選択は変えない。

.. code-block:: python

    import mlib

    wire = mlib.createWire("brow_geo", "brow_crv", dropoffDistance=3.0, name="brow_wire")
"""

import math
import maya.cmds as cmds
from ..core.object import Object
from ..core.shapeBuild import require_name
from ..decorator import _pick_alias, preservedSelection, undoChunk
from ..util import _UNSET
from typing import Iterable
from mlib.components.component import Component
from mlib.nodes.geometryFilter import GeometryFilter
from mlib.nodes.node import Node


def createWire(targets: str | Node | Component | Iterable, curves: str | Node | Iterable[str | Node], name: str | None = ..., dropoffDistance: float | None = ..., *, n: str | None = ..., dds: float | None = ...) -> GeometryFilter:
    """形状またはコンポーネントに、カーブで変形するwireデフォーマーを作る。

    選択状態は使わない。カーブごとに、基準のカーブ(``<カーブ名>BaseWire``)をMayaが作る。
    fast引数は無い(OpenMayaにデフォーマーを作る同じ機能が無いため)。Undoが有効なら1回で戻せる。
    name・dropoffDistanceは ``cmds.wire`` と同じ短縮名 ``n``・``dds`` でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        targets (str | Node | Component | Iterable): 変形する形状・そのtransform・コンポーネント。
        curves (str | Node | Iterable[str | Node]): 変形に使うnurbsCurve、またはそのtransform。
            ``cmds.wire`` の ``wire`` フラグに渡す。
        name (str | None): wireに付ける名前。NoneならMayaの既定の名前。既定はNone。
        dropoffDistance (float | None): カーブからの影響が届く距離(cm)。0より大きい有限な値。
            すべてのカーブに同じ値を設定する。NoneならMayaの既定。既定はNone。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        dds (float | None): dropoffDistanceの短縮名。dropoffDistanceと同時には指定できない。

    Returns:
        GeometryFilter: 作ったwireデフォーマー。実際の型は、Mayaの ``wire`` 型から作ったクラス(``mlib.nodes.Wire``)。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、dropoffDistanceが数値でもNoneでもない場合、
            nameが文字列でもNoneでもない場合、または対象やカーブが対応していない型の場合。
        ValueError: nameが空文字列か ``|`` を含む場合、dropoffDistanceが0以下か有限でない場合、
            または対象やカーブが空か無効な場合。
        RuntimeError: 名前からノードが見つからない場合、またはMayaが作成を拒否した場合。

    Examples:
        .. code-block:: python

            wire = mlib.createWire(face.getVertices(range(40)), ["lip_upper_crv", "lip_lower_crv"], dds=2.0)
    """
    ...
