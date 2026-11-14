# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaの型名とクラスの対応を管理する。登録されていない型には、クラスを自動で作る。"""

import weakref
import maya.cmds as cmds
from typing import Any, Mapping

__all__ = ['NodeRegistry']
_INHERITED_TYPES_CACHE: dict
_GENERATING_REGISTRIES: Any
_RENAMED_NODE_TYPES: dict
_NODE_TYPE_ALIASES: dict
_REAL_TYPE_CACHE: dict
_NODE_TYPES_SINCE: Any

def _inherited_node_types(node_type: str) -> tuple[str, ...]:
    """ノードタイプの継承チェーンを取得する。

    ``cmds.nodeType(node_type, isTypeName=True, inherited=True)`` を使う。
    これはノードが無くても、型名だけで継承を調べられる。
    ただし毎回 Maya に問い合わせると少し遅いので、Maya が認識した型名だけ結果を保存しておく。
    知らない型名は、後からプラグインで追加されるかもしれないので、結果を保存しない。
    Maya API 2.0 には同じことを調べる方法が無いため、cmds を使う。

    Args:
        node_type (str): Maya の nodeType 名。

    Returns:
        tuple[str, ...]: 継承チェーン。node_type 自身が先頭で、直接の親から基底の型へ向かって並ぶ。
            Maya が認識しない型名なら、node_type 自身だけの1要素の tuple。
    """
    ...

def _node_type_exists(node_type: str) -> bool:
    """Mayaが型名として認識するnodeTypeかを判定する。

    :func:`_inherited_node_types` と同じ問い合わせと保存を使う。保存するのは認識できた型だけにする。
    知らない型名は、後からプラグインで追加されるかもしれないので、毎回問い合わせる。
    ``om2.MNodeClass(知らない型)`` は例外にならず、typeId 0 を返すだけ。そのため、型があるかどうかの判定は
    この cmds の問い合わせだけで行う。

    Args:
        node_type (str): Maya の nodeType 名。

    Returns:
        bool: ``cmds.nodeType(node_type, isTypeName=True)`` が型名として認識すれば True。
    """
    ...

def _real_node_type(node_type: object) -> Any:
    """版によって違うノード型名を、このMayaが認識する名前へ読み替える。

    2026で名前が変わった ``multDoubleLinear``/``multDL``・``addDoubleLinear``/``addDL`` が対象。
    どの版でも、その版の名前へ読み替える。
    それ以外の名前と、どちらの名前も認識できない場合は、そのまま返す。

    Args:
        node_type (object): ノード型名。文字列以外はそのまま返す。

    Returns:
        object: この版の型名、または入力の値。
    """
    ...

def _real_node_types(value: object) -> Any:
    """``ls(type=...)`` などで指定した型名を、この版の名前へ読み替える。

    型名は文字列1つか、文字列の並びで受け付ける。

    Args:
        value (object): 型名、型名の並び、またはそれ以外の値。

    Returns:
        object: 読み替えた値。並びはlistにする。それ以外の値はそのまま返す。
    """
    ...

def _unknown_node_type_message(node_type: str) -> str:
    """作成できないノード型名の例外メッセージを作る。

    Args:
        node_type (str): Mayaが認識しないノード型名。

    Returns:
        str: 例外メッセージ。Maya標準に加わった版が分かっている型なら、その版を案内する。
    """
    ...

def _clear_type_hierarchy_cache() -> None:
    """型の継承の保存内容と、自動で作ったクラスを消す。

    クラスを自動で作るすべての登録表が対象。プラグインのロード・アンロードの後に呼ぶ。
    次に型を選ぶときに継承を調べ直し、クラスを作り直す。
    消す前に持っていた自動のクラスでは、これ以降のオブジェクトに対して ``isinstance`` がFalseになる。

    Returns:
        None: 値を返さない。
    """
    ...

def _generated_class_name(node_type: str) -> str:
    """Maya の nodeType 名から、自動で作るクラスの名前を決める。

    先頭の1文字を大文字にする(``pointLight`` → ``PointLight``)。
    先頭がもともと大文字の型名(``AISEnvFacade`` など)は、そのまま使う。

    Args:
        node_type (str): Maya の nodeType 名。

    Returns:
        str: 自動で作るクラスの名前。
    """
    ...


