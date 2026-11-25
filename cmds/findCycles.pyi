# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""シーン全体、または指定したノード・アトリビュートから、DGの循環の候補を探す(``cmds.cycleCheck`` 相当)。"""

import math
import maya.cmds as cmds
from ..core.object import Object
from ..decorator import _require_bool
from typing import Iterable
from mlib.nodes.node import Node
from mlib.plugs.plug import Plug
from mlib.plugs.plug import Plugs

_SEPARATOR: str

def findCycles(nodes: str | Node | Plug | Iterable[str | Node | Plug] | None = ..., *, dag: bool = ..., timeLimit: float | None = ..., firstOnly: bool = ...) -> list[Plugs]:
    """シーン全体、または指定したノード・アトリビュートから、DGの循環の候補を探す。

    ``cmds.cycleCheck(list=True, secondary=True)`` を1回実行し、見つかった経路ごとにPlugへ変換して返す。
    経路は ``cycleCheck`` が検出した順に並び、完全な循環とは限らない(部分経路も含む)。
    1つのノードを通る単純な循環を流れの順に並べたいときは :meth:`Node.findCycles <mlib.nodes.node.Node.findCycles>` を使う。
    シーンは変更しない。

    Args:
        nodes (str | Node | Plug | Iterable[str | Node | Plug] | None): 調べる対象。Noneならシーン全体。
        dag (bool): Trueなら、DAGの親子による依存も循環に含める(``cycleCheck`` の ``dag``)。既定はFalse。
        timeLimit (float | None): 探す時間の上限(秒)。Noneなら上限なし。上限に達すると、それまでに見つかった分を返す。
        firstOnly (bool): Trueなら、最初に見つかった完全な循環だけを探す(``cycleCheck`` の ``firstCycleOnly``)。既定はFalse。

    Returns:
        list[Plugs]: 経路ごとのアトリビュートの並び。見つからなければ空リスト。

    Raises:
        TypeError: nodesの要素が名前・Node・Plugでない場合、dag・firstOnlyがboolでない場合、
            またはtimeLimitが数値・None以外の場合。
        ValueError: nodesが空の場合、nodesに削除済みのNode・Plugがある場合、またはtimeLimitが0以下・有限でない場合。
        RuntimeError: 名前の対象が見つからない場合(文言は ``ノードが見つかりません: <名前>``)、
            またはMayaが調査を拒否した場合。

    Examples:
        >>> import mlib
        >>> for path in mlib.findCycles(timeLimit=10.0):
        ...     print([plug._full_name() for plug in path])
        >>> mlib.findCycles(["arm_ctrl", "arm_jnt"], dag=True, firstOnly=True)
    """
    ...
