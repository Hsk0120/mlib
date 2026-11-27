"""シーン全体、または指定したノード・アトリビュートから、DGの循環の候補を探す(``cmds.cycleCheck`` 相当)。"""

import math

import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _require_bool

#: cycleCheckの結果を経路ごとに分ける区切り。アトリビュートの名前には現れない文字を使う。
_SEPARATOR = "|<mlibCycle>|"


def findCycles(nodes=None, *, dag=False, timeLimit=None, firstOnly=False):
    """シーン全体、または指定したノード・アトリビュートから、DGの循環の候補を探す。

    ``cmds.cycleCheck(list=True, secondary=True)`` を1回実行し、見つかった経路ごとにPlugへ変換して返す。
    経路は ``cycleCheck`` が検出した順に並び、完全な循環とは限らない(部分経路も含む)。
    1つのノードを通る単純な循環を流れの順に並べたいときは :meth:`Node.findCycles <mlib.nodes.node.Node.findCycles>` を使う。
    シーンは変更しない。

    Args:
        nodes (str | Node | Plug | Iterable[str | Node | Plug] | None): 調べる対象。Noneならシーン全体。既定はNone。
        dag (bool): Trueなら、DAGの親子による依存も循環に含める(``cycleCheck`` の ``dag``)。既定はFalse。
        timeLimit (float | None): 探す時間の上限(秒)。Noneなら上限なし。上限に達すると、それまでに見つかった分を返す。既定はNone。
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
    # 循環参照の回避: plugsはcmdsのgetPlugを経由してnodesを参照するため、使う時点で読み込む。
    from ..plugs.plug import Plugs
    from .getPlug import getPlug

    _require_bool(dag, "dag")
    _require_bool(firstOnly, "firstOnly")
    flags = {"list": True, "secondary": True, "dag": dag, "firstCycleOnly": firstOnly, "listSeparator": _SEPARATOR}
    if timeLimit is not None:
        if isinstance(timeLimit, bool) or not isinstance(timeLimit, (int, float)):
            raise TypeError(f"timeLimitは数値かNoneで指定してください: {type(timeLimit).__name__}")
        if not math.isfinite(timeLimit) or timeLimit <= 0:
            raise ValueError(f"timeLimitは0より大きい有限な秒数で指定してください: {timeLimit}")
        flags["timeLimit"] = f"{float(timeLimit)}sec"
    if nodes is None:
        names = []
        flags["all"] = True
    else:
        items = [nodes] if isinstance(nodes, (str, Object)) else list(nodes)
        if not items:
            raise ValueError("nodesに調べる対象を1つ以上指定してください")
        names = []
        for item in items:
            if not isinstance(item, (str, Object)):
                raise TypeError(f"nodesには名前・Node・Plugを指定してください: {type(item).__name__}")
            if isinstance(item, Object):
                # 削除済みのNode・Plugは、ほかのコマンドと同じくValueErrorにする。
                names.append(Object._input_name(item))
                continue
            # 見つからない名前は、cmds.cycleCheckのValueErrorにせず、ほかのコマンドと同じRuntimeErrorにする。
            if not item or not cmds.ls(item):
                raise RuntimeError(f"ノードが見つかりません: {item}")
            names.append(item)
    paths, current = [], []
    for name in [*(cmds.cycleCheck(*names, **flags) or []), _SEPARATOR]:
        if name != _SEPARATOR:
            current.append(name)
        elif current:
            paths.append(current)
            current = []
    return [Plugs._from_plugs([getPlug(name) for name in path]) for path in paths]
