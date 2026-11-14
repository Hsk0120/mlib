"""モジュールとプラグインの組で入る製品(Bifrost など)が入っているか確かめ、ロードする。"""

import maya.cmds as cmds

from .. import logger
from .module import Module
from .plugin import Plugin
from .version import Version

# クラスメソッドへ移した旧モジュール関数をreload時に除去する。
globals().pop("_maya_year", None)

# Versionへ集約した旧関数参照をreload時に残さない。
for _name in ("parse_version", "is_at_least", "format_version"):
    globals().pop(_name, None)

SKIPPED = "skipped"
"""str: 対象外の Maya の版なので、何もしなかった。"""
LOADED = "loaded"
"""str: ロードに失敗したものが無く、版の確認も通った。"""
MISSING = "missing"
"""str: 最小の版に足りない。または、見つからなかった製品のプラグインが、すべてロードに失敗した。"""
OUTDATED = "outdated"
"""str: 入ってはいるが、すでにロードされているプラグインが古い版だった。"""
LOAD_FAILED = "load-failed"
"""str: 1個以上のプラグインのロードに失敗した。"""


class PluginPackage:
    """製品が入っているかを確かめ、ロードする。

    モジュール・プラグインと、必要な版を持つ。作るときはMayaへの問い合わせもロードもしない。
    tryLoadで、対象のMayaの版・入っている版・ロードの結果を順に判定する。
    ロードしたプラグインを自動でアンロードすることはしない。
    """

    def __init__(self, name, plugins=(), module=None, versionPlugin=None, minimumVersion=None, minimumMaya=None, installHint=None):
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
        if not isinstance(name, str):
            raise TypeError("nameはstrで指定してください")
        if not name:
            raise ValueError("nameは空でない文字列で指定してください")
        self._name = name
        self._plugins = tuple(item if isinstance(item, Plugin) else Plugin(item) for item in plugins)
        self._module = module if isinstance(module, Module) or module is None else Module(module)
        if not self._plugins and self._module is None:
            raise ValueError("pluginsかmoduleを指定してください")
        if versionPlugin is None:
            self._version_plugin = self._plugins[0] if self._plugins else None
        else:
            self._version_plugin = versionPlugin if isinstance(versionPlugin, Plugin) else Plugin(versionPlugin)
        if minimumVersion is None:
            self._minimum_version = None
        else:
            self._minimum_version = Version.parse(minimumVersion)
            if self._minimum_version is None:
                raise ValueError(f"minimumVersionは'3.0.0'のようなバージョンで指定してください: {minimumVersion!r}")
        self._minimum_maya = None if minimumMaya is None else int(minimumMaya)
        self._install_hint = installHint

    def __repr__(self):
        """デバッグ用に、製品名と最小の版を含む表示を返す。

        Returns:
            str: 型名・製品名・最小の版を含む文字列。
        """
        minimum = str(self._minimum_version) if self._minimum_version is not None else "なし"
        return f"PluginPackage({self._name!r}, minimumVersion={minimum})"

    @staticmethod
    def showDialog(message, title="インストールが必要です"):
        """警告のダイアログを表示する。GUI の無いバッチ・スタンドアロンでは何もしない。

        Args:
            message (str): 表示する文章。
            title (str): ダイアログのタイトル。

        Returns:
            None: 値を返さない。
        """
        if cmds.about(batch=True):
            return
        cmds.confirmDialog(title=title, message=message, button=["OK"], defaultButton="OK", icon="warning")

    @property
    def name(self):
        """製品名を取得する。

        Returns:
            str: 製品名。
        """
        return self._name

    @property
    def plugins(self):
        """ロードするプラグインを取得する。

        Returns:
            list[Plugin]: プラグイン。ロードする順に並ぶ。
        """
        return list(self._plugins)

    @property
    def module(self):
        """版を取得するモジュールを取得する。

        Returns:
            Module | None: モジュール。指定していない場合は None。
        """
        return self._module

    @property
    def minimumVersion(self):
        """必要な最小の版を取得する。

        Returns:
            Version | None: 最小の版。指定していない場合は None。
        """
        return self._minimum_version

    @property
    def minimumMaya(self):
        """対象とする最小の Maya の年を取得する。

        Returns:
            int | None: 年。指定していない場合は None。
        """
        return self._minimum_maya

    def isMayaSupported(self):
        """現在の Maya が対象の版か判定する。

        Returns:
            bool: ``minimumMaya`` を指定していない場合と、現在の Maya の年がそれ以上の場合は True。
        """
        return self._minimum_maya is None or self._maya_year() >= self._minimum_maya

    def getInstalledVersion(self):
        """Maya に登録されている製品の版を取得する。

        モジュールが登録されていればその版、無ければ版を調べるプラグインの版を使う。

        Returns:
            Version | None: 版。製品が入っていない場合と、版が取れない場合は None。
        """
        version = self._module.getVersion() if self._module is not None else None
        if version is None and self._version_plugin is not None:
            version = self._version_plugin.getVersion()
        return version

    def getLoadedVersion(self):
        """版を調べるプラグインの、ロードされている版を取得する。

        Returns:
            Version | None: 版。ロードされていない場合は None。
        """
        plugin = self._version_plugin
        if plugin is None or not plugin.isLoaded():
            return None
        return plugin.getVersion()

    def isInstalled(self):
        """必要な版が入っているか判定する。

        ロードする前のプラグインは、Maya に登録されていないことがある。そのため ``minimumVersion`` を
        指定していない製品では、この判定が False でも :meth:`tryLoad` がロードを試す。

        Returns:
            bool: ``minimumVersion`` 以上が入っていれば True。``minimumVersion`` を指定していない
            場合は、版が取れるか、モジュールかプラグインが 1 つでも登録されていれば True。
        """
        version = self.getInstalledVersion()
        if self._minimum_version is not None:
            return version is not None and version >= self._minimum_version
        if version is not None:
            return True
        if self._module is not None and self._module.isRegistered():
            return True
        return any(plugin.isRegistered() for plugin in self._plugins)

    def getMessage(self, found=None):
        """製品を入れる必要があるときの、警告の文を作る。

        Args:
            found (Version | None): 見つかった版。省略すると、今入っているものから求める。

        Returns:
            str: 日本語と英語の警告の文。
        """
        if found is None:
            found = self.getInstalledVersion()
        wanted = f"{self._name} {self._minimum_version}" if self._minimum_version else self._name
        year = self._maya_year()
        hint = self._install_hint or f"Autodesk アカウントなどから Maya {year} 用の {wanted} 以降を入手してインストールしてください。"
        found_text = str(found) if found is not None else "なし"
        return (
            f"{wanted} 以降が見つかりません(検出した版: {found_text})。\n\n{hint}\n"
            "インストール後に Maya を再起動すると、自動でロードされます。\n\n"
            f"{wanted} or later was not found for Maya {year}. Please install it."
        )

    def loadPlugins(self):
        """すべてのプラグインをロードする。ロードできないものがあっても続ける。

        Returns:
            list[str]: ロードに失敗したプラグインの名前。失敗するたびに警告を出す。
        """
        failed = []
        for plugin in self._plugins:
            try:
                plugin.load(quiet=True)
            except Exception as error:
                failed.append(plugin.name)
                logger.warning("[mlib] プラグイン%sを読み込めません(%s用): %s", plugin.name, self._name, error)
        return failed

    def tryLoad(self, dialog=True, warn=True):
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
        if not self.isMayaSupported():
            return SKIPPED
        title = f"{self._name} のインストールが必要です"
        show = (lambda text: self.showDialog(text, title)) if dialog is True else (dialog or None)
        installed = self.isInstalled()
        if not installed and self._minimum_version is not None:
            self._report(show, warn, self.getMessage(self.getInstalledVersion()))
            return MISSING
        failed = self.loadPlugins()
        if not installed and self._plugins and len(failed) == len(self._plugins):
            # 版を指定しない製品は、ロードできるかどうかで導入の有無を判断する。
            self._report(show, warn, self.getMessage())
            return MISSING
        running = self.getLoadedVersion()
        if self._minimum_version is not None and running is not None and running < self._minimum_version:
            self._report(show, warn, self.getMessage(running))
            return OUTDATED
        return LOAD_FAILED if failed else LOADED

    @staticmethod
    def _maya_year():
        """現在のMayaの年の版を調べる。

        Returns:
            int: 2025などの年の版。
        """
        return int(str(cmds.about(version=True)).split(".")[0])

    def _report(self, show, warn, message):
        """指定した通知先へメッセージを送る。

        Args:
            show (callable | None): メッセージ全体を渡して表示するコールバック。
            warn (bool): Trueなら、最初の行を warning にも渡す。
            message (str): 知らせる内容。コールバックで起きた例外は、そのまま外へ伝わる。

        Returns:
            None: 値を返さない。
        """
        if warn:
            logger.warning("[mlib] %s", message.split("\n")[0])
        if show is not None:
            show(message)
