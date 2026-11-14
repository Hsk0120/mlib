# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaの状態・環境・イベントと、共通の処理をまとめる。

公開する名前は、使われたときに読み込む。こうすることで、Node/Plugの初期化中に
選択関連のクラスを先にimportせずに済み、読み込み直したあとも現在のモジュールから取得できる。
"""

from importlib import import_module
from typing import TYPE_CHECKING
from . import units
from .callbacks import Callbacks
from .curveFit import CurveFit
from .dampedSpring import DampedSpring
from .deferred import Deferred
from .drivenKey import DrivenKey
from .environment import Environment
from .keyframe import Keyframe, Keyframes
from .module import Module
from .namespace import Namespace
from .plugin import Plugin
from .pluginPackage import LOAD_FAILED, LOADED, MISSING, OUTDATED, SKIPPED, PluginPackage
from .scalarGraph import ScalarGraph
from .sceneTime import Time
from .scriptJob import ScriptJob
from .scriptJobs import ScriptJobs
from .selection import Selection
from .version import Version
from .progress import ProgressCancelled, progressBar
from typing import Any

_exports: dict
__all__ = ['Callbacks', 'CurveFit', 'DampedSpring', 'Deferred', 'DrivenKey', 'Environment', 'Keyframe', 'Keyframes', 'LOADED', 'LOAD_FAILED', 'MISSING', 'Module', 'Namespace', 'OUTDATED', 'Plugin', 'PluginPackage', 'ProgressCancelled', 'SKIPPED', 'ScalarGraph', 'ScriptJob', 'ScriptJobs', 'Selection', 'Time', 'Version', 'progressBar', 'units']

def __getattr__(name: str) -> Any:
    """公開する名前を、それを定義している現在のモジュールから取得する。

    Args:
        name (str): 取得する公開名。

    Returns:
        object: クラス・関数・定数またはモジュール。

    Raises:
        AttributeError: 公開していない名前の場合。
    """
    ...

def __dir__() -> list[str]:
    """モジュール内の名前と、使われたときに読み込む公開名を列挙する。

    Returns:
        list[str]: 補完や探索に使う名前の一覧。
    """
    ...
