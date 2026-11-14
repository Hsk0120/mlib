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

#: fastで新しく作るカーブの型。駆動先のアトリビュート型から選ぶ(setDrivenKeyframeと同じ。他はanimCurveUU)。
_CURVE_TYPES = {"doubleLinear": "animCurveUL", "doubleAngle": "animCurveUA", "time": "animCurveUT"}

#: ドライバー・駆動先に使える数値スカラーのアトリビュート型名。
_NUMERIC_SCALAR_TYPES = frozenset(("double", "float", "doubleAngle", "doubleLinear", "time", "bool", "byte", "char", "short", "long", "enum"))


def _plug(value):
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
    if isinstance(value, (Plug, om2.MPlug)) or (isinstance(value, str) and "." in value):
        result = Plug._resolve_input(value)
    else:
        raise TypeError("Plug・MPlug・「ノード.アトリビュート」の文字列のどれかを指定してください")
    # Plug.isValidは所有ノードとアトリビュート(deleteAttrで消えた動的アトリビュートを含む)の存在を確かめる。
    if not result.isValid():
        raise RuntimeError("無効なPlugは使えません")
    if result.mplug().isArray or result.mplug().isCompound:
        raise ValueError("マルチアトリビュートやコンパウンドアトリビュートではなく、スカラーのPlugを指定してください")
    if attributeType(result.mplug()) not in _NUMERIC_SCALAR_TYPES:
        raise ValueError("数値のスカラーのPlugを指定してください")
    return result


def _contains_plug(plugs, mplug):
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
    return any(candidate == mplug for candidate in plugs)


def _sources(plug):
    """入力元のPlugを返す。

    間にある単位変換ノードは飛ばしてたどる。マルチアトリビュートの要素も含める。

    Args:
        plug (Plug | str): 接続元を調べるアトリビュート。

    Returns:
        list[Plug]: 単位変換ノードを飛ばした先の接続元。接続されていなければ空。
    """
    return Plug._resolve_input(plug).getConnections(source=True, destination=False, skipConversionNodes=True)


