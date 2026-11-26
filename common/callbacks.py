"""OpenMayaのメッセージコールバックを、持ち主ごとにまとめて登録・解除する。"""

import maya.api.OpenMaya as om2

from .. import logger
from ..util import _required_time_unit

# MSceneMessage.addCallbackで登録できる(引数なしで呼ばれる)シーンのイベント名。
# 戻り値を判定に使うCheck系は下の別の表、プラグイン名の配列を受け取るPluginLoad系は扱わない。
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

#: MSceneMessage.addCheckCallbackで登録する、操作を止められるシーンのイベント名(関数は引数なしで呼ぶ)。
_SCENE_CHECK_EVENTS = ("beforeNewCheck", "beforeSaveCheck")

#: MSceneMessage.addCheckFileCallbackで登録する、操作を止められるシーンのイベント名(対象のファイルは関数へ渡さない)。
_SCENE_CHECK_FILE_EVENTS = ("beforeOpenCheck", "beforeImportCheck", "beforeExportCheck", "beforeCreateReferenceCheck", "beforeLoadReferenceCheck")


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

    def addSceneCallback(self, event, callback):
        """シーンのイベント(``om2.MSceneMessage``)のコールバックを登録する。

        ``…Check`` で終わる確認のイベント(``"beforeSaveCheck"`` など)では、シーンの操作の前に呼び、
        関数が偽の値を返せばその操作を止める。``om2.MSceneMessage.addCheckCallback``(``beforeNewCheck``・``beforeSaveCheck``)と
        ``addCheckFileCallback``(``beforeOpenCheck`` など。対象のファイルは関数へ渡さない)を使う。
        確認のイベントの関数の中で起きた例外は警告にして、操作は続ける(Trueを返したのと同じ)。
        そのほかのイベントでは、関数の戻り値は使わない。

        Args:
            event (str): イベント名。``"afterOpen"``・``"beforeSave"``・``"afterNew"`` のように、
                ``MSceneMessage.k*`` から ``k`` を除いたlowerCamelCaseで書く。確認のイベントは
                ``"beforeNewCheck"``・``"beforeSaveCheck"``・``"beforeOpenCheck"``・``"beforeImportCheck"``・
                ``"beforeExportCheck"``・``"beforeCreateReferenceCheck"``・``"beforeLoadReferenceCheck"``。
                PluginLoad系は扱わない。
            callback (Callable): 引数なしで呼ぶ処理。確認のイベントでは、真の値を返せば操作を続け、偽の値(Noneを含む)を返せば止める。

        Returns:
            int: 登録したコールバックの識別子。

        Raises:
            TypeError: eventが文字列でない場合、またはcallbackが呼び出せない場合。
            ValueError: 知らないイベント名の場合、またはこの版のMayaに無いイベントの場合。
        """
        if not isinstance(event, str):
            raise TypeError("eventはstrで指定してください")
        _require_callable(callback)
        if event in _SCENE_CHECK_EVENTS + _SCENE_CHECK_FILE_EVENTS:
            return self._add_scene_check_callback(event, callback)
        message = None
        if event in _SCENE_EVENTS:
            message = getattr(om2.MSceneMessage, "k" + event[:1].upper() + event[1:], None)
        if message is None:
            raise ValueError(f"知らないシーンイベントです: {event!r}")
        return self._register(om2.MSceneMessage.addCallback(message, _guarded(callback, event)))

    def addEventCallback(self, event, callback):
        """Mayaのイベント(``om2.MEventMessage``)のコールバックを登録する。

        Args:
            event (str): Mayaのイベント名をそのまま書く(``"timeChanged"``・``"SelectionChanged"`` など)。
                ``cmds.scriptJob(listEvents=True)`` と同じ一覧にある名前で、大文字と小文字を区別する。
            callback (Callable): 引数なしで呼ぶ処理。

        Returns:
            int: 登録したコールバックの識別子。

        Raises:
            TypeError: eventが文字列でない場合、またはcallbackが呼び出せない場合。
            ValueError: Mayaに無いイベント名の場合。
        """
        if not isinstance(event, str):
            raise TypeError("eventはstrで指定してください")
        _require_callable(callback)
        # scriptJob(listEvents=True)はバッチでNoneを返すため、同じ一覧をom2から取得する。
        if event not in om2.MEventMessage.getEventNames():
            raise ValueError(f"知らないイベント名です: {event!r}")
        return self._register(om2.MEventMessage.addEventCallback(event, _guarded(callback, event)))

    def addTimeChangeCallback(self, callback, *, timeUnit="frame"):
        """現在時刻が変わったときのコールバックを登録する。

        ``om2.MDGMessage.addTimeChangeCallback`` を使う。``callback(time)`` の形で、変わった後の時刻を渡して呼ぶ。
        ``addEventCallback("timeChanged", ...)`` と違い、時刻を受け取れる。

        Args:
            callback (Callable): ``callback(time)`` の形で呼ぶ処理。timeはfloat。
            timeUnit (str): timeの単位。``"frame"``(既定。現在のUIの時間単位のフレーム)か ``"sec"``。

        Returns:
            int: 登録したコールバックの識別子。

        Raises:
            TypeError: callbackが呼び出せない場合、またはtimeUnitが文字列でない場合(Noneを含む)。
            ValueError: timeUnitが対応していない単位名の場合。
        """
        _require_callable(callback)
        unit = _required_time_unit(timeUnit)

        def forward(time, client_data):  # noqa: ARG001 引数はMayaのコールバックが決める
            if unit == "frame":
                callback(time.asUnits(om2.MTime.uiUnit()))
            else:
                callback(time.asUnits(om2.MTime.kSeconds))

        return self._register(om2.MDGMessage.addTimeChangeCallback(_guarded(forward, "timeChange")))

    def addAttributeChangedCallback(self, node, callback):
        """ノードのアトリビュートが変わったときのコールバックを登録する。

        ``om2.MNodeMessage.addAttributeChangedCallback`` を使う。値を設定したときだけでなく、
        接続・接続の解除・アトリビュートの追加や削除などでも呼ばれる。
        どの変更かは、messageの ``om2.MNodeMessage.k*`` のビットで見分ける。

        Args:
            node (Node | str): 見張るノード。
            callback (Callable): ``callback(message, plug)`` の形で呼ぶ処理。messageは
                ``om2.MNodeMessage.AttributeMessage`` のビット(int)、plugは変わった
                アトリビュートの :class:`~mlib.plugs.plug.Plug`。

        Returns:
            int: 登録したコールバックの識別子。

        Raises:
            TypeError: nodeが対応していない型の場合、またはcallbackが呼び出せない場合。
            RuntimeError: nodeが見つからない場合。
        """
        # commonの初期化時にnodes・plugsを読み込まないよう、使用時に読み込む。
        from ..nodes.node import Node
        from ..plugs.plug import Plug

        _require_callable(callback)
        target = Node._resolve_input(node)
        label = target.getName()

        def forward(message, plug, other_plug, client_data):  # noqa: ARG001 引数はMayaのコールバックが決める
            callback(message, Plug._resolve_input(plug))

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
            except Exception as exc:  # noqa: BLE001 1つ解除に失敗しても、残りのコールバックを解除する
                failures.append((callback_id, exc))
                logger.warning("コールバックの後始末に失敗しました(%r): %s", callback_id, exc)
            else:
                self._ids.remove(callback_id)
        if failures:
            raise RuntimeError(f"コールバックを削除できませんでした: {', '.join(repr(key) for key, _ in failures)}") from failures[0][1]

    def _add_scene_check_callback(self, event, function):
        """確認のイベントのコールバックを登録する。

        Args:
            event (str): 確かめてある、確認のイベント名。
            function (Callable): 確かめてある、引数なしで呼ぶ処理。

        Returns:
            int: 登録したコールバックの識別子。
        """
        message = getattr(om2.MSceneMessage, "k" + event[:1].upper() + event[1:])

        def check(*args):
            try:
                return bool(function())
            except Exception as exc:  # noqa: BLE001 利用側の確認の失敗で、Mayaの操作を止めない
                logger.warning("%sのコールバックが失敗しました: %s: %s", event, type(exc).__name__, exc)
                return True

        if event in _SCENE_CHECK_EVENTS:
            return self._register(om2.MSceneMessage.addCheckCallback(message, check))
        return self._register(om2.MSceneMessage.addCheckFileCallback(message, check))

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
        raise TypeError("callbackは呼び出せるオブジェクトにしてください")


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
        except Exception as exc:  # noqa: BLE001 利用側のコールバックの失敗で、Mayaのイベントの処理を止めない
            logger.warning("%sのコールバックが失敗しました: %s: %s", label, type(exc).__name__, exc)

    return callback
