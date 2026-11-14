# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ngSkinTools2のスキニングレイヤーのウェイトを移す処理。

インフルエンスを外すときに、そのウェイトをほかのインフルエンスへ移す。
"""

import maya.cmds as cmds

_PLUGIN: str

def _layer_api(skin_name: str) -> tuple[object, object] | None:
    """skinClusterのレイヤーを扱うAPIとLayersを返す。

    Args:
        skin_name (str): skinClusterの名前。

    Returns:
        tuple[object, object] | None: ngSkinTools2のAPIとLayers。
            プラグインが読み込まれていない場合、APIが無い場合、レイヤーが無い場合はNone。
    """
    ...

def _move_layer_weights(skin_name: str, moves: dict[int, int], redistributed: list[int], remaining: list[int], vertex_count: int, *, fast: bool = ...) -> bool:
    """外すインフルエンスのウェイトを、すべてのレイヤーで移す。

    移し先が決まっていればそこへ移し、決まっていなければ残りのインフルエンスへ配る。

    Args:
        skin_name (str): skinClusterの名前。
        moves (dict[int, int]): 移し元と移し先の論理番号。
        redistributed (list[int]): 移し先が無いインフルエンスの論理番号。
            ウェイトは残りのインフルエンスへ、今の比率を保って配る。
        remaining (list[int]): 外した後も残るインフルエンスの論理番号。
        vertex_count (int): 頂点数。
        fast (bool): TrueはレイヤーのUndoを記録しない。

    Returns:
        bool: レイヤーへ書き込んだらTrue。ngSkinTools2のレイヤーが使えない場合はFalse。
    """
    ...

def _move_in_layer(layer: object, moves: dict[int, int], redistributed: list[int], remaining: list[int], vertex_count: int, undo: bool) -> None:
    """1つのレイヤーのウェイトを移す。

    書き込むのは、値が変わったインフルエンスの列だけにする。

    Args:
        layer (object): ngSkinTools2のレイヤー。
        moves (dict[int, int]): 移し元と移し先の論理番号。
        redistributed (list[int]): 残りのインフルエンスへ配る論理番号。
        remaining (list[int]): 外した後も残るインフルエンスの論理番号。
        vertex_count (int): 頂点数。
        undo (bool): TrueならUndoを記録する。

    Returns:
        None: 値を返さない。
    """
    ...
