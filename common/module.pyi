# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya に登録されているモジュール(``.mod`` で定義したもの)を扱う。"""

import maya.cmds as cmds
from .versionedItem import _VersionedItem
import types



class Module(_VersionedItem):
    """名前で指す Maya のモジュール。作るときには、存在するかを確かめない。

    Autodesk 製品(Bifrost・MayaUSD・Arnold など)や ``maya/modules/*.mod`` は、
    プラグインとは別に「モジュール」として登録される。モジュールは版と場所を持つ。
    名前は、``.mod`` の ``+`` 行に書いたモジュール名(``"Bifrost"`` など)で指定する。
    """
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
    def getPath(self) -> str | None:
        """モジュールのフォルダーを取得する。

        Returns:
            str | None: モジュールの場所。登録されていない場合は None。
        """
        ...
