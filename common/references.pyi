# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""シーンのリファレンスを一覧にしたり、作ったりする。"""

from pathlib import Path
from typing import Any, Dict
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import undoChunk
from mlib.nodes.reference import Reference

_SHARED_REFERENCE_NODE: str

def _reference_nodes() -> list[tuple[str, om2.MObject]]:
    """リファレンスノードを、``cmds.ls(type="reference")`` と同じ名前順で列挙する。

    共有のリファレンスノードは除く。

    Returns:
        list[tuple[str, om2.MObject]]: ``(ノード名, MObject)`` の list。名前順(文字コード順)に並ぶ。
    """
    ...

def listReferences(topLevelOnly: bool = ...) -> list[Reference]:
    """シーンのリファレンスを、Reference のオブジェクトの一覧として取得する。

    Args:
        topLevelOnly (bool): True なら、ほかのリファレンスの中に入っていない(ネストされていない)
            トップレベルのリファレンスだけを返す。

    Returns:
        list[Reference]: リファレンスのオブジェクトの一覧(``cmds.ls(type="reference")`` と同じ名前順)。
            リファレンスが無ければ空リスト。名前順なので、リファレンスを作った順や読み込んだ順とは限らない。
    """
    ...

def createReference(path: str | Path, namespace: str | None = ...) -> Reference:
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
    ...
