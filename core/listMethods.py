"""複数形のクラス(Nodes・Plugs)へ、Pythonのlistと同じ名前の操作を足す。"""


class _ListMethods:
    """要素を ``_items`` (list)で持つ複数形のクラスへ、listと同じ名前のメソッドを足す基底クラス。

    listとの違いは2つ。

    - 追加する値は、そのクラスを作るときと同じ決まりで解決して確かめる(名前も渡せる。型の合わないものはTypeError)。
    - 同じ要素は1つしか持たない。すでにある要素を追加しても、何も変わらない。

    派生クラスは :meth:`_resolve_item` を実装する。
    """

    _items: list

    def __contains__(self, value):
        """要素として持っているかを返す。

        Args:
            value (object): 調べる値。そのクラスの要素か、要素として解決できる名前など。

        Returns:
            bool: 持っていればTrue。解決できない値・型の合わない値はFalse。
        """
        try:
            item = self._resolve_item(value)
        except (TypeError, ValueError, RuntimeError):
            return False
        return item in self._items

    def __setitem__(self, index, value):
        """番号の位置の要素を置き換える。

        Args:
            index (int | slice): Pythonのlistと同じ番号。sliceなら、その範囲を値の並びで置き換える。
            value (object | Iterable[object]): 置き換える要素。sliceなら要素の並び。

        Raises:
            IndexError: 番号が範囲の外の場合。
            TypeError: 要素の型が合わない場合。
            ValueError: 置き換えた結果、同じ要素が2つになる場合。
            RuntimeError: 解決できない値か、無効な要素の場合。
        """
        items = list(self._items)
        if isinstance(index, slice):
            items[index] = self._resolve_new_items(list(value))
        else:
            items[index] = self._resolve_new_items([value])[0]
        if any(items.count(item) > 1 for item in items):
            raise ValueError(f"{type(self).__name__}は同じ要素を2つ持てません")
        self._items = items

    def __delitem__(self, index):
        """番号の位置の要素を取り除く。シーンのノードやアトリビュートは削除しない。

        Args:
            index (int | slice): Pythonのlistと同じ番号。

        Raises:
            IndexError: 番号が範囲の外の場合。
        """
        del self._items[index]

    def __iadd__(self, other):
        """``+=`` で、後ろへ要素を足す(:meth:`extend` と同じ)。

        Args:
            other (Iterable[object]): 足す要素の並び。

        Returns:
            object: 自身。
        """
        self.extend(other)
        return self

    def append(self, value):
        """後ろへ要素を1つ足す。すでに持っている要素なら何もしない。

        Args:
            value (object): 足す要素。そのクラスの要素か、要素として解決できる名前など。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 要素の型が合わない場合。
            RuntimeError: 解決できない値か、無効な要素の場合。
        """
        item = self._resolve_new_items([value])[0]
        if item not in self._items:
            self._items.append(item)

    def extend(self, values):
        """後ろへ要素の並びを足す。すでに持っている要素は足さない。

        すべての値を確かめてから足すので、例外が起きたときは何も変わらない。

        Args:
            values (Iterable[object]): 足す要素の並び。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 要素の型が合わない場合。
            RuntimeError: 解決できない値か、無効な要素の場合。
        """
        items = self._resolve_new_items(list(getattr(values, "_items", values)))
        for item in items:
            if item not in self._items:
                self._items.append(item)

    def insert(self, index, value):
        """番号の位置へ要素を1つ入れる。すでに持っている要素なら何もしない。

        Args:
            index (int): Pythonのlistと同じ番号。
            value (object): 入れる要素。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 要素の型が合わない場合。
            RuntimeError: 解決できない値か、無効な要素の場合。
        """
        item = self._resolve_new_items([value])[0]
        if item not in self._items:
            self._items.insert(index, item)

    def remove(self, value):
        """要素を1つ取り除く。シーンのノードやアトリビュートは削除しない。

        Args:
            value (object): 取り除く要素。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: その要素を持っていない場合。
        """
        if value not in self:
            raise ValueError(f"{type(self).__name__}に無い要素は取り除けません: {value!r}")
        self._items.remove(self._resolve_item(value))

    def pop(self, index=-1):
        """番号の位置の要素を取り除いて返す。シーンのノードやアトリビュートは削除しない。

        Args:
            index (int): Pythonのlistと同じ番号。既定は最後の要素。

        Returns:
            object: 取り除いた要素。

        Raises:
            IndexError: 要素が無い場合、または番号が範囲の外の場合。
        """
        return self._items.pop(index)

    def index(self, value, start=0, stop=None):
        """要素の位置を返す。

        Args:
            value (object): 探す要素。
            start (int): 探し始める位置。既定は0。
            stop (int | None): 探し終える位置(この位置は含まない)。Noneなら最後まで。

        Returns:
            int: 要素の位置。

        Raises:
            ValueError: その範囲に要素が無い場合。
        """
        if value not in self:
            raise ValueError(f"{type(self).__name__}に無い要素です: {value!r}")
        return self._items.index(self._resolve_item(value), start, len(self._items) if stop is None else stop)

    def count(self, value):
        """要素を持っている数を返す。同じ要素は1つしか持たないので、0か1になる。

        Args:
            value (object): 数える要素。

        Returns:
            int: 持っていれば1、無ければ0。
        """
        return 1 if value in self else 0

    def clear(self):
        """要素をすべて取り除く。シーンのノードやアトリビュートは削除しない。

        Returns:
            None: 値を返さない。
        """
        del self._items[:]

    def reverse(self):
        """要素の並びを、その場で逆にする。

        Returns:
            None: 値を返さない。
        """
        self._items.reverse()

    def _resolve_new_items(self, values):
        """これから足す値の並びを、このクラスの要素へ解決して確かめる。

        既定は :meth:`_resolve_item` を1つずつ呼ぶだけ。派生クラスは、足す値に合わせて自身の型を広げるときに上書きする。

        Args:
            values (list[object]): 足す値の並び。

        Returns:
            list[object]: このクラスの要素の並び。
        """
        return [self._resolve_item(value) for value in values]

    def _resolve_item(self, value):
        """追加する値を、このクラスの要素へ解決して確かめる。

        Args:
            value (object): 追加する値。

        Returns:
            object: このクラスの要素。

        Raises:
            NotImplementedError: 派生クラスが実装していない場合。
        """
        raise NotImplementedError
