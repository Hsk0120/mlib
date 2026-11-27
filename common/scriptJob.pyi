# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya GUIのscriptJobの登録と寿命を管理する。"""

from typing import Any, Dict
import maya.cmds as cmds
from ..decorator import _require_bool
from .environment import Environment
from typing import Callable
from mlib.plugs.plug import Plug
import maya.api.OpenMaya as om2



class ScriptJob:
    """Maya GUIへ登録した1つのscriptJobを扱うクラス。

    scriptJobのIDと、止めたかどうかを持つ。オブジェクトを作ると監視を登録する。
    オブジェクトが破棄されても監視は自動では解除されないので、stop()で止める
    (parentを指定した場合は、そのUIが消えたときにもMayaが解除する)。

    callbackはそのままMayaへ渡す。いつ呼ばれるか、例外をどう扱うかはMayaに従う。
    mlibが独自のUndoチャンクを足すことはない。
    """
    def __init__(self, *, event: str | None = ..., attribute: str | Plug | om2.MPlug | None = ..., uiDeleted: str | None = ..., callback: Callable, killWithScene: bool = ..., compressUndo: bool = ..., allChildren: bool = ..., parent: str | None = ..., runOnce: bool = ..., protected: bool = ...) -> None:
        """イベント・アトリビュートの変更・UIの削除のどれかの監視を始める。

        Args:
            event (str | None): Mayaのイベント名。attribute・uiDeletedとは同時に指定できない。既定はNone。
            attribute (str | Plug | MPlug | None): 監視するアトリビュート。event・uiDeletedとは同時に指定できない。既定はNone。
            uiDeleted (str | None): 監視するUI(ウィンドウなど)の名前。消えたときにcallbackを呼ぶ。
                event・attributeとは同時に指定できない。既定はNone。
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
        ...
    @property
    def id(self) -> int:
        """int: Mayaが登録時に発行した識別子。"""
        ...
    def exists(self) -> bool:
        """この監視が今もMayaに登録されているか調べる。

        Returns:
            bool: stop()を呼んだ後ならFalse。それ以外はMayaのscriptJob(exists=ID)の結果。
                runOnceで1回呼んだ後や、parentのUIが消えた後もFalseになる。
        """
        ...
    def stop(self) -> None:
        """この監視だけを解除する。

        protectedの監視も解除する(``cmds.scriptJob(kill=ID, force=True)``)。
        すでに解除してある場合は何もしない。

        Returns:
            None: 値を返さない。
        """
        ...
