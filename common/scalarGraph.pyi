# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya標準のノードで、スカラー(1つの数値)の計算を組み立てる。"""

import re
from typing import Any, Callable, Optional
from ..decorator import _edit_context, _require_bool
from ..nodes.container import Container
from ..plugs.plug import Plug
from ..util import _finite
from typing import Any
from mlib.nodes.node import Node
import contextlib

_NAME_CHARACTER: Any


class ScalarGraph:
    """定数とPlugを組み合わせて、単位の無い数値の計算ノードを組み立てる。

    - 通常は、組み立てるメソッドごとに1つのUndoチャンクにまとめ、例外が起きたら元に戻そうとする。
    - ``fast=True`` なら、ノードを作る関数へ ``fast=True`` を渡して作り、値の設定と接続をOpenMayaで
      直接行う(Undoなし。途中で失敗しても元に戻さない)。
    - containerを持ち主にした場合、Container.createNodeにはfastが無い。そのため、fast=Trueは
      何も変更する前にNotImplementedErrorにする。
    """
    container: Optional[Container]
    def __init__(self, container: str | Container | None = ..., *, createNode: Callable | None = ...) -> None:
        """containerか、ノードを作る関数か、どちらか一方を持つ。

        Args:
            container (str | Container | None): 計算ノードの持ち主にするcontainer。既定はNone。
            createNode (Callable | None): ノードを作る関数。(node_type, name=...)を受け取り、Nodeを返すもの。
                組み立てるメソッドへfast=Trueを渡す場合は、キーワード ``fast=True`` も受け取れる必要がある
                (例: ``mlib.createNode``)。既定はNone。

        Raises:
            TypeError: createNodeが呼び出せない値の場合。
            ValueError: containerとcreateNodeを両方指定した場合、またはどちらも指定しない場合。
            RuntimeError: containerの名前のノードが見つからない場合、またはノードが無効な場合。
        """
        ...
    def sum(self, role: str, left: float | str | Plug, right: float | str | Plug, *, subtract: bool = ..., fast: bool = ...) -> Plug:
        """足し算・引き算のノードを組み立てる。

        Args:
            role (str): 計算の名前。
            left (float | str | Plug): 左辺。
            right (float | str | Plug): 右辺。
            subtract (bool): Trueなら引き算にする。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Plug: 出力のプラグ。ノードの名前が変わっても同じアトリビュートを指す。

        Raises:
            TypeError: roleが文字列でない場合、入力が数値・アトリビュート名・Plugのどれでもない(boolを含む)場合、subtractがboolでない場合、
                またはfastがboolでない場合。
            ValueError: roleに名前に使える文字(英数字と ``_``)が無い場合、入力の数値が有限でない場合、
                または入力のアトリビュート名が空の場合。
            MissingAttributeError: 入力のアトリビュート(またはノード)が無い場合(``AttributeError`` の派生)。
            RuntimeError: 入力のPlugが削除されている場合、または入力の名前が複数のものに一致する場合。
            NotImplementedError: containerを持ち主にして、fast=Trueを指定した場合。
        """
        ...
    def multiply(self, role: str, left: float | str | Plug, right: float | str | Plug, *, operation: int = ..., fast: bool = ...) -> Plug:
        """掛け算・割り算・累乗のノードを組み立てる。

        Args:
            role (str): 計算の名前。
            left (float | str | Plug): 左辺。
            right (float | str | Plug): 右辺。
            operation (int): 1は掛け算、2は割り算、3は累乗。既定は1。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Plug: 出力のプラグ。ノードの名前が変わっても同じアトリビュートを指す。

        Raises:
            TypeError: roleが文字列でない場合、入力が数値・アトリビュート名・Plugのどれでもない(boolを含む)場合、operationがintでない(boolを含む)場合、
                またはfastがboolでない場合。
            ValueError: roleに名前に使える文字(英数字と ``_``)が無い場合、入力の数値が有限でない場合、
                入力のアトリビュート名が空の場合、またはoperationが1〜3でない場合。
            MissingAttributeError: 入力のアトリビュート(またはノード)が無い場合(``AttributeError`` の派生)。
            RuntimeError: 入力のPlugが削除されている場合、または入力の名前が複数のものに一致する場合。
            NotImplementedError: containerを持ち主にして、fast=Trueを指定した場合。
        """
        ...
    def condition(self, role: str, left: float | str | Plug, right: float | str | Plug, yes: float | str | Plug, no: float | str | Plug, *, fast: bool = ...) -> Plug:
        """大きさを比べて、値を選ぶノードを組み立てる。

        Args:
            role (str): 計算の名前。
            left (float | str | Plug): 比較の左辺。
            right (float | str | Plug): 比較の右辺。
            yes (float | str | Plug): 左辺が右辺より大きい場合の値。
            no (float | str | Plug): それ以外の場合の値。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Plug: 出力のプラグ。ノードの名前が変わっても同じアトリビュートを指す。

        Raises:
            TypeError: roleが文字列でない場合、入力が数値・アトリビュート名・Plugのどれでもない(boolを含む)場合、またはfastがboolでない場合。
            ValueError: roleに名前に使える文字(英数字と ``_``)が無い場合、入力の数値が有限でない場合、
                または入力のアトリビュート名が空の場合。
            MissingAttributeError: 入力のアトリビュート(またはノード)が無い場合(``AttributeError`` の派生)。
            RuntimeError: 入力のPlugが削除されている場合、または入力の名前が複数のものに一致する場合。
            NotImplementedError: containerを持ち主にして、fast=Trueを指定した場合。
        """
        ...
    def _edit(self, name: str, fast: bool) -> contextlib.AbstractContextManager:
        """fastを確かめ、組み立て全体のUndoの範囲を返す。

        Args:
            name (str): 通常の処理で使うUndoチャンク名。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            contextlib.AbstractContextManager: 通常はundoTransaction、fastならnullcontext。

        Raises:
            TypeError: fastがboolでない場合。
            NotImplementedError: containerを持ち主にして、fast=Trueを指定した場合。
        """
        ...
    def _node(self, kind: str, role: str, fast: bool = ...) -> Node:
        """設定した作り方で、計算ノードを作る。

        Args:
            kind (str): Maya標準のノード型。
            role (str): 計算を見分ける名前。
            fast (bool): Trueなら、ノードを作る関数へ ``fast=True`` を渡す。Falseなら、これまでどおり渡さない。

        Returns:
            Node: 作成したノード。
        """
        ...
    @staticmethod
    def _feed(value: float | str | Plug, destination: Plug | str, fast: bool = ...) -> None:
        """入力に定数を設定するか、プラグを接続する。

        Args:
            value (float | str | Plug): 定数、または入力にするプラグ(名前でもよい)。
            destination (Plug | str): 接続先のアトリビュート。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。
        """
        ...

def _require_role(role: str):
    """計算の名前を確かめる。

    Args:
        role (str): 計算の名前。

    Raises:
        TypeError: 文字列でない場合。
        ValueError: 名前に使える文字(英数字と ``_``)が1つも無い場合。
    """
    ...

def _operand(value: float | str | Plug, name: str) -> float | Plug:
    """計算の入力を、定数のfloatか、有効なPlugにする。

    Args:
        value (float | str | Plug): 定数、アトリビュート名、またはPlug。
        name (str): 例外メッセージに使う引数名。

    Returns:
        float | Plug: 定数か、入力にするPlug。

    Raises:
        TypeError: 数値・アトリビュート名・Plugのどれでもない場合(boolを含む)。
        ValueError: 数値が有限でない、またはアトリビュート名が空の場合。
        MissingAttributeError: アトリビュート(またはノード)が無い場合。
        RuntimeError: Plugが削除されている、または名前が複数のものに一致する場合。
    """
    ...
