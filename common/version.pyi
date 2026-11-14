# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaに依存しない版番号の値を扱う。"""

import re
from dataclasses import dataclass
from functools import total_ordering
import types



@total_ordering
class Version:
    """版番号を表すクラス。

    「3.0.1」のような数字の並びと、その後ろに付く文字(接尾辞)を持つ。作った後は値を変えられない。

    比べるときは、足りない桁を0とみなし、ビルド情報などの接尾辞は無視する。
    たとえば3.0と3.0.0-buildは等しい。SemVerのプレリリースの順位は扱わない。
    Mayaへ問い合わせたり、プラグインを更新したりはしない。
    """
    __slots__: tuple
    def __init__(self, value: Version | str | int | tuple | list) -> None:
        """文字列・整数・整数の並びから版番号を作る。

        Args:
            value (Version | str | int | tuple | list): 版番号。
                文字列は、先頭の数字とドットを版番号として読み、残りを接尾辞として持つ。
                tupleやlistの要素には、0以上の整数か、数字だけの文字列を指定する。

        Raises:
            TypeError: 対応していない型やboolを指定した場合、または並びの要素が整数でない場合。
            ValueError: 空の並び、負の数、数字で始まらない文字列を指定した場合。
        """
        ...
    def __eq__(self, other: object) -> bool | types.NotImplementedType:
        """版番号どうしが等しいか比べる。

        数字の並びだけを比べ、接尾辞は無視する。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | NotImplementedType: 等しければTrue。相手がVersionでなければNotImplemented。
        """
        ...
    def __hash__(self) -> int:
        """ハッシュ値を返す。

        等しい版番号には同じ値を返す。

        Returns:
            int: ハッシュ値。末尾の0の有無と接尾辞では変わらない。
        """
        ...
    def __lt__(self, other: Version) -> bool | types.NotImplementedType:
        """版番号がもう一方より小さいか比べる。

        数字の並びだけを比べ、接尾辞は順番に影響しない。

        Args:
            other (Version): 比べる相手。

        Returns:
            bool | NotImplementedType: 小さければTrue。相手がVersionでなければNotImplemented。
        """
        ...
    def __repr__(self) -> str:
        """デバッグ用に、クラス名と版番号を表す文字列を返す。

        Returns:
            str: ``Version('3.0.1')`` のように、Versionを作るときの書き方の文字列。
        """
        ...
    def __str__(self) -> str:
        """数字の並びと接尾辞を、文字列にする。

        Returns:
            str: 3.0.0.0-buildのような文字列。各桁の先頭の0と、前後の空白は取り除いた形になる。
        """
        ...
    @classmethod
    def parse(cls, value: object) -> Version | None:
        """値を版番号として読む。

        版番号として読めない値は、例外にせずNoneを返す。

        Args:
            value (object): Mayaなどから取得した版番号。

        Returns:
            Version | None: 読めた版番号。読めない値、None、空文字列の場合はNone。
        """
        ...
    @property
    def parts(self) -> tuple[int, ...]:
        """tuple[int, ...]: 数字の並び。作ったときの桁数のまま持つ。"""
        ...
    @property
    def suffix(self) -> str:
        """str: 数字の並びより後ろの、ビルド情報などの文字。無ければ空文字列。"""
        ...
    @property
    def major(self) -> int:
        """int: 1桁目のメジャー番号。"""
        ...
    @property
    def minor(self) -> int:
        """int: 2桁目のマイナー番号。桁が無ければ0。"""
        ...
    @property
    def patch(self) -> int:
        """int: 3桁目のパッチ番号。桁が無ければ0。"""
        ...
    @property
    def build(self) -> int:
        """int: 4桁目のビルド番号。桁が無ければ0。接尾辞とは別の値。"""
        ...
    def replace(self, *, major: int | None = ..., minor: int | None = ..., patch: int | None = ..., build: int | None = ...) -> Version:
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
        ...
    def isAtLeast(self, minimum: Version | str | int | tuple | list) -> bool:
        """必要な版番号以上か調べる。

        Args:
            minimum (Version | str | int | tuple | list): 必要な最小の版番号。

        Returns:
            bool: 数字の並びを比べて、minimum以上ならTrue。

        Raises:
            ValueError: minimumを版番号として読めない場合。
        """
        ...
    @staticmethod
    def _component(value: int | str) -> int:
        """版番号の1桁を、0以上の整数へ変換する。

        Args:
            value (int | str): 整数、または数字だけの文字列。

        Returns:
            int: 確かめた後の、0以上の整数。

        Raises:
            TypeError: bool・小数など整数でない場合。
            ValueError: 負の整数の場合。
        """
        ...
    def _comparison_key(self) -> tuple[int, ...]:
        """比較とハッシュに使う、末尾の0を除いた数字の並びを返す。

        Returns:
            tuple[int, ...]: 数字の並び。少なくとも1桁は残す。
        """
        ...
