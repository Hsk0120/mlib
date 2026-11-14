"""Maya のロード済み/登録済みプラグインを扱う。"""

import maya.cmds as cmds

from ..core.registry import _clear_type_hierarchy_cache
from .version import Version

# 旧構成からreloadした場合も、移動したコレクションクラスを残さない。
globals().pop("Plugins", None)

# Versionへ集約した旧関数参照をreload時に残さない。
for _name in ("parse_version", "is_at_least", "format_version"):
    globals().pop(_name, None)


class Plugin:
    """名前で指す Maya のプラグイン(.mll/.py/.so)。作るときには、存在するかを確かめない。"""

    _HIK_NODE_TYPES = frozenset(("HIKCharacterNode", "HIKSolverNode", "HIKRetargeterNode", "HIKControlSetNode", "HIKSkeletonGeneratorNode"))

    def __init__(self, name):
        """プラグイン名を保持する。

        Args:
            name (str): プラグインファイル名(拡張子を除く。例: ``"matrixNodes"``)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: name が文字列でない場合。
            ValueError: name が空文字列の場合。
        """
        if not isinstance(name, str):
            raise TypeError("nameはstrで指定してください")
        if not name:
            raise ValueError("nameは空でない文字列で指定してください")
        self._name = name

    def __eq__(self, other):
        """プラグイン名で、同じプラグインか判定する。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: Plugin どうしなら、名前が同じときTrue。
                型が違えば NotImplemented。
        """
        if not isinstance(other, Plugin):
            return NotImplemented
        return self._name == other._name

    def __hash__(self):
        """プラグイン名を使ったハッシュ値を返す。

        Returns:
            int: 保持している名前のハッシュ。
        """
        return hash(self._name)

    def __repr__(self):
        """デバッグ用に、クラス名とプラグイン名を含む表示を返す。

        Returns:
            str: 型名とプラグイン名を含む文字列。
        """
        return f"Plugin({self._name!r})"

    def __str__(self):
        """プラグイン名を返す。

        Returns:
            str: 保持しているプラグイン名。
        """
        return self._name

    @classmethod
    def ensureNodePlugin(cls, nodeType):
        """指定したノード型に必要な、Maya標準のプラグインをロードする。

        Args:
            nodeType (str): 作るMayaのノード型。HumanIKの型でなければ何もしない。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: Mayaがプラグインのロードを拒否した場合。
        """
        if nodeType in cls._HIK_NODE_TYPES:
            cls("mayaHIK").ensureLoaded()

    @classmethod
    def loaded(cls):
        """ロードされているプラグインを取得する。

        Returns:
            list[Plugin]: プラグインの一覧。Mayaが返す順に並ぶ。
        """
        return [cls(name) for name in (cmds.pluginInfo(query=True, listPlugins=True) or [])]

    @classmethod
    def listUnknown(cls):
        """シーンが必要としているのに見つからない、未知のプラグインの名前を取得する。

        ``cmds.unknownPlugin(query=True, list=True)`` と同じ。読み込んだファイルの ``requires`` に
        書かれていて、Mayaが見つけられなかったプラグインが対象。

        Returns:
            list[str]: 未知のプラグインの名前。無ければ空リスト。
        """
        return list(cmds.unknownPlugin(query=True, list=True) or [])

    @classmethod
    def removeUnknown(cls, names=None):
        """未知のプラグインの記録を、シーンから外す。

        ``cmds.unknownPlugin(name, remove=True)`` と同じ。外した記録は、保存するファイルの ``requires`` に
        書かれなくなる。未知のノード(:meth:`listUnknownNodes`)は残るので、必要なら別に削除する。
        ``cmds.unknownPlugin`` はUndoに記録されないため、この操作はUndoできない。

        Args:
            names (str | list[str] | None): 外すプラグインの名前。Noneなら未知のプラグインすべて。

        Returns:
            list[str]: 外したプラグインの名前(指定した順)。

        Raises:
            TypeError: namesが文字列・文字列のリストかタプル・Noneのどれでもない場合。
            ValueError: 未知のプラグインに無い名前を含む場合(このときは何も外さない)。
        """
        unknown = cls.listUnknown()
        if names is None:
            targets = unknown
        elif isinstance(names, str):
            targets = [names]
        elif isinstance(names, (list, tuple)) and all(isinstance(name, str) for name in names):
            targets = list(names)
        else:
            raise TypeError("namesはstrか、strのリストか、Noneで指定してください")
        missing = [name for name in targets if name not in unknown]
        if missing:
            raise ValueError(f"不明なプラグインではありません: {', '.join(missing)}")
        removed = []
        for name in targets:
            if name in removed:
                continue
            cmds.unknownPlugin(name, remove=True)
            removed.append(name)
        return removed

    @classmethod
    def listUnknownNodes(cls):
        """型が分からない、未知のノードを取得する。

        対象は ``unknown``・``unknownDag``・``unknownTransform`` のノード。プラグインが見つからない
        ファイルを読み込んだときに、Mayaが元の型の代わりに作るノード。

        Returns:
            list[Node]: 未知のノード。``cmds.ls`` の順に並ぶ。無ければ空リスト。
        """
        # commonの初期化時にnodesを読み込まないよう、使用時にNodeを読み込む。
        from ..nodes.node import Node

        names = cmds.ls(type=["unknown", "unknownDag", "unknownTransform"], long=True) or []
        return [Node(name) for name in names]

    @property
    def name(self):
        """保持しているプラグイン名を取得する。

        Returns:
            str: プラグイン名。
        """
        return self._name

    def isRegistered(self):
        """Maya がこのプラグインを認識しているか判定する。

        Returns:
            bool: 登録されていれば(ロード済みか、ロードしていないが見つけられれば) True。
                知らないプラグイン名では False。
        """
        return bool(cmds.pluginInfo(self._name, query=True, registered=True))

    def isLoaded(self):
        """プラグインが現在ロードされているか判定する。

        Returns:
            bool: ロードされていれば True。知らないプラグイン名でも、例外にはならず False を返す。
        """
        return bool(cmds.pluginInfo(self._name, query=True, loaded=True))

    def getPath(self):
        """プラグインファイルの絶対パスを取得する。

        Returns:
            str | None: 登録されているプラグインのファイルパス。登録されていない場合は None。
        """
        if not self.isRegistered():
            return None
        return cmds.pluginInfo(self._name, query=True, path=True) or None

    def getVersionText(self):
        """Mayaが返すプラグインの版の文字列を、そのまま取得する。

        Returns:
            str | None: 手を加えていない版の文字列。登録されていない場合と、空の場合はNone。
        """
        if not self.isRegistered():
            return None
        return cmds.pluginInfo(self._name, query=True, version=True) or None

    def getVersion(self):
        """プラグインの現在の版を、Versionの値として取得する。

        Returns:
            Version | None: 問い合わせたときの版。登録されていない場合と、版として読み取れない場合はNone。
                取得した値をreplaceで変えても、Maya側の版は変わらない。
        """
        return Version.parse(self.getVersionText())

    def isVersionAtLeast(self, minimum):
        """プラグインの版が ``minimum`` 以上か判定する。

        Args:
            minimum (Version | str | int | tuple[int, ...]): 必要な最小の版(``"3.0.0"`` など)。

        Returns:
            bool: minimum以上ならTrue。登録されていない場合と、版が取れない場合は False。

        Raises:
            ValueError: minimum を版として読み取れない場合。
        """
        required = Version.parse(minimum)
        if required is None:
            raise ValueError(f"最小バージョンが不正です: {minimum!r}")
        version = self.getVersion()
        return version is not None and version >= required

    def load(self, **kwargs):
        """プラグインをロードする。

        うまくロードできたら、mlibが持つノード型の継承のキャッシュを消す。
        次にクラスを選ぶときに、Mayaへ問い合わせ直す。
        cmds.loadPluginを直接使ってロードした場合の変化は、ここでは見張らない。

        Args:
            **kwargs (object): ``cmds.loadPlugin`` に渡す、そのほかのキーワード引数(``quiet=True`` など)。

        Returns:
            Plugin: 自身。

        Raises:
            RuntimeError: Mayaがロードを拒否した場合、または初期化のあともロードされていない場合。
        """
        cmds.loadPlugin(self._name, **kwargs)
        # Pythonプラグインの初期化失敗は、例外なしのNoneとして返る場合がある。
        # 戻り値だけでは既にロード済みのquiet呼出しと区別できないため状態を照会する。
        if not self.isLoaded():
            raise RuntimeError(f"プラグインの初期化が完了しませんでした: {self._name}")
        _clear_type_hierarchy_cache()
        return self

    def unload(self, force=False):
        """プラグインをアンロードする。

        うまくアンロードできたら、mlibが持つノード型の継承のキャッシュを消す。
        ロードされていないプラグインでは、Mayaが警告を出すだけで、例外にはならない。

        Args:
            force (bool): True なら、使われていても強制的にアンロードする。

        Returns:
            Plugin: 自身。

        Raises:
            RuntimeError: Maya がアンロードを拒否した場合(使用中のノードがあり force=False の場合など)。
        """
        cmds.unloadPlugin(self._name, force=force)
        _clear_type_hierarchy_cache()
        return self

    def ensureLoaded(self):
        """ロードされていなければロードする。

        何度呼んでも結果は同じ(すでにロードされていれば何もしない)。

        Returns:
            Plugin: 自身。

        Raises:
            RuntimeError: Maya がロードを拒否した場合。
        """
        if not self.isLoaded():
            self.load()
        return self
