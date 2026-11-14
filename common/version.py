"""Mayaに依存しない版番号の値を扱う。"""

import re
from dataclasses import dataclass
from functools import total_ordering


@total_ordering
@dataclass(frozen=True, eq=False, repr=False, init=False)
class Version:
    """版番号を表すクラス。

    「3.0.1」のような数字の並びと、その後ろに付く文字(接尾辞)を持つ。作った後は値を変えられない。

    比べるときは、足りない桁を0とみなし、ビルド情報などの接尾辞は無視する。
    たとえば3.0と3.0.0-buildは等しい。SemVerのプレリリースの順位は扱わない。
    Mayaへ問い合わせたり、プラグインを更新したりはしない。
    """

    __slots__ = ("_parts", "_suffix")
    _parts: tuple
    _suffix: str

    def __init__(self, value):
        """文字列・整数・整数の並びから版番号を作る。

        Args:
            value (Version | str | int | tuple | list): 版番号。
                文字列は、先頭の数字とドットを版番号として読み、残りを接尾辞として持つ。
                tupleやlistの要素には、0以上の整数か、数字だけの文字列を指定する。

        Raises:
            TypeError: 対応していない型やboolを指定した場合、または並びの要素が整数でない場合。
            ValueError: 空の並び、負の数、数字で始まらない文字列を指定した場合。
        """
        suffix = ""
        if isinstance(value, type(self)):
            parts, suffix = value.parts, value.suffix
        elif isinstance(value, str):
            match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)*)(.*)", value.strip())
            if match is None:
                raise ValueError(f"バージョンは数字のリリース番号で始めてください: {value!r}")
            parts = tuple(int(part) for part in match.group(1).split("."))
            suffix = match.group(2)
        elif isinstance(value, (int, tuple, list)):
            values = (value,) if isinstance(value, int) else value
            parts = tuple(self._component(part) for part in values)
            if not parts:
                raise ValueError("バージョンには部分が1つ以上必要です")
        else:
            raise TypeError("Version・文字列・整数・整数の並びのどれかを指定してください")
        object.__setattr__(self, "_parts", parts)
        object.__setattr__(self, "_suffix", suffix)

    def __eq__(self, other):
        """版番号どうしが等しいか比べる。

        数字の並びだけを比べ、接尾辞は無視する。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | NotImplementedType: 等しければTrue。相手がVersionでなければNotImplemented。
        """
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._comparison_key() == other._comparison_key()

    def __hash__(self):
        """ハッシュ値を返す。

        等しい版番号には同じ値を返す。

        Returns:
            int: ハッシュ値。末尾の0の有無と接尾辞では変わらない。
        """
        return hash(self._comparison_key())

    def __lt__(self, other):
        """版番号がもう一方より小さいか比べる。

        数字の並びだけを比べ、接尾辞は順番に影響しない。

        Args:
            other (Version): 比べる相手。

        Returns:
            bool | NotImplementedType: 小さければTrue。相手がVersionでなければNotImplemented。
        """
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._comparison_key() < other._comparison_key()

    def __repr__(self):
        """デバッグ用に、クラス名と版番号を表す文字列を返す。

        Returns:
            str: ``Version('3.0.1')`` のように、Versionを作るときの書き方の文字列。
        """
        return f"{type(self).__name__}({str(self)!r})"

    def __str__(self):
        """数字の並びと接尾辞を、文字列にする。

        Returns:
            str: 3.0.0.0-buildのような文字列。各桁の先頭の0と、前後の空白は取り除いた形になる。
        """
        return ".".join(str(part) for part in self._parts) + self._suffix

    @classmethod
    def parse(cls, value):
        """値を版番号として読む。

        版番号として読めない値は、例外にせずNoneを返す。

        Args:
            value (object): Mayaなどから取得した版番号。

        Returns:
            Version | None: 読めた版番号。読めない値、None、空文字列の場合はNone。
        """
        try:
            return cls(value)
        except (TypeError, ValueError):
            return None

    @property
    def parts(self):
        """tuple[int, ...]: 数字の並び。作ったときの桁数のまま持つ。"""
        return self._parts

    @property
    def suffix(self):
        """str: 数字の並びより後ろの、ビルド情報などの文字。無ければ空文字列。"""
        return self._suffix

    @property
    def major(self):
        """int: 1桁目のメジャー番号。"""
        return self._parts[0]

    @property
    def minor(self):
        """int: 2桁目のマイナー番号。桁が無ければ0。"""
        return self._parts[1] if len(self._parts) > 1 else 0

    @property
    def patch(self):
        """int: 3桁目のパッチ番号。桁が無ければ0。"""
        return self._parts[2] if len(self._parts) > 2 else 0

    @property
    def build(self):
        """int: 4桁目のビルド番号。桁が無ければ0。接尾辞とは別の値。"""
        return self._parts[3] if len(self._parts) > 3 else 0

    def replace(self, *, major=None, minor=None, patch=None, build=None):
        """指定した桁を変えた、新しい版番号を返す。

        元の版番号は変えない。

        Args:
            major (int | None): 1桁目。Noneなら今の値のまま。既定はNone。
            minor (int | None): 2桁目。Noneなら今の値のまま。既定はNone。
            patch (int | None): 3桁目。Noneなら今の値のまま。既定はNone。
            build (int | None): 4桁目。Noneなら今の値のまま。既定はNone。

        Returns:
            Version: 新しい版番号。指定しなかった桁と接尾辞は元のまま。
                途中の桁が足りなければ0で埋める。

        Raises:
            TypeError: 整数でない値を指定した場合。
            ValueError: 負の値を指定した場合。
        """
        parts = list(self._parts)
        for index, value in enumerate((major, minor, patch, build)):
            if value is None:
                continue
            component = self._component(value)
            parts.extend([0] * max(0, index + 1 - len(parts)))
            parts[index] = component
        result = type(self)(parts)
        object.__setattr__(result, "_suffix", self._suffix)
        return result

    def isAtLeast(self, minimum):
        """必要な版番号以上か調べる。

        Args:
            minimum (Version | str | int | tuple | list): 必要な最小の版番号。

        Returns:
            bool: 数字の並びを比べて、minimum以上ならTrue。

        Raises:
            ValueError: minimumを版番号として読めない場合。
        """
        required = type(self).parse(minimum)
        if required is None:
            raise ValueError(f"最小バージョンが不正です: {minimum!r}")
        return self >= required

    @staticmethod
    def _component(value):
        """版番号の1桁を、0以上の整数へ変換する。

        Args:
            value (int | str): 整数、または数字だけの文字列。

        Returns:
            int: 確かめた後の、0以上の整数。

        Raises:
            TypeError: bool・小数など整数でない場合。
            ValueError: 負の整数の場合。
        """
        if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
            return int(value)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("バージョンの各部分は整数で指定してください")
        if value < 0:
            raise ValueError("バージョンの各部分は0以上で指定してください")
        return value

    def _comparison_key(self):
        """比較とハッシュに使う、末尾の0を除いた数字の並びを返す。

        Returns:
            tuple[int, ...]: 数字の並び。少なくとも1桁は残す。
        """
        parts = self._parts
        while len(parts) > 1 and parts[-1] == 0:
            parts = parts[:-1]
        return parts
