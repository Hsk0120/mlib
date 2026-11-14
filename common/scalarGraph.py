"""Maya標準のノードで、スカラー(1つの数値)の計算を組み立てる。"""

from typing import Any, Callable, Optional

from ..decorator import _edit_context
from ..nodes.container import Container
from ..plugs.plug import Plug


class ScalarGraph:
    """定数とPlugを組み合わせて、単位の無い数値の計算ノードを組み立てる。

    - 通常は、組み立てるメソッドごとに1つのUndoチャンクにまとめ、例外が起きたら元に戻そうとする。
    - ``fast=True`` なら、ノードを作る関数へ ``fast=True`` を渡して作り、値の設定と接続をOpenMayaで
      直接行う(Undoなし。途中で失敗しても元に戻さない)。
    - containerを持ち主にした場合、Container.createNodeにはfastが無い。そのため、fast=Trueは
      何も変更する前にNotImplementedErrorにする。
    """

    # __init__で設定する所有先と生成関数。
    container: Optional[Container]
    _createNode: Callable[..., Any]

    def __init__(self, container=None, *, createNode=None):
        """containerか、ノードを作る関数か、どちらか一方を持つ。

        Args:
            container (str | Container | None): 計算ノードの持ち主にするcontainer。
            createNode (Callable | None): ノードを作る関数。(node_type, name=...)を受け取り、Nodeを返すもの。
                組み立てるメソッドへfast=Trueを渡す場合は、キーワード ``fast=True`` も受け取れる必要がある
                (例: ``mlib.createNode``)。

        Raises:
            TypeError: createNodeが呼び出せない値の場合。
            ValueError: containerとcreateNodeを両方指定した場合、またはどちらも指定しない場合。
        """
        if (container is None) == (createNode is None):
            raise ValueError("'container'と'createNode'のどちらか1つだけを指定してください")
        if container is not None:
            self.container = Container(container)
            self._createNode = self.container.createNode
        elif not callable(createNode):
            raise TypeError("createNodeは呼び出せるオブジェクトにしてください")
        else:
            self.container = None
            self._createNode = createNode

    def sum(self, role, left, right, subtract=False, *, fast=False):
        """足し算・引き算のノードを組み立てる。

        Args:
            role (str): 計算の名前。
            left (float | str | Plug): 左辺。
            right (float | str | Plug): 右辺。
            subtract (bool): Trueなら引き算にする。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Plug: 出力のプラグ。ノードの名前が変わっても同じアトリビュートを指す。

        Raises:
            TypeError: fastがboolでない場合。
            NotImplementedError: containerを持ち主にして、fast=Trueを指定した場合。
        """
        with self._edit("mlibScalarGraphSum", fast):
            node = self._node("plusMinusAverage", role, fast)
            node.getPlug("operation").set(2 if subtract else 1, fast=fast)
            self._feed(left, node.getPlug("input1D")[0], fast)
            self._feed(right, node.getPlug("input1D")[1], fast)
            return node.getPlug("output1D")

    def multiply(self, role, left, right, operation=1, *, fast=False):
        """掛け算・割り算・累乗のノードを組み立てる。

        Args:
            role (str): 計算の名前。
            left (float | str | Plug): 左辺。
            right (float | str | Plug): 右辺。
            operation (int): 1は掛け算、2は割り算、3は累乗。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Plug: 出力のプラグ。ノードの名前が変わっても同じアトリビュートを指す。

        Raises:
            TypeError: fastがboolでない場合。
            NotImplementedError: containerを持ち主にして、fast=Trueを指定した場合。
        """
        with self._edit("mlibScalarGraphMultiply", fast):
            node = self._node("multiplyDivide", role, fast)
            node.getPlug("operation").set(operation, fast=fast)
            self._feed(left, node.getPlug("input1X"), fast)
            self._feed(right, node.getPlug("input2X"), fast)
            return node.getPlug("outputX")

    def condition(self, role, left, right, yes, no, *, fast=False):
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
            TypeError: fastがboolでない場合。
            NotImplementedError: containerを持ち主にして、fast=Trueを指定した場合。
        """
        with self._edit("mlibScalarGraphCondition", fast):
            node = self._node("condition", role, fast)
            node.getPlug("operation").set(2, fast=fast)
            for value, attr in ((left, "firstTerm"), (right, "secondTerm"), (yes, "colorIfTrueR"), (no, "colorIfFalseR")):
                self._feed(value, node.getPlug(attr), fast)
            return node.getPlug("outColorR")

    def _edit(self, name, fast):
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
        # 構築途中の失敗を巻き戻すため、通常経路はUndo無効時に拒否するundoTransactionを使う。
        context = _edit_context(name, fast, transaction=True)
        if fast and self.container is not None:
            raise NotImplementedError("持ち主がコンテナの場合、fast=Trueには対応していません")
        return context

    def _node(self, kind, role, fast=False):
        """設定した作り方で、計算ノードを作る。

        Args:
            kind (str): Maya標準のノード型。
            role (str): 計算を見分ける名前。
            fast (bool): Trueなら、ノードを作る関数へ ``fast=True`` を渡す。Falseなら、これまでどおり渡さない。

        Returns:
            Node: 作成したノード。
        """
        prefix = self.container.getName() + "_" if self.container is not None else ""
        if fast:
            return self._createNode(kind, name=prefix + role, fast=True)
        return self._createNode(kind, name=prefix + role)

    @staticmethod
    def _feed(value, destination, fast=False):
        """入力に定数を設定するか、プラグを接続する。

        Args:
            value (float | str | Plug): 定数、または入力にするプラグ(名前でもよい)。
            destination (Plug | str): 接続先のアトリビュート。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。
        """
        destination = Plug._resolve_input(destination)
        if isinstance(value, (str, Plug)):
            Plug._resolve_input(value).connectTo(destination, fast=fast)
        else:
            destination.set(value, fast=fast)
