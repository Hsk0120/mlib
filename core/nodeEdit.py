"""ノードの作成・名前の変更・削除を行う内部の処理。

作成と名前の変更は、Undoに記録しないOpenMayaの処理。
削除は、通常(cmds)とfast(OpenMaya)の両方で使う事前の検査と、1回にまとめた削除を持つ。
"""

import itertools

import maya.api.OpenMaya as om2
import maya.cmds as cmds


def _dag_descendants(mobject):
    """DAGノードの子孫をすべて列挙する。

    深さ優先でたどる。DGノードでは何も返さない。

    Args:
        mobject (om2.MObject): たどり始めるノード。自身は含めない。

    Yields:
        om2.MObject: 子、その子孫の順に返す(それぞれの親の子は、最後の子からたどる)。
    """
    if not mobject.hasFn(om2.MFn.kDagNode):
        return
    pending = [mobject]
    while pending:
        dag = om2.MFnDagNode(pending.pop())
        for i in range(dag.childCount()):
            child = dag.child(i)
            yield child
            pending.append(child)


def require_editable(node, descendants=False):
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
    seen = set()
    # 子孫は必要になったときに1つずつ列挙するため、対象自身が有効かを確かめてから子孫をたどる。
    for obj in itertools.chain((node,), _dag_descendants(node) if descendants else ()):
        handle = om2.MObjectHandle(obj)
        if not handle.isValid() or not handle.isAlive():
            raise RuntimeError("無効なノードは編集できません")
        key = handle.hashCode()
        if key in seen:
            continue
        seen.add(key)
        fn = om2.MFnDependencyNode(obj)
        if fn.isLocked or fn.isFromReferencedFile:
            raise RuntimeError(f"ノードがロックされているか、リファレンスです: {fn.name()}")


def check_deletion(nodes, fast=False):
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
    entries = []
    for index, node in enumerate(nodes):
        obj = node.mnode()
        handle = om2.MObjectHandle(obj) if obj is not None else None
        if handle is None or not handle.isValid() or not handle.isAlive():
            raise _deletion_error(index, "無効なノードは編集できません" if fast else "無効なノードは削除できません")
        entries.append((obj, node.getFullName()))
    # 対象ごとのDAGの子孫をAPIでたどり、ロック・リファレンスの子孫と、削除できるかを問い合わせる名前を集める。
    descendants = []
    names = [path for _obj, path in entries]
    for obj, _path in entries:
        found = list(_dag_descendants(obj))
        descendants.append(found)
        names += [om2.MDagPath.getAPathTo(child).fullPathName() for child in found]
    # cmds.ls(undeletable=True) が、既定・共有ノード等のMayaが削除を拒否するノードを返す
    # (ロックされたノードも含む)。全対象と子孫を1回で問い合わせる。
    blocked = set(cmds.ls(names, long=True, undeletable=True) or [])
    offset = len(entries)
    for index, (obj, path) in enumerate(entries):
        fn = om2.MFnDependencyNode(obj)
        if fn.isFromReferencedFile:
            raise _deletion_error(index, _referenced_message(path))
        if fn.isLocked:
            if fast:
                raise _deletion_error(index, f"ノードがロックされているか、リファレンスです: {fn.name()}")
            raise _deletion_error(index, f"ロックされたノード'{_display_name(path)}'は削除できません")
        if fn.isDefaultNode or path in blocked:
            raise _deletion_error(index, f"削除できないノードです: '{_display_name(path)}'")
        child_names = names[offset : offset + len(descendants[index])]
        offset += len(descendants[index])
        for child, child_path in zip(descendants[index], child_names):
            child_fn = om2.MFnDependencyNode(child)
            if child_fn.isFromReferencedFile:
                raise _deletion_error(index, _referenced_message(child_path, path))
            if child_fn.isLocked:
                if fast:
                    raise _deletion_error(index, f"ノードがロックされているか、リファレンスです: {child_fn.name()}")
                raise _deletion_error(index, f"'{_display_name(path)}'は削除できません。ロックされた子か、読み取り専用の子があります")
            if child_fn.isDefaultNode or child_path in blocked:
                raise _deletion_error(index, f"削除できないノードです: '{_display_name(child_path)}'")
    return entries


def delete_nodes(nodes, fast=False, checked=None):
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
    entries = check_deletion(nodes, fast=fast) if checked is None else checked
    if not fast:
        cmds.delete([path for _obj, path in entries])
        return
    modifier = om2.MDagModifier()
    queued = {}
    for obj, _path in entries:
        handle = om2.MObjectHandle(obj)
        # DAG の deleteNode はその場で削除を進めるので、子やつられて消えるノードのハンドルは無効になる。
        # 消えた対象や重複を積むと doIt が失敗するため飛ばす(ハッシュの衝突は MObject の比較で区別する)。
        same = queued.setdefault(handle.hashCode(), [])
        if not handle.isValid() or any(obj == other for other in same):
            continue
        same.append(obj)
        # cmds.deleteと同じく、対象の空の親は残す(modifierの既定Trueとは異なる)。
        modifier.deleteNode(obj, False)
    modifier.doIt()


