# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ノードの動きの軌跡(モーショントレイル)を作り、ハンドルのTransformを返す(``cmds.snapshot(motionTrail=True)`` 相当)。"""

import maya.cmds as cmds
from ..core.shapeBuild import require_name
from ..decorator import _pick_alias
from ..util import _UNSET
from mlib.nodes.node import Node
from mlib.nodes.transform import Transform


def createMotionTrail(node: Node | str, *, startTime: float | None = ..., st: float | None = ..., endTime: float | None = ..., et: float | None = ..., increment: float = ..., i: float = ..., name: str | None = ..., n: str | None = ...) -> Transform:
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
    ...
