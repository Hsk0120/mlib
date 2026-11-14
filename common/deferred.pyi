# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Pythonの関数を、MayaのGUIが手すきになったとき(アイドル時)に呼ぶよう予約する。"""

from typing import Callable



class Deferred:
    """maya.utilsの遅延実行を、共通の入口にまとめる。"""
    @staticmethod
    def call(callback: Callable, *args: object, **kwargs: object) -> None:
        """Pythonの関数の呼び出しを、maya.utils.executeDeferredへ渡す。

        いつ実行するかと、callbackで起きた例外の扱いはMayaに任せる。
        その場で実行する・予約を取り消す・Undoを管理する、といった機能は付け加えない。
        バッチでの動きもexecuteDeferredに従う。予約したAPIの戻り値は返さない。

        Args:
            callback (Callable): 呼び出せるPythonのオブジェクト。コードの文字列は受け付けない。
            *args (object): callbackへ渡す位置引数。
            **kwargs (object): callbackへ渡すキーワード引数。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: callbackが呼び出せない場合。
        """
        ...
