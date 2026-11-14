"""skinClusterのウェイトをOpenMayaで移す(``SkinCluster.transferWeights`` のfastの経路)。"""


def transfer_weights(skin, pairs):
    """インフルエンスの間でウェイトを移す。

    skinPercentでウェイトを移したときと、interactiveの正規化と同じ結果にする。

    Args:
        skin (SkinCluster): 書き込み先。
        pairs (list[tuple[str, str]]): 確かめてある(移し元, 移し先)のインフルエンス名の組。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: ウェイトがロックされているか接続されていて、書き込めない場合。
        NotImplementedError: ジオメトリが1つでない場合。
    """
    if len(skin.mfn().getOutputGeometry()) != 1:
        raise NotImplementedError("fastのウェイト転送は、ジオメトリが1つの場合だけに対応しています")
    names, values = skin._editable_weights()
    influences = skin.getInfluences()
    ids = [node.getUuid() for node in influences]
    width = len(names)
    # importが循環しないよう、Nodeは関数の中で読み込む。
    from ..nodes.node import Node

    indices = [(ids.index(Node(source).getUuid()), ids.index(Node(target).getUuid())) for source, target in pairs]
    normalize = skin.getPlug("normalizeWeights").get() == 1
    for source, target in indices:
        for offset in range(0, len(values), width):
            if values[offset + source] <= 0:
                continue
            # MayaのtransformMoveWeightsは、移し先の今の値へ足さず、
            # 移し元の値で置き換えてから正規化する。通常の経路と同じ結果にする。
            values[offset + target] = values[offset + source]
            values[offset + source] = 0.0
            if normalize:
                total = sum(values[offset : offset + width])
                if total > 0:
                    values[offset : offset + width] = [v / total for v in values[offset : offset + width]]
    skin.setWeights(names, values, fast=True)
