# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""skinClusterのウェイトをOpenMayaで移す(``SkinCluster.transferWeights`` のfastの経路)。"""

from mlib.nodes.skinCluster import SkinCluster


def transfer_weights(skin: SkinCluster, pairs: list[tuple[str, str]]) -> None:
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
    ...
