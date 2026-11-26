# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""シーンのリファレンスを一覧にしたり、作ったりする。"""

from pathlib import Path
from typing import Any, Dict
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from typing import Any
from mlib.nodes.node import Nodes
from mlib.nodes.reference import Reference
import os

_SHARED_REFERENCE_NODE: str

def _reference_nodes() -> list[tuple[str, om2.MObject]]:
    """リファレンスノードを、``cmds.ls(type="reference")`` と同じ名前順で列挙する。

    共有のリファレンスノードは除く。

    Returns:
        list[tuple[str, om2.MObject]]: ``(ノード名, MObject)`` の list。名前順(文字コード順)に並ぶ。
    """
    ...

def listReferences(topLevelOnly: bool = ..., *, sortBy: str = ...) -> Nodes[Reference]:
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
    ...

def _reference_nodes_in_load_order(parent: str | None, top_level_only: bool) -> list[str]:
    """リファレンスノードの名前を、読み込んだ順に集める。

    Args:
        parent (str | None): 親のリファレンスのファイル名(コピー番号付き)。Noneならシーン。
        top_level_only (bool): Trueなら、ネストされたリファレンスをたどらない。

    Returns:
        list[str]: リファレンスノードの名前。親の後にその子を続ける。
    """
    ...

def _require_scene_file(path: str | os.PathLike, action: str = ...) -> Path:
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
    ...

def _file_without_prompt(*args, **kwargs) -> Any:
    """``cmds.file`` を確認のダイアログなし(``prompt=False``)で呼び、呼ぶ前のpromptの設定へ戻す。

    Mayaの ``file -prompt`` は一度指定すると以後のすべての ``file`` コマンドに残るため、戻さないと
    利用者の後の操作(GUIでのリファレンスが見つからないときのダイアログなど)まで出なくなる。

    Args:
        *args: ``cmds.file`` へ渡す位置引数。
        **kwargs: ``cmds.file`` へ渡すフラグ。``prompt`` は指定しない。

    Returns:
        object: ``cmds.file`` の戻り値。
    """
    ...

def createReference(path: str | Path, namespace: str | None = ...) -> Reference:
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
    ...
