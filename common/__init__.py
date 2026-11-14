"""Mayaの状態・環境・イベントと、共通の処理をまとめる。

公開する名前は、使われたときに読み込む。こうすることで、Node/Plugの初期化中に
選択関連のクラスを先にimportせずに済み、読み込み直したあとも現在のモジュールから取得できる。
"""

from importlib import import_module
from typing import TYPE_CHECKING

# reload前に保持された公開値を、新しい公開一覧の構築前に解除する。
for _name in globals().get("__all__", ()):
    globals().pop(_name, None)

_exports = {
    "Callbacks": ("callbacks", "Callbacks"),
    "CurveFit": ("curveFit", "CurveFit"),
    "DampedSpring": ("dampedSpring", "DampedSpring"),
    "Deferred": ("deferred", "Deferred"),
    "DrivenKey": ("drivenKey", "DrivenKey"),
    "Environment": ("environment", "Environment"),
    "Keyframe": ("keyframe", "Keyframe"),
    "Keyframes": ("keyframe", "Keyframes"),
    "LOAD_FAILED": ("pluginPackage", "LOAD_FAILED"),
    "LOADED": ("pluginPackage", "LOADED"),
    "MISSING": ("pluginPackage", "MISSING"),
    "Module": ("module", "Module"),
    "Namespace": ("namespace", "Namespace"),
    "OUTDATED": ("pluginPackage", "OUTDATED"),
    "Plugin": ("plugin", "Plugin"),
    "PluginPackage": ("pluginPackage", "PluginPackage"),
    "ProgressCancelled": ("progress", "ProgressCancelled"),
    "SKIPPED": ("pluginPackage", "SKIPPED"),
    "ScalarGraph": ("scalarGraph", "ScalarGraph"),
    "ScriptJob": ("scriptJob", "ScriptJob"),
    "ScriptJobs": ("scriptJobs", "ScriptJobs"),
    "Selection": ("selection", "Selection"),
    "Time": ("sceneTime", "Time"),
    "Version": ("version", "Version"),
    "progressBar": ("progress", "progressBar"),
    "units": ("units", None),
}

__all__ = sorted(_exports)

# reload前に保持された公開値や廃止名を残さず、常に定義元から解決する。
for _name in __all__ + ["legalizeName", "legalize_name", "progress_bar"]:
    globals().pop(_name, None)

if TYPE_CHECKING:
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


def __getattr__(name):
    """公開する名前を、それを定義している現在のモジュールから取得する。

    Args:
        name (str): 取得する公開名。

    Returns:
        object: クラス・関数・定数またはモジュール。

    Raises:
        AttributeError: 公開していない名前の場合。
    """
    if name not in _exports:
        raise AttributeError(f"モジュール{__name__!r}にアトリビュート{name!r}はありません")
    module_name, attribute_name = _exports[name]
    module = import_module("." + module_name, __name__)
    return module if attribute_name is None else getattr(module, attribute_name)


def __dir__():
    """モジュール内の名前と、使われたときに読み込む公開名を列挙する。

    Returns:
        list[str]: 補完や探索に使う名前の一覧。
    """
    return sorted(set(globals()) | set(__all__))
