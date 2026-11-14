"""現在の姿勢を新しいdagPoseに保存する(``cmds.dagPose(save=True)`` 相当)。

選択状態は使わない。

.. code-block:: python

    import mlib

    pose = mlib.createDagPose(root, name="rest_pose")
    pose.restore()
"""

from typing import Any, Dict

import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _pick_alias, undoChunk
from ..util import _UNSET


@undoChunk("mlibCreateDagPose")
def createDagPose(members, name=_UNSET, bindPose=_UNSET, hierarchy=True, *, n=_UNSET, bp=_UNSET):
    """現在の姿勢を新しいポーズに保存する。

    対象とnameを確かめてから保存する。指定した名前は、保存したあとに名前を変えて付ける。
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
    """
    name = _pick_alias(name, n, "name", "n", default=None)
    bindPose = _pick_alias(bindPose, bp, "bindPose", "bp", default=False)
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node

    names = []
    for item in Object._input_names(members):
        node = Node(item)
        if not node.isValid() or not node.isType("transform"):
            raise ValueError(f"有効なtransformかjointを指定してください: {item}")
        if node.getFullName() not in names:
            names.append(node.getFullName())
    if not names:
        raise ValueError("transformかjointを1つ以上指定してください")
    if name is not None and (not isinstance(name, str) or not name):
        raise ValueError("nameは空でない文字列かNoneで指定してください")
    flags: Dict[str, Any] = {"save": True, "bindPose": bindPose, "selection": not hierarchy}
    # dagPoseのnameフラグはRedo時に名前空間を失うため、renameに任せる。
    result = cmds.dagPose(names, **flags)
    if name is not None:
        result = cmds.rename(result, name)
    return Node(result)
