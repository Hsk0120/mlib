"""ノードの動きの軌跡(モーショントレイル)を作り、ハンドルのTransformを返す(``cmds.snapshot(motionTrail=True)`` 相当)。"""

import maya.cmds as cmds

from ..core.shapeBuild import require_name
from ..decorator import _pick_alias
from ..util import _UNSET


def createMotionTrail(node, *, startTime=_UNSET, st=_UNSET, endTime=_UNSET, et=_UNSET, increment=_UNSET, i=_UNSET, name=_UNSET, n=_UNSET):
    """ノードの動きの軌跡(モーショントレイル)を作り、そのハンドルのTransformを返す。

    ``cmds.snapshot(node, motionTrail=True)`` で、startTimeからendTimeまでincrementごとの位置を結んだ軌跡を作る。
    軌跡の形を持つ ``motionTrail`` ノードと、ビューに表示するハンドル(Transformとその ``motionTrailShape``)ができる。
    ``motionTrail`` ノードは ``mlib.ls(type="motionTrail")`` などで取得する。
    時間は現在のUIの時間単位のフレームで指定する。現在の選択は変えない。Mayaのコマンドの1回なので、Undoが有効なら1回で戻せる。
    fast引数は無い(OpenMayaにモーショントレイルを作る機能が無いため)。
    各引数は ``cmds.snapshot`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        node (Node | str): 軌跡を作るDAGノード(transformなど)。
        startTime (float | None): 開始のフレーム。Noneなら再生範囲の開始。既定はNone。
        st (float | None): startTimeの短縮名。startTimeと同時には指定できない。
        endTime (float | None): 終了のフレーム。Noneなら再生範囲の終了。既定はNone。
        et (float | None): endTimeの短縮名。endTimeと同時には指定できない。
        increment (float): 位置を取る間隔(フレーム)。0より大きい値。既定は1。
        i (float): incrementの短縮名。incrementと同時には指定できない。
        name (str | None): 付けたい名前。ハンドルは ``<名前>Handle`` になる。NoneならMayaの既定の名前。既定はNone。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        Transform: 作った軌跡のハンドル。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、nodeがDAGノードでない場合、時間が数値でない場合、
            またはnameが文字列でもNoneでもない場合。
        ValueError: 時間が有限でない場合、startTimeがendTimeより大きい場合、incrementが0以下の場合、
            またはnameが空文字列か ``|`` を含む場合。
        RuntimeError: nodeが見つからないか無効な場合、またはMayaが作成を拒否した場合。

    Examples:
        >>> import mlib
        >>> handle = mlib.createMotionTrail(mlib.getNode("ball"), startTime=1, endTime=24, name="ballTrail")
        >>> handle.getName()
        'ballTrailHandle'
    """
    # common・nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..common.sceneTime import Time, _finite_time
    from ..nodes.dagNode import DagNode
    from ..nodes.node import Node

    start = _pick_alias(startTime, st, "startTime", "st", default=None)
    end = _pick_alias(endTime, et, "endTime", "et", default=None)
    step = _finite_time(_pick_alias(increment, i, "increment", "i", default=1.0), "increment")
    name = require_name(_pick_alias(name, n, "name", "n", default=None))
    target = Node._resolve_input(node)
    target._require_valid("モーショントレイルの作成")
    if not isinstance(target, DagNode):
        raise TypeError(f"nodeはDAGノードで指定してください: {target.getName()}")
    if step <= 0:
        raise ValueError("incrementは0より大きい値で指定してください")
    playback = Time.getRange()
    start = playback[0] if start is None else _finite_time(start, "startTime")
    end = playback[1] if end is None else _finite_time(end, "endTime")
    if start > end:
        raise ValueError("startTimeはendTime以下で指定してください")
    flags = {"motionTrail": True, "startTime": start, "endTime": end, "increment": step}
    if name:
        flags["name"] = name
    # snapshotの1回だけなので、チャンクを開かない。
    return Node(cmds.snapshot(target._full_name(), **flags)[0])
