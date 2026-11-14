"""形状を作る関数(``mlib.createCurve`` など)が共通で使う処理。名前・親・シェイプ名を整える。"""

import maya.cmds as cmds

from ..decorator import nativeUnits, preservedSelection, undoTransaction
from ..util import _finite


def require_name(name):
    """作るノードの名前を確かめる。

    Args:
        name (str | None): 作るノードの名前。Noneなら Maya の既定の名前。

    Returns:
        str | None: 確かめた名前。

    Raises:
        TypeError: nameが文字列でもNoneでもない場合。
        ValueError: nameが空文字列の場合、またはDAGパスの区切り ``|`` を含む場合。
    """
    if name is None:
        return None
    if not isinstance(name, str):
        raise TypeError(f"nameはstrかNoneで指定してください: {type(name).__name__}")
    if not name or "|" in name:
        raise ValueError(f"nameは'|'を含まない空でない名前で指定してください: {name!r}")
    return name


def resolve_parent(parent):
    """親として指定されたものから、Transformのオブジェクトを取得する。

    Args:
        parent (Node | str | None): 親。Noneならワールド直下。

    Returns:
        Node | None: 親のオブジェクト。

    Raises:
        TypeError: 親がTransformでない場合。
        RuntimeError: 親が無効な場合。
    """
    if parent is None:
        return None
    # nodes は core を参照するため、importが循環しないよう、呼んだときに読み込む。
    from ..nodes.node import Node
    from ..nodes.transform import Transform

    node = Node._resolve_input(parent)
    if not node.isValid():
        raise RuntimeError("parentが有効なノードではありません")
    if not isinstance(node, Transform):
        raise TypeError(f"parentはtransformで指定してください: {node.getFullName()}")
    return node


def finish_shape(transform, kind, name, parent):
    """作った形状を仕上げて、シェイプのオブジェクトを返す。

    Transform を親の下へ移し、シェイプの名前をTransformに合わせる。

    Args:
        transform (str): Mayaのコマンドが返したTransformの名前。
        kind (str): 返すシェイプの型(``"nurbsCurve"`` など)。
        name (str | None): 作るノードの名前。指定したときは、シェイプの名前を ``<Transform名>Shape`` にする。
        parent (Node | None): 親のオブジェクト。Noneならワールド直下のまま。

    Returns:
        Node: 作ったシェイプのオブジェクト。
    """
    # nodes は core を参照するため、importが循環しないよう、呼んだときに読み込む。
    from ..nodes.node import Node

    transform = cmds.ls(transform, long=True)[0]
    if parent is not None:
        transform = cmds.ls(cmds.parent(transform, parent.getFullName(), relative=True)[0], long=True)[0]
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type=kind)[0]
    if name:
        expected = transform.rsplit("|", 1)[-1] + "Shape"
        if shape.rsplit("|", 1)[-1] != expected:
            shape = cmds.rename(shape, expected)
            shape = cmds.ls(transform + "|" + shape.rsplit("|", 1)[-1], long=True)[0]
    return Node(shape)


def positive_size(value, name):
    """大きさが正の有限な値かを確かめる。

    Args:
        value (float): 大きさ。boolは受け付けない。
        name (str): 例外メッセージに使う引数名。

    Returns:
        float: 確かめた値。

    Raises:
        TypeError: 実数でない場合。
        ValueError: 0以下・無限大・NaNの場合。
    """
    value = _finite(value, name)
    if value <= 0:
        raise ValueError(f"{name}は正の値で指定してください")
    return value


def subdivision_counts(value, size, name="subdivisions"):
    """分割数の並びを確かめる。

    Args:
        value (Sequence[int]): 分割数。各要素は1以上のint(boolは除く)。
        size (int): 要素の数。
        name (str): 例外メッセージに使う引数名。

    Returns:
        tuple[int, ...]: 確かめた分割数。

    Raises:
        TypeError: 順に取り出せない場合、またはint以外を含む場合。
        ValueError: 要素の数が違う場合、または1より小さい値を含む場合。
    """
    try:
        items = tuple(value)
    except TypeError:
        raise TypeError(f"{name}は{size}個のintの並びで指定してください") from None
    if len(items) != size:
        raise ValueError(f"{name}は{size}個の値で指定してください")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in items):
        raise TypeError(f"{name}の要素はintで指定してください")
    if any(item < 1 for item in items):
        raise ValueError(f"{name}は1以上で指定してください")
    return items


def create_poly(command, flags, name, parent):
    """ポリゴンのプリミティブを作り、シェイプを返す。

    コンストラクションヒストリは作らない。

    Args:
        command (callable): ``cmds.polyCube`` など。
        flags (dict): コマンドへ渡すフラグ(距離はcm)。
        name (str | None): 確かめてある、作るノードの名前。
        parent (Node | None): 親のオブジェクト。

    Returns:
        Mesh: 作成したシェイプ。
    """
    flags = dict(flags, constructionHistory=False)
    if name:
        flags["name"] = name
    with undoTransaction("mlibCreate" + command.__name__[0].upper() + command.__name__[1:]), preservedSelection():
        # ポリゴンのコマンドは大きさを今のUIの単位で読むので、内部の単位(cm)へ切り替えてから渡す。
        with nativeUnits():
            transform = command(**flags)[0]
        return finish_shape(transform, "mesh", name, parent)
