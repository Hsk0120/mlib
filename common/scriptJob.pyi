# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya GUIのscriptJobの登録と寿命を管理する。"""

from typing import Any, Dict
import maya.cmds as cmds
from .environment import Environment
from typing import Callable
from mlib.plugs.plug import Plug
import maya.api.OpenMaya as om2



class ScriptJob:
    """Maya GUIへ登録した1つのscriptJobを扱うクラス。

    scriptJobのIDと、止めたかどうかを持つ。オブジェクトを作ると監視を登録する。
    オブジェクトが破棄されても監視は自動では解除されないので、stop()で止める。

    callbackはそのままMayaへ渡す。いつ呼ばれるか、例外をどう扱うかはMayaに従う。
    mlibが独自のUndoチャンクを足すことはない。
    """
    def __init__(self, *, event: str | None = ..., attribute: str | Plug | om2.MPlug | None = ..., callback: Callable, killWithScene: bool = ..., compressUndo: bool = ...) -> None:
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
        ...
    @property
    def id(self) -> int:
        """int: Mayaが登録時に発行した識別子。"""
        ...
    def exists(self) -> bool:
        """この監視が今もMayaに登録されているか調べる。

        Returns:
            bool: stop()を呼んだ後ならFalse。それ以外はMayaのscriptJob(exists=ID)の結果。
        """
        ...
    def stop(self) -> None:
        """この監視だけを解除する。

        すでに解除してある場合は何もしない。

        Returns:
            None: 値を返さない。
        """
        ...
