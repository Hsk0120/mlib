# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ヘッダー付きのJSONファイルを書き出し・読み込みする。読み込むときは形式名と版を確かめる。

ファイルは ``{"header": {...}, "data": {...}}`` の形で、UTF-8・整形(字下げ2)で書く。
ヘッダーには、形式名・版・書き出したmlibとMayaの版・単位を書く。単位は、長さがcm、角度が度、
時間が保存したときのUIの時間の単位でのフレーム(とそのfps)。データの数学型は :mod:`mlib.json.codec` で変換する。
"""

import json
import os
import tempfile
from pathlib import Path
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from .codec import decode, encode
import pathlib

_LINEAR_UNIT: str
_ANGLE_UNIT: str
_TIME_UNIT: str
_TIMINGS: tuple


class Header:
    """JSONファイルのヘッダー(形式名・版・書き出した環境・単位)を持つ。

    :func:`load` が返し、時間の換算(:meth:`convertTime`)に使う。書き出すときは :func:`dump` が
    今のシーンから作るので、自分で作る必要はない。
    """
    def __init__(self, format: str, version: int, mlib: str | None = ..., maya: str | None = ..., fps: float | None = ...) -> None:
        """ヘッダーの値を持たせる。

        Args:
            format (str): 形式名(``"mlib.pose"`` など)。
            version (int): 形式の版。
            mlib (str | None): 書き出したmlibの版。
            maya (str | None): 書き出したMayaの版。
            fps (float | None): 書き出したシーンのfps。Noneなら今のシーンのfps。

        Raises:
            TypeError: formatが文字列でない場合、versionがintでない場合(boolも不可)、
                またはfpsが数値でもNoneでもない場合。
            ValueError: formatが空の場合、versionが1より小さい場合、またはfpsが正でない場合。
        """
        ...
    def __repr__(self) -> str:
        """形式名・版・fpsを含む表記を返す。

        Returns:
            str: ``Header('mlib.pose', 1, fps=30.0)`` の形式。
        """
        ...
    @classmethod
    def fromData(cls, data: dict) -> Header:
        """ファイルのヘッダーの辞書から作る。

        Args:
            data (dict): :meth:`toData` の形の辞書。

        Returns:
            Header: 新しいヘッダー。

        Raises:
            ValueError: 必要なキーが無い場合、または単位に対応していない場合。
        """
        ...
    @property
    def format(self) -> str:
        """形式名を返す。

        Returns:
            str: ``"mlib.pose"`` など。
        """
        ...
    @property
    def version(self) -> int:
        """形式の版を返す。

        Returns:
            int: 版。
        """
        ...
    @property
    def mlib(self) -> str | None:
        """書き出したmlibの版を返す。

        Returns:
            str | None: 版。不明ならNone。
        """
        ...
    @property
    def maya(self) -> str | None:
        """書き出したMayaの版を返す。

        Returns:
            str | None: 版。不明ならNone。
        """
        ...
    @property
    def fps(self) -> float:
        """書き出したシーンのfpsを返す。

        Returns:
            float: 1秒あたりのフレーム数。
        """
        ...
    def convertTime(self, frame: float, timing: str = ...) -> float:
        """保存したときのフレームを、今のシーンのフレームへ換算する。

        ``timing="frame"`` は、フレーム番号をそのまま返す(何コマ目かを保つ)。
        ``"second"`` は、保存したときのfpsで秒にしてから、今のfpsのフレームへ直す(実際の時間を保つ)。
        fpsが同じなら、どちらも同じ値になる。

        Args:
            frame (float): 保存したときのフレーム。
            timing (str): ``"frame"`` か ``"second"``。既定は ``"frame"``。

        Returns:
            float: 今のシーンのフレーム。

        Raises:
            ValueError: timingが ``"frame"``・``"second"`` 以外の場合。
        """
        ...
    def toData(self) -> dict:
        """ファイルに書くヘッダーの辞書を返す。

        Returns:
            dict: ``format``・``version``・``mlib``・``maya``・``units`` を持つ新しい辞書。
        """
        ...

def currentFps() -> float:
    """今のシーンのUIの時間の単位でのfpsを返す。

    Returns:
        float: 1秒あたりのフレーム数。
    """
    ...

def dump(data: dict, path: str | os.PathLike, format: str, version: int) -> pathlib.Path:
    """データにヘッダーを付けて、JSONファイルへ書き出す。

    データは :func:`mlib.json.codec.encode` で変換してから書く。同じフォルダーの一時ファイルへ
    書いてから置き換えるので、途中で失敗しても元のファイルは壊れない。フォルダーは作らない。

    Args:
        data (dict): 書き出すデータ。数学型を含んでよい。
        path (str | os.PathLike): 書き出し先。
        format (str): 形式名(``"mlib.pose"`` など)。
        version (int): 形式の版。

    Returns:
        pathlib.Path: 書き出したファイルの絶対パス。

    Raises:
        TypeError: dataが辞書でない場合、またはJSONで書けない値を含む場合。
        ValueError: 形式名・版が正しくない場合、またはNaN・無限大を含む場合。
        OSError: 書き出しに失敗した場合。
    """
    ...

def load(path: str | os.PathLike, format: str, version: int) -> tuple[Header, dict]:
    """JSONファイルを読み込み、ヘッダーとデータを返す。

    形式名と版が期待どおりかを確かめる。データは :func:`mlib.json.codec.decode` で数学型へ戻す。
    古い版のデータを新しい版へ変換することはしない。

    Args:
        path (str | os.PathLike): 読み込むファイル。
        format (str): 期待する形式名。
        version (int): 期待する版。

    Returns:
        tuple[Header, dict]: ヘッダーとデータ。

    Raises:
        ValueError: JSONとして読めない場合、ファイルの形が違う場合、形式名・版が期待と違う場合、
            または単位に対応していない場合。
        OSError: 読み込みに失敗した場合。
    """
    ...

def _require_timing(timing: str):
    """時間の扱いの指定を確かめる。

    Args:
        timing (str): ``"frame"`` または ``"second"``。

    Raises:
        ValueError: それ以外の場合。
    """
    ...
