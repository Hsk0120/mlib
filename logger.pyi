# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""標準の logging から、Maya のメッセージ表示へ出力する。"""

import builtins
import logging
import os
import types
from typing import Any, NoReturn, TextIO

__all__ = ['MayaHandler', 'debug', 'error', 'getLogger', 'info', 'print', 'raiseWithNotify', 'warning']
LOGGER_NAME: Any
_VIEWPORT_COLORS: dict
_NO_CAUSE: Any
FULL_TRACEBACK_ENV: str
_PACKAGE_DIR: Any
_TRANSPARENT_MODULES: tuple

def _message_from(record: logging.LogRecord) -> str:
    """ビューポートに出すため、ログの本文と引数を1つの文字列にする。

    Args:
        record (logging.LogRecord): 文字列にするレコード。

    Returns:
        str: getMessage()の結果。詳しいトレースとFormatterは、Script Editorの表示だけに使う。
    """
    ...


class MayaHandler(logging.Handler):
    """詳しいログをScript Editorへ、警告以上の本文をビューポートへ出すハンドラー。"""
    def emit(self, record: logging.LogRecord) -> None:
        """ログを Script Editor へ出す。必要ならビューポートにも出す。

        - Script Editorには、標準のloggingのFormatter・exc_info・stack_infoを使って出す。
        - WARNING以上では、例外のトレースを含まない本文をビューポートにも表示する。
        - Formatterが失敗したら標準の書式に戻し、失敗した理由も詳しい表示に加える。
        - Maya APIをimportできなければ、何も出さない。Mayaへ表示するときのRuntimeErrorは握りつぶす。

        Args:
            record (logging.LogRecord): 出力するレコード。

        Returns:
            None: 値を返さない。
        """
        ...

def getLogger() -> logging.Logger:
    """Maya 向けのハンドラーを付けた、共通のロガーを取得する。

    Returns:
        logging.Logger: パッケージ名のロガー。レベルはDEBUGで、親へは伝えない。
            reloadする前のMayaHandlerは今の型のものへ置き換え、通知が重ならないようにする。
    """
    ...

def debug(message: object, *args: object, **kwargs: object) -> None:
    """DEBUGレベルのログを出す。

    Maya では Script Editor に出る。

    Args:
        message (object): ログのメッセージか、書式の文字列。
        *args (object): logging に渡す書式の引数。
        **kwargs (object): exc_info、extra、stack_info、stacklevel など、logging に渡すオプション。

    Returns:
        None: 値を返さない。
    """
    ...

def info(message: object, *args: object, **kwargs: object) -> None:
    """ふつうの情報を、INFOレベルでScript Editorへ出す。

    Args:
        message (object): ログのメッセージか、書式の文字列。
        *args (object): loggingに渡す書式の引数。
        **kwargs (object): exc_info、extraなどのloggingのオプション。

    Returns:
        None: 値を返さない。
    """
    ...

def print(*objects: object, sep: str | None = ..., end: str | None = ..., file: TextIO | None = ..., flush: bool = ...) -> None:
    """Python標準のprintと同じ決まりで出力する。

    Mayaでは、ふつうはScript Editorに表示される。ログレベルやビューポートへの通知は付けない。
    fileの指定や、改行しない出力もそのまま使える。INFOのログが要るときはinfoを使う。

    Args:
        *objects (object): 出力する値。
        sep (str | None): 値の区切り。Noneなら標準の空白。
        end (str | None): 最後に付ける文字。Noneなら標準の改行。
        file (TextIO | None): 書き込み先。Noneなら今のsys.stdout。
        flush (bool): Trueなら出力先をフラッシュする。

    Returns:
        None: 値を返さない。
    """
    ...

def warning(message: object, *args: object, **kwargs: object) -> None:
    """警告をScript Editorとビューポートへ出す。

    例外は送り出さない。引数と書式は標準のloggingと同じ。

    Args:
        message (object): メッセージか、書式の文字列。
        *args (object): loggingへ渡す書式の引数。
        **kwargs (object): exc_info、extraなどのloggingのオプション。

    Returns:
        None: 値を返さない。
    """
    ...

