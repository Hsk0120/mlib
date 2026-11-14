# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""アニメーションカーブの共通の操作。通常の編集はUndoでき、fastはOpenMayaで直接書き込む。"""

import math
from contextlib import contextmanager
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
from ..common.keyframe import Keyframe, Keyframes
from ..common.units import angleToUi
from ..core.attributeType import _convert_units, _from_seconds, _to_seconds
from ..core.fastWrite import require_writable
from ..core.nodeEdit import delete_nodes
from ..decorator import _edit_context, _require_bool, undoChunk
from ..util import _angle_unit, _from_radians, _time_unit, _to_radians
from .node import Node
from typing import Any, Iterable, Sequence
from mlib._stubtypes import GeneratorContextManager
from mlib.plugs.plug import Plug

_TANGENT_TYPES: dict
_TANGENT_NAMES: dict

def _default_tangents() -> tuple[int, int]:
    """Mayaの設定の既定の接線型(``keyTangent -q -g``)を、fastで使えるAPIの定数で返す。

    Returns:
        tuple[int, int]: 入力・出力の接線型。fastで使えない型(fixed・入力のstep/stepnext等)はautoにする。
    """
    ...


class AnimCurve(Node):
    """animCurveノードのクラス。8種類のカーブのキー・接線・外挿を編集する。

    型名の後ろの2文字が、入力(横軸)と出力(縦軸)の種類を表す(例: animCurveTAは時間→角度)。
    値の単位は次のとおり。

    - 入力がT(時間)なら、既定は現在のUIの時間単位のフレーム。各メソッドの ``timeUnit="sec"`` で秒になる。
    - 入力がU(単位なし)なら、単位の無い数値。
    - 出力がA(角度)なら、既定は度。各メソッドの ``unit="rad"`` でラジアンになる。
    - 出力がL(距離)ならcm、T(時間)ならフレーム(``timeUnit="sec"`` で秒)、U(単位なし)なら単位の無い数値。
    - 接線の角度も、既定は度。

    時間と角度の両方を持つカーブ(animCurveTA)では、unitとtimeUnitを別々に指定する。
    ドライバーのPlugの単位の変換は、DrivenKeyが受け持つ。

    通常の編集は、値をUIの単位へ換算してcmdsへ渡す。Undoが有効なら、1つのチャンクにまとめる。
    fastはUndoの設定を変えず、OpenMayaで直接書き込む。途中で失敗したときに元へ戻ることは保証しない。
    """
    def isTimeInput(self) -> bool:
        """横軸(入力)が時間か判定する。

        Returns:
            bool: 横軸が時間ならTrue、単位なしならFalse。

        Raises:
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    def getKeyCount(self) -> int:
        """キーの数を取得する。

        Returns:
            int: キー数。
        """
        ...
    def isStatic(self) -> bool:
        """出力が入力によらず一定か判定する(``MFnAnimCurve.isStatic``)。

        すべてのキーが同じ値で、接線も平らなときに一定になる。キーが無いカーブと、キーが1つのカーブも一定とみなす。
        ベイクした後で、動きの無いカーブを見つけて削除するときなどに使う。

        Returns:
            bool: 出力が一定なら True。

        Raises:
            RuntimeError: animCurveが無効な場合。
        """
        ...
    def getKeyInputs(self, *, timeUnit: str = ...) -> list[float]:
        """各キーの入力(横軸)の値を、キーの番号順に取得する。

        入力が時間(T)のカーブではtimeUnitの単位(既定は現在のUIの時間単位のフレーム)、
        単位なし(U)のカーブでは単位の無い入力値を返す。
        単位なしのカーブでは、ドライバーのPlugのUIでの表示値へは変換しない。

        Args:
            timeUnit (str): 入力が時間のカーブでの単位。``"frame"`` はフレーム、``"sec"`` は秒。既定は ``"frame"``。
                ``"frames"`` / ``"seconds"`` などの別名も使える。入力が単位なしのカーブでは使わない。

        Returns:
            list[float]: 入力値の新しいリスト。書き換えてもカーブには反映しない。

        Raises:
            TypeError: timeUnitが文字列・None以外の場合。
            ValueError: timeUnitが未対応の単位名の場合。
        """
        ...
    def getKeyValues(self, *, unit: str = ..., timeUnit: str = ...) -> list[float]:
        """各キーの出力(縦軸)の値を、キーの番号順に取得する。

        角度はunitの単位(既定は度)、距離はcm、時間はtimeUnitの単位(既定はフレーム)、そのほかは単位の無い値で返す。
        出力が時間のカーブは、MFnAnimCurve.value()のMayaの版による違いを避けるため、time型のキーの値のPlugから読む。

        Args:
            unit (str): 出力が角度(A)のカーブでの単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
                ``"degree"`` などの別名も使える。ほかのカーブでは使わない。
            timeUnit (str): 出力が時間(TT・UT)のカーブでの単位。``"frame"`` は現在のUIの時間単位のフレーム、
                ``"sec"`` は秒。既定は ``"frame"``。ほかのカーブでは使わない。

        Returns:
            list[float]: 出力値の新しいリスト。書き換えてもカーブには反映しない。

        Raises:
            TypeError: unit・timeUnitが文字列・None以外の場合。
            ValueError: unit・timeUnitが未対応の単位名の場合。
        """
        ...
    def evaluate(self, input: float, *, unit: str = ..., timeUnit: str = ...) -> float:
        """指定した入力の位置で、このカーブだけを評価する。現在の時刻は変えない。

        つながった先で合成された結果ではなく、このカーブの補間・外挿の値を返す。
        出力が時間のカーブは、Maya 2022/2023のAPIの違いを補正してから、timeUnitの単位にそろえる。

        Args:
            input (float): 評価する入力の位置。入力が時間(T)のカーブではtimeUnitの単位(既定はフレーム)、
                単位なし(U)のカーブでは単位の無い値。float()で変換し、有限な値か確かめる。
            unit (str): 出力が角度(A)のカーブでの戻り値の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
            timeUnit (str): 入力が時間のカーブでのinputの単位と、出力が時間(TT・UT)のカーブでの戻り値の単位。
                ``"frame"`` は現在のUIの時間単位のフレーム、``"sec"`` は秒。既定は ``"frame"``。

        Returns:
            float: 出力の種類に応じた値。度(unit)・cm・フレーム(timeUnit)、または単位の無い値。

        Raises:
            TypeError: float()で変換できない型の場合、またはunit・timeUnitが文字列・None以外の場合。
            ValueError: 有限でない値、float()で変換できない値、またはunit・timeUnitに対応していない単位名の場合。
            RuntimeError: キーの無いカーブの場合、またはMayaの評価が失敗した場合。キーの無いカーブは、入力を変換する前に例外にする。
        """
        ...
    def findClosestIndex(self, input: float, *, timeUnit: str = ...) -> int:
        """指定した入力に最も近いキーの番号を返す(``MFnAnimCurve.findClosest``)。

        Args:
            input (float): 入力の位置。入力が時間(T)のカーブではtimeUnitの単位(既定はフレーム)、単位なし(U)のカーブでは単位の無い値。
            timeUnit (str): 入力が時間のカーブでのinputの単位。``"frame"`` / ``"sec"``。

        Returns:
            int: 0から始まるキーの番号。同じ距離のキーが2つある場合は、Mayaの判定に従う。

        Raises:
            TypeError: inputが数値へ変換できない型の場合、またはtimeUnitが文字列・None以外の場合。
            ValueError: inputが有限でない場合、またはtimeUnitに対応していない単位名の場合。
            RuntimeError: ノードが無効(削除済み)の場合、またはキーの無いカーブの場合。
        """
        ...
    def setKey(self, input: float, value: float, inTangentType: str | None = ..., outTangentType: str | None = ..., *, unit: str = ..., timeUnit: str = ..., fast: bool = ...) -> AnimCurve:
        """キーを追加する。同じ入力の位置にキーがあれば、その値と、指定した接線の型を書き換える。

        接線の型を省略したときは、``cmds.setKeyframe`` と同じ扱いになる。すでにあるキーは接線の型を保ち、
        新しいキーはMayaの設定(Preferences > Animation の Default tangent、``keyTangent -q -g``)に従う。

        通常は、値をUIの単位へ換算してsetKeyframeを呼ぶ。fastの場合は次のように書き込む。

        - すでにあるキーは、値 → 入力側の接線の型 → 出力側の接線の型の順に書き換える。
        - 新しいキーは、両側の接線の型を指定して追加する。出力が時間のカーブでは、追加した後で値を設定する。
        - 途中で失敗しても、それまでの変更は自動では戻さない。

        Args:
            input (float): 入力の位置。入力が時間(T)のカーブではtimeUnitの単位(既定はフレーム)、単位なし(U)のカーブでは単位の無い値。
            value (float): キーの値。出力の種類に応じて度(unit)・cm・フレーム(timeUnit)、または単位の無い値。
                inputと同じく、有限な数値へ変換する。
            inTangentType (str | None): Mayaの入力側の接線の型。Noneなら上に書いた既定の型。fastではstepをautoに置き換える。
            outTangentType (str | None): Mayaの出力側の接線の型。Noneなら上に書いた既定の型。
            unit (str): 出力が角度(A)のカーブでのvalueの単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
                ``"degree"`` などの別名も使える。ほかのカーブでは使わない。
            timeUnit (str): 入力が時間のカーブでのinputの単位と、出力が時間(TT・UT)のカーブでのvalueの単位。
                ``"frame"`` は現在のUIの時間単位のフレーム、``"sec"`` は秒。既定は ``"frame"``。``"seconds"`` などの別名も使える。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            AnimCurve: 自身。fixedの接線の角度やウェイトを指定するときは、setTangentを使う。

        Raises:
            TypeError: fastがbool以外の場合、unit・timeUnitが文字列・None以外の場合、または数値へ変換できない型の場合。
            ValueError: 有限でない値や正しくない数値の場合、unit・timeUnitに対応していない場合、
                またはfastでfixed・global・知らない接線の型を指定した場合。
            RuntimeError: ノードが無効(削除済み)の場合。fastでも通常と同じ文言で、編集する前に例外にする。
            NotImplementedError: fastで入力側の接線にstepnextを指定した場合。編集する前に例外にする。
        """
        ...
    def insertKey(self, input: float, *, timeUnit: str = ...) -> AnimCurve:
        """カーブの形を変えずにキーを挿入する(``setKeyframe -insert``)。

        値と接線は、Mayaがその位置のカーブから決める。そのため、挿入の前と後で評価した値は変わらない。
        同じ入力の位置にすでにキーがあれば、何もしない。fast引数は持たない。Undoが有効なら1回で戻せる。

        Args:
            input (float): 入力の位置。入力が時間(T)のカーブではtimeUnitの単位(既定はフレーム)、単位なし(U)のカーブでは単位の無い値。
            timeUnit (str): 入力が時間のカーブでのinputの単位。``"frame"`` / ``"sec"``。

        Returns:
            AnimCurve: 自身。挿入したキーの番号は :meth:`findClosestIndex` で取得できる。

        Raises:
            TypeError: inputが数値へ変換できない型の場合、またはtimeUnitが文字列・None以外の場合。
            ValueError: inputが有限でない場合、またはtimeUnitに対応していない単位名の場合。
            RuntimeError: ノードが無効(削除済み)の場合、キーの無いカーブの場合、またはMayaが挿入を拒否した場合。
        """
        ...
    def removeKey(self, index: int | Sequence[int] | None = ..., *, time: float | Sequence[float] | None = ..., timeUnit: str = ..., keepCurve: bool = ..., fast: bool = ...) -> AnimCurve:
        """指定した番号のキー、または入力の範囲にあるキーを削除する。

        キーのクリップボードは変更しない。indexとtimeは、どちらか一方を指定する。
        既定(keepCurve=True)では、すべてのキーを削除してもカーブは残す
        (:meth:`Plug.removeKey <mlib.plugs.plug.Plug.removeKey>` と ``cmds.cutKey`` は、空になったカーブを削除する)。

        Args:
            index (int | Sequence[int] | None): 0から始まるキーの番号、またはその並び。
            time (float | Sequence[float] | None): 削除するキーの入力の時刻、または両端を含む範囲 ``(start, end)``。
                入力が時間(T)のカーブではtimeUnitの単位(既定はフレーム)、単位なし(U)のカーブでは単位の無い値。
                範囲の中にキーが無ければ、何もしない。
            timeUnit (str): 入力が時間のカーブでのtimeの単位。``"frame"`` / ``"sec"``。
            keepCurve (bool): Trueなら、すべてのキーを消してもカーブを残す。Falseなら、Mayaと同じく空のカーブを削除する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            AnimCurve: 自身。keepCurve=Falseでカーブを削除した場合、このオブジェクトは無効になる。

        Raises:
            TypeError: indexとtimeを両方指定した場合かどちらも指定しない場合、timeが数値でも2つの数値の並びでもない場合、
                またはkeepCurve・fastがbool以外の場合。
            ValueError: timeが有限でない場合、範囲の開始が終了より大きい場合、またはtimeUnitに対応していない単位名の場合。
            IndexError: indexが範囲外の場合。
        """
        ...
    def replaceKeys(self, keys: Iterable[Sequence], *, unit: str = ..., timeUnit: str = ...) -> AnimCurve:
        """カーブを残したまま、すべてのキーを指定したキーへ置き換える。

        1回のUndoで戻せる。fast引数は持たない。``keys`` の各要素は、次のどちらかの形で指定する。

        - ``(入力, 値)``
        - ``(入力, 値, 入力側の接線の型, 出力側の接線の型)``

        接線の型を省略した場合と、Noneや空文字列(:meth:`getTangent` が登録されていない型に返す値)の場合は、
        Mayaの設定(Default tangent)に従う。同じ入力が重なった場合は、後の要素で上書きする。
        空の並びを渡すと、すべてのキーを消して、空のカーブを残す。
        すべての要素を確かめてから、カーブを書き換える。

        Args:
            keys (Iterable[Sequence]): 新しいキーの並び。入力と値の単位は :meth:`setKey` と同じ。
            unit (str): 出力が角度(A)のカーブでの値の単位。``"deg"`` / ``"rad"``。
            timeUnit (str): 入力が時間(T)のカーブでの入力の単位と、出力が時間のカーブでの値の単位。``"frame"`` / ``"sec"``。

        Returns:
            AnimCurve: 自身。

        Raises:
            TypeError: 要素が2つか4つの並びでない場合、または数値へ変換できない型の場合。
            ValueError: 有限でない値の場合、知らない接線の型かfixedの場合(角度・ウェイトは :meth:`setTangent` で書く)、
                またはunit・timeUnitに対応していない単位名の場合。
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    def getTangent(self, index: int, *, unit: str = ...) -> dict:
        """指定したキーの接線の情報を取得する。

        入力側・出力側の接線の型、角度、ウェイトと、ロックの状態を返す。

        - 角度は、MAngleからunitの単位(既定は度)へ変換する。
        - 接線のウェイトは、getTangentAngleWeight()の戻り値をそのまま使い、距離の単位などへは変換しない。
          ``keyTangent`` での取得と同じく、入力が時間(T)のカーブのウェイトは、現在のUIの時間単位によって変わる。
          時間の単位の引数(timeUnit)は持たない。
        - lockとweightLockはキーごとの状態、weightedTangentsはカーブ全体の状態。

        Args:
            index (int): 0から始まる、すでにあるキーの番号。
            unit (str): inAngle・outAngleの単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
                ``"degree"`` などの別名も使える。

        Returns:
            dict: 次のキーを持つ新しい辞書。inTangentType・outTangentType、inAngle・outAngle、inWeight・outWeight、
                lock、weightLock、weightedTangents。型名はMayaのコマンドでの表記で、
                名前の登録の無いAPIの接線の型は空文字列になる。辞書を書き換えても、カーブには反映しない。

        Raises:
            TypeError: unitが文字列・None以外の場合。
            ValueError: unitに対応していない単位名の場合。
            IndexError: 番号がbool・int以外・負の値の場合、またはキーの数以上の場合。
        """
        ...
    def setTangent(self, index: int, *, unit: str = ..., fast: bool = ..., **kwargs) -> AnimCurve:
        """指定したキーの接線を変える。接線のロックの扱いはMayaの規則に従う。

        weightedTangentsを指定した場合は、カーブ全体をウェイト付きの接線にするかどうかだけを変える。
        同時に指定したキーごとのフラグは使わない。fastでも、同時に指定した値の確認は省かない。

        通常は、角度をUIの単位へ換算してkeyTangentへ渡す。fastでは、lock → weightLock → 入力側 → 出力側の順に書き込む。
        途中で失敗しても、それまでの変更は自動では戻さない。

        Args:
            index (int): 0から始まる、すでにあるキーの番号。
            unit (str): inAngle・outAngleの単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
                ``"degree"`` などの別名も使える。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            **kwargs: getTangent()の辞書と同じ9種類のフラグ(長い名前)。角度はunitの単位、接線のウェイトはAPIの値で指定する。
                fastの場合は次のように扱う。

                - 角度とウェイトはfloat()で変換して有限か確かめ、負のウェイトは例外にする。
                - 型名は大文字・小文字を区別せず、spline表記を使う。入力側のstepはautoに置き換える。
                - ロックは自動では外さない。

        Returns:
            AnimCurve: 自身。

        Raises:
            TypeError: unitが文字列・None以外の場合。
            ValueError: フラグが空か知らない名前の場合、unitに対応していない場合、
                またはfastで正しくない値やglobal・知らない接線の型を指定した場合。
            IndexError: キーの番号が正しくない場合。
            NotImplementedError: fastで入力側の接線にstepnextを指定した場合。
                ロック・ウェイトを含め、何かを書き換える前に例外にする。
        """
        ...
    def getInfinity(self) -> dict:
        """カーブの前後の外挿の方法を、名前で取得する。

        Returns:
            dict: キーが ``"pre"``・``"post"``、値が外挿の方法の名前の辞書。
        """
        ...
    def setInfinity(self, *, pre: str | None = ..., post: str | None = ..., fast: bool = ...) -> AnimCurve:
        """指定した側だけ、外挿の方法を変える。省略した側はそのまま。

        Args:
            pre (str | None): 最初のキーより前の外挿。constant・linear・cycle・cycleRelative・oscillateのどれか。
                Noneなら変えない。
            post (str | None): 最後のキーより後の外挿。preと同じ選択肢。Noneなら変えない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            AnimCurve: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: 指定した外挿の方法が正しくない場合。両側とも、変える前に確かめる。
            RuntimeError: ノードが無効な場合、または書き込み先がロック・接続などで書き込めない場合。
        """
        ...
    def isBreakdown(self, index: int) -> bool:
        """指定したキーがブレイクダウンキーか判定する(``keyframe -q -breakdown``)。

        Args:
            index (int): 0から始まる、すでにあるキーの番号。

        Returns:
            bool: ブレイクダウンキーならTrue。

        Raises:
            IndexError: 番号がbool・int以外・負の値の場合、またはキーの数以上の場合。
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    def setBreakdown(self, index: int | Sequence[int], state: bool = ...) -> AnimCurve:
        """指定したキーをブレイクダウンキーにする、または通常のキーへ戻す(``keyframe -e -breakdown``)。

        ブレイクダウンキーは、前後のキーとの時間の比率を保って動く。キーの値と入力は変えない。
        fast引数は持たない(キーごとに1回書き換えるだけなので、OpenMayaで書いても速くならない)。
        Undoが有効なら1回で戻せる。

        Args:
            index (int | Sequence[int]): 0から始まるキーの番号、またはその並び。
            state (bool): Trueならブレイクダウンキー、Falseなら通常のキーにする。既定はTrue。

        Returns:
            AnimCurve: 自身。

        Raises:
            TypeError: stateがbool以外、またはindexがNoneの場合。
            IndexError: indexが範囲外の場合。
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    def moveKey(self, index: int | Sequence[int] | None = ..., *, time: float | Sequence[float] | None = ..., timeOffset: float = ..., valueOffset: float = ..., unit: str = ..., timeUnit: str = ...) -> AnimCurve:
        """キーの入力(時刻)と値をずらす。indexとtimeを両方省略すると、すべてのキーを動かす。

        Mayaの ``keyframe -edit -relative`` と同じく、入力をずらしたキーは、動かさない隣のキーを越えない
        (越える分は、隣のキーの直前で止まる)。fast引数は持たない(範囲を1回で処理するcmds.keyframeの方が、
        キーごとにOpenMayaで書くより速い)。

        Args:
            index (int | Sequence[int] | None): 0から始まるキーの番号、またはその並び。
            time (float | Sequence[float] | None): 動かすキーの入力の時刻、または両端を含む範囲 ``(start, end)``。
                入力が時間(T)のカーブではtimeUnitの単位、単位なし(U)のカーブでは単位の無い値。indexとは同時に指定できない。
            timeOffset (float): 入力をずらす量。入力が時間のカーブではtimeUnitの単位(既定はフレーム)、単位なしのカーブでは単位の無い値。
            valueOffset (float): 値をずらす量。角度はunitの単位(既定は度)、距離はcm、時間はtimeUnitの単位。
            unit (str): 出力が角度(A)のカーブでのvalueOffsetの単位。``"deg"`` / ``"rad"``。
            timeUnit (str): 入力が時間のカーブでのtime・timeOffsetの単位と、出力が時間のカーブでのvalueOffsetの単位。
                ``"frame"`` / ``"sec"``。

        Returns:
            AnimCurve: 自身。動かすキーが無ければ何も変えない。

        Raises:
            TypeError: indexとtimeを両方指定した場合、unit・timeUnitが文字列・None以外の場合、または数値へ変換できない型の場合。
            ValueError: 有限でない値の場合、範囲の開始が終了より大きい場合、またはunit・timeUnitに対応していない単位名の場合。
            IndexError: indexが範囲外の場合。
        """
        ...
    def scaleKey(self, inputScale: float = ..., valueScale: float = ..., inputPivot: float = ..., valuePivot: float = ..., *, index: int | Sequence[int] | None = ..., time: float | Sequence[float] | None = ..., unit: str = ..., timeUnit: str = ...) -> AnimCurve:
        """キーを、基準の値を中心に拡大・縮小する。

        indexとtimeを両方省略すると、すべてのキーが対象になる。接線の扱いはMayaのscaleKeyに従う。
        fast引数は持たない(:meth:`moveKey` と同じ理由)。

        Args:
            inputScale (float): 横軸の倍率(単位なし)。0はキーが重なるのでValueErrorになる。
            valueScale (float): 縦軸の倍率(単位なし)。
            inputPivot (float): 横軸の基準の値。入力が時間(T)のカーブではtimeUnitの単位(既定はフレーム)、単位なし(U)のカーブでは単位の無い値。
            valuePivot (float): 縦軸の基準の値。出力が角度(A)のカーブではunitの単位(既定は度)、出力が時間のカーブではtimeUnitの単位。
            index (int | Sequence[int] | None): 0から始まるキーの番号、またはその並び。
            time (float | Sequence[float] | None): 拡大・縮小するキーの入力の時刻、または両端を含む範囲。
                indexとは同時に指定できない。
            unit (str): 出力が角度のカーブでのvaluePivotの単位。``"deg"`` / ``"rad"``。
            timeUnit (str): 入力が時間のカーブでのtime・inputPivotの単位と、出力が時間のカーブでのvaluePivotの単位。
                ``"frame"`` / ``"sec"``。

        Returns:
            AnimCurve: 自身。

        Raises:
            TypeError: indexとtimeを両方指定した場合、unit・timeUnitが文字列・None以外の場合、または数値へ変換できない型の場合。
            ValueError: inputScaleが0の場合、有限でない値の場合、またはunit・timeUnitに対応していない単位名の場合。
            IndexError: indexが範囲外の場合。
        """
        ...
    def mirror(self, input: bool = ..., value: bool = ..., inputPivot: float = ..., valuePivot: float = ..., *, index: int | Sequence[int] | None = ..., time: float | Sequence[float] | None = ..., unit: str = ..., timeUnit: str = ...) -> AnimCurve:
        """入力の軸(横軸)と出力の軸(縦軸)を反転する。

        中では :meth:`scaleKey` を使うので、Undoは1回にまとまる。fast引数は持たない(:meth:`scaleKey` と同じ)。

        Args:
            input (bool): Trueなら横軸を反転する。
            value (bool): Trueなら縦軸を反転する。
            inputPivot (float): 横軸の反転の中心。入力が時間(T)のカーブではtimeUnitの単位(既定はフレーム)、単位なし(U)のカーブでは単位の無い値。
            valuePivot (float): 縦軸の反転の中心。出力が角度(A)のカーブではunitの単位(既定は度)、出力が時間のカーブではtimeUnitの単位。
            index (int | Sequence[int] | None): 反転するキーの番号。indexとtimeを両方省略すると、すべてのキーが対象になる。
            time (float | Sequence[float] | None): 反転するキーの入力の時刻、または両端を含む範囲。
            unit (str): 出力が角度のカーブでのvaluePivotの単位。``"deg"`` / ``"rad"``。
            timeUnit (str): 入力が時間のカーブでのinputPivotの単位と、出力が時間のカーブでのvaluePivotの単位。
                ``"frame"`` / ``"sec"``。

        Returns:
            AnimCurve: 自身。
        """
        ...
    def eulerFilter(self) -> AnimCurve:
        """回転のカーブへEulerフィルターをかけ、360度の飛びを取り除く。

        ``cmds.filterCurve(filter="euler")`` をこのカーブ1本に実行する。
        X・Y・Zの3本をまとめて整えるときは、:meth:`Transform.eulerFilter <mlib.nodes.Transform.eulerFilter>` を使う。
        fast引数は持たない。Undoが有効なら1回で戻せる。

        Returns:
            AnimCurve: 自身。

        Raises:
            TypeError: 時間→角度のカーブ(animCurveTA)でない場合。
            RuntimeError: ノードが無効(削除済み)の場合、またはMayaがフィルターを拒否した場合。
        """
        ...
    def getDrivenPlugs(self) -> list[Plug]:
        """このカーブが動かしているアトリビュートを返す。

        unitConversionなどの変換ノードは飛ばして、その先のアトリビュートを返す。

        Returns:
            list[Plug]: ``output`` の出力先。つながっていなければ空リスト。

        Raises:
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    def getKeyframe(self, index: int) -> Keyframe:
        """指定した番号のキーを、Keyframeとして返す。

        Args:
            index (int): 0から始まる、すでにあるキーの番号。

        Returns:
            Keyframe: このカーブとキーの番号を覚えているオブジェクト。

        Raises:
            IndexError: 番号がbool・int以外・負の値の場合、またはキーの数以上の場合。
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    def getKeyframes(self, indices: Iterable[int] | None = ...) -> Keyframes:
        """複数のキーを、Keyframesとして返す。

        Args:
            indices (Iterable[int] | None): 0から始まるキーの番号の並び。Noneならすべてのキー。

        Returns:
            Keyframes: このカーブのキーの集まり。番号の小さい順に並び、同じ番号は1つにまとめる。

        Raises:
            IndexError: 範囲外の番号を含む場合。
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    def _set_key_values(self, indices: int | Sequence[int], value: float, *, unit: str = ..., timeUnit: str = ..., fast: bool = ...) -> AnimCurve:
        """指定番号のキーの値を、接線型を保ったまま変える(:class:`~mlib.common.keyframe.Keyframe` の入口)。

        Args:
            indices (int | Sequence[int]): 0始まりのキー番号。
            value (float): 新しい値。単位は :meth:`setKey` と同じ。
            unit (str): 角度出力(A型)の値の単位。
            timeUnit (str): 時間出力の値の単位。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Returns:
            AnimCurve: 自身。
        """
        ...
    def _kept_curve(self) -> GeneratorContextManager[Any]:
        """全キーの削除でMayaがカーブを消さないよう、その間だけノードをロックする。

        ``cmds.cutKey`` は空になったカーブ(つながっていないものも)を削除するが、ロックしたノードは
        削除しない。ロックの変更もUndoへ記録され、呼び出し側のチャンクにまとまる。
        """
        ...
    def _set_api_value(self, fn: oma2.MFnAnimCurve, index: int, value: float) -> None:
        """キー値を直接更新し、時間出力の秒をMTimeで保持する。

        Args:
            fn (oma2.MFnAnimCurve): 更新対象カーブ。
            index (int): キー番号。
            value (float): 内部単位の値。

        Returns:
            None: 値を返さない。
        """
        ...
    def _output_angle_unit(self, unit: str) -> str:
        """角度の単位名を検証し、出力が角度(A型)のカーブだけ換算する単位を返す。

        Args:
            unit (str): 角度の単位名。

        Returns:
            str: A型のカーブでは ``"deg"`` / ``"rad"``、それ以外は換算しない ``"rad"``。

        Raises:
            TypeError: unitが文字列・None以外の場合。
            ValueError: unitが未対応の単位名の場合。
        """
        ...
    def _input_time_unit(self, time_unit: str) -> str:
        """時間の単位名を検証し、入力が時間(T型)のカーブだけ換算する単位を返す。

        Args:
            time_unit (str): 時間の単位名。

        Returns:
            str: T型入力のカーブでは ``"frame"`` / ``"sec"``、U型入力では換算しない ``"sec"``。

        Raises:
            TypeError: time_unitが文字列・None以外の場合。
            ValueError: time_unitが未対応の単位名の場合。
        """
        ...
    def _output_time_unit(self, time_unit: str) -> str:
        """時間の単位名を検証し、出力が時間(TT・UT型)のカーブだけ換算する単位を返す。

        Args:
            time_unit (str): 時間の単位名。

        Returns:
            str: 時間出力のカーブでは ``"frame"`` / ``"sec"``、それ以外は換算しない ``"sec"``。

        Raises:
            TypeError: time_unitが文字列・None以外の場合。
            ValueError: time_unitが未対応の単位名の場合。
        """
        ...
    def _curve_fn(self) -> oma2.MFnAnimCurve:
        """保持ノードのAPI 2.0カーブ関数セットを返す。

        削除済みの MObject へ関数セットを作るとMayaが異常終了するため、先に有効性を検査する。

        Returns:
            oma2.MFnAnimCurve: 有効なカーブの関数セット。

        Raises:
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    def _api_input(self, value):
        """内部単位の入力をAPIが要求する時間値または数値へ変換する。"""
        ...
    @staticmethod
    def _api_number(value):
        """時間値を秒、その他を数値として返す。"""
        ...
    @staticmethod
    def _tangent_type(name: str, *, incoming: bool = ..., key: bool = ...):
        """Mayaの接線名を変換し、直接更新できない組合せを更新前に拒否する。

        Args:
            name (str): Maya標準の接線型名。
            incoming (bool): 入力接線として解釈するか。
            key (bool): setKeyでキーを作成・更新するか。
        """
        ...
    @staticmethod
    def _tangent_name(value):
        """API接線型をMayaのコマンド表記へ変換する。"""
        ...
    def _require_curve_writable(self):
        """直接編集前に、キーを格納するアトリビュート(keyTimeValue)のロック・入力接続を検査する。

        全キーの要素を調べるとキー数に比例して遅くなる(キーを打つたびに全要素を調べる)ため、
        マルチアトリビュート自体だけを調べる。要素ごとのロックはcmds.setKeyframeでもエラーにならない。

        Raises:
            RuntimeError: ノードが無効、またはkeyTimeValueがロック・入力接続されている場合。
        """
        ...
    def _unit_value(self, value: float, output: bool = ..., to_ui: bool = ...) -> float:
        """カーブの入出力アトリビュート定義に従い、コマンド境界で単位を変換する。

        Args:
            value (float): 変換する値。
            output (bool): Trueはoutput、Falseはinputの定義を使う。
            to_ui (bool): Trueは内部単位からUI単位、FalseはUI単位から内部単位へ変換する。

        Returns:
            float: 単位型に応じた値。無次元のアトリビュートでは値をそのまま使う。
        """
        ...
    @staticmethod
    def _finite(value: object) -> float:
        """キーや接線の入力をfloatへ変換し、非有限値を拒否する。

        float()に従うため、変換可能な数値文字列やboolもここでは受理する。
        キー番号などの厳密なint検証とは別の責務とする。

        Args:
            value (object): float()へ渡す値。

        Returns:
            float: 有限な値。

        Raises:
            TypeError: float()が受理しない型の場合。
            ValueError: 変換できない文字列など、またはNaN/正負の無限大の場合。
        """
        ...
    def _time_span(self, time: float | Sequence[float], time_unit: str) -> tuple[int, int] | None:
        """入力の時刻・範囲を、その中にあるキーの番号の範囲へ変換する。

        Args:
            time (float | Sequence[float]): 時刻、または両端を含む範囲。
            time_unit (str): T型入力のtimeの単位。

        Returns:
            tuple[int, int] | None: 最初と最後のキー番号。範囲内にキーが無ければNone。

        Raises:
            TypeError: timeが数値・2つの数値の並び以外の場合。
            ValueError: 有限でない、開始が終了より大きい、またはtime_unitが未対応の単位名の場合。
        """
        ...
    def _key_ranges(self, index: int | Iterable[int] | None, time: float | Sequence[float] | None, time_unit: str) -> list[tuple[int, int]]:
        """index・timeの指定を、``cmds.keyframe`` の ``index`` フラグに渡す番号の範囲の並びへ変換する。

        Args:
            index (int | Iterable[int] | None): キー番号、またはその並び。
            time (float | Sequence[float] | None): 入力の時刻、または両端を含む範囲。
            time_unit (str): T型入力のtimeの単位。

        Returns:
            list[tuple[int, int]]: 昇順で重ならない ``(最初, 最後)`` の並び。両方Noneは全キー、該当なしは空。

        Raises:
            IndexError: 範囲外の番号を含む場合。
        """
        ...
    def _index(self, index: int) -> tuple[int, int]:
        """0始まりの既存キー番号を検証し、cmdsの単一キー範囲へ変換する。

        Args:
            index (int): boolを除くint。負値による末尾参照は受け付けない。

        Returns:
            tuple[int, int]: 同じ番号を両端に持つ範囲。

        Raises:
            IndexError: 非int、bool、負値、または現在のキー数以上の場合。
        """
        ...