def _referenced_message(path, owner=None):
    """リファレンスのノードを削除しようとしたときの文言を作る。

    Args:
        path (str): リファレンスのノードの完全パスまたは名前。
        owner (str | None): 削除しようとした対象。pathがその子孫の場合に指定する。

    Returns:
        str: リファレンスノード(``RN`` ノード)とファイルを示す文言。
    """
    try:
        reference = cmds.referenceQuery(path, referenceNode=True)
    except RuntimeError:
        reference = None
    try:
        filename = cmds.referenceQuery(path, filename=True, withoutCopyNumber=True)
    except RuntimeError:
        filename = None
    source = f"(リファレンス: {reference!r})" if reference else ""
    if filename:
        source += f" ({filename})"
    name = _display_name(path)
    if owner is not None:
        return f"'{_display_name(owner)}'は削除できません。子孫の'{name}'がリファレンスのノードです{source}。リファレンスのノードは、リファレンスを編集するかアンロードしないと削除できません"
    return f"'{name}'は削除できません。リファレンスのノードです{source}。リファレンスのノードは、リファレンスを編集するかアンロードしないと削除できません"


def _deletion_error(index, message):
    """削除の RuntimeError を作る。例外には対象の番号を持たせる。

    Args:
        index (int): 原因になった対象の番号。
        message (str): 例外の文言。

    Returns:
        RuntimeError: ``index`` 属性を持つ例外。
    """
    error = RuntimeError(message)
    setattr(error, "index", index)  # noqa: B010  # RuntimeError の型に無い属性を追加する。
    return error


def _display_name(path):
    """例外の文言に使う名前を返す。

    Maya の表示と同じ、ほかと区別できる最も短い名前にする。

    Args:
        path (str): 完全パスまたは名前。

    Returns:
        str: DAG は partialPathName、DG はノード名。
    """
    selection = om2.MSelectionList()
    selection.add(path)
    try:
        return selection.getDagPath(0).partialPathName()
    except TypeError:
        return om2.MFnDependencyNode(selection.getDependNode(0)).name()


def rename_node(node, name, ignore_shape=False):
    """ノードの名前を変える。

    直下のShapeのうち、名前が元の名前で始まるものも、合わせて名前を変える。

    Args:
        node (om2.MObject): 名前を変えるノード。
        name (str): 新しい名前。使えない文字などはMayaが直す。
        ignore_shape (bool): Trueなら、直下のShapeの名前は変えない。

    Returns:
        str: Mayaが決めたノード名。
    """
    require_editable(node)
    fn = om2.MFnDependencyNode(node)
    old = fn.name()
    shapes = []
    if not ignore_shape and node.hasFn(om2.MFn.kTransform):
        dag = om2.MFnDagNode(node)
        for i in range(dag.childCount()):
            child = dag.child(i)
            child_fn = om2.MFnDependencyNode(child)
            # cmds.renameは、別の名前空間にあるShapeの名前は合わせて変えない。
            short = child_fn.name()
            if child.hasFn(om2.MFn.kShape) and short.startswith(old):
                require_editable(child)
                shapes.append((child, short[len(old) :]))
    result = fn.setName(str(name))
    for shape, suffix in shapes:
        om2.MFnDependencyNode(shape).setName(result + suffix)
    return result


def create_node(node_type, flags):
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
    # 循環参照の回避: nodes は core を参照するため、使う時点で読み込む。
    from ..nodes.node import Node

    unsupported = set(flags) - {"name", "parent", "skipSelect", "shared"}
    if unsupported:
        raise NotImplementedError(f"fastのcreateNodeは次のフラグに対応していません: {', '.join(sorted(unsupported))}")
    # MNodeClassは知らない型名でも例外にならず、typeId が 0 になる。その値で判定して作成前に止める
    # (呼び出し側の _node_type_exists と重なるが、軽い処理なので残す)。DAGとしての作成に失敗してDGへ切り替えても、
    # doIt の前なので、作りかけのノードはシーンに残らない。
    if om2.MNodeClass(node_type).typeId.id() == 0:
        raise RuntimeError(f"Mayaにないノード型です: {node_type}")
    parent = Node(flags["parent"]).mnode() if flags.get("parent") else om2.MObject.kNullObj
    if not parent.isNull():
        require_editable(parent)
    name = flags.get("name")
    if flags.get("shared") and name:
        selection = om2.MSelectionList()
        try:
            selection.add(name)
        except RuntimeError:
            pass
        else:
            if selection.length() == 1:
                existing = selection.getDependNode(0)
                existing_type = om2.MFnDependencyNode(existing).typeName
                if existing_type != node_type:
                    raise RuntimeError(f"shared=True: 既存のノード{name!r}の型は{existing_type!r}で、{node_type!r}ではありません")
                return existing
    modifier = om2.MDagModifier()
    try:
        obj = modifier.createNode(node_type, parent)
    except (RuntimeError, TypeError):
        if not parent.isNull():
            raise
        modifier = om2.MDGModifier()
        obj = modifier.createNode(node_type)
    modifier.doIt()
    if om2.MFnDependencyNode(obj).typeName != node_type and obj.hasFn(om2.MFn.kDagNode):
        # Shapeをワールド直下へ作る場合、MDagModifierは自動作成したTransformを返す。
        dag = om2.MFnDagNode(obj)
        obj = next(dag.child(i) for i in range(dag.childCount()) if om2.MFnDependencyNode(dag.child(i)).typeName == node_type)
    if name:
        om2.MFnDependencyNode(obj).setName(str(name))
    if not flags.get("skipSelect", False):
        selected = om2.MSelectionList()
        selected.add(obj)
        om2.MGlobal.setActiveSelectionList(selected, om2.MGlobal.kReplaceList)
    return obj
