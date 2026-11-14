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

__all__ = ["nativeUnits", "preservedSelection", "preservedSkinShape", "undoChunk", "undoTransaction", "viewportOff"]

if TYPE_CHECKING:
    from typing import Any, Dict, Union

    _chunk_active: "ContextVar[Union[bool, str]]"

# 外側のundoChunkの状態。Falseはチャンクの外、Trueは開いたチャンクの中、
# _CHUNK_SKIPPEDはUndoが無効なので開け閉めを省いたチャンクの中。
_chunk_active = ContextVar("mlib_undo_chunk_active", default=False)
_CHUNK_SKIPPED = "skipped"

#: 読みやすい表示名へ置き換える、mlib内部の定型のチャンク名(``mlib<Class><Method>``)。
_INTERNAL_CHUNK_NAME = re.compile(r"mlib[A-Z]\w*\Z")
#: 表示名に含める対象名の最大の長さ。
_CHUNK_TARGET_LIMIT = 80
#: このモジュールのファイル(表示名を組み立てるとき、with文・デコレーターのフレームを飛ばすために使う)。
_THIS_FILE = os.path.normcase(os.path.abspath(__file__))
#: worldSpaceの代わりに書かれやすいキーワード。``ws`` は worldSpace の短縮名として受ける。
_SPACE_KEYWORDS = ("space",)

# reloadしてもモジュールの辞書は残るので、廃止した公開名を取り除く。
for _obsolete_name in (
    "undoable",
    "undo_chunk",
    "undo_transaction",
    "native_units",
    "preserved_selection",
    "preserved_skin_shape",
    "viewport_off",
    "is_fast",
    "_fast_active",
    "_fast_edit",
    "_is_fast",
    "_safe_edit",
    "_flag_aliases",
    "_normalize_flags",
    "_maya_aliases",
):
    globals().pop(_obsolete_name, None)


def _chunk_target(value):
    """Undoの表示名に使う対象名を返す。

    Args:
        value (object): メソッドの ``self``、または関数の先頭の引数。

    Returns:
        str: Node・Plug・Componentなら今の名前、コレクションなら型名と要素の数、文字列ならそのまま。
            名前を得られない値なら空文字列。
    """
    # Nodeなどはこのモジュールを参照するので、importが循環しないよう関数の中で読み込む。
    from .core.object import Object

    try:
        if isinstance(value, Object):
            text = str(value)
        elif isinstance(value, str):
            text = value
        elif isinstance(getattr(value, "_items", None), list):
            text = f"{type(value).__name__}({len(value._items)})"
        else:
            return ""
    except Exception:
        return ""  # 表示名を取得できなくても、編集は止めない。
    return text if len(text) <= _CHUNK_TARGET_LIMIT else text[: _CHUNK_TARGET_LIMIT - 3] + "..."


def _readable_chunk_name(name, frame):
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
    if not isinstance(name, str) or not _INTERNAL_CHUNK_NAME.match(name):
        return name
    try:
        method, owner, target = None, None, None
        for _ in range(8):
            if frame is None:
                break
            code = frame.f_code
            filename = code.co_filename
            if logger._transparent_file(filename) or os.path.normcase(os.path.abspath(filename)) == _THIS_FILE:
                local = frame.f_locals
                function = local.get("func")
                if code.co_name == "inner" and callable(function):
                    # ContextDecorator(デコレーターとしてのundoChunk)が包んだ関数。利用者の関数の名前は変えない。
                    if not logger._internal_file(getattr(getattr(function, "__code__", None), "co_filename", "")):
                        return name
                    method = getattr(function, "__name__", None)
                    args = local.get("args") or ()
                    target = args[0] if args else None
                    break
                frame = frame.f_back
                continue
            if not logger._internal_file(filename):
                # 利用者のコード(テストを含む)が付けた名前は、mlibの定型と同じ形でもそのまま使う。
                return name
            if code.co_name.startswith(("_", "<")):
                frame = frame.f_back
                continue
            method = code.co_name
            local = frame.f_locals
            if "self" in local:
                target = local["self"]
            elif isinstance(local.get("cls"), type):
                owner = local["cls"].__name__
            elif code.co_argcount:
                target = local.get(code.co_varnames[0])
            break
        if not method or method.startswith(("_", "<")):
            return name
        if isinstance(target, type):
            owner, target = target.__name__, None
        label = f"mlib {owner}.{method}" if owner else f"mlib {method}"
        text = _chunk_target(target) if target is not None else ""
        return f"{label} {text}" if text else label
    except Exception:
        return name  # 表示名を組み立てられなくても、編集は止めない。
    finally:
        del frame


