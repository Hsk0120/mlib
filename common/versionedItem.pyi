# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""名前で指し、版を持つMayaの登録物(プラグイン・モジュール)に共通する基底クラス。"""

from .version import Version



class _VersionedItem:
    """名前を持ち、版を問い合わせられる登録物の基底クラス。

    派生クラスは、Mayaへ問い合わせる ``getVersionText`` と、種類ごとの照会を書く。
    """
    def __init__(self, name: str) -> None:
        """名前を保持する。存在するかは確かめない。

        Args:
            name (str): 登録物の名前。何の名前かは、派生クラスの説明に書く。

        Raises:
            TypeError: name が文字列でない場合。
            ValueError: name が空文字列の場合。
        """
        ...
    def __str__(self) -> str:
        """名前を返す。

        Returns:
            str: 保持している名前。
        """
        ...
    @property
    def name(self) -> str:
        """保持している名前を取得する。

        Returns:
            str: 作るときに渡した名前。
        """
        ...
    def getVersionText(self) -> str | None:
        """Mayaが返す版の文字列を、そのまま取得する。派生クラスが書く。

        Returns:
            str | None: 手を加えていない版の文字列。登録されていない場合と、空の場合はNone。

        Raises:
            NotImplementedError: 基底クラスで呼んだ場合。
        """
        ...
    def getVersion(self) -> Version | None:
        """現在の版を、Versionの値として取得する。

        Returns:
            Version | None: 問い合わせたときの版。登録されていない場合と、版として読み取れない場合はNone。
                取得した値をreplaceで変えても、Maya側の版は変わらない。
        """
        ...
    def isVersionAtLeast(self, minimum: Version | str | int | tuple[int, ...]) -> bool:
        """版が ``minimum`` 以上か判定する。

        Args:
            minimum (Version | str | int | tuple[int, ...]): 必要な最小の版(``"3.0.0"`` など)。

        Returns:
            bool: minimum以上ならTrue。登録されていない場合と、版が取れない場合は False。

        Raises:
            ValueError: minimum を版として読み取れない場合。
        """
        ...
