"""形状を作る関数(``mlib.createCurve`` など)が共通で使う処理。名前・親・シェイプ名を整える。"""

import contextlib

import maya.api.OpenMaya as om2
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


def require_existing(names):
    """名前で指定された対象がシーンにあるかを確かめる。

    Mayaのコマンドへ渡す前に確かめ、見つからない名前でMayaのValueErrorがそのまま出ないようにする。

    Args:
        names (Iterable[str]): ノード・コンポーネントの名前。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: シーンに無い名前がある場合。文言は ``ノードが見つかりません: <名前>``。
    """
    for name in names:
        if not cmds.objExists(name):
            raise RuntimeError(f"ノードが見つかりません: {name}")


def require_shape_type(names, kind, label):
    """対象が、指定した型(継承先を含む)の形状か、その形状を持つtransformかを確かめる。

    コンポーネントの名前は、持ち主のノードで確かめる。中間オブジェクトの形状は数えない。

    Args:
        names (Iterable[str]): シーンにあることを確かめた、ノード・コンポーネントの名前。
        kind (str): 求める形状のMayaの型名(``"deformableShape"``・``"nurbsCurve"`` など)。
        label (str): 例外メッセージに使う、対象の呼び名(``"ターゲット"`` など)。

    Returns:
        None: 値を返さない。

    Raises:
        ValueError: 求める型の形状を持たない対象がある場合。
    """
    for name in names:
        node = name.split(".", 1)[0]
        if kind in (cmds.nodeType(node, inherited=True) or ()):
            continue
        shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True) or ()
        if not any(kind in (cmds.nodeType(shape, inherited=True) or ()) for shape in shapes):
            raise ValueError(f"{label}に{kind}の形状がありません: {name}")


@contextlib.contextmanager
def removing_created_nodes():
    """中で例外が起きたら、中で作られて残ったノードを消してから例外を出し直す。

    Mayaのコマンドが途中で失敗したときに、作りかけのノードがシーンに残らないようにする。
    作られたノードは ``MDGMessage.addNodeAddedCallback`` で集め、成功したときは何もしない。

    Yields:
        None: 値を渡さない。

    Raises:
        Exception: 中で起きた例外をそのまま出し直す。
    """
    created = []

    def collect(mobject, client_data):  # noqa: ARG001 引数はMayaのコールバックが決める
        """作られたノードを、あとで有効か確かめられる形で覚える。"""
        created.append(om2.MObjectHandle(mobject))

    callback = om2.MDGMessage.addNodeAddedCallback(collect, "dependNode")
    try:
        yield
    except Exception:
        om2.MMessage.removeCallback(callback)
        callback = None
        names = []
        for handle in created:
            if not handle.isValid():
                continue
            mobject = handle.object()
            if mobject.hasFn(om2.MFn.kDagNode):
                names.append(om2.MFnDagNode(mobject).fullPathName())
            else:
                names.append(om2.MFnDependencyNode(mobject).name())
        for name in names:
            # transformを消すと子のシェイプも消えるので、残っているものだけを消す。
            if name and cmds.objExists(name):
                cmds.delete(name)
        raise
    finally:
        if callback is not None:
            om2.MMessage.removeCallback(callback)


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
