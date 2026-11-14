# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""動的アトリビュートを、シーンを変える前に組み立てて、OpenMayaで追加する。"""

import maya.api.OpenMaya as om2
from .nodeEdit import require_editable
from typing import Any, Sequence
from mlib.nodes.node import Node
import re

_NUMERIC_TYPES: dict
_DATA_TYPES: dict
_PROPERTIES: dict
_DEFINITION_FLAGS: Any

def _build(flags: dict, children: list[om2.MObject] | None = ...) -> om2.MObject:
    """まだノードに追加していない、アトリビュートの定義を作る。

    失敗してもシーンは変えない。

    Args:
        flags (dict): 形を整えてあるaddAttrのフラグ。
        children (list[MObject] | None): 先に作った子の定義。

    Returns:
        MObject: 新しいアトリビュートの定義。

    Raises:
        ValueError: longNameとshortNameのどちらも無い場合。
        NotImplementedError: fastで扱えないフラグや型の場合。
    """
    ...

def _attach(node: Node, attribute: om2.MObject) -> None:
    """作ってあるアトリビュートの定義を、ノードへ1回で追加する。

    Args:
        node (Node): 追加先のノード。
        attribute (MObject): まだシーンに追加していないアトリビュートの定義。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: ノードがロックされているかリファレンスされている場合、または同じ名前のアトリビュートがある場合。
    """
    ...

def extra_children(name: str, flags: dict, numeric: re.Match | None, count: int, *, deferred: object, child_names: Sequence[str] | None, child_short_names: Sequence[str] | None, child_suffixes: Sequence[str] | None, sub_type: str | None) -> list[tuple[str, str, dict]]:
    """自動で作る子の名前と成分の数を、親を追加する前に確かめる。

    Args:
        name (str): 親のロング名。
        flags (dict): 親の、形を整えてあるフラグ。変更しない。
        numeric (Match | None): 数値のコンパウンドアトリビュートの型名に一致した結果。
        count (int): 子の数。
        deferred (object): 子へ割り振る既定値。
        child_names (Sequence[str] | None): 子のロング名。
        child_short_names (Sequence[str] | None): 子のショート名。
        child_suffixes (Sequence[str] | None): 自動で作る名前の末尾に付ける文字。
        sub_type (str | None): 子に共通の型。

    Returns:
        list[tuple[str, str, dict]]: 子ごとの(ロング名, 型, 公開のaddAttrへ渡すフラグ)。

    Raises:
        ValueError: 子の名前・既定値・範囲の数が、子の数と違う場合。
    """
    ...

def validate_extra_attribute(node: Node, name: str, flags: dict, count: int, deferred: object, children: list[tuple[str, str, dict]], *, validate_defaults: bool = ...) -> None:
    """シーンを変える前に、追加できないアトリビュートを見つけて例外にする。

    名前の重なりと、前もって確かめられる既定値(typedの既定値など)を調べる。

    Args:
        node (Node): 追加先のノード。
        name (str): 親のロング名。
        flags (dict): 親の、形を整えてあるフラグ。
        count (int): 子の数。
        deferred (object): 作った後に設定する既定値。
        children (list[tuple[str, str, dict]]): 確かめてある、子を作るための入力。
        validate_defaults (bool): Trueなら、fastでないときの既定値も追加する前に確かめる。既定はTrue。
            fastのときは、まだ追加していない親子の定義を作るときに確かめるのでFalseにする。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: マルチアトリビュートへ直接、既定値を設定しようとした場合。
        ValueError: 名前が空文字列の場合、または文字列でない場合。
        RuntimeError: 同じ名前のアトリビュートがある場合、または書き込めない定義へ既定値を渡した場合。
    """
    ...

def create_extra_attribute(node: Node, name: str, flags: dict, numeric: re.Match | None, count: int, *, deferred: object, child_names: Sequence[str] | None, child_short_names: Sequence[str] | None, child_suffixes: Sequence[str] | None, sub_type: str | None) -> tuple | None:
    """Node.addAttrで追加する親と子の定義を、追加する前にすべて作ってから追加する。

    Args:
        node (Node): 追加先のノード。
        name (str): 親の名前。
        flags (dict): 親のフラグ。
        numeric (Match | None): 数値のコンパウンドアトリビュートの型名に一致した結果。
        count (int): 子の数。
        deferred (object): 子の既定値。
        child_names (Sequence[str] | None): 子のロング名。
        child_short_names (Sequence[str] | None): 子のショート名。
        child_suffixes (Sequence[str] | None): 子の名前の末尾に付ける文字。
        sub_type (str | None): 子の型。

    Returns:
        tuple | None: typedの既定値を書き込む計画。確かめてあり、データを持つオブジェクトも含む。無ければNone。

    Raises:
        TypeError: マルチアトリビュートそのものへ既定値を指定した場合、または文字列型へ文字列でない値を渡した場合。
        ValueError: 子の名前・既定値・範囲の数が、子の数と違う場合。
        RuntimeError: 書き込めないアトリビュートへ既定値を指定した場合。
        NotImplementedError: 既定値をfastで構築できない型の場合。
    """
    ...
