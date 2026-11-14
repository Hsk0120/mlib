"""Maya に登録されているモジュール(``.mod`` で定義したもの)を扱う。"""

import maya.cmds as cmds

from .version import Version

# Versionへ集約した旧関数参照をreload時に残さない。
for _name in ("parse_version", "is_at_least", "format_version"):
    globals().pop(_name, None)


class Module:
    """名前で指す Maya のモジュール。作るときには、存在するかを確かめない。

    Autodesk 製品(Bifrost・MayaUSD・Arnold など)や ``maya/modules/*.mod`` は、
    プラグインとは別に「モジュール」として登録される。モジュールは版と場所を持つ。
    """

    def __init__(self, name):
        """モジュール名を保持する。

        Args:
            name (str): モジュール名(``.mod`` の ``+`` 行に書いた名前。例: ``"Bifrost"``)。

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
        """モジュール名で、同じモジュールか判定する。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: Module どうしなら、名前が同じときTrue。型が違えば NotImplemented。
        """
        if not isinstance(other, Module):
            return NotImplemented
        return self._name == other._name

    def __hash__(self):
        """モジュール名を使ったハッシュ値を返す。

        Returns:
            int: 保持している名前のハッシュ。
        """
        return hash(self._name)

    def __repr__(self):
        """デバッグ用に、クラス名とモジュール名を含む表示を返す。

        Returns:
            str: 型名とモジュール名を含む文字列。
        """
        return f"Module({self._name!r})"

    def __str__(self):
        """モジュール名を返す。

        Returns:
            str: 保持しているモジュール名。
        """
        return self._name

    @property
    def name(self):
        """保持しているモジュール名を取得する。

        Returns:
            str: モジュール名。
        """
        return self._name

    def isRegistered(self):
        """Maya がこのモジュールを認識しているか判定する。

        Returns:
            bool: 登録されていれば True。登録されていない名前でも、例外にはならず False を返す。
        """
        return self._name in (cmds.moduleInfo(listModules=True) or [])

    def getVersionText(self):
        """Mayaが返すモジュールの版の文字列を、そのまま取得する。

        Returns:
            str | None: 手を加えていない版の文字列。登録されていない場合と、空の場合はNone。
        """
        if not self.isRegistered():
            return None
        return cmds.moduleInfo(version=True, moduleName=self._name) or None

    def getVersion(self):
        """モジュールの現在の版を、Versionの値として取得する。

        Returns:
            Version | None: 問い合わせたときの版。登録されていない場合と、版として読み取れない場合はNone。
                取得した値をreplaceで変えても、Maya側の版は変わらない。
        """
        return Version.parse(self.getVersionText())

    def isVersionAtLeast(self, minimum):
        """モジュールの版が ``minimum`` 以上か判定する。

        Args:
            minimum (Version | str | int | tuple[int, ...]): 必要な最小の版(``"3.0.0"`` など)。

        Returns:
            bool: minimum以上ならTrue。登録されていなければ False。

        Raises:
            ValueError: minimum を版として読み取れない場合。
        """
        required = Version.parse(minimum)
        if required is None:
            raise ValueError(f"最小バージョンが不正です: {minimum!r}")
        version = self.getVersion()
        return version is not None and version >= required

    def getPath(self):
        """モジュールのフォルダーを取得する。

        Returns:
            str | None: モジュールの場所。登録されていない場合は None。
        """
        if not self.isRegistered():
            return None
        return cmds.moduleInfo(path=True, moduleName=self._name) or None