class _UndoChunk(contextlib.ContextDecorator):
    """undoChunkの中身。withと関数のデコレーターの両方で使う。

    ジェネレーターは使わない。Undoが無効なら、チャンクを開け閉めしない。
    デコレーターとして使うときは、呼ぶたびに新しいインスタンスを作る。
    そのため、再帰や入れ子で呼んでも状態を共有しない。
    """

    __slots__ = ("_name", "_opened", "_token")

    def __init__(self, name):
        """チャンク名を覚えておく。withが始まるまで、Undoキューは変えない。

        Args:
            name (str | None): Undoキューのチャンク名。
        """
        self._name = name
        self._opened = False
        self._token = None

    def __enter__(self):
        """チャンクを開く。外側にチャンクが無く、Undoが有効なときだけ開く。

        Returns:
            None: withの ``as`` で受け取る値。
        """
        if _chunk_active.get():
            return
        if not cmds.undoInfo(query=True, state=True):
            # Undoが無効なら記録されないので、チャンクを開かない。内側での
            # 問い合わせも省けるよう、外側のチャンクとして扱う。
            self._token = _chunk_active.set(_CHUNK_SKIPPED)
            return
        if self._name:
            name = _readable_chunk_name(self._name, sys._getframe(1))
            cmds.undoInfo(openChunk=True, chunkName=str(name))
        else:
            cmds.undoInfo(openChunk=True)
        self._opened = True
        self._token = _chunk_active.set(True)
        return

    def __exit__(self, exc_type, exc_value, traceback):
        """開いたチャンクを閉じる。

        閉じられなかったときは警告を出す。ブロックの中で起きた例外は、握りつぶさずにそのまま伝える。

        Returns:
            bool: 常にFalse。
        """
        token = self._token
        if token is not None:
            self._token = None
            _chunk_active.reset(token)
        if self._opened:
            self._opened = False
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception as exc:
                logger.warning("Undoチャンクを閉じられませんでした: %s", exc)
        return False

    def open(self):
        """チャンクを開く。

        別々のイベント(スライダーを押す・離すなど)で開け閉めするときに使う。
        開いている間にもう一度呼んでも、何もしない(二重には開かない)。:meth:`close` で閉じる。

        Returns:
            _UndoChunk: 自身。
        """
        if self._token is None:
            self.__enter__()
        return self

    def close(self):
        """:meth:`open` で開いたチャンクを閉じる。開いていなければ何もしない。

        Returns:
            None: 値を返さない。
        """
        if self._token is not None:
            self.__exit__(None, None, None)

    def _recreate_cm(self):
        """デコレーターとして呼ばれるたびに、別のインスタンスを返す。"""
        return type(self)(self._name)


def _undo_recording():
    """今の操作がUndoへ記録されるかを判定する。

    Undoが有効なときに開いたundoChunkの中では、開いたときに問い合わせた結果を使い、
    ``cmds.undoInfo`` の問い合わせを省く。それ以外では毎回問い合わせる。

    ブロックの中でUndoを無効にした場合でもTrueを返すことがある。そのため、
    「FalseならUndoのためだけの処理を省く」という判定にだけ使う。Falseは毎回問い合わせた結果なので正確。

    Returns:
        bool: Undoへ記録される状態ならTrue。
    """
    if _chunk_active.get() is True:
        return True
    return bool(cmds.undoInfo(query=True, state=True))