def error(message: object, *args: object, **kwargs: object) -> None:
    """エラーをScript Editorとビューポートへ出す。

    例外は送り出さない。引数と書式は標準のloggingと同じ。
    知らせたうえで処理を止めたいときは、raiseWithNotifyを使う。

    Args:
        message (object): メッセージか、書式の文字列。
        *args (object): loggingへ渡す書式の引数。
        **kwargs (object): exc_info、extraなどのloggingのオプション。

    Returns:
        None: 値を返さない。
    """
    ...

def raiseWithNotify(exceptionType: type[Exception], message: str, *args: object, fromException: BaseException | None = ..., **kwargs: object) -> NoReturn:
    """エラーを知らせてから、指定した型の例外を送り出す。

    利用者に知らせて処理を止めるツール(mlibを使う側のツール)の入口で使う。
    mlib本体の例外は、Script Editorの表示と重ならないよう、知らせずに送り出す。

    Args:
        exceptionType (type[Exception]): 作る例外のクラス。
        message (str): 知らせる内容。例外の最初の引数にも使う。
        *args (object): 例外のコンストラクタへ渡す、追加の位置引数。ログには渡さない。
        fromException (BaseException | None): 指定すると ``raise ... from fromException`` として、
            例外のつながりをはっきり示す(``None`` を渡すと、つながりを示さないようにする)。
            省略すると、通常の ``raise`` と同じく、except 節の中なら自動のつながりを保つ。
        **kwargs (object): 例外のコンストラクタへ渡すキーワード引数。ログには渡さない。

    Returns:
        NoReturn: 正常には戻らない。

    Raises:
        Exception: exceptionType で指定した例外。コンストラクタが失敗した場合は、その例外。
        TypeError: fromException が例外でも None でもない場合。
    """
    ...

def _internal_file(filename: str) -> bool:
    """フレームのファイルが、mlibの内部のものかを判定する。

    拡張(``<パッケージ名>_*``)も内部に含める。テスト(``__tests__``)のファイルは利用者のコードとして扱う。

    Args:
        filename (str): ``frame.f_code.co_filename``。

    Returns:
        bool: パッケージ、または同じフォルダーに並ぶ拡張パッケージの中ならTrue。
    """
    ...

def _transparent_file(filename: str) -> bool:
    """with文・デコレーターの、標準ライブラリのフレームかを判定する。

    Args:
        filename (str): ``frame.f_code.co_filename``。

    Returns:
        bool: contextlib・functoolsのファイルならTrue。
    """
    ...

def _trimmed_traceback(trace: types.TracebackType | None) -> types.TracebackType | None:
    """後ろに続くmlib内部のフレームを取り除いたトレースバックを返す。

    最後の利用者のフレーム(mlib・contextlib・functools以外)より後ろがmlib内部だけのとき、
    その利用者のフレームで終わる新しいトレースバックを作る。元のトレースバックは変えない。
    利用者のフレームが無い(mlib内部だけの)場合や、最後が利用者のコードの場合は、そのまま返す。

    Args:
        trace (types.TracebackType | None): 表示するトレースバック。

    Returns:
        types.TracebackType | None: 短くしたトレースバック、または元の値。
    """
    ...

def _install_exception_formatter() -> bool:
    """Script Editorのエラー表示から、mlib内部のフレームを省く設定をする。

    Mayaが用意している差し替え口 ``maya.utils.formatGuiException`` を、元の関数を呼ぶ関数で包む。
    Script Editorは最後のフレームのファイルと行を表示する。そのため、mlibの中で起きた例外でも、
    利用者がmlibを呼んだ行が表示される。

    環境変数 ``MLIB_FULL_TRACEBACK`` を空でない値にすると、省かずに表示する(呼ぶたびに判定する)。
    読み直したときは、前の包みを外してから設定し直す。Mayaが無い環境では何もしない。

    Returns:
        bool: 設定したらTrue。
    """
    ...
