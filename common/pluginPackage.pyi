# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""モジュールとプラグインの組で入る製品(Bifrost など)が入っているか確かめ、ロードする。"""

import maya.cmds as cmds
from .. import logger
from .module import Module
from .plugin import Plugin
from .version import Version
from typing import Any, Callable, Iterable

SKIPPED: str
LOADED: str
MISSING: str
OUTDATED: str
LOAD_FAILED: str


class PluginPackage:
    """製品が入っているかを確かめ、ロードする。

    モジュール・プラグインと、必要な版を持つ。作るときはMayaへの問い合わせもロードもしない。
    tryLoadで、対象のMayaの版・入っている版・ロードの結果を順に判定する。
    ロードしたプラグインを自動でアンロードすることはしない。
    """
    def __init__(self, name: str, plugins: Iterable[str | Plugin] = ..., module: str | Module | None = ..., versionPlugin: str | Plugin | None = ..., minimumVersion: Version | str | int | tuple[int, ...] | None = ..., minimumMaya: int | None = ..., installHint: str | None = ...) -> None:
        """製品名・ロードするもの・必要な版を持つ。Mayaへは問い合わせない。

        Args:
            name (str): 通知に表示する製品名。
            plugins (Iterable[str | Plugin]): ロードするプラグイン。ロードする順に並べる。
            module (str | Module | None): 版を取得するモジュール。版が取れなければversionPluginの版を使う。
            versionPlugin (str | Plugin | None): 版を調べるプラグイン。既定はpluginsの先頭。
            minimumVersion (Version | str | int | tuple[int, ...] | None): 最小の版。Noneなら版を問わない。
            minimumMaya (int | None): 対象とするMayaの、最小の年の版。それより前の版では、tryLoadで何もしない。
            installHint (str | None): 製品が足りないときの通知に加える説明。

        Raises:
            TypeError: 名前やプラグイン名が文字列でない場合、pluginsを順に取り出せない場合、
                またはminimumMayaを整数に変換できない型の場合。
            ValueError: 名前やプラグイン名が空文字列の場合、最小の版が正しくない場合、
                またはpluginsもmoduleも指定していない場合。
        """
        ...
    def __repr__(self) -> str:
        """デバッグ用に、製品名と最小の版を含む表示を返す。

        Returns:
            str: 型名・製品名・最小の版を含む文字列。
        """
        ...
    @staticmethod
    def showDialog(message: str, title: str = ...) -> None:
        """警告のダイアログを表示する。GUI の無いバッチ・スタンドアロンでは何もしない。

        Args:
            message (str): 表示する文章。
            title (str): ダイアログのタイトル。

        Returns:
            None: 値を返さない。
        """
        ...
    @property
    def name(self) -> str:
        """製品名を取得する。

        Returns:
            str: 製品名。
        """
        ...
    @property
    def plugins(self) -> list[Plugin]:
        """ロードするプラグインを取得する。

        Returns:
            list[Plugin]: プラグイン。ロードする順に並ぶ。
        """
        ...
    @property
    def module(self) -> Module | None:
        """版を取得するモジュールを取得する。

        Returns:
            Module | None: モジュール。指定していない場合は None。
        """
        ...
    @property
    def minimumVersion(self) -> Version | None:
        """必要な最小の版を取得する。

        Returns:
            Version | None: 最小の版。指定していない場合は None。
        """
        ...
    @property
    def minimumMaya(self) -> int | None:
        """対象とする最小の Maya の年を取得する。

        Returns:
            int | None: 年。指定していない場合は None。
        """
        ...
    def isMayaSupported(self) -> bool:
        """現在の Maya が対象の版か判定する。

        Returns:
            bool: ``minimumMaya`` を指定していない場合と、現在の Maya の年がそれ以上の場合は True。
        """
        ...
    def getInstalledVersion(self) -> Version | None:
        """Maya に登録されている製品の版を取得する。

        モジュールが登録されていればその版、無ければ版を調べるプラグインの版を使う。

        Returns:
            Version | None: 版。製品が入っていない場合と、版が取れない場合は None。
        """
        ...
    def getLoadedVersion(self) -> Version | None:
        """版を調べるプラグインの、ロードされている版を取得する。

        Returns:
            Version | None: 版。ロードされていない場合は None。
        """
        ...
    def isInstalled(self) -> bool:
        """必要な版が入っているか判定する。

        ロードする前のプラグインは、Maya に登録されていないことがある。そのため ``minimumVersion`` を
        指定していない製品では、この判定が False でも :meth:`tryLoad` がロードを試す。

        Returns:
            bool: ``minimumVersion`` 以上が入っていれば True。``minimumVersion`` を指定していない
            場合は、版が取れるか、モジュールかプラグインが 1 つでも登録されていれば True。
        """
        ...
    def getMessage(self, found: Version | None = ...) -> str:
        """製品を入れる必要があるときの、警告の文を作る。

        Args:
            found (Version | None): 見つかった版。省略すると、今入っているものから求める。

        Returns:
            str: 日本語と英語の警告の文。
        """
        ...
    def loadPlugins(self) -> list[str]:
        """すべてのプラグインをロードする。ロードできないものがあっても続ける。

        Returns:
            list[str]: ロードに失敗したプラグインの名前。失敗するたびに警告を出す。
        """
        ...
    def tryLoad(self, dialog: bool | Callable[[str], None] = ..., warn: bool = ...) -> str:
        """対象のMayaと必要な版を確かめてからロードし、結果の定数を返す。

        - minimumMayaより前の版のMayaでは、何もしない。
        - 最小の版を指定した場合、製品が入っていないか版が足りなければ、ロードしない。
        - 最小の版を指定していない場合、製品が見つからなくてもロードを試す。
          すべてのプラグインが失敗すればMISSINGにする。

        失敗しても、ロードできたプラグインを自動ではアンロードしない。

        Args:
            dialog (bool | Callable[[str], None]): TrueならshowDialogで表示し、False/Noneなら表示しない。
                呼び出せるものを渡すと、足りないときの通知の文を渡して呼ぶ。
            warn (bool): Trueなら、製品が入っていないことや版が足りないことをlogger.warningで知らせる。
                プラグインごとのロード失敗の警告は、このフラグでは止めない。

        Returns:
            str: SKIPPED(対象外)、LOADED(成功)、MISSING(入っていない・版が足りない)、
                OUTDATED(ロードされている版が古い)、LOAD_FAILED(ロードに失敗したものがある)。
        """
        ...
    @staticmethod
    def _maya_year() -> int:
        """現在のMayaの年の版を調べる。

        Returns:
            int: 2025などの年の版。
        """
        ...
    def _report(self, show: Callable[..., Any] | None, warn: bool, message: str) -> None:
        """指定した通知先へメッセージを送る。

        Args:
            show (callable | None): メッセージ全体を渡して表示するコールバック。
            warn (bool): Trueなら、最初の行を warning にも渡す。
            message (str): 知らせる内容。コールバックで起きた例外は、そのまま外へ伝わる。

        Returns:
            None: 値を返さない。
        """
        ...
