"""名前で指し、版を持つMayaの登録物(プラグイン・モジュール)に共通する基底クラス。"""

from .version import Version


class _VersionedItem:
    """名前を持ち、版を問い合わせられる登録物の基底クラス。

    派生クラスは、Mayaへ問い合わせる ``getVersionText`` と、種類ごとの照会を書く。
    """

    def __init__(self, name):
        """名前を保持する。存在するかは確かめない。

        Args:
            name (str): 登録物の名前。何の名前かは、派生クラスの説明に書く。

        Raises:
            TypeError: name が文字列でない場合。
            ValueError: name が空文字列の場合。
        """
        if not isinstance(name, str):
            raise TypeError("nameはstrで指定してください")
        if not name:
            raise ValueError("nameは空でない文字列で指定してください")
        self._name = name

    def __str__(self):
        """名前を返す。

        Returns:
            str: 保持している名前。
        """
        return self._name

    @property
    def name(self):
        """保持している名前を取得する。

        Returns:
            str: 作るときに渡した名前。
        """
        return self._name

    def getVersionText(self):
        """Mayaが返す版の文字列を、そのまま取得する。派生クラスが書く。

        Returns:
            str | None: 手を加えていない版の文字列。登録されていない場合と、空の場合はNone。

        Raises:
            NotImplementedError: 基底クラスで呼んだ場合。
        """
        raise NotImplementedError(f"{type(self).__name__}はgetVersionTextを実装していません")

    def getVersion(self):
        """現在の版を、Versionの値として取得する。

        Returns:
            Version | None: 問い合わせたときの版。登録されていない場合と、版として読み取れない場合はNone。
                取得した値をreplaceで変えても、Maya側の版は変わらない。
        """
        return Version.parse(self.getVersionText())

    def isVersionAtLeast(self, minimum):
        """版が ``minimum`` 以上か判定する。

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
