# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ドリブンキーの、ドライバーのPlugと駆動先のPlugの組を扱う。"""

import math
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.attributeType import _convert_angles, _convert_times, _convert_units, attributeType
from ..core.fastWrite import require_writable
from ..decorator import _edit_context
from ..nodes.animCurve import AnimCurve
from ..nodes.node import Node
from ..plugs.plug import Plug
from ..util import _angle_unit, _time_unit
from typing import Iterable

_CURVE_TYPES: dict
_NUMERIC_SCALAR_TYPES: frozenset

def _plug(value: Plug | om2.MPlug | str) -> Plug:
    """Plug・MPlug・アトリビュート名が、数値のスカラーのPlugを指すか確かめる。

    文字列は Plug と同じ方法で探すため、``str(plug)`` が返す形
    (``grp1|dup.tx``、``bs.weight[0]``、エイリアス名、``cubeShape.pnts[1].pntx`` など)をそのまま渡せる。

    - アトリビュートが見つからない場合や、名前が1つに決まらない場合は RuntimeError。
    - アトリビュートを指さない文字列や、対応していない型は TypeError。

    アトリビュートの型はアトリビュートの定義から判定する(:func:`mlib.core.attributeType.attributeType`)。
    そのため、確かめるときにシーンは変更しない。

    Args:
        value (Plug | om2.MPlug | str): 数値のスカラーのPlug、またはアトリビュート名。

    Returns:
        Plug: 有効な、数値のスカラーのアトリビュートのオブジェクト。
    """
    ...

def _contains_plug(plugs: Iterable[om2.MPlug], mplug: om2.MPlug) -> bool:
    """同じプラグが含まれているか調べる。

    持ち主のノード・アトリビュート・論理番号がすべて同じなら、同じプラグとみなす。
    インスタンス化されたシェイプのアトリビュートは、どのインスタンスのパスから取得しても同じ
    プラグになる。名前(インスタンスのパスを含む ``getFullName()``)では比べない。

    Args:
        plugs (Iterable[om2.MPlug]): 比べる相手のプラグ。
        mplug (om2.MPlug): 探すプラグ。

    Returns:
        bool: 同じプラグが含まれる場合は True。
    """
    ...

def _sources(plug: Plug | str) -> list[Plug]:
    """入力元のPlugを返す。

    間にある単位変換ノードは飛ばしてたどる。マルチアトリビュートの要素も含める。

    Args:
        plug (Plug | str): 接続元を調べるアトリビュート。

    Returns:
        list[Plug]: 単位変換ノードを飛ばした先の接続元。接続されていなければ空。
    """
    ...

def _curves(driven: Plug, strict: bool = ...) -> list[AnimCurve]:
    """駆動先から入力をたどり、入力が単位なしのカーブを集める。

    blendWeightedがあれば、その入力もたどる。

    Args:
        driven (Plug): ドリブンキーで動かすアトリビュート。
        strict (bool): Trueなら、対応していない接続の形を例外にする。

    Returns:
        list[AnimCurve]: 駆動先の入力へつながる、入力が単位なしのカーブ。同じものは1回だけ含む。
    """
    ...


