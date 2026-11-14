# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""アトリビュートの値を書き込む処理(cmdsとOpenMayaの両方)。独自プラグインは使わない。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import _require_bool
from .attributeType import NUMERIC_WRITERS, _convert_units, _require_number, _round_integer
from typing import Any, Iterator

_TYPED_DATA_FACTORIES: dict

def require_supported_type(plug: om2.MPlug) -> None:
    """fastで書き込める型かを確かめる。

    子を持つ場合は、すべての子の定義を調べる。値と書き込めるかどうかは調べない。

    safeの部分更新の前に呼ぶ。こうすると、ロックや不正な値のエラーが先に出て、
    その後ろにある未対応の型が見えなくなるのを防げる。
    対応するデータ型(``doubleArray`` など)の表は、実際のデータを作るprepare_dataと共通にしている。

    Args:
        plug (om2.MPlug): 書き込み先。有効なことは確かめてあるもの。

    Returns:
        None: 値を返さない。

    Raises:
        NotImplementedError: 子を含め、fastで扱えない型がある場合。
    """
    ...

def _ancestor_plugs(mplug: om2.MPlug) -> Iterator[om2.MPlug]:
    """プラグ自身と、その上にあるプラグを順に列挙する。

    コンパウンドアトリビュートの親や、要素が属するマルチアトリビュートを上へたどる。
    ロックと入力接続は親やマルチアトリビュートにも付けられるので、書き込めるかどうかの検査で使う。

    Args:
        mplug (om2.MPlug): たどり始めるプラグ。

    Yields:
        om2.MPlug: まずmplug自身。次に親またはマルチアトリビュートを、いちばん上に着くまで順に返す。
    """
    ...

def require_writable(plug: om2.MPlug, _fn: om2.MFnAttribute | None = ...) -> None:
    """プラグへ書き込めるかを調べる。

    ロック・入力接続・書き込めないアトリビュートかどうかを、OpenMayaで調べる。

    Args:
        plug (om2.MPlug): 調べるプラグ。
        _fn (om2.MFnAttribute | None): 同じ更新の中で作ったアトリビュートの
            function set。省略すると新しく作る。値や検査の結果は保存しない。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: ロック・入力接続・書込み禁止がある場合。
    """
    ...

def writable_compound(mplug: om2.MPlug) -> None:
    """プラグとその子へ書き込めるかを調べる。

    コンパウンドアトリビュートなら、すべての子も調べる。

    Args:
        mplug (om2.MPlug): 調べるプラグ。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: 自身または子にロック・入力接続・書込み禁止がある場合。
    """
    ...

def require_range(plug: om2.MPlug, value: float, _fn: om2.MFnNumericAttribute | om2.MFnUnitAttribute | None = ...) -> None:
    """値がアトリビュートのハード範囲に収まるかを調べる。

    cmds.setAttrと同じ検査をする。

    Args:
        plug (om2.MPlug): 調べるプラグ。
        value (float): 書き込む予定の値。単位を持つ型ではcm・rad・秒で渡す。
        _fn (om2.MFnNumericAttribute | om2.MFnUnitAttribute | None): 同じ更新の中で
            作ったfunction set。範囲と単位の定義は、呼ぶたびに取得し直す。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: 値が設定されたハード範囲外の場合。
    """
    ...

