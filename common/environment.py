"""Mayaの実行環境(バッチかGUIか・版番号)を調べる。"""

import maya.cmds as cmds

from .version import Version


class Environment:
    """実行中のMayaの状態を調べるクラスメソッドの集まり。インスタンスは作らない。

    シーンは変更しない。どのメソッドも、呼び出すたびにMayaへ問い合わせる。

    .. code-block:: python

        from mlib.common import Environment

        if Environment.isInteractive() and Environment.getMayaVersion() >= Version("2025"):
            ...
    """

    def __new__(cls, *args, **kwargs):
        """インスタンスを作らせない。

        Raises:
            TypeError: 常に送出する。
        """
        raise TypeError("Environmentはクラスメソッドだけを提供します。Environment.isBatch()のように直接呼び出してください")

    @classmethod
    def isBatch(cls):
        """バッチ(mayapy・``maya -batch``)で実行中か調べる(``cmds.about(batch=True)``)。

        Returns:
            bool: バッチならTrue。
        """
        return bool(cmds.about(batch=True))

    @classmethod
    def isInteractive(cls):
        """GUIのある対話的なセッションで実行中か調べる。

        Returns:
            bool: バッチでなければTrue(``not isBatch()``)。
        """
        return not cls.isBatch()

    @classmethod
    def getMayaVersion(cls):
        """Mayaの版を取得する(``cmds.about(version=True)``)。

        版によっては、Mayaが返す文字列が年の版だけ(例 ``"2027"``)で、更新番号を含まない。
        更新番号まで比べる場合は :meth:`getApiVersion` を使う。

        Returns:
            Version: Mayaの版(例 ``Version("2027")``)。``major`` は ``getApiVersion() // 10000`` と一致する。

        Raises:
            RuntimeError: Mayaが返した文字列を、版として読み取れない場合。
        """
        text = cmds.about(version=True)
        version = Version.parse(text)
        if version is None:
            raise RuntimeError(f"Mayaのバージョンを読み取れません: {text!r}")
        return version

    @classmethod
    def getApiVersion(cls):
        """MayaのAPIの版番号を取得する(``cmds.about(apiVersion=True)``)。

        Returns:
            int: APIの版番号(例 ``20270000``。年の版×10000 + 更新番号×100 + パッチ)。
        """
        return int(cmds.about(apiVersion=True))
