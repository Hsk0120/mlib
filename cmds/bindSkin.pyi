# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""形状をインフルエンスへバインドし、作ったskinClusterを返す(``cmds.skinCluster`` 相当)。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.object import Object
from ..decorator import _pick_alias, undoChunk, undoTransaction
from ..util import _UNSET
from typing import Iterable
from mlib.nodes.node import Node
from mlib.nodes.skinCluster import SkinCluster
import os

_DEFAULT_FLAGS: tuple
_REJECTED_FLAGS: frozenset
_FILE_FLAGS: tuple

def bindSkin(joints: Node | str | Iterable[Node | str] | None, geometry: Node | str, maximumInfluences: int | None = ..., *, mi: int | None = ..., weights: str | os.PathLike | None = ..., nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ..., method: str = ..., **kwargs: object) -> SkinCluster:
    """形状を指定したインフルエンスへバインドする。

    Mayaの Bind Skin と同じく ``cmds.skinCluster`` でバインドする。既定では、指定したjointだけを
    インフルエンスにし(``toSelectedBones=True``)、正規化はInteractive(``normalizeWeights=1``)にする。
    選択状態は使わない。形状がすでに skinCluster で変形されている場合は、何もせずエラーにする。
    fast引数は無い(OpenMayaにバインドと同じ機能が無いため)。Undoが有効なら1回で戻せる。

    ``weights`` に :meth:`SkinCluster.exportWeights <mlib.nodes.skinCluster.SkinCluster.exportWeights>` で
    書き出したファイルを指定すると、バインドしたあとにファイルの内容を書き込む。書き込むのは、ウェイト・
    DQブレンドウェイト・設定・ロック・ngSkinTools2のレイヤーで、規則は :meth:`SkinCluster.setWeightsData
    <mlib.nodes.skinCluster.SkinCluster.setWeightsData>` と同じ。

    - ``joints`` がNoneなら、ファイルのインフルエンスのうち、シーンにあるものでバインドする。
      ファイルの名前とシーンの名前は ``nameMap``・``replace``・``namespaceMap`` で対応付ける。
    - ``joints`` を指定した場合も、ファイルのインフルエンスでシーンにあるものは、
      ウェイト0で追加してから書き込む。
    - 設定(最大インフルエンス数・その維持・正規化・スキニングの方法)は、引数で指定しなければ
      ファイルの値でバインドする。書き込んだあとはファイルの値になる。

    ファイルの検査(形式・頂点数・インフルエンス)はバインドの前に行う。
    書き込みの途中で失敗した場合は、バインドも含めて元へ戻す。

    Args:
        joints (Node | str | Iterable[Node | str] | None): インフルエンスにするtransform(jointなど)。
            Noneなら ``weights`` のファイルのインフルエンスを使う(``weights`` が必要)。
        geometry (Node | str): Mayaがバインドできる形状、またはそのtransform。``weights`` を使うときはMesh。
        maximumInfluences (int | None): 1つの頂点に割り当てるインフルエンスの最大数。正の整数。
            Noneなら ``weights`` のファイルの値を使い、ファイルが無ければ4にする。既定はNone。
        mi (int | None): maximumInfluencesの短縮名。maximumInfluencesと同時には指定できない。
        weights (str | os.PathLike | None): ``mlib.skinWeights`` 形式のファイル。Noneなら読み込まない。
        nameMap (dict[str, str] | None): ファイルのインフルエンスの名前(名前空間を除いたもの)の対応表。
        replace (Iterable[tuple[str, str]] | None): ファイルのインフルエンスの名前へ、順に当てる文字列の置換。
        namespaceMap (dict[str, str] | None): ファイルのインフルエンスの名前空間の対応。
        method (str): ファイルの頂点をどう対応付けるか。``"index"`` (既定)は頂点番号、
            ``"position"`` は最も近い位置で対応付ける。
        **kwargs (object): ``cmds.skinCluster`` のそのほかのフラグ(``bindMethod``・``dropoffRate``・
            ``name`` など)。長い名前・短い名前のどちらでもよい。
            ``toSelectedBones``・``normalizeWeights`` を指定すると、既定値の代わりにその値を使う。

    Returns:
        SkinCluster: 作ったskinCluster。

    Raises:
        TypeError: maximumInfluencesと短縮名 ``mi`` を同時に指定した場合、query・editフラグを渡した場合、
            または ``weights`` なしで対応付けの引数を渡した場合。
        ValueError: インフルエンスが空の場合、maximumInfluencesが正の整数でない場合、
            形状がすでにスキニングされている場合、``joints`` と ``weights`` が両方Noneの場合、
            またはファイルの形式・頂点数・インフルエンスが合わない場合。
        OSError: ファイルを読み込めない場合。
        RuntimeError: 名前からノードが見つからない場合、またはMayaがバインドを拒否した場合。

    Examples:
        >>> import mlib
        >>> skin = mlib.bindSkin([hip, knee, ankle], "leg_geo", maximumInfluences=3)
        >>> skin = mlib.bindSkin(None, "leg_geo", weights="leg_weights.json", namespaceMap={"chrA": "chrB"})

        >>> skin.exportWeights("body_weights.json")
        >>> cmds.delete(skin)
        >>> skin = mlib.bindSkin(None, "body_geo", weights="body_weights.json")
    """
    ...

def _file_flags(settings: dict, flags: dict) -> dict:
    """まだ指定されていない ``cmds.skinCluster`` のフラグを、ファイルの設定から作る。

    Args:
        settings (dict): 検査済みの設定(:meth:`SkinCluster._parse_weights_data` の ``settings``)。
        flags (dict): 指定済みのフラグ。長い名前・短い名前のどちらかがあれば、そのフラグは作らない。

    Returns:
        dict: 追加するフラグ。
    """
    ...

def _load_weights(path: str | os.PathLike, geometry: Node | str, nameMap: dict[str, str] | None, replace: Iterable[tuple[str, str]] | None, namespaceMap: dict[str, str] | None, method: str) -> tuple[dict, list[Node]]:
    """ウェイトのファイルを読み込み、バインドの前にできる検査を行う。

    シーンは変更しない。

    Args:
        path (str | os.PathLike): ``mlib.skinWeights`` 形式のファイル。
        geometry (Node | str): バインドする形状、またはそのtransform。
        nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。
        replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置換。
        namespaceMap (dict[str, str] | None): 名前空間の対応。
        method (str): ``"index"`` または ``"position"``。

    Returns:
        tuple[dict, list[Node]]: ``{"data": 元のデータ, "settings": 検査済みの設定}`` と、
            ファイルのインフルエンスのうちシーンにあるもの(保存した順。同じものは1回だけ)。

    Raises:
        ValueError: ファイルの形式・データ・頂点数が正しくない場合、形状がMeshでない場合、
            または保存したインフルエンスが1つもシーンに無い場合。
        OSError: 読み込みに失敗した場合。
    """
    ...
