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

__all__ = ["getDiagnostics", "status"]

# importlib.reloadで廃止した登録デコレーターを残さない。
for _name in ("node_wrapper", "plug_wrapper", "discover_node_package", "discover_plug_package"):
    globals().pop(_name, None)

_states = {}
_loading = False
_diagnosing = False
_package_name = (__package__ or "").rpartition(".")[0]
_extension_pattern = re.compile(re.escape(_package_name) + r"_[a-z][a-z0-9_]*")
# 親のimportに失敗すると子だけsys.modulesに残るため、試行した名前も保持する。
# extensions自体のreloadでも、次の一括解除まで追跡を失わない。
_attempted = globals().get("_attempted", set())


def status():
    """最後に初期化したときの、拡張ごとの状態と理由を返す。

    依存するものが今使えるかは、調べ直さない。調べ直すときはgetDiagnosticsを使う。

    Returns:
        dict: 拡張の名前ごとの状態と理由。コピーを返す。
    """
    return {name: dict(state) for name, state in _states.items()}


def getDiagnostics():
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
    global _diagnosing
    modules = {name: module for name, module in list(sys.modules.items()) if _extension_pattern.fullmatch(name)}
    names = set(_states) | set(modules)
    result = {}
    reentered = _diagnosing
    if not reentered:
        _diagnosing = True
    try:
        for name in sorted(names):
            initialization = _states.get(name)
            record = {"initialization": dict(initialization) if initialization is not None else None, "available": None, "reason": ""}
            result[name] = record
            module = modules.get(name)
            if module is None:
                record["reason"] = "拡張の宣言がimportされていません"
            elif _loading or getattr(getattr(module, "__spec__", None), "_initializing", False):
                record["reason"] = "拡張を初期化しています"
            elif reentered:
                record["reason"] = "利用できるかどうかを問い合わせています"
            elif vars(module).get("MLIB_EXTENSION_API") != 1:
                record["reason"] = "MLIB_EXTENSION_API != 1"
            else:
                try:
                    available = _is_available(module)
                    record["available"] = available
                    if not available:
                        record["reason"] = "任意の依存が利用できません"
                except Exception as exc:
                    record["reason"] = str(exc) or type(exc).__name__
    finally:
        if not reentered:
            _diagnosing = False
    return result


def _prepare_reload():
    """mlib本体を読み込み直す前に、拡張をまとめて解除する。

    拡張として宣言しているものと、読み込みに失敗したものを解除する。外部のSDKやMayaプラグインは対象外。
    利用側が持っているPythonのオブジェクトは、利用側で取得し直す。
    初期化の途中で呼ばれた場合は、モジュールを1つも削除せずに例外にする。
    """
    roots = {name for name, module in list(sys.modules.items()) if _extension_pattern.fullmatch(name) and getattr(module, "MLIB_EXTENSION_API", None) == 1}
    roots.update(_attempted)
    if _loading or any(getattr(getattr(sys.modules.get(name), "__spec__", None), "_initializing", False) for name in roots):
        raise RuntimeError(f"拡張の初期化中は{_package_name}をリロードできません")
    for name in list(sys.modules):
        if name.split(".", 1)[0] in roots:
            del sys.modules[name]
    _attempted.clear()


def _is_available(package):
    """拡張のis_available()を呼んで、今使えるかを調べる。

    初期化と診断で、同じように戻り値の型を確かめるために使う。

    Args:
        package (ModuleType): 宣言を読み終えた拡張のパッケージ。

    Returns:
        bool: 拡張が今使えるならTrue。

    Raises:
        TypeError: is_availableが呼び出せない場合、またはboolを返さない場合。
    """
    query = vars(package).get("is_available")
    if not callable(query):
        raise TypeError("is_availableは呼び出せるオブジェクトにしてください")
    available = query()
    if not isinstance(available, bool):
        raise TypeError("is_available()はboolを返してください")
    return available


def _require_dependencies(name, locations):
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
    for location in locations:
        root = Path(location) / name
        for path in root.rglob("*.py"):
            if any(part in {"__tests__", "tests", "docs", "_docs", "__pycache__"} for part in path.relative_to(root).parts[:-1]):
                continue
            with tokenize.open(str(path)) as stream:
                tree = ast.parse(stream.read(), filename=str(path))
            for node in ast.walk(tree):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    imports = [node.module or ""]
                for target in imports:
                    package = target.split(".", 1)[0]
                    if package != name and _extension_pattern.fullmatch(package):
                        raise ValueError(f"拡張どうしは依存できません: {name} -> {package}")


