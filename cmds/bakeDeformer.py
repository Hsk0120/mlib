"""デフォーマー(delta mush・cluster など)による変形を、スキンのウェイトへ焼き込む(``cmds.bakeDeformer`` 相当)。

Mayaの Bake Deformers to Skin Weights と同じく ``cmds.bakeDeformer`` を使う。
ジョイントを動かしたときの変形を元の形状で測り、変形先の形状の skinCluster のウェイトにする。
戻り値はその skinCluster。

変形先を省略すると、元の形状そのものを skinCluster だけで変形する形へ置き換える。
このとき元のデフォーマーは取り除かれる。

.. code-block:: python

    import mlib

    skin = mlib.bakeDeformer("body_geo", "root_JNT", "body_game_geo", maxInfluences=4)
"""

import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _pick_alias, undoChunk
from ..util import _UNSET

#: ``**kwargs`` では受け付けないフラグ。形状・スケルトンの指定は名前の違う専用引数(source・skeleton・
#: destination・destinationSkeleton)で受け、query・editは作成専用のため受け付けない。
_REJECTED_FLAGS = frozenset(("srcMeshName", "sm", "srcSkeletonName", "ss", "dstMeshName", "dm", "dstSkeletonName", "ds", "query", "q", "edit", "e"))


def bakeDeformer(source, skeleton, destination=None, destinationSkeleton=None, maxInfluences=_UNSET, *, mi=_UNSET, **kwargs):
    """元の形状の変形を、変形先の形状の skinCluster のウェイトへ焼き込む。

    選択状態は使わない。変形先がすでにバインドされていれば、その skinCluster のウェイトを書き換える。
    fast引数は無い(OpenMayaに同じ機能が無いため)。Undoが有効なら1回で戻せる。

    Args:
        source (Node | str): 変形を測る元の形状(またはその transform)。デフォーマーで変形していること。
        skeleton (Joint | str): 元の形状を動かすスケルトンの、ルートの joint。
        destination (Node | str | None): ウェイトを焼き込む形状。Noneならsourceそのものに焼き込む。
            このとき元のデフォーマーを取り除き、skinCluster だけで変形する形にする。
        destinationSkeleton (Joint | str | None): 変形先のスケルトンのルート。Noneならskeletonと同じ。
        maxInfluences (int): 1つの頂点に影響するインフルエンスの最大数。正の整数。既定は4。
        mi (int): maxInfluencesの短縮名。maxInfluencesと同時には指定できない。
        **kwargs (object): ``cmds.bakeDeformer`` のそのほかのフラグ。長い名前・短い名前のどちらでもよい。
            使えるのは ``influences``・``pruneWeights``・``smoothWeights``・``hierarchy``・
            ``customRangeOfMotion``・``bakeRangeOfMotion``・``colorizeSkeleton``。
            ``srcMeshName``・``srcSkeletonName``・``dstMeshName``・``dstSkeletonName`` (と短縮名)は
            専用の引数で指定するため受け付けない。query・editも受け付けない。

    Returns:
        SkinCluster: 変形先の形状の skinCluster。

    Raises:
        TypeError: maxInfluencesと短縮名 ``mi`` を同時に指定した場合、または ``**kwargs`` で受け付けない
            フラグを渡した場合。
        ValueError: maxInfluencesが正の整数でない場合。
        RuntimeError: 名前からノードが見つからない場合、Mayaが焼き込みを拒否した場合、
            または変形先に skinCluster が見つからない場合。
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node
    from ..nodes.skinCluster import SkinCluster

    maxInfluences = _pick_alias(maxInfluences, mi, "maxInfluences", "mi", default=4)
    rejected = sorted(_REJECTED_FLAGS.intersection(kwargs))
    if rejected:
        raise TypeError(f"bakeDeformerは次の引数を受け付けません: {', '.join(rejected)}")
    if isinstance(maxInfluences, bool) or not isinstance(maxInfluences, int) or maxInfluences < 1:
        raise ValueError("maxInfluencesは正のintで指定してください")
    source_node = Node(Object._input_name(source))
    target = source_node if destination is None else Node(Object._input_name(destination))
    root = Node(Object._input_name(skeleton))
    target_root = root if destinationSkeleton is None else Node(Object._input_name(destinationSkeleton))
    with undoChunk("mlibBakeDeformer"):
        cmds.bakeDeformer(
            srcMeshName=source_node.getFullName(),
            srcSkeletonName=root.getFullName(),
            dstMeshName=target.getFullName(),
            dstSkeletonName=target_root.getFullName(),
            maxInfluences=maxInfluences,
            **kwargs,
        )
    # 結果の照会はUndoのまとまりの外で行う(中で行うとRedoでウェイトが焼き込み前の値になる)。
    skins = cmds.ls(cmds.listHistory(target.getFullName()) or [], type="skinCluster")
    if not skins:
        raise RuntimeError(f"bakeDeformerがskinClusterを作成できませんでした: {target.getFullName()}")
    return SkinCluster(skins[0])
