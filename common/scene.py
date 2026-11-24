"""シーンのファイルを、パスとして扱いながら開く・保存する・読み込む。"""

import os
from pathlib import Path

import maya.cmds as cmds

from ..decorator import preservedSelection
from .references import _require_scene_file, createReference

# 拡張子とMayaのファイルの形式の対応。保存・書き出しの形式は拡張子で決める。
_FILE_TYPES = {".ma": "mayaAscii", ".mb": "mayaBinary"}


class Scene(type(Path())):
    """Mayaのシーンのファイル。``pathlib.Path`` を継承し、パスの操作はそのまま使える。

    ``Scene(path)`` はファイルのパスを持つだけで、シーンは変えない。今開いているシーンは
    :meth:`getCurrent` で取得する。開く・保存する・読み込むのは明示的なメソッドで行う。
    ``Path`` の ``open()`` はファイルを読み書きするためのもので、シーンを開くのは :meth:`openFile`。

    パスから作った値(``scene.parent``・``scene.with_suffix(".mb")``・``scene / "x"``)も ``Scene`` になる。
    ``str(scene)`` はそのままMayaのコマンドへ渡せる。

    Examples:
        >>> scene = mlib.Scene.getCurrent()
        >>> scene.stem
        'shot010'
        >>> mlib.Scene("D:/assets/chair.ma").reference(namespace="chair")
        >>> scene.with_name("shot010_v002.ma").save()
    """

    __slots__ = ()

    @classmethod
    def getCurrent(cls):
        """今開いているシーンのファイルを取得する。

        Returns:
            Scene | None: 今のシーンのファイル。一度も保存していない(名前の無い)シーンならNone。
        """
        name = cmds.file(query=True, sceneName=True)
        return cls(name) if name else None

    @classmethod
    def isModified(cls):
        """今開いているシーンに、保存していない変更があるかを調べる。

        Returns:
            bool: 保存していない変更があればTrue。
        """
        return bool(cmds.file(query=True, modified=True))

    @classmethod
    def newFile(cls, *, force=False):
        """新しい空のシーンにする。

        Args:
            force (bool): Trueなら、保存していない変更を破棄する。

        Raises:
            RuntimeError: 保存していない変更があり、forceがFalseの場合。
        """
        _require_discardable(force)
        cmds.file(new=True, force=True)

    def isCurrent(self):
        """このファイルが、今開いているシーンかを調べる。

        Returns:
            bool: 今のシーンのファイルと同じパスならTrue(Windowsでは大文字・小文字と区切り文字の違いを無視する)。
        """
        current = Scene.getCurrent()
        return current is not None and _same_file(self, current)

    def openFile(self, *, force=False):
        """このファイルを開き、今のシーンにする。

        Args:
            force (bool): Trueなら、保存していない変更を破棄する。

        Raises:
            OSError: ファイルが無い場合(``FileNotFoundError``)。
            RuntimeError: 保存していない変更があり、forceがFalseの場合。
        """
        path = _require_scene_file(self, "開く")
        _require_discardable(force)
        # GUIでも確認のダイアログで止めない。
        cmds.file(str(path), open=True, force=True, prompt=False)

    def save(self, *, force=False):
        """今のシーンを、このファイルへ保存する。今のシーンの名前もこのファイルにする。

        形式は拡張子で決める(``.ma`` はmayaAscii、``.mb`` はmayaBinary)。

        Args:
            force (bool): Trueなら、今のシーンとは別のファイルがすでにあっても上書きする。
                今のシーンと同じファイルへの保存は、forceに関係なく上書きする。

        Raises:
            ValueError: 拡張子が ``.ma`` でも ``.mb`` でもない場合。
            OSError: 今のシーンとは別のファイルがすでにあり、forceがFalseの場合(``FileExistsError``)。
        """
        file_type = _require_file_type(self)
        if not self.isCurrent():
            _require_writable(self, force)
            cmds.file(rename=str(self))
        cmds.file(save=True, type=file_type, force=True)

    def importFile(self, *, namespace=None):
        """このファイルの中身を、今のシーンへインポートする。

        Args:
            namespace (str | None): 中身を入れる名前空間。NoneならMayaの既定を使う。

        Returns:
            Nodes: インポートで新しくできたノード。

        Raises:
            OSError: ファイルが無い場合(``FileNotFoundError``)。
        """
        # commonの初期化時にnodesを読み込まないよう、使用時に読み込む。
        from ..nodes.node import Node, Nodes

        path = _require_scene_file(self, "インポートする")
        kwargs = {"i": True, "returnNewNodes": True, "prompt": False}
        if namespace is not None:
            kwargs["namespace"] = namespace
        names = cmds.file(str(path), **kwargs) or []
        return Nodes._wrap([Node(name) for name in names if cmds.objExists(name)])

    def reference(self, *, namespace=None):
        """このファイルを、今のシーンへリファレンスする。

        :func:`mlib.common.references.createReference` と同じ。

        Args:
            namespace (str | None): リファレンスの中身を入れる名前空間。NoneならMayaの既定を使う。

        Returns:
            Reference: 作ったトップレベルのリファレンスノード。

        Raises:
            OSError: ファイルが無い場合(``FileNotFoundError``)。
            RuntimeError: Mayaが作成を拒否した場合、または新しいトップレベルのリファレンスが1件に決まらない場合。
        """
        return createReference(self, namespace=namespace)

    def export(self, nodes=None, *, force=False):
        """今のシーンを、このファイルへ書き出す。今のシーンの名前は変えない。

        形式は拡張子で決める(``.ma`` はmayaAscii、``.mb`` はmayaBinary)。

        Args:
            nodes (Node | Nodes | Iterable[Node] | Iterable[str] | None): 書き出すノード。Noneならシーン全体を書き出す。
                ノードを指定したときは、その選択で書き出し(``exportSelected``)、終わったら選択を元に戻す。
                並びは、Nodeだけか名前だけにする(``Nodes`` と同じく、混ぜるとTypeError)。
            force (bool): Trueなら、ファイルがすでにあっても上書きする。

        Raises:
            TypeError: nodesが対応しない型の場合、またはNodeと名前が混ざっている場合。
            ValueError: 拡張子が ``.ma`` でも ``.mb`` でもない場合、またはnodesが空の場合。
            OSError: ファイルがすでにあり、forceがFalseの場合(``FileExistsError``)。
            RuntimeError: 今のシーンと同じファイルへ書き出そうとした場合。保存は :meth:`save` で行う。
        """
        # commonの初期化時にnodesを読み込まないよう、使用時に読み込む。
        from ..nodes.node import Nodes

        file_type = _require_file_type(self)
        if self.isCurrent():
            raise RuntimeError(f"今のシーンのファイルへは書き出せません。保存はsaveで行ってください: {self}")
        targets = None if nodes is None else Nodes(nodes)
        if targets is not None and not targets:
            raise ValueError("書き出すnodesが空です")
        _require_writable(self, force)
        if targets is None:
            cmds.file(str(self), exportAll=True, type=file_type, force=True)
            return
        with preservedSelection():
            cmds.select(targets, replace=True, noExpand=True)
            cmds.file(str(self), exportSelected=True, type=file_type, force=True)


