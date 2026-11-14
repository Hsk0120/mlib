"""形状をインフルエンスへバインドし、作ったskinClusterを返す(``cmds.skinCluster`` 相当)。

Mayaの Bind Skin と同じく ``cmds.skinCluster`` でバインドする。既定では、指定したjointだけを
インフルエンスにし(``toSelectedBones=True``)、正規化はInteractive(``normalizeWeights=1``)にする。

``weights`` に :meth:`SkinCluster.exportWeights <mlib.nodes.skinCluster.SkinCluster.exportWeights>` で
書き出したファイルを渡すと、ファイルにあるインフルエンスでバインドし、ウェイトと設定もファイルから読み込む。

.. code-block:: python

    import mlib

    skin = mlib.bindSkin([hip, knee, ankle], "leg_geo", maximumInfluences=3)
    skin = mlib.bindSkin(None, "leg_geo", weights="leg_weights.json", namespaceMap={"chrA": "chrB"})
"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _pick_alias, undoChunk, undoTransaction
from ..util import _UNSET

#: bindSkin が既定値を決めるフラグ(長名, 短名, 既定値)。
_DEFAULT_FLAGS = (("toSelectedBones", "tsb", True), ("normalizeWeights", "nw", 1))

#: 作成専用のため受け付けないフラグ。
_REJECTED_FLAGS = frozenset(("query", "q", "edit", "e"))

#: ウェイトのファイルの設定から既定値を決めるフラグ(長名, 短名, 設定名)。
_FILE_FLAGS = (("normalizeWeights", "nw", "normalizeWeights"), ("obeyMaxInfluences", "omi", "maintainMaxInfluences"), ("skinMethod", "sm", "skinningMethod"))


def bindSkin(joints, geometry, maximumInfluences=_UNSET, *, mi=_UNSET, weights=None, nameMap=None, replace=None, namespaceMap=None, method="index", **kwargs):
    """形状を指定したインフルエンスへバインドする。

    選択状態は使わない。形状がすでに skinCluster で変形されている場合は、何もせずエラーにする。
    fast引数は無い(OpenMayaにバインドと同じ機能が無いため)。Undoが有効なら1回で戻せる。

    ``weights`` を指定すると、バインドしたあとにファイルの内容を書き込む。書き込むのは、ウェイト・
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
        .. code-block:: python

            skin.exportWeights("body_weights.json")
            cmds.delete(skin)
            skin = mlib.bindSkin(None, "body_geo", weights="body_weights.json")
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node, Nodes
    from ..nodes.skinCluster import SkinCluster

    maximumInfluences = _pick_alias(maximumInfluences, mi, "maximumInfluences", "mi", default=None)
    rejected = sorted(_REJECTED_FLAGS.intersection(kwargs))
    if rejected:
        raise TypeError(f"bindSkinは次の引数を受け付けません: {', '.join(rejected)}")
    if maximumInfluences is not None and (isinstance(maximumInfluences, bool) or not isinstance(maximumInfluences, int) or maximumInfluences < 1):
        raise ValueError("maximumInfluencesは正のintで指定してください")
    saved = None
    if weights is None:
        if nameMap is not None or replace is not None or namespaceMap is not None or method != "index":
            raise TypeError("nameMap・replace・namespaceMap・methodを使うにはweightsが必要です")
        if joints is None:
            raise ValueError("weightsを指定しない場合はjointsが必要です")
        influences = [Node(name) for name in Nodes._resolve_inputs(joints)]
    else:
        saved, influences = _load_weights(weights, geometry, nameMap, replace, namespaceMap, method)
        if joints is not None:
            influences = [Node(name) for name in Nodes._resolve_inputs(joints)]
    if not influences:
        raise ValueError("インフルエンスを1つ以上指定してください")
    target = Node(Object._input_name(geometry))
    if SkinCluster._geometry_skin_uuids(target):
        raise ValueError("ジオメトリにはすでにskinClusterがあります")
    flags = dict(kwargs)
    if maximumInfluences is None:
        stored = saved["settings"]["maxInfluences"] if saved else None
        maximumInfluences = 4 if stored is None else stored
    flags["maximumInfluences"] = maximumInfluences
    if saved:
        flags.update(_file_flags(saved["settings"], flags))
    for long, short, default in _DEFAULT_FLAGS:
        if long not in flags and short not in flags:
            flags[long] = default
    names = [node.getFullName() for node in influences]
    if saved is None:
        with undoChunk("mlibBindSkin"):
            result = cmds.skinCluster(names, target.getFullName(), **flags)
            return Node(result[0])
    # 循環参照の回避: mlib.json はnodesを読み込むため、使う時点で読み込む。
    from ..json.nameMapping import NameMapping

    with undoTransaction("mlibBindSkin"):
        skin = Node(cmds.skinCluster(names, target.getFullName(), **flags)[0])
        data, nodes, report = skin._prepare_weights_data(saved["data"], NameMapping(nameMap, replace, namespaceMap), method)
        skin._apply_weights_data(data, nodes, method, report, False)
    report.warn(f"SkinCluster {skin.getName()}")
    return skin


