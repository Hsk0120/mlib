# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Pythonの探索パスの直下にあるmlib_*の拡張を見つけて登録する。独自のMayaプラグインはロードしない。"""

import ast
import importlib
import importlib.machinery
import importlib.util
import os
import pkgutil
import re
import sys
import tokenize
from collections.abc import Mapping
from pathlib import Path
from .. import logger
from typing import Any, Iterable
from mlib.core.registry import NodeRegistry
from types import ModuleType

__all__ = ['getDiagnostics', 'status']
_states: dict
_loading: bool
_diagnosing: bool
_package_name: Any
_extension_pattern: Any
_attempted: Any

def status() -> dict:
    """最後に初期化したときの、拡張ごとの状態と理由を返す。

    依存するものが今使えるかは、調べ直さない。調べ直すときはgetDiagnosticsを使う。

    Returns:
        dict: 拡張の名前ごとの状態と理由。コピーを返す。
    """
    ...

def getDiagnostics() -> dict[str, dict]:
    """拡張ごとに、初期化したときの記録と、今使えるかどうかを分けて取得する。

    status()は初期化したときの記録だけを返す。この関数は、読み込み済みの拡張のis_available()を呼び直して、
    今使えるかを調べる。ただし、拡張を新しくimportしたり、型を登録したり、reloadしたり、
    Mayaプラグインをロードしたりはしない。
    is_availableの中で依存するものをimportしてもよいが、シーンやUIを変えないことが拡張側の決まりになっている。

    Returns:
        dict[str, dict]: 拡張の名前ごとの記録。initializationは初期化したときの記録のコピー(記録が無ければNone)、
            availableはbool。次の場合はavailableをNoneにし、reasonに理由を入れる:
            拡張がまだimportされていない、初期化中、宣言が正しくない、呼び出しが入れ子になった、調べるのに失敗した。
            初期化の記録と登録表は変えない。
    """
    ...

def _prepare_reload():
    """mlib本体を読み込み直す前に、拡張をまとめて解除する。

    拡張として宣言しているものと、読み込みに失敗したものを解除する。外部のSDKやMayaプラグインは対象外。
    利用側が持っているPythonのオブジェクトは、利用側で取得し直す。
    初期化の途中で呼ばれた場合は、モジュールを1つも削除せずに例外にする。
    """
    ...

def _is_available(package: ModuleType) -> bool:
    """拡張のis_available()を呼んで、今使えるかを調べる。

    初期化と診断で、同じように戻り値の型を確かめるために使う。

    Args:
        package (ModuleType): 宣言を読み終えた拡張のパッケージ。

    Returns:
        bool: 拡張が今使えるならTrue。

    Raises:
        TypeError: is_availableが呼び出せない場合、またはboolを返さない場合。
    """
    ...

def _require_dependencies(name: str, locations: Iterable[str]) -> None:
    """拡張がほかの拡張をimportしていないか、登録する前に確かめる。

    拡張のPythonのソースを読んで調べる。

    Args:
        name (str): 調べる拡張の名前。
        locations (Iterable[str]): パッケージがある親フォルダー。

    Returns:
        None: 値を返さない。

    Raises:
        ValueError: ほかのmlib_*をimportしている場合。

    Note:
        動的なimportは、実行してまで調べない。拡張を作る人は、動的なimportでも同じ規則を守る。
    """
    ...

def _find_candidates() -> dict[str, set[str]]:
    """拡張ごとに、実際に置いてある場所を集める。

    探索パスの重なりは除く。importはしない。

    Returns:
        dict[str, set[str]]: 拡張の名前と、置いてある場所(形を整えたパス)。
    """
    ...

def _may_contain_candidate(path: str) -> bool:
    """探索パスの直下に、拡張の名前と一致するものがありそうか調べる。

    パッケージかどうかを調べる前に、手早く絞り込むために使う。
    pkgutil.iter_modulesは、ふつうのフォルダーではすべてのサブフォルダーの中身を一覧する。
    そのため、Mayaの長い探索パスでは起動が遅くなる。
    ふつうのフォルダー(FileFinder)でパッケージとして返る名前はフォルダーの名前そのものなので、
    直下に一致するものが無ければ、結果は必ず空になる。
    zipなど、ほかのimporterは調べずに、これまでどおりiter_modulesに任せる。

    Args:
        path (str): sys.pathの1項目。

    Returns:
        bool: iter_modulesで拡張の候補を探す必要があればTrue。
    """
    ...

def _load_candidate(name: str, locations: set[str]) -> dict | None:
    """拡張の軽い宣言(パッケージの__init__)を読む。

    対象外の拡張や、今使えない拡張なら、その状態を返す。

    Args:
        name (str): 見つけた拡張の名前。
        locations (set[str]): 拡張がある親フォルダー。

    Returns:
        dict | None: 読み飛ばす場合の状態。使える拡張ならNone。

    Raises:
        TypeError: 使えるかの判定(is_available)がboolを返さない場合。
        ValueError: 同じ名前の拡張が複数の場所にある場合。
        RuntimeError: 拡張の初期化中に、また呼ばれた場合。
    """
    ...

def _validated_entries(name: str, bases: Iterable[tuple[str, type]]) -> list[tuple[NodeRegistry, dict[str, type]]]:
    """拡張が宣言した型とクラスの対応を、すべての種類について確かめて集める。

    この時点では、まだ登録しない。

    Args:
        name (str): 使える拡張の名前。
        bases (Iterable[tuple[str, type]]): サブパッケージの名前と、クラスが継承していなければならない基底クラス。

    Returns:
        list[tuple[NodeRegistry, dict[str, type]]]: 登録表と、確かめてある型とクラスの対応。

    Raises:
        TypeError: 宣言や基底クラスが正しくない場合、またはほかの拡張のクラスを継承している場合。
        ValueError: 型名が正しくない場合、またはすでに登録された型名と重なる場合。
    """
    ...

def _apply_entries(entries: list[tuple[NodeRegistry, dict[str, type]]]) -> None:
    """確かめてある型とクラスの対応を、すべての登録表へ登録する。

    途中で失敗した場合は、すべての登録表を元に戻す。

    Args:
        entries (list[tuple[NodeRegistry, dict[str, type]]]): 登録する型とクラスの対応。

    Returns:
        None: 値を返さない。

    Raises:
        Exception: 登録中に出た例外。登録表を元に戻してから、そのまま送出し直す。
    """
    ...

def _initialize():
    """mlib標準の登録が終わった後に、拡張を見つけて、拡張ごとに確かめて登録する。"""
    ...
