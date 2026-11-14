# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""1つの対象を複製し、複製した先頭のノードを、型に合ったオブジェクトで返す(``cmds.duplicate`` 相当)。"""

import re
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import _merge_flags, undoChunk
from ..util import _UNSET
from typing import Any
from mlib.nodes.node import Node

_SUFFIX: Any

def duplicate(node: object, *, fullPath: bool = ..., f: bool = ..., inputConnections: bool = ..., ic: bool = ..., instanceLeaf: bool = ..., ilf: bool = ..., name: str = ..., n: str = ..., parentOnly: bool = ..., po: bool = ..., renameChildren: bool = ..., rc: bool = ..., returnRootsOnly: bool = ..., rr: bool = ..., smartTransform: bool = ..., st: bool = ..., transformsOnly: bool = ..., to: bool = ..., upstreamNodes: bool = ..., un: bool = ..., query: bool = ..., q: bool = ..., edit: bool = ..., e: bool = ..., suffix: str | None = ..., **kwargs: object) -> Node:
    """指定したノードを複製し、型に合ったオブジェクトとして返す。

    処理は ``maya.cmds.duplicate`` が行い、MayaのUndoに対応する(1回のUndoで戻せる)。fast引数は無い。

    フラグの既定値 ``_UNSET`` は、省略されたかを見分けるためだけの値。省略したフラグはMayaへ渡さず、
    Mayaの既定の動きのままにする。長い名前と短い名前を同時に指定すると、入力を調べる前、
    Undoを始める前にエラーにする。その版のMayaに無いフラグは、Mayaがエラーにする。

    Args:
        node (object): 複製元。Node・Plug・Component・APIのオブジェクト、または名前。
            Mayaへ渡す一意な名前に変える。
        fullPath (bool): Trueなら、Mayaの複製結果を完全なDAGパスで受け取る。mlibの戻り値の型は変わらない。
        f (bool): fullPathの短縮名。fullPathと同時には指定できない。
        inputConnections (bool): Trueなら、入力の接続も複製する。
        ic (bool): inputConnectionsの短縮名。inputConnectionsと同時には指定できない。
        instanceLeaf (bool): Trueなら、末端のノードを複製せず、インスタンスにする。
        ilf (bool): instanceLeafの短縮名。instanceLeafと同時には指定できない。
        name (str): Mayaへ渡すノード名。
        n (str): nameの短縮名。nameと同時には指定できない。
        parentOnly (bool): Trueなら、指定した対象だけを複製し、子の階層を含めない。
        po (bool): parentOnlyの短縮名。parentOnlyと同時には指定できない。
        renameChildren (bool): Trueなら、複製した子の名前をMayaの規則で付け直す。
        rc (bool): renameChildrenの短縮名。renameChildrenと同時には指定できない。
        returnRootsOnly (bool): Trueなら、Maya側の戻り値を複製のルートだけにする。mlibは先頭をオブジェクトにして返す。
        rr (bool): returnRootsOnlyの短縮名。returnRootsOnlyと同時には指定できない。
        smartTransform (bool): Mayaのスマート複製の指定。前回の複製からの変換の差を使う。
        st (bool): smartTransformの短縮名。smartTransformと同時には指定できない。
        transformsOnly (bool): Trueなら、Transformだけを複製する(Mayaのフラグ)。
        to (bool): transformsOnlyの短縮名。transformsOnlyと同時には指定できない。
        upstreamNodes (bool): Trueなら、上流の依存ノードも複製する。
        un (bool): upstreamNodesの短縮名。upstreamNodesと同時には指定できない。
        query (bool): 問い合わせのモード。コマンドが対応していない場合はMayaがエラーにする。
        q (bool): queryの短縮名。queryと同時には指定できない。
        edit (bool): 編集のモード。コマンドが対応していない場合はMayaがエラーにする。
        e (bool): editの短縮名。editと同時には指定できない。
        suffix (str | None): mlib独自の指定。名前の末尾に付ける文字列。Noneなら名前を変えない。
            複製の起点のノードと、複製されたDAGの子孫すべて(shape・intermediateを含む)の名前を、
            「複製元の名前(名前空間を除く) + suffix」にする
            (例: ``L_hip|L_knee`` を ``"_FK"`` で複製すると ``L_hip_FK|L_knee_FK``)。

            - 名前空間は、Mayaが複製を置いた名前空間のまま。
            - name を同時に指定した場合、起点のノードは name のままにし、子孫だけに末尾の文字列を付ける。
            - renameChildren=True とは同時に指定できない。
            - インスタンスとして共有された子孫(instanceLeaf)と、upstreamNodes などで複製されたDGノードは、
              名前を変えない。
            - 新しい名前が兄弟と重なる場合は、Mayaが番号を付ける。
        **kwargs (object): 今後Mayaに追加される、mlibが知らないフラグ。そのままMayaへ渡す。

    Returns:
        Node: 複製の起点のノードのオブジェクト。

    Raises:
        TypeError: 長い名前と短い名前を同時に指定した場合、nodeが対応していない型の場合、
            または suffix が文字列でもNoneでもない場合。
        ValueError: node が空文字列・存在しない名前・複数に一致する名前の場合、または削除済みの対象の場合。
            suffix が空文字列の場合、英数字と ``_`` 以外を含む場合、または renameChildren=True と同時に
            指定した場合。
        RuntimeError: Maya が複製を拒否した場合。

    Examples:
        >>> import mlib
        >>> node = mlib.createNode("transform", name="example")
        >>> copied = mlib.duplicate(node, name="exampleCopy")
        >>> # 複製したjointチェーンの全ノードへ接尾辞を付ける(L_hip_FK|L_knee_FK|...)。
        >>> fk = mlib.duplicate("L_hip", suffix="_FK")
    """
    ...

def _apply_suffix(source: om2.MObject, copied: om2.MObject, suffix: str, rename_root: bool) -> None:
    """複製した側の名前を「複製元の名前 + suffix」に変える。

    複製元と複製は、子の並びが同じものとして対応させる。子の数が違う場合(transformsOnly などで
    shape が複製されない場合)は、shape を除いて対応させる。それでも合わない階層より下は名前を変えない。
    複製元と同じノード(共有されたインスタンス)も名前を変えない。

    Args:
        source (om2.MObject): 複製元の起点のノード。
        copied (om2.MObject): 複製の起点のノード。
        suffix (str): 名前の末尾に付ける文字列。
        rename_root (bool): Falseなら起点のノードの名前は変えない(name を指定したとき)。

    Returns:
        None: 値を返さない。
    """
    ...

def _collect_child_pairs(source: om2.MObject, copied: om2.MObject, pairs: list[tuple[om2.MObject, om2.MObject]]) -> None:
    """複製元と複製の子を対応させ、pairs へ追加する。

    子は同じ並び順で対応させ、深さ優先でたどる。

    Args:
        source (om2.MObject): 複製元のDAGノード。
        copied (om2.MObject): 対応する複製のDAGノード。
        pairs (list[tuple[om2.MObject, om2.MObject]]): 対応を追加するリスト。

    Returns:
        None: 値を返さない。
    """
    ...