def _require_bool(value, name):
    """引数がboolかを確かめる。

    Args:
        value (bool): 確かめる値。
        name (str): 例外メッセージに使う引数名。

    Returns:
        bool: 確かめた値。

    Raises:
        TypeError: boolでない場合。
    """
    if type(value) is not bool:
        raise TypeError(f"{name}はboolで指定してください")
    return value


def _pick_alias(long, short, longName, shortName, default=_UNSET):
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
    if short is not _UNSET:
        if long is not _UNSET:
            raise _ArgumentError(f"'{longName}'と'{shortName}'は同時に指定できません")
        return short
    if long is not _UNSET:
        return long
    if default is _UNSET:
        raise _ArgumentError(f"必須の引数がありません: '{longName}'")
    return default


def _merge_flags(kwargs, pairs):
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
    for long, short, long_name, short_name in pairs:
        if short is not _UNSET:
            if long is not _UNSET:
                raise _ArgumentError(f"'{long_name}'と'{short_name}'は同時に指定できません")
            kwargs[long_name] = short
        elif long is not _UNSET:
            kwargs[long_name] = long
    return kwargs


def _validated_flags(locked=None, keyable=None, channelBox=None):
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
    flags = {}
    for name, value in (("lock", locked), ("keyable", keyable), ("channelBox", channelBox)):
        if value is not None:
            if type(value) is not bool:
                raise TypeError(f"{name}はboolかNoneで指定してください")
            flags[name] = value
    return flags


def _edit_context(name, fast, *, transaction=False):
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
    _require_bool(fast, "fast")
    if fast:
        return contextlib.nullcontext()
    return undoTransaction(name) if transaction else undoChunk(name)


def _transform_argument_hints(method):
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
    name = method.__name__
    spread = name.startswith("set")

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        """引数が間違っていれば案内付きで止め、正しければmethodを呼ぶ。"""
        if kwargs:
            for keyword in _SPACE_KEYWORDS:
                if keyword in kwargs:
                    raise TypeError(
                        f"{name}()に想定外のキーワード引数{keyword!r}が渡されました。ワールド空間はworldSpace=Trueで指定します(既定のworldSpace=Falseはローカル)"
                    )
        if spread and len(args) >= 3 and all(isinstance(arg, (int, float)) and not isinstance(arg, bool) for arg in args[:3]):
            raise TypeError(f"{name}()に成分が別々の引数で渡されました。並びで渡してください: {name}((x, y, z))")
        return method(self, *args, **kwargs)

    return wrapper


def undoChunk(name=None):
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
    return _UndoChunk(name)


@contextlib.contextmanager
def undoTransaction(name=None):
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
    token = None
    outermost = bool(name) and not _chunk_active.get()
    if outermost:
        recording = cmds.undoInfo(query=True, state=True)
    kwargs: Dict[str, Any] = {"openChunk": True}
    if name:
        kwargs["chunkName"] = str(_readable_chunk_name(name, sys._getframe(1)))
    cmds.undoInfo(**kwargs)
    if outermost:
        token = _chunk_active.set(True if recording else _CHUNK_SKIPPED)
    try:
        yield
    except BaseException:
        guard_created = False
        closed = False
        try:
            guard = cmds.createNode("network", skipSelect=True)
            guard_created = True
            cmds.delete(guard)
        except Exception as exc:
            logger.warning("Undoのガードを作成できませんでした: %s", exc)
        try:
            cmds.undoInfo(closeChunk=True)
            closed = True
        except Exception as exc:
            logger.warning("Undoチャンクを閉じられませんでした: %s", exc)
        if guard_created and closed:
            try:
                cmds.undo()
            except Exception as exc:
                logger.warning("Undoの巻き戻しに失敗しました: %s", exc)
        else:
            logger.warning("Undoの巻き戻しを省略しました: ガードの作成かチャンクを閉じる処理が成功していません")
        raise
    else:
        cmds.undoInfo(closeChunk=True)
    finally:
        if token is not None:
            _chunk_active.reset(token)


