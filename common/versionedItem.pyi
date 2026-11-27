# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""名前で指し、版を持つMayaの登録物(プラグイン・モジュール)に共通する基底クラス。"""

from ..decorator import _require_bool
from .version import Version
from typing import Literal
from typing import overload



class _VersionedItem:
    """名前を持ち、版を問い合わせられる登録物の基底クラス。

    派生クラスは、Mayaへ問い合わせる ``_version_text`` と、種類ごとの照会を書く。
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
    @overload
    def getVersion(self, *, text: Literal[True]) -> str | None: ...
    @overload
    def getVersion(self, *, text: Literal[False] = ...) -> Version | None: ...
    @overload
    def getVersion(self, *, text: bool = ...) -> Version | str | None:
        """現在の版を取得する。

        版の比較は、戻り値の :meth:`Version.isAtLeast` で行う
        (``v = item.getVersion(); v is not None and v.isAtLeast("3.0.0")``)。

        Args:
            text (bool): True なら、Mayaが返す版の文字列を手を加えずに返す。
                数字で始まらない版(``"development"`` など)はVersionとして読めないので、こちらで読む。既定はFalse。

        Returns:
            Version | str | None: 問い合わせたときの版。``text=True`` なら文字列。
                登録されていない場合と、版として読み取れない場合(``text=True`` では空の場合)はNone。
                取得した値をreplaceで変えても、Maya側の版は変わらない。

        Raises:
            TypeError: text が bool でない場合。
        """
        ...
    def _version_text(self) -> str | None:
        """Mayaが返す版の文字列を、そのまま取得する。派生クラスが書く。

        Returns:
            str | None: 手を加えていない版の文字列。登録されていない場合と、空の場合はNone。

        Raises:
            NotImplementedError: 基底クラスで呼んだ場合。
        """
        ...
