"""シーンのリファレンスを一覧にしたり、作ったりする。"""

from pathlib import Path
from typing import Any, Dict

import maya.api.OpenMaya as om2
import maya.cmds as cmds

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


def listReferences(topLevelOnly=False, *, sortBy="name"):
    """シーンのリファレンスを、Reference のオブジェクトの一覧として取得する。

    Args:
        topLevelOnly (bool): True なら、ほかのリファレンスの中に入っていない(ネストされていない)
            トップレベルのリファレンスだけを返す。
        sortBy (str): 並び順。``"name"``(既定)は ``cmds.ls(type="reference")`` と同じ名前順。
            ``"load"`` はシーンに読み込んだ順(``cmds.file(q=True, reference=True)`` と同じ順)で、
            ネストされたリファレンスは親のすぐ後に、親の中で読み込んだ順に並べる。

    Returns:
        Nodes[Reference]: リファレンスのオブジェクトの一覧。リファレンスが無ければ空の集まり。

    Raises:
        ValueError: sortByがnameとload以外の場合。
    """
    # commonの初期化時にnodesを読み込まないよう、使用時にReferenceを読み込む。
    from ..nodes.node import Nodes
    from ..nodes.reference import Reference

    if sortBy not in ("name", "load"):
        raise ValueError(f"sortByはnameかloadで指定してください: {sortBy!r}")
    if sortBy == "load":
        references = [Reference(name) for name in _reference_nodes_in_load_order(None, topLevelOnly)]
        return Nodes._wrap(references)
    references = [Reference(mobject) for _, mobject in _reference_nodes()]
    if topLevelOnly:
        references = [reference for reference in references if reference.getParentReference() is None]
    return Nodes._wrap(references)


def _reference_nodes_in_load_order(parent, top_level_only):
    """リファレンスノードの名前を、読み込んだ順に集める。

    Args:
        parent (str | None): 親のリファレンスのファイル名(コピー番号付き)。Noneならシーン。
        top_level_only (bool): Trueなら、ネストされたリファレンスをたどらない。

    Returns:
        list[str]: リファレンスノードの名前。親の後にその子を続ける。
    """
    paths = cmds.file(parent, query=True, reference=True) if parent else cmds.file(query=True, reference=True)
    names = []
    for path in paths or ():
        names.append(cmds.referenceQuery(path, referenceNode=True))
        if not top_level_only:
            names.extend(_reference_nodes_in_load_order(path, False))
    return names


def _require_scene_file(path, action="リファレンスする"):
    """リファレンスするファイルがあるかを確かめる。シーンは変えない。

    ``~`` はユーザーのホームに展開し、相対パスは ``cmds.file`` と同じくMayaのプロジェクト(workspace)から探す。

    Args:
        path (str | os.PathLike): 確かめるファイルのパス。空でないことは呼び出し側で確かめてある。
        action (str): メッセージに入れる、ファイルに対して行うこと(例: ``"開く"``)。

    Returns:
        Path: ``~`` を展開したパス。相対パスは相対のまま返す。

    Raises:
        OSError: ファイルが無い場合(``FileNotFoundError``)。
    """
    scene_path = Path(path).expanduser()
    found_path = scene_path if scene_path.is_absolute() else Path(cmds.workspace(expandName=str(scene_path)))
    if not found_path.is_file():
        raise FileNotFoundError(f"{action}ファイルが見つかりません: {scene_path}")
    return scene_path


def _file_without_prompt(*args, **kwargs):
    """``cmds.file`` を確認のダイアログなし(``prompt=False``)で呼び、呼ぶ前のpromptの設定へ戻す。

    Mayaの ``file -prompt`` は一度指定すると以後のすべての ``file`` コマンドに残るため、戻さないと
    利用者の後の操作(GUIでのリファレンスが見つからないときのダイアログなど)まで出なくなる。

    Args:
        *args: ``cmds.file`` へ渡す位置引数。
        **kwargs: ``cmds.file`` へ渡すフラグ。``prompt`` は指定しない。

    Returns:
        object: ``cmds.file`` の戻り値。
    """
    previous = cmds.file(query=True, prompt=True)
    try:
        return cmds.file(*args, prompt=False, **kwargs)
    finally:
        cmds.file(prompt=bool(previous))


def createReference(path, namespace=None):
    """ファイルをリファレンスし、新しく作られたトップレベルのReferenceを返す。

    リファレンスしたファイルの中にあるリファレンス(子のリファレンス)も作られることがあるが、
    返すのは親のリファレンスを持たない1件だけ。
    リファレンスノードを特定できなかった場合も、作ったものを自動では元に戻さない。
    ファイルがあるかは作る前に確かめ、無ければ何も作らずにOSErrorにする(相対パスはMayaのプロジェクトから探す)。
    ファイルの中身が壊れている場合はMayaに任せる。Mayaは例外にせず、読み込めていない(未解決の)
    リファレンスを作ることがあり、その場合もそのリファレンスを返す。

    Args:
        path (str | Path): リファレンスするファイル。``~`` はユーザーのホームに展開する。
        namespace (str | None): リファレンスの中身を入れる名前空間。NoneならMayaの既定を使う。

    Returns:
        Reference: 作ったトップレベルのリファレンスノード。

    Raises:
        ValueError: pathが空の場合、またはstrでもPathでもない場合。
        OSError: ファイルが無い場合(``FileNotFoundError``)。
        RuntimeError: Mayaが作成を拒否した場合、または新しいトップレベルのリファレンスが1件に決まらない場合。

    Note:
        fast引数は無い。リファレンスの読み込み(ファイルの読み込み・リファレンスノードと名前空間の作成)は
        ``cmds.file(reference=True)`` でしかできず、OpenMayaに同じことをUndoなしで行う方法が無いため。

        ``cmds.file`` と同じく、Undoに記録されない(Undoで取り消せない。mlibもチャンクを足さない)。
        確認のダイアログは出さず、Mayaの ``file -prompt`` の設定は呼ぶ前の値へ戻す。
    """
    # commonの初期化時にnodesを読み込まないよう、使用時にReferenceを読み込む。
    from ..nodes.reference import Reference

    if not isinstance(path, (str, Path)) or not str(path):
        raise ValueError("pathは空でない文字列かPathで指定してください")
    scene_path = _require_scene_file(path)

    existing = {name for name, _ in _reference_nodes()}
    # GUIでも確認ダイアログで止めず、読み込めないときは例外にする(promptの設定は呼ぶ前の値へ戻す)。
    kwargs: Dict[str, Any] = {"reference": True}
    if namespace is not None:
        kwargs["namespace"] = namespace
    _file_without_prompt(str(scene_path), **kwargs)

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