@contextlib.contextmanager
def nativeUnits():
    """ブロックの中だけ、距離と角度のUIの単位をcmとradにする。

    OpenMayaのsetUIUnitで変える。例外が起きても、始める前の単位に戻す。
    時間の単位とシーンの値は変えない。単位の切り替えそのものは、Undoに記録しない。
    """
    previous_linear = om2.MDistance.uiUnit()
    previous_angle = om2.MAngle.uiUnit()
    try:
        om2.MDistance.setUIUnit(om2.MDistance.kCentimeters)
        om2.MAngle.setUIUnit(om2.MAngle.kRadians)
        yield
    finally:
        om2.MDistance.setUIUnit(previous_linear)
        om2.MAngle.setUIUnit(previous_angle)


@contextlib.contextmanager
def preservedSelection():
    """今の選択を覚えておき、ブロックが終わったら元に戻す。

    コンポーネントの選択も含めて覚える。終わるときに、まだシーンにあるものだけを
    cmds.selectで選択し直す。例外が起きたときも元に戻す。
    ブロック全体を1つのUndoチャンクにまとめる。ブロックの中で行った変更は元に戻さない。
    """
    original = om2.MGlobal.getActiveSelectionList()
    with undoChunk("mlibPreservedSelection"):
        try:
            yield
        finally:
            names = original.getSelectionStrings()
            surviving = [name for name in names if cmds.objExists(name)]
            if surviving:
                cmds.select(surviving, replace=True, noExpand=True)
            else:
                cmds.select(clear=True)


@contextlib.contextmanager
def preservedSkinShape(joints):
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
    # 循環参照の回避: nodes は decorator を参照するので、使うときに読み込む。
    from .nodes.joint import Joints

    skins = Joints(joints).getSkinClusters()
    skin_names = [skin.getFullName() for skin in skins]
    previous_modes = {}

    with undoChunk("mlibPreservedSkinShape"):
        for name in skin_names:
            try:
                previous_modes[name] = bool(cmds.skinCluster(name, query=True, moveJointsMode=True))
            except RuntimeError as exc:
                logger.warning("スキン形状の保護: moveJointsModeを取得できませんでした: %s (%s)", name, exc)
                continue
            try:
                cmds.skinCluster(name, edit=True, moveJointsMode=True)
            except RuntimeError as exc:
                logger.warning("スキン形状の保護: moveJointsModeを有効にできませんでした: %s (%s)", name, exc)
                continue
        try:
            yield skins
        finally:
            for name in skin_names:
                try:
                    cmds.skinCluster(name, edit=True, recacheBindMatrices=True)
                except RuntimeError as exc:
                    logger.warning("スキン形状の保護: バインドマトリクスを再キャッシュできませんでした: %s (%s)", name, exc)
            for name, state in previous_modes.items():
                try:
                    cmds.skinCluster(name, edit=True, moveJointsMode=state)
                except RuntimeError as exc:
                    logger.warning("スキン形状の保護: moveJointsModeを元に戻せませんでした: %s (%s)", name, exc)


@contextlib.contextmanager
def viewportOff():
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
    if Environment.isBatch():
        yield
        return
    pane = mel.eval("global string $gMainPane; $mlibMainPane = $gMainPane;")
    if not pane or not cmds.paneLayout(pane, exists=True):
        raise RuntimeError("Mayaのメインペインが利用できません")
    previous = cmds.paneLayout(pane, query=True, manage=True)
    try:
        cmds.paneLayout(pane, edit=True, manage=False)
        yield
    finally:
        if cmds.paneLayout(pane, exists=True):
            cmds.paneLayout(pane, edit=True, manage=previous)
