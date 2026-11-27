"""形状にblendShapeを作成し、ターゲットを登録する(``cmds.blendShape`` 相当)。"""

from typing import Any, Dict

import maya.cmds as cmds

from ..core.object import Object
from ..core.shapeBuild import require_name
from ..decorator import _pick_alias, _require_bool, undoChunk
from ..util import _UNSET


def createBlendShape(base, targets=(), *, name=_UNSET, n=_UNSET, frontOfChain=_UNSET, foc=_UNSET, origin=_UNSET, o=_UNSET):
    """形状にblendShapeを作成し、ターゲットを登録する(``cmds.blendShape`` 相当)。

    ターゲットは指定した順に、論理番号0から登録する。
    ターゲット名はMayaの規則どおり、ターゲットのtransform名(名前空間を除いた名前)になる。
    ターゲットの形状との接続は、Mayaの既定どおり残す。Undoが有効なら1回で戻せる。
    名前は作ったあとに付ける(``cmds.blendShape`` のnameフラグは、Redoで名前空間を失うため)。
    name・frontOfChain・originは ``cmds.blendShape`` と同じ短縮名 ``n``・``foc``・``o`` でも指定できる
    (長い名前と短縮名は同時に指定できない)。

    Args:
        base (str | Node): 変形する形状(メッシュなど)、またはそのtransform。
        targets (str | Node | Iterable[str | Node]): ターゲットの形状、またはそのtransform。
            省略するとターゲットの無いblendShapeを作る(あとから :meth:`~mlib.nodes.BlendShape.addTarget` で追加する)。
        name (str | None): 付ける名前。NoneならMayaが自動で名前を付ける。既定はNone。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        frontOfChain (bool): Trueなら、既存のデフォーマー(skinClusterなど)より前、つまり変形の最初に置く。
            リグでよく使う「ブレンドシェイプ → スキン」の順になる。Falseなら最後に置く。既定はTrue。
        foc (bool): frontOfChainの短縮名。frontOfChainと同時には指定できない。
        origin (str | None): ターゲットとの差を測る空間。``"local"`` はオブジェクト空間(Transformの移動・回転・スケールを無視する)、
            ``"world"`` はワールド空間(Transformの違いも差に含める)。省略するとMayaの既定(``"local"``)。
        o (str): originの短縮名。originと同時には指定できない。

    Returns:
        BlendShape: 作ったblendShape。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、frontOfChainがboolでない場合、
            nameが文字列でもNoneでもない場合、または対象が対応していない型の場合。
        ValueError: nameが空文字列か ``|`` を含む場合、originがlocal・world以外の場合、または対象が空か無効な場合。
        RuntimeError: 名前からノードが見つからない場合、またはMayaが作成を拒否した場合。

    Examples:
        >>> import mlib
        >>> blend = mlib.createBlendShape(body, [smile, frown], name="face_blendShape")
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node

    name = _pick_alias(name, n, "name", "n", default=None)
    frontOfChain = _pick_alias(frontOfChain, foc, "frontOfChain", "foc", default=True)
    _require_bool(frontOfChain, "frontOfChain")
    name = require_name(name)
    origin = _pick_alias(origin, o, "origin", "o", default=None)
    if origin is not None and origin not in ("local", "world"):
        raise ValueError(f"originはlocalかworldで指定してください: {origin!r}")
    base_name = Node._input_name(base)
    target_names = [Node._input_name(target) for target in Object._input_names(targets, allow_plugs=False)]
    flags: Dict[str, Any] = {"frontOfChain": True} if frontOfChain else {}
    if origin is not None:
        flags["origin"] = origin
    with undoChunk("mlibCreateBlendShape"):
        result = cmds.blendShape(*target_names, base_name, **flags)
        if name is not None:
            # blendShapeのnameフラグはRedo時に名前空間を失うため、renameに任せる。
            return Node(cmds.rename(result[0], name))
        return Node(result[0])
