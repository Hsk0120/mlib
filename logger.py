"""標準の logging から、Maya のメッセージ表示へ出力する。"""

import builtins
import logging
import os
import types

__all__ = ["MayaHandler", "debug", "error", "getLogger", "info", "print", "raiseWithNotify", "warning"]

#: ログをまとめるロガーの名前(パッケージ名)。
LOGGER_NAME = (__package__ or __name__).split(".", 1)[0]
_VIEWPORT_COLORS = {logging.WARNING: "#ffcc00", logging.ERROR: "#ff4d4d", logging.CRITICAL: "#ff4d4d"}
_NO_CAUSE = object()
#: 設定すると、Script Editorのエラー表示でmlib内部のフレームを省かない環境変数。
FULL_TRACEBACK_ENV = "MLIB_FULL_TRACEBACK"
#: 内部のフレームとして扱うパッケージのフォルダー(このモジュールの親フォルダー)。
_PACKAGE_DIR = os.path.normcase(os.path.dirname(os.path.abspath(__file__)))
#: 内部のフレームの後ろに挟まっても、利用者の行として扱わない標準ライブラリ(with文・デコレーター)。
_TRANSPARENT_MODULES = ("contextlib", "functools")


def _message_from(record):
    """ビューポートに出すため、ログの本文と引数を1つの文字列にする。

    Args:
        record (logging.LogRecord): 文字列にするレコード。

    Returns:
        str: getMessage()の結果。詳しいトレースとFormatterは、Script Editorの表示だけに使う。
    """
    return record.getMessage()


class MayaHandler(logging.Handler):
    """詳しいログをScript Editorへ、警告以上の本文をビューポートへ出すハンドラー。"""

    def emit(self, record):
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
        message = _message_from(record)
        try:
            details = self.format(record)
        except Exception as exc:
            # 通知の書式で失敗しても、呼び出し元の例外や、finallyの残りの後始末を止めない。
            details = logging.Formatter().format(record)
            details += f"\nログ書式の適用に失敗しました: {exc}"
        try:
            # Maya非依存を保てるよう、呼ばれたときにだけ読み込む。
            import maya.cmds as cmds

            # mayapyの初期化が済むまでは、MGlobalの表示APIを呼ばない。
            if not hasattr(cmds, "about"):
                return
            # Maya非依存を保てるよう、呼ばれたときにだけ読み込む。
            import maya.api.OpenMaya as om2
        except ImportError:
            return

        try:
            if record.levelno >= logging.ERROR:
                om2.MGlobal.displayError(details)
            elif record.levelno >= logging.WARNING:
                om2.MGlobal.displayWarning(details)
            else:
                om2.MGlobal.displayInfo(details)
        except RuntimeError:
            pass

        if record.levelno < logging.WARNING:
            return

        try:
            # この処理でだけ使うため、mlibの読み込み時間に含めない。
            import html  # 通知時だけ使うため、import mlibの時間に含めない。

            # Maya非依存を保てるよう、呼ばれたときにだけ読み込む。
            import maya.cmds as cmds

            color = _VIEWPORT_COLORS.get(record.levelno, "#ff4d4d")
            cmds.inViewMessage(amg=f'<font color="{color}">{html.escape(message)}</font>', pos="midCenter", fade=True)
        except (ImportError, RuntimeError):
            pass