def _curves(driven, strict=False):
    """駆動先から入力をたどり、入力が単位なしのカーブを集める。

    blendWeightedがあれば、その入力もたどる。

    Args:
        driven (Plug): ドリブンキーで動かすアトリビュート。
        strict (bool): Trueなら、対応していない接続の形を例外にする。

    Returns:
        list[AnimCurve]: 駆動先の入力へつながる、入力が単位なしのカーブ。同じものは1回だけ含む。
    """
    found, visited = [], []

    def visit(destination):
        """接続を再帰的にたどる。知らない形の接続は、strictなら例外にする。

        Args:
            destination (Plug): 接続元を調べるアトリビュート。

        Returns:
            None: 値を返さない。
        """
        for source in _sources(destination):
            if _contains_plug(visited, source.mplug()):
                continue
            visited.append(source.mplug())
            node = source.getNode()
            attribute, kind = source.getLongName(), node.getType()
            if kind in {"animCurveUA", "animCurveUL", "animCurveUT", "animCurveUU"} and attribute == "output":
                found.append(node)
            elif kind == "blendWeighted" and attribute == "output":
                visit(node.getPlug("input"))
            elif strict:
                raise RuntimeError(
                    f"{driven.getFullName()}にドリブンキーを設定できません: {destination.getFullName()}にはすでに{source.getFullName()}({kind})からの入力があり、これはドリブンキーのカーブではありません。先に切断するか(plug.disconnectInput()など)、blendWeightedノードで両方の入力をまとめてください"
                )

    visit(driven)
    return found


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

    def __init__(self, driver, driven):
        """既存の数値のPlugを2つ持つ。ドリブンキーがまだ無くても作れる。

        Args:
            driver (Plug | om2.MPlug | str): ドライバーのアトリビュート。文字列は ``"node.attribute"`` の形で書く。
            driven (Plug | om2.MPlug | str): 動かされるアトリビュート。

        Raises:
            TypeError: Plug・MPlug・アトリビュート名のどれでもない場合。
            ValueError: スカラーでない場合、数値でない場合、または2つが同じアトリビュートの場合。
            RuntimeError: アトリビュートが存在しない場合。
        """
        self._driver, self._driven = _plug(driver), _plug(driven)
        if self._driver.mplug() == self._driven.mplug():
            raise ValueError("ドライバーとドリブンは別のPlugで指定してください")

    def __repr__(self):
        """ドライバーと駆動先のアトリビュート名を含む表示を返す。

        Returns:
            str: ドライバーと駆動先のアトリビュート名を含む表示。
        """
        return f"DrivenKey({self.getDriverPlug().getFullName()!r}, {self.getDrivenPlug().getFullName()!r})"

    @classmethod
    def find(cls, driven):
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
        target = _plug(driven)
        items, seen = [], []
        for curve in _curves(target):
            for source in _sources(curve.getPlug("input")):
                try:
                    driver = _plug(source)
                except ValueError:
                    continue  # 数値スカラーでないドライバーは DrivenKey の対象外。
                if not _contains_plug(seen, driver.mplug()):
                    seen.append(driver.mplug())
                    items.append(cls(driver, target))
        return items

    def getDriverPlug(self):
        """ドライバーのアトリビュートのPlugを取得する。

        持っているアトリビュートを、もう一度確かめてから返す。

        Returns:
            Plug: 同じアトリビュートのオブジェクト。今の値を取得したり、コピーしたりはしない。

        Raises:
            RuntimeError: 削除などで、アトリビュートが無くなっている場合。
        """
        return _plug(self._driver)

    def getDrivenPlug(self):
        """駆動先のアトリビュートのPlugを取得する。

        持っているアトリビュートを、もう一度確かめてから返す。

        Returns:
            Plug: 同じアトリビュートのオブジェクト。今の値を取得したり、コピーしたりはしない。

        Raises:
            RuntimeError: 削除などで、アトリビュートが無くなっている場合。
        """
        return _plug(self._driven)

    def getCurves(self):
        """このドライバーと駆動先の組のカーブを取得する。

        接続は毎回調べる。ほかのドライバーのカーブや、blendWeightedのweightの入力は含めない。
        ドライバーは名前ではなくプラグそのもので比べる。そのため、インスタンス化されたシェイプの
        アトリビュートを、どのインスタンスのパスから指定しても同じ関係として扱う。

        Returns:
            list[AnimCurve]: この組のカーブ。まだ無い場合と、対象にならない形の場合は空。
        """
        driver = self.getDriverPlug().mplug()
        return [curve for curve in _curves(self.getDrivenPlug()) if _contains_plug((source.mplug() for source in _sources(curve.getPlug("input"))), driver)]

    def exists(self):
        """この組のカーブがつながっているか調べる。

        カーブにキーが1つも無くてもTrueになる。

        Returns:
            bool: この組のカーブがつながっていればTrue。キーが無くてもTrue。
        """
        return bool(self.getCurves())

    def setKey(self, driverValue, value, inTangentType="linear", outTangentType="linear", *, unit="deg", timeUnit="frame", fast=False):
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
        with _edit_context("mlibDrivenKeySetKey", fast):
            angle_unit = _angle_unit(unit)
            time_unit = _time_unit(timeUnit)
            x, y = float(driverValue), float(value)
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("キーの値は有限な数値で指定してください")
            driver, driven = self.getDriverPlug(), self.getDrivenPlug()
            # 角度・時間の値を内部単位(rad・秒)へ揃えてから、Mayaコマンドが受け取るUI単位へ換算する。
            x = _convert_times(driver.mplug(), _convert_angles(driver.mplug(), x, angle_unit), time_unit)
            _curves(driven, strict=True)
            curves = self.getCurves()
            if len(curves) > 1:
                raise RuntimeError("このドライバーとドリブンの組に、複数のカーブが一致します")
            if fast:
                # カーブの横軸はドライバーのUI単位(unitConversion経由の値)。縦軸はAnimCurve.setKeyが換算する。
                self._set_key_fast(curves, _convert_units(driver.mplug(), x), y, inTangentType, outTangentType, unit, timeUnit)
                return self
            y = _convert_times(driven.mplug(), _convert_angles(driven.mplug(), y, angle_unit), time_unit)
            count = cmds.setDrivenKeyframe(
                driven.getFullName(),
                currentDriver=driver.getFullName(),
                driverValue=_convert_units(driver.mplug(), x),
                value=_convert_units(driven.mplug(), y),
                inTangentType=inTangentType,
                outTangentType=outTangentType,
                insertBlend=False,
            )
            if not count:
                raise RuntimeError("Mayaがドリブンキーを設定しませんでした")
            # 現在値と異なる位置のキー更新後も、駆動先が古い評価値を保持しないようにする。
            cmds.dgdirty([curve.getFullName() for curve in self.getCurves()])
            return self

    def _set_key_fast(self, curves, input, value, inTangentType, outTangentType, unit, timeUnit):
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
        # カーブを作る前に接線型を検証し、未対応の指定でノードを残さない。
        AnimCurve._tangent_type(inTangentType, incoming=True, key=True)
        AnimCurve._tangent_type(outTangentType, key=True)
        if curves:
            curve = curves[0]
        else:
            driver, driven = self.getDriverPlug(), self.getDrivenPlug()
            if _sources(driven):
                raise NotImplementedError(
                    f"fastのsetKeyは{driven.getFullName()}への2つ目のドライバーに対応していません(MayaがblendWeightedノードを挿入するため)"
                )
            require_writable(driven.mplug())
            kind = _CURVE_TYPES.get(attributeType(driven.mplug()), "animCurveUU")
            # setDrivenKeyframeと同じく、名前空間を除いたノード名とエイリアス(無ければロング名)を使う。
            attribute = driven.mplug().partialName(useAlias=True, useLongNames=True)
            name = driven.getNode().getName().rpartition("|")[2].rpartition(":")[2] + "_" + attribute
            for character in "[].":
                name = name.replace(character, "_")
            curve = Node._create_node(kind, {"name": name.rstrip("_"), "skipSelect": True}, fast=True)
            curve.getPlug("input").connect(driver, fast=True)
            driven.connect(curve.getPlug("output"), fast=True)
        curve.setKey(input, value, inTangentType, outTangentType, unit=unit, timeUnit=timeUnit, fast=True)
