# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""パッケージの中のモジュールを、参照の関係に合わせた順で読み直す。"""

import importlib
import pkgutil
import sys
import types
from typing import Iterable
from types import ModuleType

__all__ = ['reload_package']

def reload_package(package_name: str) -> tuple[ModuleType]:
    """読み込み済みのパッケージを読み直す。

    パッケージの中にある今のモジュールを探し直し、依存する側が後になる順で読み直す。

    - 新しく増えたモジュールは読み込む。
    - ファイルが消えたモジュールは、sys.modulesと、親のモジュールの同じ名前の属性から取り除く。
    - 読み直す順は、globalsにあるモジュール・クラス・関数の参照から推し量る。
      関数の中で後から行うimportは見つけられない。

    使う側がfrom-importで取り込んだ名前や、手元に持っているインスタンスは差し替えない。
    読み直した後は、必要な参照を取り直す。
    モジュールの辞書に残っている、消された定義までまとめて消すわけではない。途中で失敗しても、自動では元に戻さない。

    Args:
        package_name (str): 読み込み済みのパッケージの完全な名前(``mlib`` など)。

    Returns:
        tuple[module]: 読み直したモジュール。処理した順に並ぶ。
    """
    ...

def _discover_module_names(package_name: str) -> tuple[str]:
    """パッケージの中に今あるモジュールの名前を取得する。

    Args:
        package_name (str): モジュールを探すパッケージの完全な名前。

    Returns:
        tuple[str]: 見つかったモジュールの名前。パッケージ自身も含む。
    """
    ...

def _reload_order(module_names: Iterable[str]) -> list[str]:
    """読み直す順番を決める。

    モジュールの中の参照から、どのモジュールに依存しているかを推し量る。

    Args:
        module_names (iterable[str]): 読み直すモジュールの完全な名前。

    Returns:
        list[str]: 読み直す順に並べたモジュール名。依存されている側が先になる。
    """
    ...

def _module_dependencies(module: types.ModuleType, module_names: set[str]) -> set[str]:
    """モジュールが依存しているmlibのモジュール名を取り出す。

    モジュールの globals を調べる。import の循環を避けるため関数の中で import している参照
    (例: nodes.node と plugs.plug がお互いを参照する場合)は globals に出てこないので、
    ここでは見つけられない。これらは読み直す順番に関係しない。実行時には、呼ぶたびにその時点の
    sys.modules から取り出すので、読み直し忘れにはならない。

    Args:
        module (types.ModuleType): 依存を調べるモジュール。
        module_names (set[str]): 読み直す対象として扱うモジュール名。

    Returns:
        set[str]: モジュールが参照しているmlibのモジュール名。
    """
    ...
