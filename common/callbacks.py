"""OpenMayaのメッセージコールバックを、持ち主ごとにまとめて登録・解除する。"""

import maya.api.OpenMaya as om2

from .. import logger

# MSceneMessage.addCallbackで登録できる(引数なしで呼ばれる)シーンのイベント名。
# 戻り値を判定に使うCheck系と、プラグイン名の配列を受け取るPluginLoad系は扱わない。
_SCENE_EVENTS = (
    "beforeNew",
    "afterNew",
    "beforeOpen",
    "afterOpen",
    "beforeImport",
    "afterImport",
    "beforeFileRead",
    "afterFileRead",
    "afterSceneReadAndRecordEdits",
    "beforeSave",
    "afterSave",
    "beforeExport",
    "exportStarted",
    "afterExport",
    "beforeReference",
    "afterReference",
    "beforeCreateReference",
    "afterCreateReference",
    "beforeRemoveReference",
    "afterRemoveReference",
    "beforeImportReference",
    "afterImportReference",
    "beforeExportReference",
    "afterExportReference",
    "beforeLoadReference",
    "afterLoadReference",
    "beforeUnloadReference",
    "afterUnloadReference",
    "beforeSoftwareRender",
    "afterSoftwareRender",
    "beforeSoftwareFrameRender",
    "afterSoftwareFrameRender",
    "softwareRenderInterrupted",
    "sceneUpdate",
    "mayaInitialized",
    "mayaExiting",
)


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

    def __init__(self):
        """何も登録していない空のグループを作る。"""
        self._ids = []
        self._context_active = False

    def __enter__(self):
        """``with`` を始める。ここでは何も登録しない。

        Returns:
            Callbacks: 自身。

        Raises:
            RuntimeError: 同じインスタンスで入れ子にした場合。
        """
        if self._context_active:
            raise RuntimeError("同じインスタンスでCallbacksを入れ子にはできません")
        self._context_active = True
        return self

    def __exit__(self, *excInfo):
        """``with`` を抜けるときに、このグループが持つコールバックをすべて解除する。

        本文で例外が起きた場合は、解除で起きた例外で本文の例外を置き換えない。

        Args:
            *excInfo (object): 本文の例外の型・例外・トレースバック(正常に終わったならすべてNone)。

        Returns:
            bool: 常にFalse(本文の例外はそのまま送出し直す)。

        Raises:
            RuntimeError: 本文は正常に終わったが、解除に失敗した場合。
        """
        try:
            self.remove()
        except Exception:
            if excInfo[0] is None:
                raise
        finally:
            self._context_active = False
        return False

    def addSceneCallback(self, event, function):
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
        if not isinstance(event, str):
            raise TypeError("eventはstrで指定してください")
        _require_callable(function)
        message = None
        if event in _SCENE_EVENTS:
            message = getattr(om2.MSceneMessage, "k" + event[:1].upper() + event[1:], None)
        if message is None:
            raise ValueError(f"知らないシーンイベントです: {event!r}")
        return self._register(om2.MSceneMessage.addCallback(message, _guarded(function, event)))

    def addEventCallback(self, eventName, function):
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
        if not isinstance(eventName, str):
            raise TypeError("eventNameはstrで指定してください")
        _require_callable(function)
        # scriptJob(listEvents=True)はバッチでNoneを返すため、同じ一覧をom2から取得する。
        if eventName not in om2.MEventMessage.getEventNames():
            raise ValueError(f"知らないイベント名です: {eventName!r}")
        return self._register(om2.MEventMessage.addEventCallback(eventName, _guarded(function, eventName)))

    def addAttributeChangedCallback(self, node, function):
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
        # commonの初期化時にnodes・plugsを読み込まないよう、使用時に読み込む。
        from ..nodes.node import Node
        from ..plugs.plug import Plug

        _require_callable(function)
        target = Node._resolve_input(node)
        label = target.getName()

        def forward(message, plug, _other_plug, _client_data):
            function(message, Plug._resolve_input(plug))

        return self._register(om2.MNodeMessage.addAttributeChangedCallback(target.mnode(), _guarded(forward, label)))

    def remove(self):
        """このグループが登録したコールバックを、すべて解除する。

        解除できたものだけを、このグループの一覧から除く。解除で例外が起きても警告を出して
        残りを続け、失敗したものはあとでremove()を呼べばもう一度試せる。
        ほかの持ち主のコールバックは解除しない。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 解除に失敗したものが1つ以上ある場合。最初に失敗した原因の例外を__cause__に入れる。
        """
        failures = []
        for callback_id in list(self._ids):
            try:
                om2.MMessage.removeCallback(callback_id)
            except Exception as exc:
                failures.append((callback_id, exc))
                logger.warning("コールバックの後始末に失敗しました(%r): %s", callback_id, exc)
            else:
                self._ids.remove(callback_id)
        if failures:
            raise RuntimeError(f"コールバックを削除できませんでした: {', '.join(repr(key) for key, _ in failures)}") from failures[0][1]

    def _register(self, callback_id):
        """登録したコールバックの識別子を、このグループの一覧に加える。

        Args:
            callback_id (int): Mayaが返した識別子。

        Returns:
            int: callback_id。
        """
        self._ids.append(callback_id)
        return callback_id


def _require_callable(function):
    """関数が呼び出せるか確かめる。

    Args:
        function (object): 確かめる対象。

    Raises:
        TypeError: 呼び出せない場合。
    """
    if not callable(function):
        raise TypeError("functionは呼び出せるオブジェクトにしてください")


def _guarded(function, label):
    """om2へ渡すコールバックを作る。中で起きた例外は警告にして、外へは伝えない。

    Args:
        function (Callable): 実際の処理。
        label (str): 警告に表示する登録先の名前。

    Returns:
        Callable: om2へ渡すコールバック。sceneとeventでは、clientDataだけを受け取る。
    """

    def callback(*args):
        try:
            # scene・eventのコールバックは末尾のclientDataだけを受け取るため、引数なしで呼ぶ。
            if len(args) <= 1:
                function()
            else:
                function(*args)
        except Exception as exc:
            logger.warning("%sのコールバックが失敗しました: %s: %s", label, type(exc).__name__, exc)

    return callback