def _find_candidates():
    """拡張ごとに、実際に置いてある場所を集める。

    探索パスの重なりは除く。importはしない。

    Returns:
        dict[str, set[str]]: 拡張の名前と、置いてある場所(形を整えたパス)。
    """
    candidates = {}
    for path in dict.fromkeys(sys.path):
        if not _may_contain_candidate(path):
            continue
        for info in pkgutil.iter_modules([path]):
            if info.ispkg and _extension_pattern.fullmatch(info.name):
                location = os.path.normcase(os.path.realpath(path))
                candidates.setdefault(info.name, set()).add(location)
    return candidates


def _may_contain_candidate(path):
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
    importer = pkgutil.get_importer(path)
    if not isinstance(importer, importlib.machinery.FileFinder):
        return True
    if importer.path is None:
        return False
    try:
        # フォルダーでない・読めない場合はOSError(NotADirectoryError等)になるため、事前の判定は要らない。
        return any(_extension_pattern.fullmatch(entry.name) for entry in Path(importer.path).iterdir())
    except OSError:
        return False


def _load_candidate(name, locations):
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
    if len(locations) != 1:
        raise ValueError(f"拡張パッケージが重複しています: {name}")
    previous = sys.modules.get(name)
    if getattr(getattr(previous, "__spec__", None), "_initializing", False):
        raise RuntimeError(f"拡張の__init__で{_package_name}やラッパーをimportしないでください。サブモジュールを読み込む前に宣言を終えてください")
    _attempted.add(name)
    package = importlib.import_module(name)
    if getattr(package, "MLIB_EXTENSION_API", None) != 1:
        _attempted.discard(name)
        return {"state": "skipped", "reason": "MLIB_EXTENSION_API != 1"}
    available = _is_available(package)
    if not available:
        return {"state": "unavailable", "reason": "任意の依存が利用できません"}
    return None


def _validated_entries(name, bases):
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
    entries = []
    for suffix, base in bases:
        if importlib.util.find_spec(f"{name}.{suffix}") is None:
            continue
        namespace = importlib.import_module(f"{name}.{suffix}")
        # 公開名は拡張の__init__で定義する。ここでは型対応だけを検証する。
        declared = getattr(namespace, "_WRAPPER_CLASSES", {})
        if not isinstance(declared, Mapping):
            raise TypeError("_WRAPPER_CLASSESはマッピングにしてください")
        wrappers = dict(declared)
        for key, cls in wrappers.items():
            if not isinstance(key, str):
                raise TypeError("ラッパーの型名はstrで指定してください")
            if not key:
                raise ValueError("ラッパーの型名は空でない文字列で指定してください")
            if not isinstance(cls, type) or not issubclass(cls, base):
                raise TypeError(f"ラッパーの基底クラスが不正です: {key}")
            if any(
                _extension_pattern.fullmatch(base_cls.__module__.split(".", 1)[0]) and base_cls.__module__.split(".", 1)[0] != name for base_cls in cls.__mro__
            ):
                raise TypeError("拡張のラッパーは、ほかの拡張のクラスを継承できません")
            if base._registry.lookup(key) is not None:
                raise ValueError(f"ラッパーの型名が重複しています: {key}")
        entries.append((base._registry, wrappers))
    return entries


def _apply_entries(entries):
    """確かめてある型とクラスの対応を、すべての登録表へ登録する。

    途中で失敗した場合は、すべての登録表を元に戻す。

    Args:
        entries (list[tuple[NodeRegistry, dict[str, type]]]): 登録する型とクラスの対応。

    Returns:
        None: 値を返さない。

    Raises:
        Exception: 登録中に出た例外。登録表を元に戻してから、そのまま送出し直す。
    """
    snapshots = [(registry, registry._snapshot()) for registry, _ in entries]
    try:
        for registry, wrappers in entries:
            for key, cls in wrappers.items():
                registry.register(key, cls)
    except Exception:
        for registry, snapshot in snapshots:
            registry._restore(snapshot)
        raise


def _initialize():
    """mlib標準の登録が終わった後に、拡張を見つけて、拡張ごとに確かめて登録する。"""
    global _loading, _states
    if _loading:
        return
    # 循環参照の回避: nodes は core を参照するため、使う時点で読み込む。
    from ..nodes import Node
    from ..plugs import Plug

    _loading = True
    _states = {}
    try:
        for name, locations in sorted(_find_candidates().items()):
            try:
                state = _load_candidate(name, locations)
                if state is None:
                    _require_dependencies(name, locations)
                    entries = _validated_entries(name, (("nodes", Node), ("plugs", Plug)))
                    _apply_entries(entries)
                    state = {"state": "loaded", "reason": ""}
                _states[name] = state
            except Exception as exc:
                _states[name] = {"state": "error", "reason": str(exc)}
                logger.warning("%sの拡張%s: %s", _package_name, name, exc)
    finally:
        _loading = False
