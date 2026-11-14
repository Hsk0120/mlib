"""Maya GUIのscriptJobの登録と寿命を管理する。"""

from typing import Any, Dict

import maya.cmds as cmds

from .environment import Environment


class ScriptJob:
    """Maya GUIへ登録した1つのscriptJobを扱うクラス。

    scriptJobのIDと、止めたかどうかを持つ。オブジェクトを作ると監視を登録する。
    オブジェクトが破棄されても監視は自動では解除されないので、stop()で止める。

    callbackはそのままMayaへ渡す。いつ呼ばれるか、例外をどう扱うかはMayaに従う。
    mlibが独自のUndoチャンクを足すことはない。
    """

    def __init__(self, *, event=None, attribute=None, callback, killWithScene=False, compressUndo=False):
        """イベントまたはアトリビュートの変更の監視を始める。

        Args:
            event (str | None): Mayaのイベント名。attributeとは同時に指定できない。
            attribute (str | Plug | MPlug | None): 監視するアトリビュート。eventとは同時に指定できない。
            callback (Callable): 引数なしで呼ぶ処理。
            killWithScene (bool): Trueなら、シーンをクリアするときに監視を解除する。既定はFalse。
            compressUndo (bool): Trueなら、callbackでの変更を直前の操作のUndoにまとめる。既定はFalse。

        Raises:
            TypeError: callbackが呼び出せない場合。
            ValueError: eventとattributeのどちらか1つだけを指定していない場合。
            RuntimeError: バッチ実行中、またはMayaが登録を拒否した場合。
        """
        # commonの初期化時にplugsを読み込まないよう、使用時にPlugを読み込む。
        from ..plugs.plug import Plug as _InputPlug

        if (event is None) == (attribute is None):
            raise ValueError("eventかattributeのどちらか1つだけを指定してください")
        if not callable(callback):
            raise TypeError("callbackは呼び出せるオブジェクトにしてください")
        if Environment.isBatch():
            raise RuntimeError("scriptJobにはMayaのGUIセッションが必要です")
        options: Dict[str, Any] = {"killWithScene": killWithScene, "compressUndo": compressUndo}
        # 先頭の検査により、attributeがNoneならeventが指定されている。
        if attribute is None:
            options["event"] = [event, callback]
        else:
            options["attributeChange"] = [_InputPlug._resolve_input(attribute).getFullName(), callback]
        self._id = cmds.scriptJob(**options)
        self._stopped = False

    @property
    def id(self):
        """int: Mayaが登録時に発行した識別子。"""
        return self._id

    def exists(self):
        """この監視が今もMayaに登録されているか調べる。

        Returns:
            bool: stop()を呼んだ後ならFalse。それ以外はMayaのscriptJob(exists=ID)の結果。
        """
        return not self._stopped and bool(cmds.scriptJob(exists=self._id))

    def stop(self):
        """この監視だけを解除する。

        すでに解除してある場合は何もしない。

        Returns:
            None: 値を返さない。
        """
        if self.exists():
            cmds.scriptJob(kill=self._id)
        self._stopped = True