def getLogger():
    """Maya 向けのハンドラーを付けた、共通のロガーを取得する。

    Returns:
        logging.Logger: パッケージ名のロガー。レベルはDEBUGで、親へは伝えない。
            reloadする前のMayaHandlerは今の型のものへ置き換え、通知が重ならないようにする。
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in tuple(logger.handlers):
        if (
            type(handler).__module__ in {__name__, LOGGER_NAME + ".utils.logger"}
            and type(handler).__name__ == "MayaHandler"
            and not isinstance(handler, MayaHandler)
        ):
            logger.removeHandler(handler)
            handler.close()
    if not any(isinstance(handler, MayaHandler) for handler in logger.handlers):
        logger.addHandler(MayaHandler())
    return logger


def debug(message, *args, **kwargs):
    """DEBUGレベルのログを出す。

    Maya では Script Editor に出る。

    Args:
        message (object): ログのメッセージか、書式の文字列。
        *args (object): logging に渡す書式の引数。
        **kwargs (object): exc_info、extra、stack_info、stacklevel など、logging に渡すオプション。

    Returns:
        None: 値を返さない。
    """
    getLogger().debug(message, *args, **kwargs)


def info(message, *args, **kwargs):
    """ふつうの情報を、INFOレベルでScript Editorへ出す。

    Args:
        message (object): ログのメッセージか、書式の文字列。
        *args (object): loggingに渡す書式の引数。
        **kwargs (object): exc_info、extraなどのloggingのオプション。

    Returns:
        None: 値を返さない。
    """
    getLogger().info(message, *args, **kwargs)


def print(*objects, sep=" ", end="\n", file=None, flush=False):
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
    builtins.print(*objects, sep=sep, end=end, file=file, flush=flush)


def warning(message, *args, **kwargs):
    """警告をScript Editorとビューポートへ出す。

    例外は送り出さない。引数と書式は標準のloggingと同じ。

    Args:
        message (object): メッセージか、書式の文字列。
        *args (object): loggingへ渡す書式の引数。
        **kwargs (object): exc_info、extraなどのloggingのオプション。

    Returns:
        None: 値を返さない。
    """
    getLogger().warning(message, *args, **kwargs)


def error(message, *args, **kwargs):
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
    getLogger().error(message, *args, **kwargs)


def raiseWithNotify(exceptionType, message, *args, fromException=_NO_CAUSE, **kwargs):
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
    error(message)
    exception = exceptionType(message, *args, **kwargs)
    if fromException is _NO_CAUSE:
        raise exception
    if fromException is not None and not isinstance(fromException, BaseException):
        # raise ... from が送り出すものと同じ TypeError(型を絞ってつなげる)。
        raise TypeError("例外の原因はBaseExceptionの派生で指定してください")
    raise exception from fromException


def _internal_file(filename):
    """フレームのファイルが、mlibの内部のものかを判定する。

    拡張(``<パッケージ名>_*``)も内部に含める。テスト(``__tests__``)のファイルは利用者のコードとして扱う。

    Args:
        filename (str): ``frame.f_code.co_filename``。

    Returns:
        bool: パッケージ、または同じフォルダーに並ぶ拡張パッケージの中ならTrue。
    """
    path = os.path.normcase(os.path.abspath(filename))
    root = os.path.dirname(_PACKAGE_DIR)
    if not path.startswith(root + os.sep):
        return False
    parts = path[len(root) + 1 :].split(os.sep)
    base = os.path.basename(_PACKAGE_DIR)
    return len(parts) > 1 and (parts[0] == base or parts[0].startswith(base + "_")) and "__tests__" not in parts


def _transparent_file(filename):
    """with文・デコレーターの、標準ライブラリのフレームかを判定する。

    Args:
        filename (str): ``frame.f_code.co_filename``。

    Returns:
        bool: contextlib・functoolsのファイルならTrue。
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    return stem in _TRANSPARENT_MODULES


def _trimmed_traceback(trace):
    """後ろに続くmlib内部のフレームを取り除いたトレースバックを返す。

    最後の利用者のフレーム(mlib・contextlib・functools以外)より後ろがmlib内部だけのとき、
    その利用者のフレームで終わる新しいトレースバックを作る。元のトレースバックは変えない。
    利用者のフレームが無い(mlib内部だけの)場合や、最後が利用者のコードの場合は、そのまま返す。

    Args:
        trace (types.TracebackType | None): 表示するトレースバック。

    Returns:
        types.TracebackType | None: 短くしたトレースバック、または元の値。
    """
    entries = []
    while trace is not None:
        entries.append(trace)
        trace = trace.tb_next
    last_user = None
    for index, entry in enumerate(entries):
        filename = entry.tb_frame.f_code.co_filename
        if not _internal_file(filename) and not _transparent_file(filename):
            last_user = index
    if last_user is None or not any(_internal_file(entry.tb_frame.f_code.co_filename) for entry in entries[last_user + 1 :]):
        return entries[0] if entries else None
    trimmed = None
    for entry in reversed(entries[: last_user + 1]):
        trimmed = types.TracebackType(trimmed, entry.tb_frame, entry.tb_lasti, entry.tb_lineno)
    return trimmed


def _install_exception_formatter():
    """Script Editorのエラー表示から、mlib内部のフレームを省く設定をする。

    Mayaが用意している差し替え口 ``maya.utils.formatGuiException`` を、元の関数を呼ぶ関数で包む。
    Script Editorは最後のフレームのファイルと行を表示する。そのため、mlibの中で起きた例外でも、
    利用者がmlibを呼んだ行が表示される。

    環境変数 ``MLIB_FULL_TRACEBACK`` を空でない値にすると、省かずに表示する(呼ぶたびに判定する)。
    読み直したときは、前の包みを外してから設定し直す。Mayaが無い環境では何もしない。

    Returns:
        bool: 設定したらTrue。
    """
    try:
        # Mayaの無い環境(静的検査)でもloggerをimportできるよう、設定時に読み込む。
        import maya.utils as maya_utils
    except ImportError:
        return False
    current = getattr(maya_utils, "formatGuiException", None)
    if current is None:
        return False
    previous = getattr(current, "_mlib_previous", current)

    def format_gui_exception(exception_type, exception, trace, detail=2):
        """mlib内部のフレームを省いてから、Mayaの書式の関数へ渡す。

        Args:
            exception_type (type): 例外の型。
            exception (BaseException): 例外。
            trace (types.TracebackType | None): トレースバック。
            detail (int): Mayaの表示の詳細度。

        Returns:
            str: Script Editorへ表示する文字列。
        """
        if not os.environ.get(FULL_TRACEBACK_ENV):
            try:
                trace = _trimmed_traceback(trace)
            except Exception:
                pass  # 省けなくても、Mayaのエラー表示そのものは止めない。
        return previous(exception_type, exception, trace, detail)

    format_gui_exception._mlib_previous = previous
    maya_utils.formatGuiException = format_gui_exception
    return True


_install_exception_formatter()
