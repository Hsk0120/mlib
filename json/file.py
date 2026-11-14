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

#: ヘッダーに書く単位。長さ・角度・時間の種類は決まっていて、fpsだけ保存したときのシーンの値を書く。
_LINEAR_UNIT = "cm"
_ANGLE_UNIT = "deg"
_TIME_UNIT = "frame"
#: 読み込むときのfpsの扱い。"frame" はフレーム番号を保ち、"second" は秒を保つ。
_TIMINGS = ("frame", "second")


class Header:
    """JSONファイルのヘッダー(形式名・版・書き出した環境・単位)を持つ。

    :func:`load` が返し、時間の換算(:meth:`convertTime`)に使う。書き出すときは :func:`dump` が
    今のシーンから作るので、自分で作る必要はない。
    """

    def __init__(self, format, version, mlib=None, maya=None, fps=None):
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
        if not isinstance(format, str):
            raise TypeError("formatは文字列で指定してください")
        if not format:
            raise ValueError("formatは空にできません")
        if isinstance(version, bool) or not isinstance(version, int):
            raise TypeError("versionはintで指定してください")
        if version < 1:
            raise ValueError("versionは1以上で指定してください")
        if fps is None:
            fps = currentFps()
        if isinstance(fps, bool) or not isinstance(fps, (int, float)):
            raise TypeError("fpsは数値で指定してください")
        if not fps > 0:
            raise ValueError("fpsは正の値で指定してください")
        self._format = format
        self._version = version
        self._mlib = mlib
        self._maya = maya
        self._fps = float(fps)

    def __repr__(self):
        """形式名・版・fpsを含む表記を返す。

        Returns:
            str: ``Header('mlib.pose', 1, fps=30.0)`` の形式。
        """
        return f"Header({self._format!r}, {self._version}, fps={self._fps})"

    @classmethod
    def fromData(cls, data):
        """ファイルのヘッダーの辞書から作る。

        Args:
            data (dict): :meth:`toData` の形の辞書。

        Returns:
            Header: 新しいヘッダー。

        Raises:
            ValueError: 必要なキーが無い場合、または単位に対応していない場合。
        """
        if not isinstance(data, dict) or not isinstance(data.get("units"), dict):
            raise ValueError("JSONのヘッダーは'units'を持つオブジェクトにしてください")
        units = data["units"]
        expected = {"linear": _LINEAR_UNIT, "angle": _ANGLE_UNIT, "time": _TIME_UNIT}
        for key, unit in expected.items():
            if units.get(key) != unit:
                raise ValueError(f"JSONのヘッダーの{key}の単位に対応していません: {units.get(key)!r}({unit!r}が必要です)")
        try:
            return cls(data["format"], data["version"], data.get("mlib"), data.get("maya"), units.get("fps"))
        except (KeyError, TypeError) as error:
            raise ValueError(f"JSONのヘッダーが不正です: {error}") from error

    @property
    def format(self):
        """形式名を返す。

        Returns:
            str: ``"mlib.pose"`` など。
        """
        return self._format

    @property
    def version(self):
        """形式の版を返す。

        Returns:
            int: 版。
        """
        return self._version

    @property
    def mlib(self):
        """書き出したmlibの版を返す。

        Returns:
            str | None: 版。不明ならNone。
        """
        return self._mlib

    @property
    def maya(self):
        """書き出したMayaの版を返す。

        Returns:
            str | None: 版。不明ならNone。
        """
        return self._maya

    @property
    def fps(self):
        """書き出したシーンのfpsを返す。

        Returns:
            float: 1秒あたりのフレーム数。
        """
        return self._fps

    def convertTime(self, frame, timing="frame"):
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
        _require_timing(timing)
        if timing == "frame":
            return frame
        return frame / self._fps * currentFps()

    def toData(self):
        """ファイルに書くヘッダーの辞書を返す。

        Returns:
            dict: ``format``・``version``・``mlib``・``maya``・``units`` を持つ新しい辞書。
        """
        return {
            "format": self._format,
            "version": self._version,
            "mlib": self._mlib,
            "maya": self._maya,
            "units": {"linear": _LINEAR_UNIT, "angle": _ANGLE_UNIT, "time": _TIME_UNIT, "fps": self._fps},
        }


def currentFps():
    """今のシーンのUIの時間の単位でのfpsを返す。

    Returns:
        float: 1秒あたりのフレーム数。
    """
    return 1.0 / om2.MTime(1, om2.MTime.uiUnit()).asUnits(om2.MTime.kSeconds)


def dump(data, path, format, version):
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
    if not isinstance(data, dict):
        raise TypeError("dataはdictで指定してください")
    # 循環参照の回避: mlib.__version__ はパッケージの初期化の最後に設定される。
    from .. import __version__

    header = Header(format, version, __version__, cmds.about(version=True))
    payload = {"header": header.toData(), "data": encode(data)}
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    destination = Path(os.fspath(path)).resolve()
    descriptor, temporary = tempfile.mkstemp(prefix=".mlib-", suffix=".json", dir=str(destination.parent))
    leftover = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text + "\n")
        leftover.replace(destination)
    finally:
        # Path.unlink(missing_ok=True)はPython 3.8以降のため、存在を確かめてから消す。
        if leftover.exists():
            leftover.unlink()
    return destination


def load(path, format, version):
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
    with Path(path).open(encoding="utf-8") as stream:
        try:
            payload = json.load(stream)
        except json.JSONDecodeError as error:
            raise ValueError(f"{os.fspath(path)}をJSONとして読み込めません: {error}") from error
    if not isinstance(payload, dict) or set(payload) != {"header", "data"} or not isinstance(payload["data"], dict):
        raise ValueError(f"{os.fspath(path)}はmlibのJSONファイルではありません('header'と'data'が必要です)")
    header = Header.fromData(payload["header"])
    if header.format != format:
        raise ValueError(f"{os.fspath(path)}の形式は{header.format!r}です。{format!r}が必要です")
    if header.version != version:
        raise ValueError(f"{os.fspath(path)}は{format}のバージョン{header.version}です。バージョン{version}が必要です")
    return header, decode(payload["data"])


def _require_timing(timing):
    """時間の扱いの指定を確かめる。

    Args:
        timing (str): ``"frame"`` または ``"second"``。

    Raises:
        ValueError: それ以外の場合。
    """
    if timing not in _TIMINGS:
        raise ValueError(f"timingは'frame'か'second'で指定してください: {timing!r}")
