# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""om2.MQuaternion を継承したクォータニオンと、回転の補間・分解。"""

import math
from typing import Any, Sequence
import maya.api.OpenMaya as om2
from ..util import _angle_unit, _checked_index, _copy_state, _finite, _foreign_comparison, _from_radians, _rethrow_init_error, _to_radians
from .vector import Vector, _axis_name, _reduce_value, _resolve_mvector, _zero
from typing import Any, Iterable, Iterator
from mlib.maths.eulerRotate import EulerRotate
from mlib.maths.matrix import Matrix
from typing_extensions import Self
import types

_MQuaternion: Any
_MVector: Any
_NEW: Any
_INIT: Any
_GET: Any
_SET: Any
_NUMBER: tuple

def _quaternion_keywords(x: float = ..., y: float = ..., z: float = ..., w: float = ...) -> tuple:
    """キーワード引数付きの Quaternion の生成引数を (x, y, z, w) へまとめる。

    Args:
        x (float): X 成分。
        y (float): Y 成分。
        z (float): Z 成分。
        w (float): W 成分。

    Returns:
        tuple: (x, y, z, w)。
    """
    ...

def _unit_copy(value: om2.MQuaternion) -> Quaternion:
    """MQuaternion 系を正規化した新しい Quaternion を返す。

    Args:
        value (om2.MQuaternion): 正規化元。mlib の Quaternion 以外の MQuaternion も受け付ける。

    Returns:
        Quaternion: 長さ 1 の新しいクォータニオン。

    Raises:
        ValueError: ゼロクォータニオンの場合。
    """
    ...

def _roll_bend_axes(aimAxis: str, upAxis: str) -> tuple[om2.MVector, om2.MVector, om2.MVector]:
    """ロール・曲げの分解に使う、向ける軸・アップ軸・横の軸(``aim × up``)を返す。

    Args:
        aimAxis (str): ボーンの向きの軸。``"x"``・``"-y"`` 等。
        upAxis (str): アップ軸。aimAxisと別の軸。

    Returns:
        tuple[om2.MVector, om2.MVector, om2.MVector]: (aim, up, side)。どれも長さ1。

    Raises:
        TypeError: aimAxis・upAxisが文字列でない場合。
        ValueError: 軸の名前が不正、またはaimAxisとupAxisが同じ軸(符号違いを含む)の場合。
    """
    ...


