# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ノードのアニメーションを保存・復元する。対象は、入力が時間のアニメカーブとアニメーションレイヤー。"""

import math
import maya.cmds as cmds
from ..decorator import _require_bool
from ..nodes.node import Node
from ._animCurveData import _is_time_input, _merge_keys, _output_kind, _read_curve, _require_curve, _transform_keys, _write_curve
from .plugRef import PlugRef
from .snapshot import Snapshot
from typing import Iterable
from mlib.json.nameMapping import NameMapping
from mlib.json.snapshot import ValidationReport
from mlib.plugs.plug import Plug

_MODES: tuple
_LAYER_FLAGS: tuple
_LAYER_ENUMS: tuple


class AnimationSnapshot(Snapshot):
    """ノードのアトリビュートにつながるアニメカーブを、アニメーションレイヤーごとに持つ。

    対象は、入力が時間のアニメカーブ。カーブは次の内容まで保存し、同じ形に作り直す。

    - キーの時刻と値
    - 接線の型・角度・ウェイト、接線とウェイトのロック、ブレークダウン
    - ウェイト付き接線かどうか、前後のインフィニティ

    値はmlibの既定の単位(角度は度、距離はcm)、時刻は保存したときのUIの時間の単位でのフレームで保存する。
    そのため、適用するときのUIの単位には左右されない。

    アニメーションレイヤーに入ったアトリビュートは、ベースレイヤーとそれぞれのレイヤーのカーブを別々に保存する。
    レイヤーの設定(ウェイト・ミュート・ソロ・ロック・オーバーライド・パススルー・回転と
    スケールの累積モード・親レイヤー)も保存する。

    ドリブンキー(入力に単位の無いカーブ)は :class:`~mlib.json.drivenKeysSnapshot.DrivenKeysSnapshot` で扱う。

    データの形::

        {"timeRange": [1.0, 24.0] or None, "rootLayer": "BaseAnimation" or None,
         "layers": [{"name": "L1", "parent": None, "weight": 1.0, "mute": False, "solo": False, "lock": False,
                     "override": False, "passthrough": True, "rotationAccumulationMode": "...",
                     "scaleAccumulationMode": "..."}, ...],
         "curves": [{"plug": {<PlugRef>}, "layer": None or "L1", "curve": {<カーブ>}}, ...]}

    ``layer`` がNoneのカーブは、ベースレイヤーのカーブ(レイヤーが無ければ、アトリビュートへ直接つながるカーブ)。
    カーブの辞書の形は ``mlib/json/_animCurveData.py`` の説明を参照する。

    Examples:
        >>> anim = AnimationSnapshot.capture(mlib.ls(type="joint"), time=(1, 24))
        >>> anim.save("walk.json")
        >>> AnimationSnapshot.load("walk.json").apply(namespaceMap={"chrA": "chrB"}, mode="insert", timeOffset=100)
    """
    FORMAT: str
    VERSION: int
    @classmethod
    def capture(cls, nodes: Iterable[Node | str], *, time: tuple[float, float] | None = ...) -> AnimationSnapshot:
        """ノードのアトリビュートにつながるアニメカーブと、アニメーションレイヤーを取得する。

        入力が時間のアニメカーブが対象。次のカーブを取得する。

        - アトリビュートへ直接つながるカーブ。
        - アニメーションレイヤーに入ったアトリビュートの、ベースレイヤーとそれぞれのレイヤーのカーブ。

        キーが1つも無い(範囲の中に無い)カーブは保存しない。
        保存したレイヤーの親レイヤーも保存する。ただしルート(BaseAnimation)は除く。

        Args:
            nodes (Iterable[Node | str]): 対象のノード。Nodeや名前を1つだけ渡してもよい。
            time (tuple[float, float] | None): 時刻の範囲。両端を含み、今のUIの時間の単位でのフレームで指定する。
                範囲の中のキーだけを保存する。Noneならすべてのキー。既定はNone。

        Returns:
            AnimationSnapshot: 取得したカーブを持つ新しいインスタンス。

        Raises:
            TypeError: nodesがノードでもその並びでもない場合、またはtimeが2つの数値の並びでない場合。
            ValueError: timeが有限な値でない場合、または開始が終了より大きい場合。
            RuntimeError: ノードが無い場合。
        """
        ...
    def apply(self, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ..., mode: str = ..., timeOffset: float = ..., timing: str = ..., createLayers: bool = ..., fast: bool = ...) -> ValidationReport:
        """保存したカーブを、対応づけたノードのアトリビュートへ書き戻す。

        カーブが無いアトリビュートには、新しく作る。通常は1回のUndoにまとめ、途中で失敗したら元に戻す。

        書き戻せないものは飛ばして記録し、最後にまとめて警告する。

        - ``missing``: 見つからないノード・アトリビュート。
        - ``skipped``: ロックされたアトリビュート。アニメカーブ・アニメーションレイヤー以外
          (コンストレイント・ドリブンキーなど)が入力につながったアトリビュート。
          出力の種類(角度・距離など)が違うカーブ。見つからない、またはロックされたレイヤーのカーブ。

        Args:
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。既定はNone。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。既定はNone。
            namespaceMap (dict[str, str] | None): 名前空間の対応。レイヤー名には当てない。既定はNone。
            mode (str): すでにあるキーの扱い。既定は ``"replace"``。

                - ``"replace"``: カーブごと入れ替える。ウェイト付き接線とインフィニティも保存した値にする。
                - ``"insert"``: 保存した範囲のキーだけを置き換え、範囲の外のキーは残す。範囲は ``capture`` の
                  ``time`` で、省略していたらカーブごとの最初と最後のキー(どちらもtimeOffsetを足した後)。
                - ``"merge"``: 同じ時刻のキーだけを上書きし、ほかのキーは残す。

                insert・mergeでは、すでにあるカーブのウェイト付き接線とインフィニティをそのまま保つ。
            timeOffset (float): キーの時刻へ足す量(今のUIの時間の単位でのフレーム)。
            timing (str): 保存したときとfpsが違うときの扱い。既定は ``"frame"``。
                ``"frame"`` はフレーム番号を保つ。``"sec"`` は秒を保つように、時刻と接線を換算する。
            createLayers (bool): Trueなら、見つからないレイヤーを保存した設定で作る。同じ名前の
                レイヤーがあれば、設定を変えずにそれを使う。Falseなら、見つからないレイヤーのカーブを飛ばす。既定はTrue。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。キーの書き込みは通常の約4倍速い。
                途中で失敗しても元に戻さない。

        Returns:
            ValidationReport: 適用の結果。

        Raises:
            TypeError: timeOffsetが数値でない場合、またはcreateLayers・fastがboolでない場合。
            ValueError: modeが対応していない値の場合、timeOffsetが有限な値でない場合、
                またはtimingが ``"frame"``・``"sec"`` 以外の場合。
        """
        ...
    def validate(self, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ..., mode: str = ..., timeOffset: float = ..., timing: str = ..., createLayers: bool = ...) -> ValidationReport:
        """適用する前に、シーンとの対応を確かめる。シーンは変えない。

        :meth:`apply` と同じ指定(``fast`` を除く)を受け、同じ決まりで確かめる。

        Args:
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。既定はNone。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。既定はNone。
            namespaceMap (dict[str, str] | None): 名前空間の対応。既定はNone。
            mode (str): :meth:`apply` の ``mode``。既定は ``"replace"``。
            timeOffset (float): :meth:`apply` の ``timeOffset``。既定は0。
            timing (str): :meth:`apply` の ``timing``。既定は ``"frame"``。
            createLayers (bool): :meth:`apply` の ``createLayers``。既定はTrue。

        Returns:
            ValidationReport: 見つからないもの・書けないもの・適用できない問題。

        Raises:
            TypeError: timeOffsetが数値でない場合、またはcreateLayersがboolでない場合。
            ValueError: modeが対応していない値の場合、timeOffsetが有限な値でない場合、
                またはtimingが ``"frame"``・``"sec"`` 以外の場合。
        """
        ...
    def _apply_options(self, mode: str, time_offset: float, timing: str, create_layers: bool) -> dict:
        """applyとvalidateの、アニメーションだけの指定を確かめて辞書にする。

        Args:
            mode (str): すでにあるキーの扱い。
            time_offset (float): キーの時刻へ足す量。
            timing (str): fpsが違うときの扱い。
            create_layers (bool): 見つからないレイヤーを作るか。

        Returns:
            dict: ``_validate``・``_apply`` へ渡す指定。

        Raises:
            TypeError: time_offsetが数値でない場合、またはcreate_layersがboolでない場合。
            ValueError: modeが対応していない値の場合、time_offsetが有限な値でない場合、
                またはtimingが ``"frame"``・``"sec"`` 以外の場合。
        """
        ...
    def _require_data(self, data: dict):
        """``curves``・``layers`` の形を確かめる。

        Args:
            data (dict): 持たせる前のデータ。

        Raises:
            ValueError: データの形が正しくない場合。
        """
        ...
    def _validate(self, mapping: NameMapping, report: ValidationReport, options: dict):
        """見つからないノード・アトリビュートを記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 使わない。
        """
        ...
    def _apply(self, mapping: NameMapping, report: ValidationReport, options: dict, fast: bool):
        """カーブを書き込む。

        fastでは、cmdsで行う部分(カーブ・レイヤーの作成)もUndoに記録しない。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): mode・timeOffset・timing・createLayers。
            fast (bool): TrueはUndoなしでOpenMayaを使う。
        """
        ...
    def _apply_curves(self, mapping: NameMapping, report: ValidationReport, options: dict, fast: bool):
        """保存したカーブを順に書き込む。

        作ったレイヤーのロックは、最後に保存した状態へ戻す。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): mode・timeOffset・timing・createLayers。
            fast (bool): TrueはキーをOpenMayaで書く。
        """
        ...


