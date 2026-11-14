# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""OpenMayaのメッセージコールバックを、持ち主ごとにまとめて登録・解除する。"""

import maya.api.OpenMaya as om2
from .. import logger
from typing import Callable
from mlib.nodes.node import Node

_SCENE_EVENTS: tuple


class Callbacks:
    """複数のOpenMayaコールバックを、持ち主ごとにまとめて管理する。

    登録したコールバックはMayaが持っているため、このオブジェクトを捨てても解除されない
    (ガベージコレクションでも自動では解除しない)。:meth:`remove` を呼ぶか、
    ``with Callbacks() as cb:`` の形で使う。
    登録した関数の中で起きた例外は、警告として知らせるだけで、Mayaへは伝えない。
    バッチ(mayapy)でも登録できる。

    .. code-block:: python

        from mlib.common import Callbacks

        with Callbacks() as cb:
            cb.addSceneCallback("afterOpen", refresh)
            cb.addEventCallback("timeChanged", refresh)
            ...  # with を抜けると解除する
    """
    def __init__(self) -> None:
        """何も登録していない空のグループを作る。"""
        ...
    def __enter__(self) -> Callbacks:
        """``with`` を始める。ここでは何も登録しない。

        Returns:
            Callbacks: 自身。

        Raises:
            RuntimeError: 同じインスタンスで入れ子にした場合。
        """
        ...
    def __exit__(self, *excInfo: object) -> bool:
        """``with`` を抜けるときに、このグループが持つコールバックをすべて解除する。

        本文で例外が起きた場合は、解除で起きた例外で本文の例外を置き換えない。

        Args:
            *excInfo (object): 本文の例外の型・例外・トレースバック(正常に終わったならすべてNone)。

        Returns:
            bool: 常にFalse(本文の例外はそのまま送出し直す)。

        Raises:
            RuntimeError: 本文は正常に終わったが、解除に失敗した場合。
        """
        ...
    def addSceneCallback(self, event: str, function: Callable) -> int:
        """シーンのイベント(``om2.MSceneMessage``)のコールバックを登録する。

        Args:
            event (str): イベント名。``"afterOpen"``・``"beforeSave"``・``"afterNew"`` のように、
                ``MSceneMessage.k*`` から ``k`` を除いたlowerCamelCaseで書く。Check系とPluginLoad系は扱わない。
            function (Callable): 引数なしで呼ぶ処理。

        Returns:
            int: 登録したコールバックの識別子。

        Raises:
            TypeError: eventが文字列でない場合、またはfunctionが呼び出せない場合。
            ValueError: 知らないイベント名の場合、またはこの版のMayaに無いイベントの場合。
        """
        ...
    def addEventCallback(self, eventName: str, function: Callable) -> int:
        """Mayaのイベント(``om2.MEventMessage``)のコールバックを登録する。

        Args:
            eventName (str): Mayaのイベント名をそのまま書く(``"timeChanged"``・``"SelectionChanged"`` など)。
                ``cmds.scriptJob(listEvents=True)`` と同じ一覧にある名前で、大文字と小文字を区別する。
            function (Callable): 引数なしで呼ぶ処理。

        Returns:
            int: 登録したコールバックの識別子。

        Raises:
            TypeError: eventNameが文字列でない場合、またはfunctionが呼び出せない場合。
            ValueError: Mayaに無いイベント名の場合。
        """
        ...
    def addAttributeChangedCallback(self, node: Node | str, function: Callable) -> int:
        """ノードのアトリビュートが変わったときのコールバックを登録する。

        ``om2.MNodeMessage.addAttributeChangedCallback`` を使う。値を設定したときだけでなく、
        接続・接続の解除・アトリビュートの追加や削除などでも呼ばれる。
        どの変更かは、messageの ``om2.MNodeMessage.k*`` のビットで見分ける。

        Args:
            node (Node | str): 見張るノード。
            function (Callable): ``function(message, plug)`` の形で呼ぶ処理。messageは
                ``om2.MNodeMessage.AttributeMessage`` のビット(int)、plugは変わった
                アトリビュートの :class:`~mlib.plugs.plug.Plug`。

        Returns:
            int: 登録したコールバックの識別子。

        Raises:
            TypeError: nodeが対応していない型の場合、またはfunctionが呼び出せない場合。
            RuntimeError: nodeが見つからない場合。
        """
        ...
    def remove(self) -> None:
        """このグループが登録したコールバックを、すべて解除する。

        解除できたものだけを、このグループの一覧から除く。解除で例外が起きても警告を出して
        残りを続け、失敗したものはあとでremove()を呼べばもう一度試せる。
        ほかの持ち主のコールバックは解除しない。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 解除に失敗したものが1つ以上ある場合。最初に失敗した原因の例外を__cause__に入れる。
        """
        ...
    def _register(self, callback_id: int) -> int:
        """登録したコールバックの識別子を、このグループの一覧に加える。

        Args:
            callback_id (int): Mayaが返した識別子。

        Returns:
            int: callback_id。
        """
        ...

def _require_callable(function: object):
    """関数が呼び出せるか確かめる。

    Args:
        function (object): 確かめる対象。

    Raises:
        TypeError: 呼び出せない場合。
    """
    ...

def _guarded(function: Callable, label: str) -> Callable:
    """om2へ渡すコールバックを作る。中で起きた例外は警告にして、外へは伝えない。

    Args:
        function (Callable): 実際の処理。
        label (str): 警告に表示する登録先の名前。

    Returns:
        Callable: om2へ渡すコールバック。sceneとeventでは、clientDataだけを受け取る。
    """
    ...
