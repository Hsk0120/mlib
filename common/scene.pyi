# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""シーンのファイルを、パスとして扱いながら開く・保存する・読み込む。"""

import os
from pathlib import Path
import maya.cmds as cmds
from ..decorator import _require_bool, preservedSelection
from .references import _file_without_prompt, _require_scene_file, createReference
from typing import Iterable
from mlib.nodes.node import Node
from mlib.nodes.node import Nodes
from mlib.nodes.reference import Reference

_FILE_TYPES: dict


class Scene(type(Path())):
    """Mayaのシーンのファイル。``pathlib.Path`` を継承し、パスの操作はそのまま使える。

    ``Scene(path)`` はファイルのパスを持つだけで、シーンは変えない。今開いているシーンは
    :meth:`getCurrent` で取得する。開く・保存する・読み込むのは明示的なメソッドで行う。
    ``Path`` の ``open()`` はファイルを読み書きするためのもので、シーンを開くのは :meth:`openFile`。

    パスから作った値(``scene.parent``・``scene.with_suffix(".mb")``・``scene / "x"``)も ``Scene`` になる。
    ``str(scene)`` はそのままMayaのコマンドへ渡せる。

    Note:
        ファイルの操作(:meth:`newFile`・:meth:`openFile`・:meth:`save`・:meth:`importFile`・:meth:`reference`・
        :meth:`export`)は、``cmds.file`` と同じくUndoに記録されない(Undoで取り消せない。mlibもチャンクを足さない)。
        :meth:`openFile`・:meth:`importFile`・:meth:`reference` は確認のダイアログを出さず、
        Mayaの ``file -prompt`` の設定は呼ぶ前の値へ戻す。

    Examples:
        >>> scene = mlib.Scene.getCurrent()
        >>> scene.stem
        'shot010'
        >>> mlib.Scene("D:/assets/chair.ma").reference(namespace="chair")
        >>> scene.with_name("shot010_v002.ma").save()
    """
    __slots__: tuple
    @classmethod
    def getCurrent(cls) -> Scene | None:
        """今開いているシーンのファイルを取得する。

        Returns:
            Scene | None: 今のシーンのファイル。一度も保存していない(名前の無い)シーンならNone。
        """
        ...
    @classmethod
    def isModified(cls) -> bool:
        """今開いているシーンに、保存していない変更があるかを調べる。

        Returns:
            bool: 保存していない変更があればTrue。
        """
        ...
    @classmethod
    def newFile(cls, *, force: bool = ...):
        """新しい空のシーンにする。

        Args:
            force (bool): Trueなら、保存していない変更を破棄する。既定はFalse。

        Raises:
            TypeError: forceがboolでない場合。
            RuntimeError: 保存していない変更があり、forceがFalseの場合。
        """
        ...
    def isCurrent(self) -> bool:
        """このファイルが、今開いているシーンかを調べる。

        Returns:
            bool: 今のシーンのファイルと同じパスならTrue(Windowsでは大文字・小文字と区切り文字の違いを無視する)。
        """
        ...
    def openFile(self, *, force: bool = ...):
        """このファイルを開き、今のシーンにする。

        Args:
            force (bool): Trueなら、保存していない変更を破棄する。既定はFalse。

        Raises:
            TypeError: forceがboolでない場合。
            OSError: ファイルが無い場合(``FileNotFoundError``)。
            RuntimeError: 保存していない変更があり、forceがFalseの場合。
        """
        ...
    def save(self, *, force: bool = ...):
        """今のシーンを、このファイルへ保存する。今のシーンの名前もこのファイルにする。

        形式は拡張子で決める(``.ma`` はmayaAscii、``.mb`` はmayaBinary)。

        Args:
            force (bool): Trueなら、今のシーンとは別のファイルがすでにあっても上書きする。
                今のシーンと同じファイルへの保存は、forceに関係なく上書きする。既定はFalse。

        Raises:
            TypeError: forceがboolでない場合。
            ValueError: 拡張子が ``.ma`` でも ``.mb`` でもない場合。
            OSError: 今のシーンとは別のファイルがすでにあり、forceがFalseの場合(``FileExistsError``)。
        """
        ...
    def importFile(self, *, namespace: str | None = ...) -> Nodes:
        """このファイルの中身を、今のシーンへインポートする。

        Args:
            namespace (str | None): 中身を入れる名前空間。NoneならMayaの既定を使う。

        Returns:
            Nodes: インポートで新しくできたノード。

        Raises:
            TypeError: namespaceが文字列・None以外の場合。
            OSError: ファイルが無い場合(``FileNotFoundError``)。
        """
        ...
    def reference(self, *, namespace: str | None = ...) -> Reference:
        """このファイルを、今のシーンへリファレンスする。

        :func:`mlib.common.references.createReference` と同じ。

        Args:
            namespace (str | None): リファレンスの中身を入れる名前空間。NoneならMayaの既定を使う。

        Returns:
            Reference: 作ったトップレベルのリファレンスノード。

        Raises:
            TypeError: namespaceが文字列・None以外の場合。
            OSError: ファイルが無い場合(``FileNotFoundError``)。
            RuntimeError: Mayaが作成を拒否した場合、または新しいトップレベルのリファレンスが1件に決まらない場合。
        """
        ...
    def export(self, nodes: Node | Nodes | Iterable[Node] | Iterable[str] | None = ..., *, force: bool = ...):
        """今のシーンを、このファイルへ書き出す。今のシーンの名前は変えない。

        形式は拡張子で決める(``.ma`` はmayaAscii、``.mb`` はmayaBinary)。

        Args:
            nodes (Node | Nodes | Iterable[Node] | Iterable[str] | None): 書き出すノード。Noneならシーン全体を書き出す。
                ノードを指定したときは、その選択で書き出し(``exportSelected``)、終わったら選択を元に戻す。
                並びは、Nodeだけか名前だけにする(``Nodes`` と同じく、混ぜるとTypeError)。既定はNone。
            force (bool): Trueなら、ファイルがすでにあっても上書きする。既定はFalse。

        Raises:
            TypeError: nodesが対応しない型の場合、Nodeと名前が混ざっている場合、またはforceがboolでない場合。
            ValueError: 拡張子が ``.ma`` でも ``.mb`` でもない場合、またはnodesが空の場合。
            OSError: ファイルがすでにあり、forceがFalseの場合(``FileExistsError``)。
            RuntimeError: 今のシーンと同じファイルへ書き出そうとした場合。保存は :meth:`save` で行う。
        """
        ...