class DrivenKey:
    """ドリブンキーの関係を扱う。

    数値のスカラーのドライバーのPlugと、駆動先のPlugを持つ。

    - 作るときは2つのPlugを確かめるだけで、カーブや接続は作らない。
    - 接続は問い合わせるたびに調べる。たどるのは、単位変換ノードと、blendWeightedのinputを経由する接続。
    - pairBlend・アニメーションレイヤー・任意の計算ノードまでたどる、何にでも使える探索ではない。

    setKeyの数値は、次の単位で受け取り、Mayaのコマンドへ渡すときにUI単位へ変換する。

    - 角度のアトリビュート: 既定は度(``unit="rad"`` でラジアン)。
    - 距離: cm。
    - 時間のアトリビュート: 既定は現在のUI時間単位のフレーム(``timeUnit="sec"`` で秒)。

    AnimCurveのU型のカーブ(入力に単位が無いカーブ)へ渡す値とは別物なので、混同しないこと。
    """
    def __init__(self, driver: Plug | om2.MPlug | str, driven: Plug | om2.MPlug | str) -> None:
        """既存の数値のPlugを2つ持つ。ドリブンキーがまだ無くても作れる。

        Args:
            driver (Plug | om2.MPlug | str): ドライバーのアトリビュート。文字列は ``"node.attribute"`` の形で書く。
            driven (Plug | om2.MPlug | str): 動かされるアトリビュート。

        Raises:
            TypeError: Plug・MPlug・アトリビュート名のどれでもない場合。
            ValueError: スカラーでない場合、数値でない場合、または2つが同じアトリビュートの場合。
            RuntimeError: アトリビュートが存在しない場合。
        """
        ...
    def __repr__(self) -> str:
        """ドライバーと駆動先のアトリビュート名を含む表示を返す。

        Returns:
            str: ドライバーと駆動先のアトリビュート名を含む表示。
        """
        ...
    @classmethod
    def find(cls, driven: Plug | om2.MPlug | str) -> list[DrivenKey]:
        """駆動先につながっているドリブンキーの関係を取得する。

        シーンは変更しない。

        Args:
            driven (Plug | om2.MPlug | str): 探す駆動先のアトリビュート。文字列は ``"node.attribute"`` の形で書く。

        Returns:
            list[DrivenKey]: ドライバーごとの関係。対象にならない形は含めない
                (数値のスカラーでないドライバーや、``choice.output`` のように値によって型が
                変わる generic アトリビュートなど)。同じドライバー(プラグそのもので比べる)は1件にまとめる。

        Raises:
            TypeError: driven が Plug・MPlug・アトリビュート名のどれでもない場合。
            ValueError: driven がスカラーでない場合、または数値でない場合。
            RuntimeError: driven のアトリビュートが存在しない場合。
        """
        ...
    def getDriverPlug(self) -> Plug:
        """ドライバーのアトリビュートのPlugを取得する。

        持っているアトリビュートを、もう一度確かめてから返す。

        Returns:
            Plug: 同じアトリビュートのオブジェクト。今の値を取得したり、コピーしたりはしない。

        Raises:
            RuntimeError: 削除などで、アトリビュートが無くなっている場合。
        """
        ...
    def getDrivenPlug(self) -> Plug:
        """駆動先のアトリビュートのPlugを取得する。

        持っているアトリビュートを、もう一度確かめてから返す。

        Returns:
            Plug: 同じアトリビュートのオブジェクト。今の値を取得したり、コピーしたりはしない。

        Raises:
            RuntimeError: 削除などで、アトリビュートが無くなっている場合。
        """
        ...
    def getCurves(self) -> list[AnimCurve]:
        """このドライバーと駆動先の組のカーブを取得する。

        接続は毎回調べる。ほかのドライバーのカーブや、blendWeightedのweightの入力は含めない。
        ドライバーは名前ではなくプラグそのもので比べる。そのため、インスタンス化されたシェイプの
        アトリビュートを、どのインスタンスのパスから指定しても同じ関係として扱う。

        Returns:
            list[AnimCurve]: この組のカーブ。まだ無い場合と、対象にならない形の場合は空。
        """
        ...
    def exists(self) -> bool:
        """この組のカーブがつながっているか調べる。

        カーブにキーが1つも無くてもTrueになる。

        Returns:
            bool: この組のカーブがつながっていればTrue。キーが無くてもTrue。
        """
        ...
    def setKey(self, driverValue: float, value: float, inTangentType: str = ..., outTangentType: str = ..., *, unit: str = ..., timeUnit: str = ..., fast: bool = ...) -> DrivenKey:
        """ドライバーの値と駆動先の値を指定して、ドリブンキーを追加または更新する。

        2つの値はfloat()で数値にし、有限か確かめる。それぞれのPlugの定義に従ってUI単位へ変換し、
        setDrivenKeyframeを呼ぶ。ドライバーの今の値と、シーンの時刻は変えない。
        キーを作ったあとは、そのカーブをdgdirtyで更新が必要な状態にし、駆動先を評価し直させる。
        Undoが有効なら1回のチャンクにまとめる。

        ``fast=True`` なら、Undoに記録せずOpenMayaで更新する。

        - この組のカーブがあれば、:meth:`AnimCurve.setKey <mlib.nodes.animCurve.AnimCurve.setKey>` のfastで
          キーを追加または更新する。
        - 無ければ、setDrivenKeyframeと同じ型・名前のカーブを作り、ドライバー→カーブ→駆動先とつなぐ
          (単位の違う接続には、Mayaが自動でunitConversionを挟む)。
          型は、駆動先が距離ならanimCurveUL、角度ならanimCurveUA、時間ならanimCurveUT、それ以外はanimCurveUU。
          名前は、名前空間を除いた ``<駆動先ノード>_<アトリビュート>`` (エイリアスがあればエイリアス)。

        Args:
            driverValue (float): ドライバーの値。角度はunitの単位(既定は度)、距離はcm、
                時間はtimeUnitの単位(既定はフレーム)、それ以外は単位なし。
            value (float): 駆動先の値。単位はdriverValueとは別に、駆動先のアトリビュートの定義で決まる。
            inTangentType (str): Mayaの入力側の接線の型。
            outTangentType (str): Mayaの出力側の接線の型。
            unit (str): 角度のアトリビュートの値の単位。既定の ``"deg"`` は度、``"rad"`` はラジアン
                (``"degree"`` / ``"radians"`` などの別名でもよい)。角度以外のアトリビュートでは使わない。
            timeUnit (str): 時間のアトリビュートの値の単位。既定の ``"frame"`` は現在のUI時間単位のフレーム、
                ``"sec"`` は秒(``"seconds"`` などの別名でもよい)。時間以外のアトリビュートでは使わない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DrivenKey: 自身。

        Raises:
            TypeError: 値の型がfloat()で変換できない場合、unit・timeUnitが文字列でもNoneでもない場合、
                またはfastがboolでない場合。
            ValueError: 値が有限でない場合、float()で変換できない場合、unit・timeUnitが対応していない単位名の場合、
                またはfastで、fixed・globalなど直接設定できない接線の型を指定した場合。
            RuntimeError: 対象にならない入力の接続がある場合、同じ組にカーブが複数ある場合、
                駆動先がロックされている場合、またはMayaがキーの作成を拒否した場合。
            NotImplementedError: fastで、この組のカーブが無く、駆動先にほかのドライバーのカーブがすでに
                つながっている場合(MayaならblendWeightedを挟む)、または入力側の接線にstepnextを指定した場合。
                どちらも、何も変更する前にエラーにする。

        Note:
            複数のドライバーをまとめるときは、Maya標準のblendWeightedを使う。
            pairBlendを自動で挟むことはしない。最終的な出力は、ほかのカーブやまとめるときのウェイトにも左右される。
            途中で失敗した場合に、自動で元へ戻すことはしない。
        """
        ...
    def _set_key_fast(self, curves: list[AnimCurve], input: float, value: float, inTangentType: str, outTangentType: str, unit: str, timeUnit: str) -> None:
        """:meth:`setKey` のfastの処理。必要ならカーブを作ってつなぎ、OpenMayaでキーを書き込む。

        Args:
            curves (list[AnimCurve]): この組のカーブ(0個か1個)。
            input (float): カーブの横軸の値(ドライバーのUI単位)。
            value (float): 駆動先の値。:meth:`setKey` のvalueと同じ単位。
            inTangentType (str): Mayaの入力側の接線の型。
            outTangentType (str): Mayaの出力側の接線の型。
            unit (str): 角度の値の単位。
            timeUnit (str): 時間の値の単位。

        Returns:
            None: 値を返さない。
        """
        ...
