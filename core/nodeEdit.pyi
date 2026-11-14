# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ノードの作成・名前の変更・削除を行う内部の処理。

作成と名前の変更は、Undoに記録しないOpenMayaの処理。
削除は、通常(cmds)とfast(OpenMaya)の両方で使う事前の検査と、1回にまとめた削除を持つ。
"""

import itertools
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from typing import Iterator, Sequence
from mlib.nodes.node import Node


def _dag_descendants(mobject: om2.MObject) -> Iterator[om2.MObject]:
    """DAGノードの子孫をすべて列挙する。

    深さ優先でたどる。DGノードでは何も返さない。

    Args:
        mobject (om2.MObject): たどり始めるノード。自身は含めない。

    Yields:
        om2.MObject: 子、その子孫の順に返す(それぞれの親の子は、最後の子からたどる)。
    """
    ...

def require_editable(node: om2.MObject, descendants: bool = ...) -> None:
    """ノードを編集できるかを調べる。

    階層などを変える前に呼び、リファレンスのノードやロックされたノードなら止める。

    Args:
        node (om2.MObject): 調べるノード。
        descendants (bool): TrueならDAGの子孫も調べる。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: ノードが無効な場合、またはロックされたノードかリファレンスのノードが、対象か子孫に含まれる場合。
    """
    ...

def check_deletion(nodes: Sequence[Node], fast: bool = ...) -> list[tuple[om2.MObject, str]]:
    """削除する前に、すべての対象を調べる。

    1つでも削除できない対象があれば、何も削除せずに例外にする。調べる内容は次のとおり。

    - 対象とDAGの子孫のロック、リファレンスかどうか。
    - Mayaが削除を拒否するノード。``cmds.ls(undeletable=True)`` が返す既定のノードや共有ノードで、
      time1・persp・defaultLayer などがある。

    通常の ``cmds.delete`` にまとめて渡すと、これらはエラーを表示するだけで飛ばされ、ほかの削除は続く。
    OpenMaya での削除は、既定のノードや共有ノードでMayaが異常終了する。そのため、どちらの場合も書き換える前に例外にする。

    Args:
        nodes (Sequence[Node]): 削除するノード。呼び出しで渡された順。
        fast (bool): Trueなら、例外の文言をfast(OpenMaya)の経路の従来の文言にする。

    Returns:
        list[tuple[om2.MObject, str]]: 対象の順に並べた (MObject, 完全パスまたは名前)。

    Raises:
        RuntimeError: 無効な対象がある場合、またはロック・リファレンス・削除できないノードが対象かDAGの子孫に
            含まれる場合。属性 ``index`` に、原因になった対象の番号を持つ。
    """
    ...

def delete_nodes(nodes: Sequence[Node], fast: bool = ..., checked: list | None = ...) -> None:
    """すべての対象を1回で削除する。

    削除の前に検査をする。削除の仕方は次のとおり。

    - 通常は、完全パスを ``cmds.delete`` へ1回で渡す。
    - fast は、1つの MDagModifier へすべての対象を積み、doIt を1回呼ぶ(DG ノードも同じ modifier で扱う)。

    削除の順番や、つられて消えるノードは、Maya がまとめて削除するときの決まりに従う。
    同じノードを重ねて指定した場合や、親と子の両方を指定した場合、通常は ``cmds.delete`` がまとめる。
    fast では、先の削除ですでに消えた対象を積まない(親と一緒に消えた子、つられて消えたノード、同じノードの重複)。

    Args:
        nodes (Sequence[Node]): 削除するノード。呼び出しで渡された順で、1つ以上。
        fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
        checked (list | None): 同じ nodes で :func:`check_deletion` を呼んだときの戻り値。
            Noneならここで検査する。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: :func:`check_deletion` が削除を拒否した場合。何も削除しない。
    """
    ...

def _referenced_message(path: str, owner: str | None = ...) -> str:
    """リファレンスのノードを削除しようとしたときの文言を作る。

    Args:
        path (str): リファレンスのノードの完全パスまたは名前。
        owner (str | None): 削除しようとした対象。pathがその子孫の場合に指定する。

    Returns:
        str: リファレンスノード(``RN`` ノード)とファイルを示す文言。
    """
    ...

def _deletion_error(index: int, message: str) -> RuntimeError:
    """削除の RuntimeError を作る。例外には対象の番号を持たせる。

    Args:
        index (int): 原因になった対象の番号。
        message (str): 例外の文言。

    Returns:
        RuntimeError: ``index`` 属性を持つ例外。
    """
    ...

def _display_name(path: str) -> str:
    """例外の文言に使う名前を返す。

    Maya の表示と同じ、ほかと区別できる最も短い名前にする。

    Args:
        path (str): 完全パスまたは名前。

    Returns:
        str: DAG は partialPathName、DG はノード名。
    """
    ...

def rename_node(node: om2.MObject, name: str, ignore_shape: bool = ...) -> str:
    """ノードの名前を変える。

    直下のShapeのうち、名前が元の名前で始まるものも、合わせて名前を変える。

    Args:
        node (om2.MObject): 名前を変えるノード。
        name (str): 新しい名前。使えない文字などはMayaが直す。
        ignore_shape (bool): Trueなら、直下のShapeの名前は変えない。

    Returns:
        str: Mayaが決めたノード名。
    """
    ...

def create_node(node_type: str, flags: dict) -> om2.MObject:
    """OpenMayaでノードを作成する。

    createNodeのおもなフラグ(name・parent・skipSelect・shared)に対応する。

    Args:
        node_type (str): 作成するnodeType。
        flags (dict): 形を揃えてあるname・parent・skipSelect・shared。

    Returns:
        om2.MObject: 作成したノード。Shapeの場合、自動で作られる親ではなくShapeを返す。
            shared=Trueで、同じ名前・同じ型のノードが1つだけあれば、そのノードを返す。
            cmdsはルート名前空間の名前だけを使い回すが、ここでは名前空間付きの名前でも
            既存のノードを返す(cmdsに近づけた扱い)。

    Raises:
        RuntimeError: Mayaが認識しないnodeTypeの場合、親がロックされているかリファレンスの場合、
            またはshared=Trueで同じ名前のノードの型が違う場合(cmdsは新しい連番の名前で作るが、fastは型を見て止める)。
        NotImplementedError: name・parent・skipSelect・shared以外のフラグを指定した場合。
    """
    ...
