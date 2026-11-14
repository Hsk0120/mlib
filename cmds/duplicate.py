"""1つの対象を複製し、複製した先頭のノードを、型に合ったオブジェクトで返す(``cmds.duplicate`` 相当)。"""

import re

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import _merge_flags, undoChunk
from ..util import _UNSET

#: suffix に使える文字(Mayaのノード名の文字)。
_SUFFIX = re.compile(r"^[A-Za-z0-9_]+$")


def duplicate(
    node,
    *,
    fullPath=_UNSET,
    f=_UNSET,
    inputConnections=_UNSET,
    ic=_UNSET,
    instanceLeaf=_UNSET,
    ilf=_UNSET,
    name=_UNSET,
    n=_UNSET,
    parentOnly=_UNSET,
    po=_UNSET,
    renameChildren=_UNSET,
    rc=_UNSET,
    returnRootsOnly=_UNSET,
    rr=_UNSET,
    smartTransform=_UNSET,
    st=_UNSET,
    transformsOnly=_UNSET,
    to=_UNSET,
    upstreamNodes=_UNSET,
    un=_UNSET,
    query=_UNSET,
    q=_UNSET,
    edit=_UNSET,
    e=_UNSET,
    suffix=None,
    **kwargs,
):
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
    _merge_flags(
        kwargs,
        (
            (fullPath, f, "fullPath", "f"),
            (inputConnections, ic, "inputConnections", "ic"),
            (instanceLeaf, ilf, "instanceLeaf", "ilf"),
            (name, n, "name", "n"),
            (parentOnly, po, "parentOnly", "po"),
            (renameChildren, rc, "renameChildren", "rc"),
            (returnRootsOnly, rr, "returnRootsOnly", "rr"),
            (smartTransform, st, "smartTransform", "st"),
            (transformsOnly, to, "transformsOnly", "to"),
            (upstreamNodes, un, "upstreamNodes", "un"),
            (query, q, "query", "q"),
            (edit, e, "edit", "e"),
        ),
    )
    if suffix is not None:
        if not isinstance(suffix, str):
            raise TypeError("suffixは文字列かNoneで指定してください")
        if not _SUFFIX.match(suffix):
            raise ValueError(f"suffixは英数字と'_'だけの空でない文字列で指定してください: {suffix!r}")
        if kwargs.get("renameChildren"):
            raise ValueError("suffixはrenameChildren=Trueと同時に指定できません")
        # 接尾辞の改名には複製の起点を一意に特定する必要があるため、完全パスで受け取る。
        kwargs.setdefault("fullPath", True)
    with undoChunk("mlibDuplicate"):
        # nodesはcmdsを参照するため、循環importを避けて関数内で読み込む。
        from ..core.object import Object as _InputObject
        from ..nodes import Node

        name = _InputObject._input_name(node)
        source = Node._resolve_input(node) if suffix is not None else None
        result = cmds.duplicate(name, **kwargs)
        copied = Node(result[0])
        if suffix is not None:
            # suffixを指定した場合は、複製前に起点を解決済み。
            assert source is not None
            _apply_suffix(source.mnode(), copied.mnode(), suffix, "name" not in kwargs)
        return copied


def _apply_suffix(source, copied, suffix, rename_root):
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
    pairs = [(source, copied)] if rename_root else []
    if source.hasFn(om2.MFn.kDagNode) and copied.hasFn(om2.MFn.kDagNode):
        _collect_child_pairs(source, copied, pairs)
    for origin, target in pairs:
        if origin == target:
            continue
        base = om2.MFnDependencyNode(origin).name().rpartition(":")[2]
        current = om2.MFnDependencyNode(target).name()
        namespace = current.rpartition(":")[0]
        new_name = ":" + (namespace + ":" if namespace else "") + base + suffix
        if target.hasFn(om2.MFn.kDagNode):
            cmds.rename(om2.MFnDagNode(target).fullPathName(), new_name, ignoreShape=True)
        else:
            cmds.rename(current, new_name)


def _collect_child_pairs(source, copied, pairs):
    """複製元と複製の子を対応させ、pairs へ追加する。

    子は同じ並び順で対応させ、深さ優先でたどる。

    Args:
        source (om2.MObject): 複製元のDAGノード。
        copied (om2.MObject): 対応する複製のDAGノード。
        pairs (list[tuple[om2.MObject, om2.MObject]]): 対応を追加するリスト。

    Returns:
        None: 値を返さない。
    """
    if source == copied:
        return
    source_fn = om2.MFnDagNode(source)
    copied_fn = om2.MFnDagNode(copied)
    origins = [source_fn.child(index) for index in range(source_fn.childCount())]
    targets = [copied_fn.child(index) for index in range(copied_fn.childCount())]
    if len(origins) != len(targets):
        origins = [child for child in origins if not child.hasFn(om2.MFn.kShape)]
    if len(origins) != len(targets):
        return
    for origin, target in zip(origins, targets):
        pairs.append((origin, target))
        _collect_child_pairs(origin, target, pairs)
