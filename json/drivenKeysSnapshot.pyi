# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ドリブンキーを保存・復元する。

ドリブンキーとは、ドライバーのアトリビュートを入力にするアニメカーブと、その間にあるノードのこと。
"""

import math
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..cmds import getPlug
from ..common.drivenKey import DrivenKey
from ..core.attributeType import _from_seconds
from ._animCurveData import _is_time_input, _output_kind, _read_curve, _require_curve, _write_curve
from .animationSnapshot import _require_nodes
from .plugRef import PlugRef
from .snapshot import Snapshot
from typing import Iterable
from mlib.json.nameMapping import NameMapping
from mlib.json.snapshot import ValidationReport
from mlib.nodes.node import Node
from mlib.plugs.plug import Plug



class DrivenKeysSnapshot(Snapshot):
    """駆動されるアトリビュートごとに、ドライバーのPlug・カーブ・blendWeightedの重みを持つ。

    カーブは :class:`~mlib.json.animationSnapshot.AnimationSnapshot` と同じく、すべての内容を保存する。

    カーブの入力(ドライバーの値)は、ドライバーのアトリビュートのmlibの単位(角度は度、距離はcm、
    時間はフレーム)へ直して保存する。Mayaがドライバーとカーブの間に入れるunitConversionの係数は、
    保存したときのUIの単位で決まる。そのため適用するときは、作り直された係数に合わせて入力を換算する。
    値はカーブの出力の単位(角度は度、距離はcm、それ以外は単位なし)。

    複数のドライバーを合計するblendWeightedは、Mayaのドリブンキーの設定(``setDrivenKeyframe``)で作り直し、
    それぞれの入力の重み(weight)を元に戻す。

    データの形::

        {"items": [{"driven": {<PlugRef>}, "blendWeighted": False,
                    "drivers": [{"driver": {<PlugRef>}, "weight": 1.0, "curve": {<カーブ>}}, ...]}, ...]}

    Examples:
        >>> keys = DrivenKeysSnapshot.capture(mlib.ls("*_corrective_jnt"))
        >>> keys.save("drivenKeys.json")
        >>> DrivenKeysSnapshot.load("drivenKeys.json").apply(replace=[("_L_", "_R_")])
    """
    FORMAT: str
    VERSION: int
    @classmethod
    def capture(cls, nodes: Iterable[Node | str]) -> DrivenKeysSnapshot:
        """駆動されるノードのアトリビュートから、ドリブンキーを取得する。

        対象は、アトリビュートの入力につながる、入力に単位の無いカーブ(animCurveU*)と、blendWeightedを通る
        カーブ。ドライバーにつながっていないカーブと、blendWeightedへのカーブ以外の入力は保存しない。

        Args:
            nodes (Iterable[Node | str]): 駆動されるノード。Nodeや名前を1つだけ渡してもよい。

        Returns:
            DrivenKeysSnapshot: 取得したドリブンキーを持つ新しいインスタンス。

        Raises:
            TypeError: nodesがノードでもその並びでもない場合。
            RuntimeError: ノードが無い場合。
        """
        ...
    def apply(self, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ...) -> ValidationReport:
        """保存したドリブンキーを、対応づけたドライバーと駆動先で作り直す。

        ドライバーと駆動先の組ごとに、次のように書く。

        - すでにカーブがあれば、そのすべてのキーを置き換える。
        - 無ければ、Mayaのドリブンキーの設定(``setDrivenKeyframe``。必要ならblendWeighted・unitConversionも
          作られる)でカーブを作ってから書く。

        保存していない、ほかのドライバーのカーブは変えない。1回のUndoにまとめ、途中で失敗したら元に戻す。

        書き戻せないものは飛ばして記録し、最後にまとめて警告する。

        - ``missing``: 見つからないドライバー・駆動先。
        - ``skipped``: ロックされた駆動先。ドリブンキー以外(コンストレイント・入力が時間のカーブなど)が
          入力につながった駆動先。出力の種類が違うカーブ。

        fast引数は持たない(ドリブンキーはキーが少なく、作成はcmdsで行うので、速くならない)。

        Args:
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。ドライバーと駆動先の両方に当てる。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。
            namespaceMap (dict[str, str] | None): 名前空間の対応。

        Returns:
            ValidationReport: 適用の結果。
        """
        ...
    def _require_data(self, data: dict):
        """``items`` の形を確かめる。

        Args:
            data (dict): 持たせる前のデータ。

        Raises:
            ValueError: データの形が正しくない場合。
        """
        ...
    def _validate(self, mapping: NameMapping, report: ValidationReport, options: dict):
        """見つからないドライバー・駆動先を記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 使わない。
        """
        ...
    def _apply(self, mapping: NameMapping, report: ValidationReport, options: dict, fast: bool):
        """ドライバーと駆動先の組ごとにカーブを用意し、キーを書き込む。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 使わない。
            fast (bool): 使わない(常にcmdsで書く)。
        """
        ...

def _apply_driver(driver: Plug, driven: Plug, saved: dict, report: ValidationReport):
    """ドライバーと駆動先の組のカーブを用意し、保存したキーで書き直す。

    Args:
        driver (Plug): ドライバー。
        driven (Plug): 駆動先。
        saved (dict): 保存したドライバーの項目。
        report (ValidationReport): 記録先。
    """
    ...

def _resolve(data: dict, mapping: NameMapping, report: ValidationReport) -> Plug | None:
    """PlugRefの辞書からPlugを探し、見つからなければreportへ記録する。

    Args:
        data (dict): PlugRefの辞書。
        mapping (NameMapping): 名前の対応づけ。
        report (ValidationReport): 記録先。

    Returns:
        Plug | None: 見つかったPlug。
    """
    ...

def _blend_curves(blend: str) -> list[tuple[str, int]]:
    """blendWeightedのそれぞれの入力につながる、ドリブンキーのカーブを集める。

    Args:
        blend (str): blendWeightedノードの名前。

    Returns:
        list[tuple[str, int]]: カーブ名と、blendWeightedの入力の番号。
    """
    ...

def _driver(curve: str) -> str | None:
    """カーブの入力につながるドライバーのPlug名を返す。

    Args:
        curve (str): カーブ名。

    Returns:
        str | None: ドライバーのPlug名。つながっていなければNone。
    """
    ...

def _input_scale(curve: str, driver: str) -> float:
    """カーブの入力の値を、ドライバーのmlibの単位の値へ直す倍率を返す。

    カーブの入力の値にこの倍率を掛けると、ドライバーのmlibの単位の値になる。
    カーブの入力は、ドライバーの内部の単位(rad・cm・秒)の値に、unitConversionの係数を掛けた値になっている。

    Args:
        curve (str): カーブ名。
        driver (str): ドライバーのPlug名。

    Returns:
        float: 倍率。
    """
    ...