class Quaternion(om2.MQuaternion):
    """om2.MQuaternionを継承した、XYZWのクォータニオン。

    値は後から書き換えられ、ハッシュはできない(dictのキーやsetの要素にできない)。
    OpenMayaのAPIへそのまま渡せる。作り方は ``__init__`` を参照する。渡した値はコピーして使う。
    軸と角度で作るときの角度はラジアン。作るときも積を計算するときも、正規化はしない。

    演算子の意味は次のとおり。

    - ``q1 * q2`` は、q1、q2の順に適用する回転。マトリクスの積と同じ順序になる(Hamilton積では ``q2 ⊗ q1``)。
    - 足し算・引き算・単項の ``-`` は、成分ごとの演算。
    - ``数値 * q`` は4成分それぞれのスカラー倍。``q * 数値`` と割り算はできない。
    - 結果はQuaternionになる。左辺が ``om2.MQuaternion`` でも同じ。
      ただし ``om2.MEulerRotation * q`` はOpenMayaの型を、``EulerRotate * q`` はEulerRotateを返す。
    - ``*=`` / ``+=`` / ``-=`` は自身を書き換える。OpenMayaに無い ``+=`` / ``-=`` も同じオブジェクトを書き換える。

    継承したメソッドのうち数学値を返すものも、対応するmlibの型を返す。
    名前にItが付かない操作は新しい値を返し、Itが付く操作は自身を書き換える。

    成分へ代入できる。lenは4で、番号は-4〜3。範囲外はIndexErrorになる。
    スライスでは成分のtupleを返し、反復はXYZWの順になる。
    ``==`` は成分の完全一致を比べる。同じ回転を表していても、qと-qは等しくない。
    違う型との比較は :class:`~mlib.maths.vector.Vector` と同じ扱いになる。
    """
    __slots__: tuple
    __hash__: None
    def __new__(cls, *args, **kwargs) -> Self:
        """基底初期化でC++実体を確保し、clsの単位クォータニオンを作る。

        ``__init__`` を省略しても実体へアクセスできるよう、先に確保する。
        詳細は :meth:`mlib.maths.vector.Vector.__new__` を参照。

        Args:
            *args: ここでは使わない生成引数。
            **kwargs: ここでは使わないキーワード引数。

        Returns:
            Quaternion: clsの単位クォータニオン。
        """
        ...
    def __init__(self, *args, **kwargs) -> None:
        """成分を設定する。

        Args:
            *args: om2のMQuaternionのコンストラクタが受け付ける引数。
                ``()``、``(x, y, z, w)``、``(values)``、``(MQuaternion)``、``(angle, axis)``、``(a, b[, factor])`` など。
                このほか、次の形も受け付ける。

                - ``(EulerRotate | om2.MEulerRotation)``: ``asQuaternion()`` と同じ回転。
                - ``(Matrix | om2.MMatrix)``: ``om2.MTransformationMatrix`` で分解した回転の成分
                  (スケール・シアー・平行移動は除く)。
            **kwargs: ``x``、``y``、``z``、``w``。位置引数と組み合わせて使える。
                省略した成分は (0, 0, 0, 1) の値になる。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 未知のキーワード引数、または同じ成分を二重に指定した場合。
            ValueError: om2 のコンストラクタが受け付けない引数の場合。
        """
        ...
    def __getitem__(self, index: int | slice) -> float | tuple[float, ...]:
        """成分を取得する。

        Args:
            index (int | slice): -4〜3 の番号(X、Y、Z、W の順)、またはスライス。

        Returns:
            float | tuple[float, ...]: 指定成分。スライスでは成分の tuple。

        Raises:
            TypeError: 番号が整数・スライス以外の場合。
            IndexError: 番号が範囲外の場合。
        """
        ...
    def __setitem__(self, index: int, value: float) -> None:
        """成分を設定する。

        Args:
            index (int): -4〜3 の番号。
            value (float): 設定する値。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 番号が整数以外の場合。
            IndexError: 番号が範囲外の場合。
        """
        ...
    def __iter__(self) -> Iterator[float]:
        """X、Y、Z、W の順に成分を反復する。

        Returns:
            Iterator[float]: 4成分のイテレータ。
        """
        ...
    def __reduce__(self) -> tuple:
        """copy / pickle 用に、コンストラクタを通さずに再構築する情報を返す。

        Returns:
            tuple: ``(_rebuild, (type(self), (x, y, z, w))[, state])``。
            利用者の派生クラスの ``__init__`` は呼ばず、``__dict__`` と ``__slots__`` の
            アトリビュートは再構築時に復元する。
        """
        ...
    def __reduce_ex__(self, protocol: int) -> tuple:
        """pickle のプロトコルにかかわらず __reduce__ と同じ情報を返す。

        Args:
            protocol (int): pickle のプロトコル番号。使用しない。

        Returns:
            tuple: ``__reduce__()`` の結果。
        """
        ...
    def __copy__(self) -> Quaternion:
        """同じ型・同じ成分の複製を返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートも浅く写す。

        Returns:
            Quaternion: 自身と同じクラスの新しいインスタンス。
        """
        ...
    def __deepcopy__(self, memo: dict) -> Quaternion:
        """同じ型・同じ成分の複製を返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートは深く複製する。

        Args:
            memo (dict): copy.deepcopy の memo。

        Returns:
            Quaternion: 自身と同じクラスの新しいインスタンス。
        """
        ...
    def __repr__(self) -> str:
        """クラス名と4成分を含むデバッグ表現を返す。

        Returns:
            str: ``Quaternion(x, y, z, w)`` の形式の文字列。
        """
        ...
    __str__: Any
    def __eq__(self, other: object) -> bool | types.NotImplementedType:
        """MQuaternion 系との成分の完全一致を判定する。

        Args:
            other (object): 比較対象。

        Returns:
            bool | types.NotImplementedType: MQuaternion 系なら om2 と同じ比較の結果。
            その他の om2 の型は False。それ以外の型は NotImplemented(相手の比較に委ね、
            どちらも判断しなければ False になる)。
        """
        ...
    def __ne__(self, other: object) -> bool | types.NotImplementedType:
        """``__eq__`` の否定を返す。

        Args:
            other (object): 比較対象。

        Returns:
            bool | types.NotImplementedType: MQuaternion 系なら om2 と同じ比較の結果。
            その他の om2 の型は True。それ以外の型は NotImplemented。
        """
        ...
    def __mul__(self, other: object) -> Quaternion | types.NotImplementedType:
        """om2 の順序でクォータニオンの積を返す(自身を先に適用する回転)。

        Args:
            other (object): 右側の MQuaternion 系。

        Returns:
            Quaternion | types.NotImplementedType: 積。正規化しない。対応しない型は NotImplemented。
        """
        ...
    def __rmul__(self, other: object) -> Quaternion | types.NotImplementedType:
        """左辺の MQuaternion 系との積を om2 の順序で返す。数値なら成分をスケールする。

        ``数値 * q`` は om2 と同じく4成分それぞれのスカラー倍(正規化しない)。
        ``q * 数値`` は om2 と同じく対応しない。

        Args:
            other (object): 左側の MQuaternion 系、または int / float。

        Returns:
            Quaternion | types.NotImplementedType: 積。対応しない型は NotImplemented。
        """
        ...
    def __imul__(self, other: object) -> Quaternion | types.NotImplementedType:
        """自身へ右から MQuaternion 系を掛ける(``self = self * other``)。

        Args:
            other (object): 右側の MQuaternion 系。

        Returns:
            Quaternion | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        ...
    def __add__(self, other: object) -> Quaternion | types.NotImplementedType:
        """成分ごとの和を返す(om2 の ``+``)。

        Args:
            other (object): MQuaternion 系。

        Returns:
            Quaternion | types.NotImplementedType: 和。対応しない型は NotImplemented。
        """
        ...
    def __radd__(self, other: object) -> Quaternion | types.NotImplementedType:
        """左辺の MQuaternion 系との成分ごとの和を返す。

        Args:
            other (object): MQuaternion 系。

        Returns:
            Quaternion | types.NotImplementedType: 和。対応しない型は NotImplemented。
        """
        ...
    def __iadd__(self, other: object) -> Quaternion | types.NotImplementedType:
        """MQuaternion 系を成分ごとに自身へ加算する(om2 の MQuaternion には無い in-place 版)。

        Args:
            other (object): MQuaternion 系。

        Returns:
            Quaternion | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        ...
    def __sub__(self, other: object) -> Quaternion | types.NotImplementedType:
        """成分ごとの差を返す(om2 の ``-``)。

        Args:
            other (object): MQuaternion 系。

        Returns:
            Quaternion | types.NotImplementedType: 差。対応しない型は NotImplemented。
        """
        ...
    def __rsub__(self, other: object) -> Quaternion | types.NotImplementedType:
        """左辺の MQuaternion 系から自身を引いた成分ごとの差を返す。

        Args:
            other (object): MQuaternion 系。

        Returns:
            Quaternion | types.NotImplementedType: 差。対応しない型は NotImplemented。
        """
        ...
    def __isub__(self, other: object) -> Quaternion | types.NotImplementedType:
        """MQuaternion 系を成分ごとに自身から減算する(om2 の MQuaternion には無い in-place 版)。

        Args:
            other (object): MQuaternion 系。

        Returns:
            Quaternion | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        ...
    def __neg__(self) -> Quaternion:
        """全成分の符号を反転したクォータニオンを返す(同じ回転を表す)。

        Returns:
            Quaternion: 新しいクォータニオン。
        """
        ...
    @classmethod
    def fromAxisAngle(cls, axis: om2.MVector | Iterable[float], angle: float, *, unit: str = ...) -> Quaternion:
        """軸と角度から、回転のクォータニオンを作る。

        Args:
            axis (om2.MVector | Iterable[float]): 回転軸。中で正規化してから使う。
            angle (float): 回転の角度。単位はunitで決まる。
            unit (str): angleの単位。``"rad"`` はラジアン(om2と同じ)、``"deg"`` は度。既定は ``"rad"``。
                ``"degree"`` / ``"radians"`` などの別名も使える。

        Returns:
            Quaternion: axisを中心にangleだけ回転する単位クォータニオン。

        Raises:
            TypeError: unitが文字列・None以外の場合。
            ValueError: axisが0のベクトルの場合(om2はこの場合に単位クォータニオンを返す)、またはunitに対応していない場合。
        """
        ...
    @classmethod
    def fromRollBend(cls, roll: float, bendH: float, bendV: float, aimAxis: str = ..., upAxis: str = ..., *, unit: str = ...) -> Quaternion:
        """ロール(捻り)と、横・縦の曲げの角度から、回転のクォータニオンを作る。

        :meth:`asRollBend` の逆の計算になる。aimAxis周りにrollだけ捻ってから、aimAxisを曲げる回転を作る
        (om2の積の順序で ``捻り * 曲げ``)。
        曲げは、upAxis周りのbendHと、横の軸(``aimAxis × upAxis``)周りのbendVの組で表す。
        片方が0なら、もう片方の軸周りの回転そのものになる。

        Args:
            roll (float): aimAxis周りの捻りの角度。
            bendH (float): upAxis周りの曲げの角度。aimAxisを横の軸の負の側へ倒す向きが正。
            bendV (float): 横の軸周りの曲げの角度。aimAxisをupAxisの側へ倒す向きが正。
            aimAxis (str): ボーンの向きの軸。``"x"``・``"y"``・``"z"``・``"-x"``・``"-y"``・``"-z"`` のどれか。既定は ``"x"``。
            upAxis (str): アップ軸。aimAxisと違う軸にする。既定は ``"y"``。
            unit (str): 角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。

        Returns:
            Quaternion: 呼び出したクラスの新しい単位クォータニオン。

        Raises:
            TypeError: 角度が数値でない場合、aimAxis・upAxisが文字列でない場合、またはunitが文字列・None以外の場合。
            ValueError: 角度が有限でない場合、軸の名前が正しくない場合、aimAxisとupAxisが同じ軸の場合、
                またはunitに対応していない場合。
        """
        ...
    @staticmethod
    def squad(*args) -> Quaternion:
        """クォータニオンの空間での三次曲線(squad)で補間したQuaternionを返す。

        計算はOpenMayaのMQuaternion.squadで行う。入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: p, a, b, q, tの順に指定する。pとqは両端、aとbは中間の制御点、tは補間の割合。
                省略できるspinは、何周余分に回るか。

        Returns:
            Quaternion: 計算結果の新しいQuaternion。
        """
        ...
    @staticmethod
    def squadPt(*args) -> Quaternion:
        """squadの曲線を滑らかにつなぐための、中間の制御点の回転を計算する。

        計算はOpenMayaのMQuaternion.squadPtで行う。入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: 隣り合う3つのクォータニオンq0, q1, q2を指定する。

        Returns:
            Quaternion: 計算結果の新しいQuaternion。
        """
        ...
    def dot(self, other: om2.MQuaternion) -> float:
        """4成分の内積を返す。

        Args:
            other (om2.MQuaternion): 内積の相手。x、y、z、w を持つ値。

        Returns:
            float: 内積。
        """
        ...
    def length(self) -> float:
        """クォータニオンの長さ(ノルム)を返す。

        Returns:
            float: 長さ。
        """
        ...
    def lengthSq(self) -> float:
        """クォータニオンの長さの2乗(自身との内積)を返す。

        Returns:
            float: 長さの2乗。
        """
        ...
    def unitIt(self) -> Quaternion:
        """自身を正規化する。

        0のクォータニオンは正規化できないので、例外にする。

        Returns:
            Quaternion: 更新した自身。

        Raises:
            ValueError: 0のクォータニオンの場合。自身は変更しない。
        """
        ...
    def unit(self) -> Quaternion:
        """正規化した新しいクォータニオンを返す。

        om2の ``normal()`` は、0のクォータニオンに対して単位クォータニオンを返す。
        このメソッドは、0のクォータニオンを例外にする。

        Returns:
            Quaternion: 長さ1のクォータニオン。

        Raises:
            ValueError: 0のクォータニオンの場合。
        """
        ...
    def conjugate(self) -> Quaternion:
        """共役クォータニオンを返す。

        om2の同名メソッドを上書きして、mlibの型で返す。

        Returns:
            Quaternion: XYZ 成分の符号を反転した新しいクォータニオン。
        """
        ...
    def inverse(self) -> Quaternion:
        """逆クォータニオンを返す。

        逆クォータニオンは、共役を長さの2乗で割った値。単位クォータニオンならconjugate()と同じになる。
        om2の同名メソッドを上書きして、mlibの型で返す。
        om2は0のクォータニオンに対してNaNを返すが、このメソッドは例外にする。

        Returns:
            Quaternion: 逆クォータニオン。

        Raises:
            ValueError: 0のクォータニオンの場合。
        """
        ...
    def rotateVector(self, vector: om2.MVector | Iterable[float]) -> Vector:
        """XYZのベクトルを、このクォータニオンで回転する。

        自身のコピーを正規化してから使う。自身と入力のベクトルは変更しない。
        長さが1でないQuaternionをMVector.rotateBy()へ直接渡すと、その長さでベクトルの大きさも変わる。
        このメソッドは正規化してから回すので、大きさは変わらない。平行移動も含まない。

        Args:
            vector (om2.MVector | Iterable[float]): 回転するXYZ。MPointを渡した場合、wは無視する。

        Returns:
            Vector: 回転した新しいベクトル。入力の型が派生クラスでも引き継がず、派生クラスで足したPythonの状態も引き継がない。

        Raises:
            ValueError: 自身が0のクォータニオンの場合。
        """
        ...
    def angleTo(self, other: om2.MQuaternion) -> float:
        """別のクォータニオンが表す回転との角度の差を、ラジアンで返す。

        両方を正規化してから比べる。qと-qは同じ回転を表すので、その場合の差は0になる。
        acosを使わず ``4 * atan2(|p - q|, |p + q|)`` で計算するので、差が0やpiに近くても精度が落ちない。

        Args:
            other (om2.MQuaternion): 角度の差を測る相手の回転。

        Returns:
            float: 0からpiまでのラジアンの角度。

        Raises:
            ValueError: 自身またはotherが0のクォータニオンの場合。
        """
        ...
    def slerp(self, other: om2.MQuaternion, t: float, spin: int = ...) -> Quaternion:
        """別のクォータニオンとの球面線形補間を返す。

        om2の静的メソッド ``MQuaternion.slerp(p, q, t, spin=0)`` を上書きする。
        ``p.slerp(q, t)`` のようにインスタンスから呼べるほか、``Quaternion.slerp(p, q, t)`` の形でも使える。
        入力を正規化してから、om2のslerpへ渡す。spinが0なら最短経路で補間する。

        Args:
            other (om2.MQuaternion): 補間先の回転。
            t (float): 補間の割合。0で自身、1でotherになる。
            spin (int): om2のslerpへ渡す、余分に回る回数。既定は0。

        Returns:
            Quaternion: 補間した結果。

        Raises:
            ValueError: 自身またはotherが0のクォータニオンの場合。
        """
        ...
    def asCanonicalAxisAngle(self) -> tuple[Vector, float]:
        """軸と角度の組へ分解する。

        om2の ``asAxisAngle`` とは次の点が違う。

        - wが負なら符号を反転して、角度を0からpiの範囲に収める。
        - 回転が無い場合の軸は (1, 0, 0) にする。
        - 角度を ``2 * atan2(|xyz|, w)`` で求めるので、ごく小さい回転でも精度が落ちない。

        Returns:
            tuple[Vector, float]: 正規化した回転軸と、ラジアンの回転の角度(0からpi)。

        Raises:
            ValueError: 自身が0のクォータニオンの場合。
        """
        ...
    def asSwingTwist(self, axis: om2.MVector | Iterable[float] = ...) -> tuple[Quaternion, Quaternion]:
        """指定した軸周りの捻り(twist)と、それ以外の曲げ(swing)へ分解する。

        ``twist`` はaxis周りだけの回転、``swing`` はaxisの向きを変える残りの回転。
        om2の積の順序で ``twist * swing`` が自身と同じ回転になる(twistを先に、swingを後に適用する)。

        Args:
            axis (om2.MVector | Iterable[float]): 捻りの軸。中で正規化してから使う。

        Returns:
            tuple[Quaternion, Quaternion]: (swing, twist)。どちらも正規化してある。

        Raises:
            ValueError: axisが0のベクトルの場合、または自身が0のクォータニオンの場合。
        """
        ...
    def asRollBend(self, aimAxis: str = ..., upAxis: str = ..., *, unit: str = ...) -> tuple[float, float, float]:
        """ボーンの回転を、ロール(aimAxis周りの捻り)と、横・縦の曲げの角度へ分解する。

        自身を正規化して、``捻り * 曲げ`` に分ける。捻りを先に適用し、続けてaimAxisを最短経路で倒すのが曲げ。
        曲げは、upAxis周りのbendHと、横の軸(``aimAxis × upAxis``)周りのbendVで表す。

        曲げの2つの角度は、半角の正接で組み合わせる(``tan(全体の曲げ/2)² = tan(bendH/2)² + tan(bendV/2)²``)。
        そのため、片方が0なら、もう片方はその軸周りの回転角そのものになる。オイラー角と違い、回転順序の影響も受けない。
        ツイストの取り出しや、ポーズに応じたドライバーの値に使う。:meth:`fromRollBend` で元の回転へ戻せる。

        Args:
            aimAxis (str): ボーンの向きの軸。``"x"``・``"y"``・``"z"``・``"-x"``・``"-y"``・``"-z"`` のどれか。既定は ``"x"``。
            upAxis (str): アップ軸。aimAxisと違う軸にする。既定は ``"y"``。
            unit (str): 戻り値の角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。

        Returns:
            tuple[float, float, float]: (roll, bendH, bendV)。rollも曲げも-180〜180度。
                aimAxisが真後ろへ向く180度の曲げでは、曲げの向きが決まらない。

        Raises:
            TypeError: aimAxis・upAxisが文字列でない場合、またはunitが文字列・None以外の場合。
            ValueError: 軸の名前が正しくない場合、aimAxisとupAxisが同じ軸(符号だけ違う場合を含む)の場合、
                unitに対応していない場合、または自身が0のクォータニオンの場合。
        """
        ...
    def asDecomposedEulerRotate(self, order: str | int = ...) -> EulerRotate:
        """EulerRotateへ変換する。

        正規化した回転マトリクスを ``om2.MEulerRotation.decompose`` で分解する。
        そのため、``Matrix.euler`` と同じ規約の角度になる。
        同じ向きを表す別の解として、中間の軸が90度を超える角度を返すことがある。

        Args:
            order (str | int): 回転順序。``"xyz"``/``"yzx"``/``"zxy"``/``"xzy"``/
                ``"yxz"``/``"zyx"``、またはom2の番号0〜5。

        Returns:
            EulerRotate: ラジアンのEulerの回転値。

        Raises:
            ValueError: orderに対応していない場合、または0のクォータニオンの場合。
        """
        ...
    def mirror(self, axis: str | int = ...) -> Quaternion:
        """向きを「ビヘイビア」でミラーした、新しいクォータニオンを返す。

        ミラーの規約は :meth:`Matrix.mirror <mlib.maths.matrix.Matrix.mirror>` と同じ。

        Args:
            axis (str | int): 反転する軸。``"x"``・``"y"``・``"z"``、ミラー面の ``"YZ"``・``"XZ"``・``"XY"``、
                または0/1/2で指定する。x⇔YZ、y⇔XZ、z⇔XYが同じ意味になる。文字の順序と大文字・小文字は問わない。

        Returns:
            Quaternion: 自身と同じ型の新しい回転。

        Raises:
            TypeError: axisが文字列・int以外の場合。
            ValueError: axisが不正な場合。
        """
        ...
    def mirrorIt(self, axis: str | int = ...) -> Quaternion:
        """自身の向きを「ビヘイビア」でミラーする。

        Args:
            axis (str | int): 反転する軸。:meth:`mirror` と同じ。

        Returns:
            Quaternion: 更新した自身。
        """
        ...
    def asUnitMatrix(self) -> Matrix:
        """自身のコピーを正規化して、回転のマトリクスを作る。

        正規化するのはコピーで、自身は変更しない。
        OpenMayaの計算をそのまま使うasMatrix()と違い、正規化してから変換し、0のクォータニオンは例外にする。

        Returns:
            Matrix: 回転だけを持つ新しい4行4列のマトリクス。派生クラスで足したPythonの状態は引き継がない。

        Raises:
            ValueError: 自身が0のクォータニオンの場合。
        """
        ...
    def normal(self, *args) -> Quaternion:
        """OpenMayaの規則で正規化した、新しいQuaternionを返す。

        自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            Quaternion: 計算結果の新しい値。
        """
        ...
    def exp(self, *args) -> Quaternion:
        """クォータニオンの指数を、新しいQuaternionとして返す。

        自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            Quaternion: 計算結果の新しい値。
        """
        ...
    def log(self, *args) -> Quaternion:
        """クォータニオンの自然対数を、新しいQuaternionとして返す。

        自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            Quaternion: 計算結果の新しい値。
        """
        ...
    def safeLog(self) -> Quaternion:
        """自然対数を、新しいQuaternionとして返す。wが負なら、先に符号を反転する。

        符号を反転しても、表す回転は同じ。単位クォータニオンでは、結果の虚部の長さ(回転角の半分)がpi/2以下になる。
        qと-qは同じ回転を表すので、:meth:`log` の結果をそのまま足し合わせて回転を平均・補間すると、遠回りすることがある。
        このメソッドはそれを避けるために使う。

        Returns:
            Quaternion: 対数。自身は変更しない。
        """
        ...
    def asMatrix(self, *args) -> Matrix:
        """この回転を、同じ回転を表すマトリクスへ変換する。

        自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            Matrix: 計算結果の新しい値。
        """
        ...
    def asEulerRotation(self, *args) -> EulerRotate:
        """この回転を、同じ回転を表すEulerRotateへ変換する。

        自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            EulerRotate: 計算結果の新しい値。
        """
        ...
    def asEulerRotate(self, *args) -> EulerRotate:
        """この回転を、EulerRotateの新しい値として返す。

        中ではasEulerRotationを呼ぶ。

        Args:
            *args: OpenMayaのasEulerRotationへ渡す位置引数。

        Returns:
            EulerRotate: ラジアンのEulerの回転値。asEulerRotationと同じ結果になる。

        Note:
            OpenMayaのasEulerRotationも、これまでどおり使える。
            引数・例外・自身を変更しない点は、asEulerRotationと同じ。
        """
        ...
    def asAxisAngle(self) -> tuple[Vector, float]:
        """軸と角度の組へ分解する。軸はmlibのVectorで返す。

        計算はOpenMayaのMQuaternion.asAxisAngleで行う。

        Returns:
            tuple[Vector, float]: 軸と、ラジアンの角度。角度の範囲はOpenMayaに従う。
        """
        ...
    @classmethod
    def _wrap(cls, value: om2.MQuaternion | om2.MEulerRotation | om2.MMatrix) -> Quaternion:
        """om2 の値を複製した cls のインスタンスを返す。

        Python の ``__new__`` / ``__init__`` を通さない(利用者の派生クラスの
        ``__init__`` も呼ばない)。

        Args:
            value (om2.MQuaternion | om2.MEulerRotation | om2.MMatrix): 複製元。
                ``setValue`` が受け付ける値。

        Returns:
            Quaternion: cls の新しいインスタンス。
        """
        ...
    x: Any
    y: Any
    z: Any
    w: Any