class _LayerResolver:
    """保存したレイヤー名を、シーンのアニメーションレイヤーへ対応づける(必要なら作る)。"""
    def __init__(self, layers: list[dict], create: bool) -> None:
        """保存したレイヤーの設定を覚えておく。

        Args:
            layers (list[dict]): 保存したレイヤーの設定(親が先に並ぶ)。
            create (bool): Trueなら、見つからないレイヤーを作る。
        """
        ...
    def resolve(self, name: str) -> tuple[str | None, str]:
        """レイヤー名に対応するシーンのレイヤーを返す。

        Args:
            name (str): 保存したレイヤー名。

        Returns:
            tuple[str | None, str]: レイヤー名と、使えない場合の理由。
        """
        ...
    def restoreLocks(self):
        """作ったレイヤーのうち、保存したときにロックされていたものをロックする。"""
        ...
    def _find_or_create(self, name: str) -> tuple[str | None, str]:
        """シーンにあるレイヤーを使うか、保存した設定で作る。

        Args:
            name (str): 保存したレイヤー名。

        Returns:
            tuple[str | None, str]: レイヤー名と、使えない場合の理由。
        """
        ...

def _require_nodes(nodes: object) -> list[Node]:
    """ノード・名前・その並びを、Nodeのlistにする。

    Args:
        nodes (object): 対象のノード。

    Returns:
        list[Node]: 対象のノード。

    Raises:
        TypeError: ノード・名前・その並びでない場合。
        RuntimeError: ノードが無い場合。
    """
    ...