class NodeRegistry:
    """ノード型・アトリビュート型などの名前と、クラスを対応づける登録表。

    ``generate_classes=True`` の表は、Maya が認識するが登録されていない nodeType に対して、
    クラスを自動で作って返す。自動で作るクラスの親は、Maya の継承チェーン
    (``cmds.nodeType(inherited=True)``)の上で最も近い登録済みのクラスになる。

    登録済みのクラスと、作る対象の間にある抽象型(weightGeometryFilter・containerBase・
    entity など)のクラスは作らない。そのため、自動で作ったクラスどうしの ``isinstance`` は
    Maya の継承を表さない。継承を判定するときは ``Node.isType()`` を使う。
    """
    def __init__(self, fallback_class: type, resolve_inherited_types: bool = ..., generate_classes: bool = ...) -> None:
        """登録表を作る。最初は何も登録されていない。

        Args:
            fallback_class (type): 登録されていない名前に使うクラス。Maya が認識しない
                型名では、クラスを自動で作らずにこのクラスを返す。
            resolve_inherited_types (bool): ``True`` なら、そのままの名前で登録が無いとき、
                Maya のノードタイプの継承チェーンをたどり、最も近い登録済みの祖先の型のクラスを返す
                (Plug のアトリビュート型のように、Mayaのノードタイプの継承と関係ない名前の表では使わない)。
                ``generate_classes=True`` では、この設定に関わらず継承チェーンを使う。
            generate_classes (bool): ``True`` なら、そのままの名前で登録が無く Maya が認識する型に
                対して、クラスを自動で作って保存する。親は最も近い登録済みの祖先の型
                (無ければ fallback_class)。祖先の型のクラスをそのまま返すことはしない。

        Returns:
            None: 値を返さない。
        """
        ...
    def register(self, node_type: str, wrapper_class: type) -> None:
        """名前にクラスを登録する。同じ名前がすでにあれば上書きする。

        NodeのnodeTypeとPlugのアトリビュート型の両方で使う。
        名前が空でないstrで、値がクラスであることを確かめる。
        自動で作ったクラスは、親の候補が変わるので、すべて捨てる。

        Args:
            node_type (str): 登録する名前。空にはできない。
            wrapper_class (type): 対応するクラス。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: キーが文字列以外、またはwrapper_classがクラス以外の場合。
            ValueError: キーが空文字列の場合。
        """
        ...
    def clear(self):
        """この表の登録と、自動で作ったクラスを空にする。fallback_classと継承をたどる設定はそのまま。"""
        ...
    def replace(self, wrappers: Mapping[str, type]) -> None:
        """この表の登録をまるごと置き換える。

        置き換える前に、すべての名前が空でないstrで、値がクラスであることを確かめる。
        確かめるのはこの形だけ。確認で失敗したら、今の登録と自動で作ったクラスはそのまま残す。

        Args:
            wrappers (Mapping[str, type]): 登録する名前とクラスの対応。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: キーが文字列以外、または値がクラス以外の場合。
            ValueError: キーが空文字列の場合。
        """
        ...
    def wrapper_class(self, node_type: str) -> type:
        """名前に対応するクラスを返す。

        登録が無ければ、設定に従って、自動で作ったクラス・祖先の型のクラス・fallback_classのどれかを使う。
        探す順番は次のとおり。

        1. そのままの名前の登録
        2. すでに自動で作ったクラス
        3. クラスを自動で作る(generate_classes=True)
        4. 最も近い登録済みの祖先の型(resolve_inherited_types=True)
        5. fallback_class

        Maya が認識しない型名ではクラスを作らず、fallback_classを返す(知らない型名は、後からプラグインで
        追加されるかもしれないので、見つからなかった結果は保存しない)。

        Args:
            node_type (str): 登録した名前。継承をたどる表やクラスを自動で作る表では、MayaのnodeType名。

        Returns:
            type: 名前どおりの登録、自動で作ったクラス、最も近い登録済みの祖先の型、またはfallback_classのクラス。
        """
        ...
    def lookup(self, key: str | None) -> type | None:
        """登録したクラスを返す。登録が無ければ ``None``。

        fallback_classを使わず、「その名前そのままの登録があるか」だけを知りたいときに使う
        (例: Plug のアトリビュート型で処理を振り分けるとき)。自動で作ったクラスは登録ではないので返さない。

        Args:
            key (str | None): 登録した名前(nodeType やアトリビュート型など)。None は登録が無いものとして扱う。

        Returns:
            type | None: 登録済みクラス。
        """
        ...
    def _generate_class(self, node_type: str) -> type:
        """登録されていない型のクラスを自動で作る。

        Maya が認識する型が対象。作ったクラスは保存してから返す。
        親は、継承チェーンの上で最も近い登録済みのクラスにする。チェーンに登録が無ければ
        fallback_classを親にする。間にある抽象型のクラスは作らない。

        Args:
            node_type (str): Maya が認識する nodeType 名。

        Returns:
            type: 作ったクラス。``_generated_node_type`` に型名、``_generated`` に True を持つ。
        """
        ...
    def _invalidate_generated(self) -> None:
        """自動で作ったクラスの保存先を空にする。次に必要になったときに作り直す。

        Returns:
            None: 値を返さない。
        """
        ...
    def _registered_types(self, base: type | None = ...) -> list[str]:
        """登録した型名を返す。自動で作ったクラスの型名は含まない。

        Args:
            base (type | None): 指定すると、このクラスか、その派生クラスが登録された
                型名だけを返す。

        Returns:
            list[str]: 登録した名前。名前順に並ぶ。
        """
        ...
    @staticmethod
    def _require_entry(node_type: str, wrapper_class: type) -> None:
        """登録する型名とクラスを確かめる。すでにある名前の上書きは止めない。

        Args:
            node_type (str): 登録する型名。
            wrapper_class (type): 対応するクラス。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 型名が文字列以外、またはwrapper_classがクラスではない場合。
            ValueError: 型名が空文字列の場合。
        """
        ...
    def _snapshot(self) -> dict[str, type]:
        """今の登録をコピーして返す。

        拡張の登録を始める前に呼ぶ。

        Returns:
            dict[str, type]: この登録表だけが、元に戻すときに使う内部の状態。
        """
        ...
    def _restore(self, snapshot: dict[str, type]) -> None:
        """登録を、保存しておいた状態へ戻す。

        登録の途中で失敗したときに使う。保存した内容は確かめてあるので、登録し直さずにそのまま戻す。
        自動で作ったクラスは捨てる。

        Args:
            snapshot (dict[str, type]): _snapshotで取得した内部の状態。

        Returns:
            None: 値を返さない。
        """
        ...
