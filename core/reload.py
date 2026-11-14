"""パッケージの中のモジュールを、参照の関係に合わせた順で読み直す。"""

import importlib
import pkgutil
import sys
import types

__all__ = ["reload_package"]


def reload_package(package_name):
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
    # 新しいファイルが見つかるように、importの仕組みへ知らせる。各モジュールが持つ
    # キャッシュはreloadのときにそれぞれ作り直すので、ここではキャッシュの一覧を持たない。
    importlib.invalidate_caches()
    module_names = _discover_module_names(package_name)
    loaded_names = {name for name in sys.modules if name == package_name or name.startswith(f"{package_name}.")}
    for stale_name in loaded_names - set(module_names):
        stale_module = sys.modules.pop(stale_name, None)
        parent_name, _, child_name = stale_name.rpartition(".")
        parent = sys.modules.get(parent_name)
        if isinstance(stale_module, types.ModuleType) and parent is not None and getattr(parent, child_name, None) is stale_module:
            delattr(parent, child_name)
    for module_name in module_names:
        importlib.import_module(module_name)
    module_names = _reload_order(module_names)
    reloaded = []
    for module_name in module_names:
        module = sys.modules.get(module_name)
        if module is None:
            continue
        reloaded.append(importlib.reload(module))

    return tuple(reloaded)


def _discover_module_names(package_name):
    """パッケージの中に今あるモジュールの名前を取得する。

    Args:
        package_name (str): モジュールを探すパッケージの完全な名前。

    Returns:
        tuple[str]: 見つかったモジュールの名前。パッケージ自身も含む。
    """
    package = sys.modules[package_name]
    names = {package_name}
    for module_info in pkgutil.walk_packages(package.__path__, f"{package_name}."):
        names.add(module_info.name)
    return tuple(sorted(names))


def _reload_order(module_names):
    """読み直す順番を決める。

    モジュールの中の参照から、どのモジュールに依存しているかを推し量る。

    Args:
        module_names (iterable[str]): 読み直すモジュールの完全な名前。

    Returns:
        list[str]: 読み直す順に並べたモジュール名。依存されている側が先になる。
    """
    module_set = set(module_names)
    dependencies = {name: _module_dependencies(sys.modules[name], module_set) for name in module_names}
    order = []
    visited = set()
    visiting = set()

    def visit(name):
        """依存しているモジュールから順にたどり、読み直す順番を組み立てる。

        すでにたどった、または今たどっている途中のモジュールなら、そこで止める。
        こうして、お互いに依存しているときに終わらなくなるのを防ぐ。

        Args:
            name (str): 訪問するモジュールの完全修飾名。

        Returns:
            None: 値を返さない。
        """
        if name in visited:
            return
        if name in visiting:
            return
        visiting.add(name)
        for dependency in sorted(dependencies[name]):
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        order.append(name)

    for name in sorted(module_names):
        visit(name)
    return order


def _module_dependencies(module, module_names):
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
    dependencies = set()
    for value in vars(module).values():
        if isinstance(value, types.ModuleType):
            owner = value.__name__
        else:
            owner = getattr(value, "__module__", None)
        if owner in module_names and owner != module.__name__:
            dependencies.add(owner)
            # `from ..maths import Matrix` のようにパッケージ経由で取り込んだ名前は、
            # 定義 module だけでなくその親パッケージ(__init__)も先に読み直す必要がある。
            assert isinstance(owner, str)  # module_names は文字列の集まり。
            package = owner.rpartition(".")[0]
            while package and package in module_names:
                if package != module.__name__ and not module.__name__.startswith(package + "."):
                    dependencies.add(package)
                package = package.rpartition(".")[0]
    return dependencies
