"""Maya GUIのscriptJobの登録と寿命を管理する。"""

from typing import Any, Dict

import maya.cmds as cmds

from ..decorator import _require_bool
from .environment import Environment


class ScriptJob:
    """Maya GUIへ登録した1つのscriptJobを扱うクラス。

    scriptJobのIDと、止めたかどうかを持つ。オブジェクトを作ると監視を登録する。
    オブジェクトが破棄されても監視は自動では解除されないので、stop()で止める
    (parentを指定した場合は、そのUIが消えたときにもMayaが解除する)。

    callbackはそのままMayaへ渡す。いつ呼ばれるか、例外をどう扱うかはMayaに従う。
    mlibが独自のUndoチャンクを足すことはない。
    """

    def __init__(
        self,
        *,
        event=None,
        attribute=None,
        uiDeleted=None,
        callback,
        killWithScene=False,
        compressUndo=False,
        allChildren=False,
        parent=None,
        runOnce=False,
        protected=False,
    ):
        """イベント・アトリビュートの変更・UIの削除のどれかの監視を始める。

        Args:
            event (str | None): Mayaのイベント名。attribute・uiDeletedとは同時に指定できない。
            attribute (str | Plug | MPlug | None): 監視するアトリビュート。event・uiDeletedとは同時に指定できない。
            uiDeleted (str | None): 監視するUI(ウィンドウなど)の名前。消えたときにcallbackを呼ぶ。
                event・attributeとは同時に指定できない。
            callback (Callable): 引数なしで呼ぶ処理。
            killWithScene (bool): Trueなら、シーンをクリアするときに監視を解除する。既定はFalse。
            compressUndo (bool): Trueなら、callbackでの変更を直前の操作のUndoにまとめる。既定はFalse。
            allChildren (bool): Trueなら、attributeの子(コンパウンドアトリビュートの子・マルチアトリビュートの要素)の
                変更でも呼ぶ。attributeを指定したときだけ使える。既定はFalse。
            parent (str | None): 監視を持たせるUIの名前。そのUIが消えると、Mayaが監視を解除する。既定はNone。
            runOnce (bool): Trueなら、1回呼んだら監視を解除する。既定はFalse。
            protected (bool): Trueなら、Mayaの ``scriptJob(killAll=True)`` などでは解除されないようにする
                (:meth:`stop` では解除できる)。既定はFalse。

        Raises:
            TypeError: callbackが呼び出せない場合、またはkillWithScene・compressUndo・allChildren・runOnce・protectedがboolでない場合。
            ValueError: event・attribute・uiDeletedのどれか1つだけを指定していない場合、
                attributeを指定せずにallChildren=Trueにした場合、またはparent・uiDeletedが空文字列の場合。
            RuntimeError: バッチ実行中、またはMayaが登録を拒否した場合。
        """
        # commonの初期化時にplugsを読み込まないよう、使用時にPlugを読み込む。
        from ..plugs.plug import Plug

        if sum(item is not None for item in (event, attribute, uiDeleted)) != 1:
            raise ValueError("event・attribute・uiDeletedのどれか1つだけを指定してください")
        if not callable(callback):
            raise TypeError("callbackは呼び出せるオブジェクトにしてください")
        for value, key in (
            (killWithScene, "killWithScene"),
            (compressUndo, "compressUndo"),
            (allChildren, "allChildren"),
            (runOnce, "runOnce"),
            (protected, "protected"),
        ):
            _require_bool(value, key)
        if allChildren and attribute is None:
            raise ValueError("allChildrenはattributeを指定したときだけ使えます")
        for value, key in ((parent, "parent"), (uiDeleted, "uiDeleted")):
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{key}は空でないUIの名前で指定してください")
        if Environment.isBatch():
            raise RuntimeError("scriptJobにはMayaのGUIセッションが必要です")
        options: Dict[str, Any] = {"killWithScene": killWithScene, "compressUndo": compressUndo}
        if event is not None:
            options["event"] = [event, callback]
        elif attribute is not None:
            options["attributeChange"] = [Plug._resolve_input(attribute)._full_name(), callback]
            if allChildren:
                options["allChildren"] = True
        else:
            options["uiDeleted"] = [uiDeleted, callback]
        if parent is not None:
            options["parent"] = parent
        if runOnce:
            options["runOnce"] = True
        if protected:
            options["protected"] = True
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
                runOnceで1回呼んだ後や、parentのUIが消えた後もFalseになる。
        """
        return not self._stopped and bool(cmds.scriptJob(exists=self._id))

    def stop(self):
        """この監視だけを解除する。

        protectedの監視も解除する(``cmds.scriptJob(kill=ID, force=True)``)。
        すでに解除してある場合は何もしない。

        Returns:
            None: 値を返さない。
        """
        if self.exists():
            cmds.scriptJob(kill=self._id, force=True)
        self._stopped = True
