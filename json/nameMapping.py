"""保存したときのノード名を、読み込み先のシーンの名前へ変換する規則。"""

from collections.abc import Iterable


def _replace_pairs(replace):
    """名前の置き換え(``replace``)を確かめて、``(旧, 新)`` の組のタプルにする。

    Args:
        replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。

    Returns:
        tuple[tuple[str, str], ...] | None: 置き換えの組。NoneならNone。

    Raises:
        TypeError: Noneでも文字列でない並びでもない場合、組が並びでない場合、または組の要素が文字列でない場合。
        ValueError: 組が2つの要素でない場合、または置き換え前の文字列が空の場合。
    """
    if replace is None:
        return None
    if isinstance(replace, (str, bytes)) or not isinstance(replace, Iterable):
        raise TypeError(f"replaceは(old, new)の組の並びで指定してください: {type(replace).__name__}")
    pairs = []
    for pair in replace:
        if isinstance(pair, (str, bytes)) or not isinstance(pair, Iterable):
            raise TypeError(f"replaceの要素は(old, new)の組で指定してください: {type(pair).__name__}")
        items = tuple(pair)
        if len(items) != 2:
            raise ValueError("replaceの要素は(old, new)の組で指定してください")
        old, new = items
        if not isinstance(old, str) or not isinstance(new, str):
            raise TypeError("replaceの組は文字列で指定してください")
        if not old:
            raise ValueError("replaceの置き換え前の文字列は空にできません")
        pairs.append((old, new))
    return tuple(pairs)


class NameMapping:
    """名前の対応表・文字列の置き換え・名前空間の入れ替えをまとめ、ノード名を変換する。

    3つを同時に指定した場合は次の順に当てはめる。

    1. ``nameMap``: 名前空間を除いた名前で引く。見つかれば置き換えた名前を使い、``replace`` は当てない。
    2. ``replace``: ``(旧, 新)`` の組を順に当てて、文字列を置き換える。
    3. ``namespaceMap``: 名前空間を入れ替える。キー ``""`` は名前空間の無いノードを表す。

    ``NameMapping()`` は名前を変えない。
    """

    def __init__(self, nameMap=None, replace=None, namespaceMap=None):
        """対応づけの規則を持たせる。

        Args:
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表(``{"arm_L_jnt": "leftArm_jnt"}``)。既定はNone。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え(``[("_L_", "_R_")]``)。既定はNone。
            namespaceMap (dict[str, str] | None): 名前空間の対応(``{"chrA": "chrB"}``)。
                先頭の ``":"`` は無視する。入れ子の名前空間では、一致する最も長い親を入れ替える。既定はNone。

        Raises:
            TypeError: どれかの引数の型が正しくない場合(replaceが組の並びでない場合を含む)。
            ValueError: 置き換えの組が2つの要素でない場合、または置き換え前の文字列が空の場合。
        """
        self._name_map = _string_dict(nameMap, "nameMap")
        self._namespace_map = {_strip(key): _strip(value) for key, value in _string_dict(namespaceMap, "namespaceMap").items()}
        self._replace = _replace_pairs(replace) or ()

    def __repr__(self):
        """指定した規則を含む表記を返す。

        Returns:
            str: ``NameMapping(nameMap=..., replace=..., namespaceMap=...)`` の形式。
        """
        return f"NameMapping(nameMap={self._name_map!r}, replace={list(self._replace)!r}, namespaceMap={self._namespace_map!r})"

    def convert(self, name):
        """ノード名(DAGパスの1要素)を変換する。

        Args:
            name (str): ``"chrA:arm_L_jnt"`` のような名前空間付きの名前。``"|"`` を含めない。

        Returns:
            str: 変換後の名前。

        Raises:
            TypeError: nameが文字列でない場合。
        """
        if not isinstance(name, str):
            raise TypeError("nameは文字列で指定してください")
        namespace, _separator, short = name.rpartition(":")
        namespace = _strip(namespace)
        if short in self._name_map:
            short = self._name_map[short]
        else:
            for old, new in self._replace:
                short = short.replace(old, new)
        namespace = self._map_namespace(namespace)
        return f"{namespace}:{short}" if namespace else short

    def _apply_path(self, path):
        """DAGパスのそれぞれの要素を :meth:`convert` で変換する。

        Args:
            path (str): ``"|chrA:root|chrA:arm_L_jnt"`` のようなパス。DGノード名もそのまま渡せる。

        Returns:
            str: 変換後のパス。先頭の ``"|"`` は保つ。

        Raises:
            TypeError: pathが文字列でない場合。
        """
        if not isinstance(path, str):
            raise TypeError("pathは文字列で指定してください")
        return "|".join(self.convert(part) if part else part for part in path.split("|"))

    def _map_namespace(self, namespace):
        """名前空間を ``namespaceMap`` で入れ替える。

        Args:
            namespace (str): 先頭の ``":"`` を除いた名前空間。ルートは空文字列。

        Returns:
            str: 入れ替えた名前空間。対応が無ければそのまま。
        """
        if namespace in self._namespace_map:
            return self._namespace_map[namespace]
        parts = namespace.split(":") if namespace else []
        for size in range(len(parts) - 1, 0, -1):
            parent = ":".join(parts[:size])
            if parent in self._namespace_map:
                mapped = self._namespace_map[parent]
                rest = ":".join(parts[size:])
                return f"{mapped}:{rest}" if mapped else rest
        return namespace


def _strip(namespace):
    """名前空間の先頭と末尾の ``":"`` を除く。

    Args:
        namespace (str): 名前空間。

    Returns:
        str: ``":"`` を除いた名前空間。
    """
    return namespace.strip(":")


def _string_dict(value, name):
    """キーと値が文字列の辞書かを確かめ、コピーを返す。

    Args:
        value (dict[str, str] | None): 確かめる辞書。
        name (str): エラーメッセージに使う引数名。

    Returns:
        dict[str, str]: 新しい辞書。Noneなら空の辞書。

    Raises:
        TypeError: 辞書でない場合、またはキー・値が文字列でない場合。
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{name}はdictで指定してください")
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise TypeError(f"{name}のキーと値は文字列で指定してください")
    return dict(value)
