# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""形状やコンポーネントにclusterを作り、clusterデフォーマーを返す(``cmds.cluster`` 相当)。

ハンドル(clusterHandleを持つtransform)は :meth:`Cluster.getWeightedNode <mlib.nodes.cluster.Cluster.getWeightedNode>`
で取得する。作成は1回のUndoにまとめ、現在の選択は変えない。

.. code-block:: python

    import mlib

    cluster = mlib.createCluster("body_geo.vtx[0:20]", name="chest_cluster")
    handle = cluster.getWeightedNode()
"""

import maya.cmds as cmds
from ..core.object import Object
from ..core.shapeBuild import require_name
from ..decorator import _pick_alias, _require_bool, preservedSelection, undoChunk
from ..util import _UNSET
from typing import Iterable
from mlib.components.component import Component
from mlib.nodes.cluster import Cluster
from mlib.nodes.node import Node


def createCluster(targets: str | Node | Component | Iterable, name: str | None = ..., relative: bool = ..., *, n: str | None = ..., rel: bool = ...) -> Cluster:
    """形状またはコンポーネントにclusterを作る。

    選択状態は使わない。fast引数は無い(OpenMayaにデフォーマーを作る同じ機能が無いため)。
    Undoが有効なら1回で戻せる。name・relativeは ``cmds.cluster`` と同じ短縮名 ``n``・``rel`` でも指定できる
    (長い名前と短縮名は同時に指定できない)。

    Args:
        targets (str | Node | Component | Iterable): 変形する形状・そのtransform・コンポーネント
            (``"body_geo.vtx[0:20]"``・:class:`~mlib.components.vertex.Vertices` など)。
        name (str | None): clusterに付ける名前。ハンドルは ``<名前>Handle`` になる。
            NoneならMayaの既定の名前。既定はNone。
        relative (bool): Trueなら、ハンドルの親の変換を無視し、ハンドル自身の変換だけで変形する。既定はFalse。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        rel (bool): relativeの短縮名。relativeと同時には指定できない。

    Returns:
        Cluster: 作ったcluster。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、relativeがboolでない場合、
            nameが文字列でもNoneでもない場合、または対象が対応していない型の場合。
        ValueError: nameが空文字列か ``|`` を含む場合、または対象が空か無効な場合。
        RuntimeError: 名前からノードが見つからない場合、またはMayaが作成を拒否した場合。

    Examples:
        .. code-block:: python

            cluster = mlib.createCluster(shape.getVertices([0, 1, 2]), relative=True)
            cluster.getWeightedNode().setTranslation((0, 1, 0))
    """
    ...
