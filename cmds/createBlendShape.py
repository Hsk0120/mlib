"""形状にblendShapeを作成し、ターゲットを登録する(``cmds.blendShape`` 相当)。

.. code-block:: python

    import mlib

    blend = mlib.createBlendShape(body, [smile, frown], name="face_blendShape")
"""

from typing import Any, Dict

import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _pick_alias, _require_bool, undoChunk
from ..util import _UNSET


def createBlendShape(base, targets=(), name=_UNSET, frontOfChain=_UNSET, *, n=_UNSET, foc=_UNSET):
    """形状にblendShapeを作成し、ターゲットを登録する(``cmds.blendShape`` 相当)。

    ターゲットは指定した順に、論理番号0から登録する。
    ターゲット名はMayaの規則どおり、ターゲットのtransform名(名前空間を除いた名前)になる。
    ターゲットの形状との接続は、Mayaの既定どおり残す。Undoが有効なら1回で戻せる。
    name・frontOfChainは ``cmds.blendShape`` と同じ短縮名 ``n``・``foc`` でも指定できる
    (長い名前と短縮名は同時に指定できない)。

    Args:
        base (str | Node): 変形する形状(メッシュなど)、またはそのtransform。
        targets (str | Node | Iterable[str | Node]): ターゲットの形状、またはそのtransform。
            省略するとターゲットの無いblendShapeを作る(あとから :meth:`~mlib.nodes.BlendShape.addTarget` で追加する)。
        name (str | None): 付ける名前。NoneならMayaが自動で名前を付ける。既定はNone。
        frontOfChain (bool): Trueなら、既存のデフォーマー(skinClusterなど)より前、つまり変形の最初に置く。
            リグでよく使う「ブレンドシェイプ → スキン」の順になる。Falseなら最後に置く。既定はTrue。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        foc (bool): frontOfChainの短縮名。frontOfChainと同時には指定できない。

    Returns:
        BlendShape: 作ったblendShape。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、frontOfChainがboolでない場合、
            nameが文字列でもNoneでもない場合、または対象が対応していない型の場合。
        ValueError: nameが空文字列の場合、または対象が空か無効な場合。
        RuntimeError: 名前からノードが見つからない場合、またはMayaが作成を拒否した場合。
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node

    name = _pick_alias(name, n, "name", "n", default=None)
    frontOfChain = _pick_alias(frontOfChain, foc, "frontOfChain", "foc", default=True)
    _require_bool(frontOfChain, "frontOfChain")
    if name is not None and not isinstance(name, str):
        raise TypeError("nameは文字列かNoneで指定してください")
    if name == "":
        raise ValueError("nameは空でない文字列かNoneで指定してください")
    base_name = Node._input_name(base)
    target_names = [Node._input_name(target) for target in Object._input_names(targets, allow_plugs=False)]
    flags: Dict[str, Any] = {"frontOfChain": True} if frontOfChain else {}
    if name is not None:
        flags["name"] = name
    with undoChunk("mlibCreateBlendShape"):
        result = cmds.blendShape(*(target_names + [base_name]), **flags)
        return Node(result[0])
