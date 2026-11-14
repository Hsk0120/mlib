# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaのfileノードを扱う。"""

from ..decorator import _edit_context
from .texture2d import Texture2d



class File(Texture2d):
    """Mayaのfileノードを表すクラス。値の設定や接続はPlugで行う。"""
    def getFilePath(self) -> str:
        """ファイルパスを取得する。

        UDIMなどのトークンは展開せず、書かれたまま返す。

        Returns:
            str: ファイルパス。UDIMなどのトークンは展開しない。
        """
        ...
    def setFilePath(self, path: str, *, fast: bool = ...) -> File:
        """ファイルパスを設定する。

        ファイルがあるかどうかは確かめず、ファイルのコピーもしない。

        Args:
            path (str): ファイルパス。UDIMなどのトークンを含むパターンでもよい。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            File: 自身。

        Raises:
            TypeError: fastがbool以外、またはpathがstr以外の場合。
            RuntimeError: アトリビュートがロックされている、または入力が接続されていて設定できない場合。

        Note:
            ``fast=True`` は通常と同じ検証の後にOpenMayaで直接更新する(Undoなし)。
        """
        ...
    def getColorSpace(self) -> str:
        """入力色空間の名前を取得する。

        Returns:
            str: 今設定されている入力色空間の名前。
        """
        ...
    def setColorSpace(self, name: str, *, fast: bool = ...) -> File:
        """入力色空間を設定する。

        名前が正しいかは確かめず、そのまま書き込む。使える色空間は色管理の設定(OCIOの構成など)で
        変わるので、今の設定に無い名前も設定できる。

        Args:
            name (str): 色空間の名前。今のMayaの色管理の設定で使える名前を指定する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            File: 自身。パスを変えたときに色空間を自動で決めるルールの設定は変えない。

        Raises:
            TypeError: fastがbool以外、またはnameがstr以外の場合。
            RuntimeError: アトリビュートがロックされている、または入力が接続されていて設定できない場合。

        Note:
            ``fast=True`` は通常と同じ検証の後にOpenMayaで直接更新する(Undoなし)。
        """
        ...
