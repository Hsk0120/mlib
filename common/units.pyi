# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""シーン設定を書き換えずに距離・角度・時間を変換する。"""

import re
import maya.api.OpenMaya as om2
from ..util import _angle_unit, _time_unit


def distanceToUi(centimeters: float) -> float:
    """cmの距離を、現在のUI距離単位の数値へ変換する。

    Args:
        centimeters (float): cm単位の距離。

    Returns:
        float: 現在のUI距離単位で表した値。
    """
    ...

def _distance_unit(unit: str | None) -> int:
    """距離単位名をOpenMayaの単位へ解決する。

    Args:
        unit (str | None): 単位の名前。Mayaの長い名前と短い名前のどちらでもよい。Noneなら現在のUI単位。

    Returns:
        int: MDistanceの単位定数。

    Raises:
        TypeError: 文字列またはNoneでない場合。
        ValueError: 未対応の単位名の場合。
    """
    ...

def convertDistance(value: float, fromUnit: str | None = ..., toUnit: str | None = ...) -> float:
    """距離の単位を変換する。

    シーンの単位の設定は変えない。

    Args:
        value (float): 変換する距離。
        fromUnit (str | None): valueの単位。Noneなら現在のシーンの単位。
        toUnit (str | None): 戻り値の単位。Noneなら現在のシーンの単位。
            fromUnitとtoUnitには、mm/cm/m/km/in/ft/yd/miか、Mayaの長い名前(meterなど)を指定する。

    Returns:
        float: toUnitの単位で表した距離。

    Raises:
        TypeError: 単位が文字列でもNoneでもない場合。
        ValueError: 対応していない単位名の場合。
    """
    ...

def distanceFromUi(value: float) -> float:
    """現在のUI距離単位の数値を、cmへ変換する。

    Args:
        value (float): 現在のUI距離単位で表した値。

    Returns:
        float: cm単位の距離。
    """
    ...

def _angle_constant(unit: str) -> int:
    """角度の単位名をMAngleの単位定数へ解決する。

    Args:
        unit (str): ``"deg"`` / ``"rad"`` と ``"degree"`` 等の別名。

    Returns:
        int: MAngleの単位定数。

    Raises:
        TypeError: unitが文字列・None以外の場合。
        ValueError: 未対応の単位名の場合。
    """
    ...

def angleToUi(value: float, *, unit: str = ...) -> float:
    """角度を現在のUI角度単位の数値へ変換する。

    Args:
        value (float): unitの単位の角度。
        unit (str): valueの単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
            ``"degree"`` / ``"radians"`` などの別名も使える。

    Returns:
        float: 現在のUI角度単位で表した値。

    Raises:
        TypeError: unitが文字列・None以外の場合。
        ValueError: unitが未対応の単位名の場合。
    """
    ...

def angleFromUi(value: float, *, unit: str = ...) -> float:
    """現在のUI角度単位の数値を、指定単位の角度へ変換する。

    Args:
        value (float): 現在のUI角度単位で表した値。
        unit (str): 戻り値の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
            ``"degree"`` / ``"radians"`` などの別名も使える。

    Returns:
        float: unitの単位の角度。

    Raises:
        TypeError: unitが文字列・None以外の場合。
        ValueError: unitが未対応の単位名の場合。
    """
    ...

def convertAngle(value: float, fromUnit: str | None = ..., toUnit: str | None = ...) -> float:
    """角度の単位を変換する。

    シーンの単位の設定は変えない。

    Args:
        value (float): 変換する角度。
        fromUnit (str | None): valueの単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
            ``"degree"`` / ``"radians"`` などの別名も使える。Noneなら現在のUI角度単位。
        toUnit (str | None): 戻り値の単位。指定の仕方はfromUnitと同じ。既定は ``"rad"``。

    Returns:
        float: toUnitの単位で表した角度。

    Raises:
        TypeError: 単位が文字列でもNoneでもない場合。
        ValueError: 対応していない単位名の場合。
    """
    ...

def _time_constant(unit: str | None) -> int:
    """時間の単位名をMTimeの単位定数へ解決する。

    Args:
        unit (str | None): ``"frame"`` (現在のUI時間単位)・``"sec"`` とその別名、
            Mayaの ``currentUnit -time`` の名前(``"film"``・``"ntsc"``・``"24fps"``・``"29.97df"`` 等)。
            Noneは現在のUI時間単位。

    Returns:
        int: MTimeの単位定数。

    Raises:
        TypeError: 文字列またはNoneでない場合。
        ValueError: 未対応の単位名の場合。
    """
    ...

def convertTime(value: float, fromUnit: str | None = ..., toUnit: str | None = ...) -> float:
    """時間の単位を変換する。

    シーンの単位の設定は変えない。

    Args:
        value (float): 変換する時間。
        fromUnit (str | None): valueの単位。Noneと ``"frame"`` は現在のUI時間単位のフレーム、``"sec"`` は秒。
            ``"frames"`` / ``"seconds"`` などの別名も使える。Mayaの時間単位の名前(``"film"``・``"ntsc"``・
            ``"pal"``・``"game"``・``"hour"``・``"min"``・``"millisec"``・``"24fps"``・``"29.97df"`` など)も指定できる。
        toUnit (str | None): 戻り値の単位。指定の仕方はfromUnitと同じ。

    Returns:
        float: toUnitの単位で表した時間。

    Raises:
        TypeError: 単位が文字列でもNoneでもない場合。
        ValueError: 対応していない単位名の場合。
    """
    ...

def secondsPerFrame() -> float:
    """現在の時間単位で、1フレームが何秒かを取得する。

    Returns:
        float: 1フレームの秒数。
    """
    ...
