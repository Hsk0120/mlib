"""シーンのリファレンスを一覧にしたり、作ったりする。"""

from pathlib import Path
from typing import Any, Dict

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import undoChunk

# Maya が常に作る共有のリファレンスノード。ユーザーが作ったリファレンスではないため、一覧から除く。
_SHARED_REFERENCE_NODE = "sharedReferenceNode"


def _reference_nodes():
    """リファレンスノードを、``cmds.ls(type="reference")`` と同じ名前順で列挙する。

    共有のリファレンスノードは除く。

    Returns:
        list[tuple[str, om2.MObject]]: ``(ノード名, MObject)`` の list。名前順(文字コード順)に並ぶ。
    """
    iterator = om2.MItDependencyNodes(om2.MFn.kReference)
    fn = om2.MFnDependencyNode()
    nodes = []
    while not iterator.isDone():
        mobject = iterator.thisNode()
        iterator.next()
        fn.setObject(mobject)
        name = fn.name()
        if name != _SHARED_REFERENCE_NODE:
            nodes.append((name, mobject))
    # cmds.ls(type="reference") は名前の文字コード順で返すため、作成順の反復結果を並べ替える。
    nodes.sort(key=lambda item: item[0])
    return nodes


def listReferences(topLevelOnly=False):
    """シーンのリファレンスを、Reference のオブジェクトの一覧として取得する。

    Args:
        topLevelOnly (bool): True なら、ほかのリファレンスの中に入っていない(ネストされていない)
            トップレベルのリファレンスだけを返す。

    Returns:
        list[Reference]: リファレンスのオブジェクトの一覧(``cmds.ls(type="reference")`` と同じ名前順)。
            リファレンスが無ければ空リスト。名前順なので、リファレンスを作った順や読み込んだ順とは限らない。
    """
    # commonの初期化時にnodesを読み込まないよう、使用時にReferenceを読み込む。
    from ..nodes.reference import Reference

    references = [Reference(mobject) for _, mobject in _reference_nodes()]
    if topLevelOnly:
        references = [reference for reference in references if reference.getParentReference() is None]
    return references


@undoChunk("mlibCreateReference")
def createReference(path, namespace=None):
    """ファイルをリファレンスし、新しく作られたトップレベルのReferenceを返す。

    リファレンスしたファイルの中にあるリファレンス(子のリファレンス)も作られることがあるが、
    返すのは親のリファレンスを持たない1件だけ。
    リファレンスノードを特定できなかった場合も、作ったものを自動では元に戻さない。

    Args:
        path (str | Path): リファレンスするファイル。``~`` はユーザーのホームに展開する。
        namespace (str | None): リファレンスの中身を入れる名前空間。NoneならMayaの既定を使う。

    Returns:
        Reference: 作ったトップレベルのリファレンスノード。

    Raises:
        ValueError: pathが空の場合、またはstrでもPathでもない場合。
        RuntimeError: Mayaが作成を拒否した場合、または新しいトップレベルのリファレンスが1件に決まらない場合。

    Note:
        fast引数は無い。リファレンスの読み込み(ファイルの読み込み・リファレンスノードと名前空間の作成)は
        ``cmds.file(reference=True)`` でしかできず、OpenMayaに同じことをUndoなしで行う方法が無いため。
    """
    # commonの初期化時にnodesを読み込まないよう、使用時にReferenceを読み込む。
    from ..nodes.reference import Reference

    if not isinstance(path, (str, Path)) or not str(path):
        raise ValueError("pathは空でない文字列かPathで指定してください")
    scene_path = Path(path).expanduser()

    existing = {name for name, _ in _reference_nodes()}
    kwargs: Dict[str, Any] = {"reference": True}
    if namespace is not None:
        kwargs["namespace"] = namespace
    cmds.file(str(scene_path), **kwargs)

    created = [Reference(mobject) for name, mobject in _reference_nodes() if name not in existing]
    # 参照先ファイル自身がネストした参照を持つ場合、その子参照ノードも同時に
    # 新規ノードとして現れるため、親を持たないトップレベルのものだけを選ぶ。
    top_level = [reference for reference in created if reference.getParentReference() is None]
    if len(top_level) != 1:
        names = [reference.getName() for reference in created]
        raise RuntimeError(f"新しく作成されたリファレンスノードを特定できませんでした: {names}")
    return top_level[0]


# reload時にも廃止した公開名を残さない。
for _obsolete_name in ("create_reference", "list_references"):
    globals().pop(_obsolete_name, None)
