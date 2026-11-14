# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Undoチャンクと、Mayaの単位・選択・スキン・表示を一時的に変えるデコレーター・コンテキストマネージャー。

公開している6つのほかに、fast/safeの状態の管理と、フラグを揃える内部の補助(先頭が ``_``)もここに置く。
"""

import contextlib
import functools
import os
import re
import sys
from contextvars import ContextVar
from typing import TYPE_CHECKING
import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.mel as mel
from . import logger
from .common.environment import Environment
from .util import _UNSET, _ArgumentError
from typing import Any, Dict, Union
from typing import Any, Callable, Iterable, Iterator
from mlib._stubtypes import ContextDecorator
from mlib._stubtypes import GeneratorContextManager
from mlib.nodes.joint import Joint
from mlib.nodes.skinCluster import SkinClusters
import types

__all__ = ['nativeUnits', 'preservedSelection', 'preservedSkinShape', 'undoChunk', 'undoTransaction', 'viewportOff']
_chunk_active: 'ContextVar[Union[bool, str]]'
_CHUNK_SKIPPED: str
_INTERNAL_CHUNK_NAME: Any
_CHUNK_TARGET_LIMIT: int
_THIS_FILE: Any
_SPACE_KEYWORDS: tuple

def _chunk_target(value: object) -> str:
    """Undoの表示名に使う対象名を返す。

    Args:
        value (object): メソッドの ``self``、または関数の先頭の引数。

    Returns:
        str: Node・Plug・Componentなら今の名前、コレクションなら型名と要素の数、文字列ならそのまま。
            名前を得られない値なら空文字列。
    """
    ...

def _readable_chunk_name(name: object, frame: types.FrameType | None) -> Any:
    """mlib内部の決まった形のチャンク名を、操作と対象が分かる表示名にする。

    ``mlibTransformSetTranslation`` のような名前を、呼び出したメソッド名と対象から作った
    ``mlib setTranslation L_arm_CTRL``・``mlib set L_elbow_JNT.rotateX`` の形へ置き換える。

    公開のメソッドを探すとき、with文・デコレーター・``_`` で始まる内部のメソッドのフレームは飛ばす。
    決まった形でない名前と、mlibの外(利用者のコード)で開いたチャンクの名前は、そのまま返す。

    Args:
        name (object): 指定されたチャンク名。
        frame (types.FrameType | None): チャンクを開いた場所を呼び出した側のフレーム。

    Returns:
        object: 表示名。置き換えないときは name。
    """
    ...


class _UndoChunk(contextlib.ContextDecorator):
    """undoChunkの中身。withと関数のデコレーターの両方で使う。

    ジェネレーターは使わない。Undoが無効なら、チャンクを開け閉めしない。
    デコレーターとして使うときは、呼ぶたびに新しいインスタンスを作る。
    そのため、再帰や入れ子で呼んでも状態を共有しない。
    """
    __slots__: tuple
    def __init__(self, name: str | None) -> None:
        """チャンク名を覚えておく。withが始まるまで、Undoキューは変えない。

        Args:
            name (str | None): Undoキューのチャンク名。
        """
        ...
    def __enter__(self) -> None:
        """チャンクを開く。外側にチャンクが無く、Undoが有効なときだけ開く。

        Returns:
            None: withの ``as`` で受け取る値。
        """
        ...
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        """開いたチャンクを閉じる。

        閉じられなかったときは警告を出す。ブロックの中で起きた例外は、握りつぶさずにそのまま伝える。

        Returns:
            bool: 常にFalse。
        """
        ...
    def open(self) -> _UndoChunk:
        """チャンクを開く。

        別々のイベント(スライダーを押す・離すなど)で開け閉めするときに使う。
        開いている間にもう一度呼んでも、何もしない(二重には開かない)。:meth:`close` で閉じる。

        Returns:
            _UndoChunk: 自身。
        """
        ...
    def close(self) -> None:
        """:meth:`open` で開いたチャンクを閉じる。開いていなければ何もしない。

        Returns:
            None: 値を返さない。
        """
        ...
    def _recreate_cm(self):
        """デコレーターとして呼ばれるたびに、別のインスタンスを返す。"""
        ...

def _undo_recording() -> bool:
    """今の操作がUndoへ記録されるかを判定する。

    Undoが有効なときに開いたundoChunkの中では、開いたときに問い合わせた結果を使い、
    ``cmds.undoInfo`` の問い合わせを省く。それ以外では毎回問い合わせる。

    ブロックの中でUndoを無効にした場合でもTrueを返すことがある。そのため、
    「FalseならUndoのためだけの処理を省く」という判定にだけ使う。Falseは毎回問い合わせた結果なので正確。

    Returns:
        bool: Undoへ記録される状態ならTrue。
    """
    ...

def _require_bool(value: bool, name: str) -> bool:
    """引数がboolかを確かめる。

    Args:
        value (bool): 確かめる値。
        name (str): 例外メッセージに使う引数名。

    Returns:
        bool: 確かめた値。

    Raises:
        TypeError: boolでない場合。
    """
    ...

def _pick_alias(long: object, short: object, longName: str, shortName: str, default: object = ...) -> Any:
    """長い名前と短縮名の引数から、指定された方の値を選ぶ。

    Args:
        long (object): 長い名前の引数の値。指定されていなければ ``_UNSET``。
        short (object): 短縮名の引数の値。指定されていなければ ``_UNSET``。
        longName (str): 長い名前の引数名。例外メッセージに使う。
        shortName (str): 短縮名の引数名。例外メッセージに使う。
        default (object): どちらも指定されていないときに返す値。``_UNSET`` なら、必須の引数として例外にする。

    Returns:
        object: 指定された値、または既定の値。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、または既定の値が無く、どちらも指定されていない場合
            (どちらも ``_ArgumentError``)。
    """
    ...

def _merge_flags(kwargs: dict, pairs: Iterable[tuple[object, object, str, str | None]]) -> dict:
    """長い名前と短縮名で受けたcmdsのフラグを、長い名前で辞書へ入れる。

    入れるのは、指定されたフラグだけ。

    Args:
        kwargs (dict): 入れる先。Mayaのコマンドへ ``**kwargs`` で渡す辞書。
        pairs (Iterable[tuple[object, object, str, str | None]]): (長い名前の値, 短縮名の値, 長い名前, 短縮名) の並び。
            短縮名が無いフラグは、短縮名を None にする。指定されていない値は ``_UNSET``。

    Returns:
        dict: 渡されたkwargsそのもの。指定されていないフラグは加えない。

    Raises:
        TypeError: 同じフラグの長い名前と短縮名を同時に指定した場合(``_ArgumentError``)。
    """
    ...

def _validated_flags(locked: bool | None = ..., keyable: bool | None = ..., channelBox: bool | None = ...) -> dict[str, bool]:
    """アトリビュートの状態の値を確かめ、Mayaのフラグ名の辞書にする。

    すべての値を確かめてから辞書にする。

    Args:
        locked (bool | None): ロックするか。Noneなら変えない。
        keyable (bool | None): キーを打てるようにするか。
        channelBox (bool | None): Channel Boxに表示するか。

    Returns:
        dict[str, bool]: 指定されたMayaのフラグ(``lock``・``keyable``・``channelBox``)だけを入れた辞書。

    Raises:
        TypeError: boolでもNoneでもない値がある場合。
    """
    ...

def _edit_context(name: str, fast: bool, *, transaction: bool = ...) -> contextlib.AbstractContextManager:
    """書き込むメソッドの中身を包む、Undoのコンテキストを返す。

    fastがboolかも確かめる。
    ``with _edit_context("mlibClassMethod", fast):`` と書くと、fastの決まった書き方
    (``nullcontext() if fast else undoChunk(name)``)が1行で済む。

    Args:
        name (str): 通常の経路のUndoチャンク名(``mlib<Class><Method>``)。Mayaに表示する名前は、
            呼び出したメソッドと対象から ``mlib setTranslation L_arm_CTRL`` の形で作る。
        fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
        transaction (bool): Trueなら、通常の経路で ``undoTransaction`` を使う
            (Undoが無効なときに止める必要がある、作成の処理で使う)。Falseなら ``undoChunk`` を使う。既定はFalse。

    Returns:
        contextlib.AbstractContextManager: fastならnullcontext、通常ならundoChunkかundoTransaction。

    Raises:
        TypeError: fastがboolでない場合。
    """
    ...

def _transform_argument_hints(method: Callable) -> Callable:
    """位置・回転・マトリクスのメソッドに、よくある引数の間違いの案内を付ける。

    - ``space=`` を指定すると、``worldSpace=True`` を案内するTypeErrorにする
      (``ws=`` は ``worldSpace`` の短縮名として受け付ける)。
    - ``setTranslation(1, 2, 3)`` のように成分を分けて渡すと、1つの並びで渡す書き方を案内するTypeErrorにする。

    どちらも書き込む前に止める。``space=`` という別名は加えない。

    Args:
        method (Callable): Transformのメソッド。

    Returns:
        Callable: 引数を確かめてからmethodを呼ぶ関数。
    """
    ...

def undoChunk(name: str | None = ...) -> ContextDecorator:
    """Undoできる操作を、1つのチャンクにまとめる。

    ``with undoChunk(name)`` と ``@undoChunk(name)`` のどちらでも使える。

    - 入れ子にした場合は、外側の名前とチャンクを使う。ただし、undoTransactionが開く独立したチャンクは省かない。
    - 終わるときは、例外が起きても起きなくてもチャンクを閉じる。閉じられなかったときは警告を出す。
      ブロックの中で起きた例外は、そのまま送り出す。
    - 自動で元に戻す処理はしない。fastでの書き込みもUndoできるようにはならない。

    始めるときにUndoが無効(``cmds.undoInfo(query=True, state=True)`` がFalse)なら、
    記録されないので、チャンクを開け閉めしない。ブロックの中でUndoを有効にしても、
    そのブロックの操作は1つのチャンクにまとまらない。

    押してから離すまでのように、開く処理と閉じる処理が別々の呼び出しになる場合は、戻り値の
    ``open()``・``close()`` を使う(``chunk = undoChunk("drag"); chunk.open(); ...; chunk.close()``)。
    二重に開く呼び出しや、開かずに閉じる呼び出しは何もしない。

    Args:
        name (str | None): Undoキューのチャンク名。省略するとMayaの既定の表示になる。mlib内部の決まった形の
            名前(``mlib<Class><Method>``)は、呼び出したメソッドと対象から
            ``mlib setTranslation L_arm_CTRL`` の形の表示名にする。

    Returns:
        contextlib.ContextDecorator: withかデコレーターとして使うコンテキスト。
            withの ``as`` で受け取る値はNone。``open()``・``close()`` も持つ。
    """
    ...

def undoTransaction(name: str | None = ...) -> GeneratorContextManager[Any]:
    """ブロックの中で例外が起きたら、Undoを1回実行して変更を戻そうとする。

    ``with undoTransaction(name)`` と ``@undoTransaction(name)`` のどちらでも使える。
    Undoが有効なことが前提。正常に終わったときは、独立した1つのチャンクを残す。
    fastでの直接の書き込みや、ファイルの操作は戻せない。

    例外が起きたときは、networkノードを作って消し、Undoの記録を1つ確実に作ってからチャンクを閉じる。
    空のチャンクのままUndoすると、直前の別の操作を戻してしまう。それを防ぐため、
    この記録(ガード)を作れなかったときや、チャンクを閉じられなかったときはUndoしない。
    戻す処理に失敗したときは警告を出し、元の例外を送り出す。すべて戻せるとは限らない。

    名前を指定した場合、ブロックの中のundoChunkはこのチャンクの内側として扱い、Mayaの
    チャンクを入れ子に開かない(Mayaは入れ子のチャンクを外側の1つにまとめ、表示名は
    最初に開いた名前付きのチャンクの名前になる。そのため、Undoの単位も名前も変わらない)。
    この扱いは、外側にundoChunkも名前付きのundoTransactionも無いときだけ、始めるときにUndoの状態を
    1回問い合わせて決める。Undoが無効なら、ブロックの中のundoChunkもこれまでどおり開け閉めしない。
    名前を省略した場合は、最初の内側のチャンク名が表示名になるので、これまでどおり開く。

    Args:
        name (str | None): Undoキューのチャンク名。省略するとMayaの既定の表示になる。
    """
    ...

def nativeUnits() -> GeneratorContextManager[Any]:
    """ブロックの中だけ、距離と角度のUIの単位をcmとradにする。

    OpenMayaのsetUIUnitで変える。例外が起きても、始める前の単位に戻す。
    時間の単位とシーンの値は変えない。単位の切り替えそのものは、Undoに記録しない。
    """
    ...

def preservedSelection() -> GeneratorContextManager[Any]:
    """今の選択を覚えておき、ブロックが終わったら元に戻す。

    コンポーネントの選択も含めて覚える。終わるときに、まだシーンにあるものだけを
    cmds.selectで選択し直す。例外が起きたときも元に戻す。
    ブロック全体を1つのUndoチャンクにまとめる。ブロックの中で行った変更は元に戻さない。
    """
    ...

def preservedSkinShape(joints: Iterable[Joint | str]) -> GeneratorContextManager[SkinClusters]:
    """スキンの形を崩さずに、ジョイントの姿勢を編集できるようにする。

    ジョイントにつながっているskinClusterを、ブロックの中だけmoveJointsModeにする。
    終わるときは、recacheBindMatricesで今の姿勢をバインドマトリクスへ書き込み、
    取得できた元のモードへ戻す。

    - 階層の自由な変更や、インフルエンスの削除をしたときの結果は保証しない。
      すべてのフレームで変形が保たれることも保証しない。
    - モードの取得・切り替え・バインドマトリクスの書き込み・元に戻す処理でRuntimeErrorが起きたら、
      警告を出して続ける。警告が出たときは、保護や元に戻す処理が終わっていないことがある。
    - ブロックの中で起きた例外は、そのまま伝える。
    - 通常の変更は1つのUndoチャンクにまとめる。fastでの直接の書き込みは戻せない。

    Args:
        joints (Iterable[Joint | str]): 対象のジョイント。Jointでないものを渡すとTypeError、
            見つからないものを渡したときも例外になる。

    Yields:
        SkinClusters: 保護しているskinClusterのコレクション。
    """
    ...

def viewportOff() -> GeneratorContextManager[None]:
    """メインペインを隠し、終わったら元の表示に戻す。

    ``@viewportOff()`` と ``with viewportOff():`` のどちらでも使える。
    GUIでは、メインペインのpaneLayoutのmanageを一時的に外す。
    バッチ実行では表示を何も変えない。OGS・refresh・評価の設定は変えない。
    入れ子にしても元の状態を保つ。処理中に起きた例外は、やり直さずにそのまま伝える。

    Yields:
        None: 表示を止めている間に、ブロックの処理を実行する。

    Raises:
        RuntimeError: GUIのメインペインを取得できない場合、または変更できない場合。
    """
    ...
