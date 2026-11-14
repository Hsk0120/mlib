# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""現在の姿勢を新しいdagPoseに保存する(``cmds.dagPose(save=True)`` 相当)。"""

from typing import Any, Dict
import maya.cmds as cmds
from ..core.object import Object
from ..decorator import _pick_alias, undoChunk
from ..util import _UNSET
from typing import Iterable
from mlib.nodes.dagPose import DagPose
from mlib.nodes.node import Node


def createDagPose(members: Node | str | Iterable[Node | str], name: str | None = ..., bindPose: bool = ..., hierarchy: bool = ..., *, n: str | None = ..., bp: bool = ...) -> DagPose:
    """現在の姿勢を新しいポーズに保存する。

    選択状態は使わない。対象とnameを確かめてから保存する。指定した名前は、保存したあとに名前を変えて付ける。
    名前の変更に失敗しても、保存したポーズは自動では元に戻さない。
    name・bindPoseは ``cmds.dagPose`` と同じ短縮名 ``n``・``bp`` でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        members (Node | str | Iterable[Node | str]): 保存するTransformまたはJoint。
        name (str | None): 付ける名前。NoneならMayaが自動で名前を付ける。既定はNone。
        bindPose (bool): Trueならバインドポーズとして保存する。既定はFalse。
        hierarchy (bool): TrueならMaya標準のとおり階層ごと保存する。Falseなら指定したものだけを保存する。
            Mayaは、元に戻すのに必要な親の情報も保存することがある。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        bp (bool): bindPoseの短縮名。bindPoseと同時には指定できない。

    Returns:
        DagPose: 作ったポーズ。Mayaが既存のポーズを使い回した場合はそのポーズ。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合。
        ValueError: 対象が空の場合、Transformでないものを含む場合、または名前が正しくない場合。
        RuntimeError: ノードが見つからない場合、またはMayaが保存を拒否した場合。

    Examples:
        >>> import mlib
        >>> pose = mlib.createDagPose(root, name="rest_pose")
        >>> pose.restore()
    """
    ...