def _require_discardable(force: bool):
    """保存していない変更を破棄してよいかを確かめる。シーンは変えない。

    Args:
        force (bool): Trueなら、変更があっても破棄してよい。

    Raises:
        RuntimeError: 保存していない変更があり、forceがFalseの場合。
    """
    ...

def _require_file_type(path: Path) -> str:
    """拡張子から、保存・書き出しの形式を決める。

    Args:
        path (Path): 書き出すファイル。

    Returns:
        str: ``"mayaAscii"`` か ``"mayaBinary"``。

    Raises:
        ValueError: 拡張子が ``.ma`` でも ``.mb`` でもない場合。
    """
    ...

def _require_writable(path: Path, force: bool):
    """書き出し先のファイルを上書きしてよいかを確かめる。シーンは変えない。

    Args:
        path (Path): 書き出すファイル。
        force (bool): Trueなら、ファイルがあっても上書きしてよい。

    Raises:
        OSError: ファイルがすでにあり、forceがFalseの場合(``FileExistsError``)。
    """
    ...

def _same_file(first: Path, second: Path) -> bool:
    """2つのパスが同じファイルを指すかを、OSの決まり(Windowsは大文字・小文字と区切り文字の違いを無視する)で比べる。

    Args:
        first (Path): 比べるパス。
        second (Path): 比べるパス。

    Returns:
        bool: 同じファイルならTrue。
    """
    ...
