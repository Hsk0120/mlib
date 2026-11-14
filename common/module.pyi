# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya に登録されているモジュール(``.mod`` で定義したもの)を扱う。"""

import maya.cmds as cmds
from .version import Version
import types



class Module:
    """名前で指す Maya のモジュール。作るときには、存在するかを確かめない。

    Autodesk 製品(Bifrost・MayaUSD・Arnold など)や ``maya/modules/*.mod`` は、
    プラグインとは別に「モジュール」として登録される。モジュールは版と場所を持つ。
    """
    def __init__(self, name: str) -> None:
        """モジュール名を保持する。

        Args:
            name (str): モジュール名(``.mod`` の ``+`` 行に書いた名前。例: ``"Bifrost"``)。

        Raises:
            TypeError: name が文字列でない場合。
            ValueError: name が空文字列の場合。
        """
        ...
    def __eq__(self, other: object) -> bool | types.NotImplementedType:
        """モジュール名で、同じモジュールか判定する。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: Module どうしなら、名前が同じときTrue。型が違えば NotImplemented。
        """
        ...
    def __hash__(self) -> int:
        """モジュール名を使ったハッシュ値を返す。

        Returns:
            int: 保持している名前のハッシュ。
        """
        ...
    def __repr__(self) -> str:
        """デバッグ用に、クラス名とモジュール名を含む表示を返す。

        Returns:
            str: 型名とモジュール名を含む文字列。
        """
        ...
    def __str__(self) -> str:
        """モジュール名を返す。

        Returns:
            str: 保持しているモジュール名。
        """
        ...
    @property
    def name(self) -> str:
        """保持しているモジュール名を取得する。

        Returns:
            str: モジュール名。
        """
        ...
    def isRegistered(self) -> bool:
        """Maya がこのモジュールを認識しているか判定する。

        Returns:
            bool: 登録されていれば True。登録されていない名前でも、例外にはならず False を返す。
        """
        ...
    def getVersionText(self) -> str | None:
        """Mayaが返すモジュールの版の文字列を、そのまま取得する。

        Returns:
            str | None: 手を加えていない版の文字列。登録されていない場合と、空の場合はNone。
        """
        ...
    def getVersion(self) -> Version | None:
        """モジュールの現在の版を、Versionの値として取得する。

        Returns:
            Version | None: 問い合わせたときの版。登録されていない場合と、版として読み取れない場合はNone。
                取得した値をreplaceで変えても、Maya側の版は変わらない。
        """
        ...
    def isVersionAtLeast(self, minimum: Version | str | int | tuple[int, ...]) -> bool:
        """モジュールの版が ``minimum`` 以上か判定する。

        Args:
            minimum (Version | str | int | tuple[int, ...]): 必要な最小の版(``"3.0.0"`` など)。

        Returns:
            bool: minimum以上ならTrue。登録されていなければ False。

        Raises:
            ValueError: minimum を版として読み取れない場合。
        """
        ...
    def getPath(self) -> str | None:
        """モジュールのフォルダーを取得する。

        Returns:
            str | None: モジュールの場所。登録されていない場合は None。
        """
        ...