def _prepared_writes(plug: om2.MPlug, value: object, _writable_checked: bool = ...) -> list[tuple]:
    """書き込む内容の一覧を作る。

    書き込む前に、すべての成分の型と制限を調べる。そのうえで、OpenMayaで直接書き込む内容を並べる。

    Args:
        plug (om2.MPlug): 書き込み先。
        value (object): 内部単位(cm・rad・秒)の値。
        _writable_checked (bool): Trueなら、書き込めるかどうかを調べ直さない。
            呼び出し元が同じ更新の直前に、自身とすべての子へ :func:`require_writable` を済ませているときに使う。
            型・値・範囲の検査は省かない。

    Returns:
        list[tuple]: 書き込む内容の一覧。各要素は(setter, プラグ, 変換した値, function set)。
            function setは書き込みが終わるまで持っておく。

    Raises:
        TypeError: 数値型への数値以外、または文字列型への文字列以外の入力の場合。
        ValueError: コンパウンドアトリビュートの値の成分の数が、子の数と違う場合。
        RuntimeError: 書き込めない場合、またはハード範囲の外の場合(enumはフィールドの最小〜最大の外)。
        NotImplementedError: API 2.0で値を作れない型の場合。
    """
    ...

def set_plug(plug: om2.MPlug, value: object, _writable_checked: bool = ...) -> None:
    """MPlugへ値を書き込む。Undoには記録しない。

    書き込む前に、すべての成分を調べる。順番は次のとおり。

    - すべての子の型がfastに対応するかを確かめる。未対応なら、ロックなどより先にNotImplementedErrorにする。
    - 書き込めるかどうか、入力の型、ハード範囲を確かめる。
    - 型付きデータを作り、準備した順に書き込む。

    入力の扱いは通常の経路(cmds.setAttr)と同じにする。整数型・enum・boolへ小数を渡すと四捨五入する。
    数値型への文字列や、文字列型への数値は変換せず、TypeErrorにする。
    function setは、データを渡し終えるまで持っておく。Undoの設定は変えない。
    検査を通った後のOpenMayaでの書き込みで失敗しても、先に書いた成分は自動では元に戻さない。

    Args:
        plug (om2.MPlug): 書き込み先。
        value (object): 角度はrad、距離はcm、時間は秒の値。
        _writable_checked (bool): 内部用。呼び出し元が直前に、自身とすべての子へ
            :func:`require_writable` を済ませているならTrue。その検査だけを繰り返さない。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: 入力の型が合わない場合(数値型へ数値以外、文字列型へ文字列以外を渡した場合)。
        ValueError: コンパウンドアトリビュートの値の成分の数が、子の数と違う場合。
        RuntimeError: 書き込めない場合、またはハード範囲の外の場合。
        NotImplementedError: API 2.0で対応していない型の場合。書き込めるかどうかより先に、書き込む前に止める。
    """
    ...

def set_attr(name: str, *values, fast: bool = ..., **kwargs) -> Any:
    """アトリビュートへ値を設定する。

    値はcmds.setAttrと同じ形で受け取る。fast=Trueを指定したときだけ、cmds.setAttrを使わずMPlugへ直接書き込む。

    Args:
        name (str): アトリビュート名。
        *values: cmds.setAttr と同じ形で、現在の Maya の単位の値。
        fast (bool): TrueはUndoなしのOpenMaya更新。既定False。呼出元が明示的に指定する。
        **kwargs: setAttr のフラグ。fast のときに使えるフラグは限られる。

    Returns:
        object | None: 通常の経路では ``cmds.setAttr`` の戻り値。fastではNone。

    Raises:
        TypeError: fastがboolでない場合、またはfastで入力の型が合わない場合。
        NotImplementedError: fastで、``type`` と状態のフラグ以外のフラグを指定した場合。
    """
    ...

def prepare_data(attribute: om2.MObject, value: object, *, name: str | None = ...) -> tuple:
    """マトリクスとtyped dataの値を、書き込める形に用意する。

    型と値を調べてから用意する。MPlugが無くても使える。

    Args:
        attribute (om2.MObject): アトリビュートの定義。ノードへ追加する前のものでもよい。
        value (object): 書き込む予定の値。
        name (str | None): エラーのメッセージに出す名前。

    Returns:
        tuple: (setter, 変換した値, function set)。function setは書き込みが終わるまで持っておく。

    Raises:
        TypeError: 文字列型へ文字列以外を渡した場合。
        NotImplementedError: fastで構築できない型の場合。
    """
    ...