def _file_flags(settings, flags):
    """まだ指定されていない ``cmds.skinCluster`` のフラグを、ファイルの設定から作る。

    Args:
        settings (dict): 検査済みの設定(:meth:`SkinCluster._parse_weights_data` の ``settings``)。
        flags (dict): 指定済みのフラグ。長い名前・短い名前のどちらかがあれば、そのフラグは作らない。

    Returns:
        dict: 追加するフラグ。
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.skinCluster import SkinCluster

    result = {}
    for long, short, key in _FILE_FLAGS:
        value = settings[key]
        if value is None or long in flags or short in flags:
            continue
        if key == "skinningMethod":
            value = SkinCluster._SKINNING_METHODS.index(value)
        elif key == "normalizeWeights":
            value = SkinCluster._NORMALIZE_MODES.index(value)
        result[long] = value
    return result


def _load_weights(path, geometry, nameMap, replace, namespaceMap, method):
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
    # 循環参照の回避: mlib.json・nodesはcmdsより後に読み込まれる。
    from ..json import file
    from ..json.nameMapping import NameMapping
    from ..nodes.node import Node
    from ..nodes.skinCluster import SkinCluster

    SkinCluster._require_choice(method, "method", ("index", "position"))
    mapping = NameMapping(nameMap, replace, namespaceMap)
    _, data = file.load(path, SkinCluster._WEIGHTS_FORMAT, SkinCluster._WEIGHTS_VERSION)
    saved = SkinCluster._parse_weights_data(data)
    shape = Node(Object._input_name(geometry)).mpath()
    if shape.node().hasFn(om2.MFn.kTransform):
        shape.extendToShape()
    if not shape.node().hasFn(om2.MFn.kMesh):
        raise ValueError(f"weightsを使うにはメッシュが必要です: {shape.fullPathName()}")
    count = om2.MFnMesh(shape).numVertices
    if method == "index" and saved["vertexCount"] != count:
        raise ValueError(
            f"スキンウェイトを適用できません: 保存された頂点数({saved['vertexCount']})が{shape.fullPathName()}の頂点数({count})と合っていません。method='position'を使います"
        )
    if method == "position" and not saved["positions"]:
        raise ValueError("スキンウェイトを適用できません: データに頂点の位置がありません")
    influences, seen = [], set()
    for ref in saved["influences"]:
        node = ref.resolve(mapping)
        if node is not None and node.getUuid() not in seen:
            seen.add(node.getUuid())
            influences.append(node)
    if not influences:
        raise ValueError("保存されたインフルエンスがシーンに1つもありません")
    return {"data": data, "settings": saved["settings"]}, influences
