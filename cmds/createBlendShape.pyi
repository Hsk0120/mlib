# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""形状にblendShapeを作成し、ターゲットを登録する(``cmds.blendShape`` 相当)。"""

from typing import Any, Dict
import maya.cmds as cmds
from ..core.object import Object
from ..decorator import _pick_alias, _require_bool, undoChunk
from ..util import _UNSET
from typing import Iterable
from mlib.nodes.blendShape import BlendShape
from mlib.nodes.node import Node


def createBlendShape(base: str | Node, targets: str | Node | Iterable[str | Node] = ..., name: str | None = ..., frontOfChain: bool = ..., *, n: str | None = ..., foc: bool = ...) -> BlendShape:
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

    Examples:
        >>> import mlib
        >>> blend = mlib.createBlendShape(body, [smile, frown], name="face_blendShape")
    """
    ...
