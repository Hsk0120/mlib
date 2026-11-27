"""名前で指し、版を持つMayaの登録物(プラグイン・モジュール)に共通する基底クラス。"""

from ..decorator import _require_bool
from .version import Version


class _VersionedItem:
    """名前を持ち、版を問い合わせられる登録物の基底クラス。

    派生クラスは、Mayaへ問い合わせる ``_version_text`` と、種類ごとの照会を書く。
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

    def getVersion(self, *, text=False):
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
        _require_bool(text, "text")
        raw = self._version_text()
        if text:
            return raw
        return Version.parse(raw)

    def _version_text(self):
        """Mayaが返す版の文字列を、そのまま取得する。派生クラスが書く。

        Returns:
            str | None: 手を加えていない版の文字列。登録されていない場合と、空の場合はNone。

        Raises:
            NotImplementedError: 基底クラスで呼んだ場合。
        """
        raise NotImplementedError(f"{type(self).__name__}は_version_textを実装していません")
