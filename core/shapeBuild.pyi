# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""形状を作る関数(``mlib.createCurve`` など)が共通で使う処理。名前・親・シェイプ名を整える。"""

import maya.cmds as cmds
from ..decorator import nativeUnits, preservedSelection, undoTransaction
from ..util import _finite
from typing import Any, Callable, Sequence
from mlib.nodes.mesh import Mesh
from mlib.nodes.node import Node


def require_name(name: str | None) -> str | None:
    """作るノードの名前を確かめる。

    Args:
        name (str | None): 作るノードの名前。Noneなら Maya の既定の名前。

    Returns:
        str | None: 確かめた名前。

    Raises:
        TypeError: nameが文字列でもNoneでもない場合。
        ValueError: nameが空文字列の場合、またはDAGパスの区切り ``|`` を含む場合。
    """
    ...

def resolve_parent(parent: Node | str | None) -> Node | None:
    """親として指定されたものから、Transformのオブジェクトを取得する。

    Args:
        parent (Node | str | None): 親。Noneならワールド直下。

    Returns:
        Node | None: 親のオブジェクト。

    Raises:
        TypeError: 親がTransformでない場合。
        RuntimeError: 親が無効な場合。
    """
    ...

def finish_shape(transform: str, kind: str, name: str | None, parent: Node | None) -> Node:
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
    ...

def positive_size(value: float, name: str) -> float:
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
    ...

def subdivision_counts(value: Sequence[int], size: int, name: str = ...) -> tuple[int, ...]:
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
    ...

def create_poly(command: Callable[..., Any], flags: dict, name: str | None, parent: Node | None) -> Mesh:
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
    ...