def _require_time_range(time: object) -> tuple[float, float] | None:
    """時刻の範囲を確かめる。

    Args:
        time (object): Noneか ``(start, end)``。

    Returns:
        tuple[float, float] | None: 範囲。

    Raises:
        TypeError: 2つの数値の並びでない場合。
        ValueError: 有限な値でない場合、または開始が終了より大きい場合。
    """
    ...

def _require_layer(layer: object, names: list[str]):
    """保存したレイヤーの設定の形を確かめる。

    Args:
        layer (object): レイヤーの設定。
        names (list[str]): このレイヤーより前に出てきたレイヤー名(親は先に出てくる)。

    Raises:
        ValueError: 形や型が正しくない場合。
    """
    ...

def _layer_members() -> dict[str, list[str]]:
    """アニメーションレイヤーに入ったアトリビュートを、ノードの完全パスごとに集める。

    Returns:
        dict[str, list[str]]: ノードの完全パスと、アトリビュートのパスの並び(重複なし)。
            レイヤーが無ければ空の辞書。
    """
    ...

def _node_curves(full: str, layered: list[str], root: str | None) -> list[tuple[str, str | None, str]]:
    """ノードのアトリビュートにつながる、入力が時間のカーブを集める。

    Args:
        full (str): ノードの完全パス。
        layered (list[str]): アニメーションレイヤーに入ったアトリビュートのパス。
        root (str | None): ルートレイヤー名。

    Returns:
        list[tuple[str, str | None, str]]: (アトリビュートのパス, レイヤー名(ベースはNone), カーブ名)。
    """
    ...

def _capture_layers(used: list[str], root: str | None) -> list[dict]:
    """使ったレイヤーとその親の設定を返す。

    ルートのレイヤーは除く。親が先に来る順に並べる。

    Args:
        used (list[str]): カーブを保存したレイヤー名。
        root (str | None): ルートレイヤー名。

    Returns:
        list[dict]: レイヤーの設定。
    """
    ...

def _resolve_plug(entry: dict, mapping: NameMapping, report: ValidationReport) -> Plug | None:
    """カーブを書くPlugを探し、見つからなければreportへ記録する。

    Args:
        entry (dict): カーブの項目。
        mapping (NameMapping): 名前の対応づけ。
        report (ValidationReport): 記録先。

    Returns:
        Plug | None: 見つかったPlug。
    """
    ...

def _target_curve(plug: str, layer: str | None, keys: list[dict]) -> tuple[str | None, str, bool]:
    """Plug(とレイヤー)のカーブを探す。無ければ、Mayaでキーを打って作る。

    Args:
        plug (str): 書き込むPlugの名前。
        layer (str | None): レイヤー名。Noneならベース(レイヤーに入っていなければ、直接つながるカーブ)。
        keys (list[dict]): 書くキー。空で、カーブも無ければ何もしない。

    Returns:
        tuple[str | None, str, bool]: (カーブ名, 使えない場合の理由(何もしない場合は空文字列),
            ここで作ったカーブならTrue)。
    """
    ...