def _require_discardable(force):
    """保存していない変更を破棄してよいかを確かめる。シーンは変えない。

    Args:
        force (bool): Trueなら、変更があっても破棄してよい。

    Raises:
        RuntimeError: 保存していない変更があり、forceがFalseの場合。
    """
    if not force and Scene.isModified():
        raise RuntimeError("今のシーンに保存していない変更があります。破棄するときはforce=Trueを指定してください")


def _require_file_type(path):
    """拡張子から、保存・書き出しの形式を決める。

    Args:
        path (Path): 書き出すファイル。

    Returns:
        str: ``"mayaAscii"`` か ``"mayaBinary"``。

    Raises:
        ValueError: 拡張子が ``.ma`` でも ``.mb`` でもない場合。
    """
    file_type = _FILE_TYPES.get(path.suffix.lower())
    if file_type is None:
        raise ValueError(f"拡張子は.maか.mbで指定してください: {path}")
    return file_type


def _require_writable(path, force):
    """書き出し先のファイルを上書きしてよいかを確かめる。シーンは変えない。

    Args:
        path (Path): 書き出すファイル。
        force (bool): Trueなら、ファイルがあっても上書きしてよい。

    Raises:
        OSError: ファイルがすでにあり、forceがFalseの場合(``FileExistsError``)。
    """
    if not force and Path(path).expanduser().exists():
        raise FileExistsError(f"ファイルがすでにあります。上書きするときはforce=Trueを指定してください: {path}")


def _same_file(first, second):
    """2つのパスが同じファイルを指すかを、OSの決まり(Windowsは大文字・小文字と区切り文字の違いを無視する)で比べる。

    Args:
        first (Path): 比べるパス。
        second (Path): 比べるパス。

    Returns:
        bool: 同じファイルならTrue。
    """
    return os.path.normcase(os.path.normpath(Path(first).expanduser())) == os.path.normcase(os.path.normpath(Path(second).expanduser()))
