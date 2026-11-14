"""Pythonの関数を、MayaのGUIが手すきになったとき(アイドル時)に呼ぶよう予約する。"""


class Deferred:
    """maya.utilsの遅延実行を、共通の入口にまとめる。"""

    @staticmethod
    def call(callback, *args, **kwargs):
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
        # Maya非依存を保てるよう、呼ばれたときにだけ読み込む。
        import maya.utils as utils

        if not callable(callback):
            raise TypeError("呼び出せるオブジェクトを指定してください")
        utils.executeDeferred(callback, *args, **kwargs)
