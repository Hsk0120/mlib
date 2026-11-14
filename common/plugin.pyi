# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya のロード済み/登録済みプラグインを扱う。"""

import maya.cmds as cmds
from ..core.registry import _clear_type_hierarchy_cache
from .version import Version
from mlib.nodes.node import Node
import types



class Plugin:
    """名前で指す Maya のプラグイン(.mll/.py/.so)。作るときには、存在するかを確かめない。"""
    def __init__(self, name: str) -> None:
        """プラグイン名を保持する。

        Args:
            name (str): プラグインファイル名(拡張子を除く。例: ``"matrixNodes"``)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: name が文字列でない場合。
            ValueError: name が空文字列の場合。
        """
        ...
    def __eq__(self, other: object) -> bool | types.NotImplementedType:
        """プラグイン名で、同じプラグインか判定する。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: Plugin どうしなら、名前が同じときTrue。
                型が違えば NotImplemented。
        """
        ...
    def __hash__(self) -> int:
        """プラグイン名を使ったハッシュ値を返す。

        Returns:
            int: 保持している名前のハッシュ。
        """
        ...
    def __repr__(self) -> str:
        """デバッグ用に、クラス名とプラグイン名を含む表示を返す。

        Returns:
            str: 型名とプラグイン名を含む文字列。
        """
        ...
    def __str__(self) -> str:
        """プラグイン名を返す。

        Returns:
            str: 保持しているプラグイン名。
        """
        ...
    @classmethod
    def ensureNodePlugin(cls, nodeType: str) -> None:
        """指定したノード型に必要な、Maya標準のプラグインをロードする。

        Args:
            nodeType (str): 作るMayaのノード型。HumanIKの型でなければ何もしない。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: Mayaがプラグインのロードを拒否した場合。
        """
        ...
    @classmethod
    def loaded(cls) -> list[Plugin]:
        """ロードされているプラグインを取得する。

        Returns:
            list[Plugin]: プラグインの一覧。Mayaが返す順に並ぶ。
        """
        ...
    @classmethod
    def listUnknown(cls) -> list[str]:
        """シーンが必要としているのに見つからない、未知のプラグインの名前を取得する。

        ``cmds.unknownPlugin(query=True, list=True)`` と同じ。読み込んだファイルの ``requires`` に
        書かれていて、Mayaが見つけられなかったプラグインが対象。

        Returns:
            list[str]: 未知のプラグインの名前。無ければ空リスト。
        """
        ...
    @classmethod
    def removeUnknown(cls, names: str | list[str] | None = ...) -> list[str]:
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
        ...
    @classmethod
    def listUnknownNodes(cls) -> list[Node]:
        """型が分からない、未知のノードを取得する。

        対象は ``unknown``・``unknownDag``・``unknownTransform`` のノード。プラグインが見つからない
        ファイルを読み込んだときに、Mayaが元の型の代わりに作るノード。

        Returns:
            list[Node]: 未知のノード。``cmds.ls`` の順に並ぶ。無ければ空リスト。
        """
        ...
    @property
    def name(self) -> str:
        """保持しているプラグイン名を取得する。

        Returns:
            str: プラグイン名。
        """
        ...
    def isRegistered(self) -> bool:
        """Maya がこのプラグインを認識しているか判定する。

        Returns:
            bool: 登録されていれば(ロード済みか、ロードしていないが見つけられれば) True。
                知らないプラグイン名では False。
        """
        ...
    def isLoaded(self) -> bool:
        """プラグインが現在ロードされているか判定する。

        Returns:
            bool: ロードされていれば True。知らないプラグイン名でも、例外にはならず False を返す。
        """
        ...
    def getPath(self) -> str | None:
        """プラグインファイルの絶対パスを取得する。

        Returns:
            str | None: 登録されているプラグインのファイルパス。登録されていない場合は None。
        """
        ...
    def getVersionText(self) -> str | None:
        """Mayaが返すプラグインの版の文字列を、そのまま取得する。

        Returns:
            str | None: 手を加えていない版の文字列。登録されていない場合と、空の場合はNone。
        """
        ...
    def getVersion(self) -> Version | None:
        """プラグインの現在の版を、Versionの値として取得する。

        Returns:
            Version | None: 問い合わせたときの版。登録されていない場合と、版として読み取れない場合はNone。
                取得した値をreplaceで変えても、Maya側の版は変わらない。
        """
        ...
    def isVersionAtLeast(self, minimum: Version | str | int | tuple[int, ...]) -> bool:
        """プラグインの版が ``minimum`` 以上か判定する。

        Args:
            minimum (Version | str | int | tuple[int, ...]): 必要な最小の版(``"3.0.0"`` など)。

        Returns:
            bool: minimum以上ならTrue。登録されていない場合と、版が取れない場合は False。

        Raises:
            ValueError: minimum を版として読み取れない場合。
        """
        ...
    def load(self, **kwargs: object) -> Plugin:
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
        ...
    def unload(self, force: bool = ...) -> Plugin:
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
        ...
    def ensureLoaded(self) -> Plugin:
        """ロードされていなければロードする。

        何度呼んでも結果は同じ(すでにロードされていれば何もしない)。

        Returns:
            Plugin: 自身。

        Raises:
            RuntimeError: Maya がロードを拒否した場合。
        """
        ...
