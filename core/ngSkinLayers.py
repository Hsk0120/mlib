"""ngSkinTools2のスキニングレイヤーのウェイトを移す処理。

インフルエンスを外すときに、そのウェイトをほかのインフルエンスへ移す。
"""

import maya.cmds as cmds

_PLUGIN = "ngSkinTools2"


def _layer_api(skin_name):
    """skinClusterのレイヤーを扱うAPIとLayersを返す。

    Args:
        skin_name (str): skinClusterの名前。

    Returns:
        tuple[object, object] | None: ngSkinTools2のAPIとLayers。
            プラグインが読み込まれていない場合、APIが無い場合、レイヤーが無い場合はNone。
    """
    if not cmds.pluginInfo(_PLUGIN, query=True, loaded=True):
        return None
    try:
        # ngSkinTools2は任意の外部ツールのため、使うときにだけimportする。
        from ngSkinTools2 import api
    except ImportError:
        return None
    if not api.get_layers_enabled(skin_name):
        return None
    return api, api.Layers(skin_name)


def _move_layer_weights(skin_name, moves, redistributed, remaining, vertex_count, *, fast=False):
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
    found = _layer_api(skin_name)
    if found is None:
        return False
    api, layers = found
    with api.suspend_updates(layers.data_node):
        for layer in layers.list():
            _move_in_layer(layer, moves, redistributed, remaining, vertex_count, not fast)
    return True


def _move_in_layer(layer, moves, redistributed, remaining, vertex_count, undo):
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
    used = set(layer.get_used_influences())
    columns = {}
    changed = set()

    def column(index):
        """列を読む。レイヤーが使っていない列は0の列を返す。"""
        if index not in columns:
            columns[index] = layer.get_weights(index) if index in used else [0.0] * vertex_count
        return columns[index]

    for source, target in moves.items():
        if source not in used:
            continue
        origin = column(source)
        if not any(origin):
            continue
        destination = column(target)
        for vertex, value in enumerate(origin):
            if value:
                destination[vertex] += value
        columns[source] = [0.0] * vertex_count
        changed.update((source, target))
    for source in redistributed:
        origin = column(source) if source in used or source in columns else None
        if not origin or not any(origin):
            continue
        rest = [column(index) for index in remaining if index in used or index in columns]
        for vertex, value in enumerate(origin):
            if not value:
                continue
            total = sum(values[vertex] for values in rest)
            if total > 0.0:
                scale = (total + value) / total
                for values in rest:
                    values[vertex] *= scale
            else:
                # 残りがすべて0の頂点は、Mayaの標準の再配分と同じく、残りのインフルエンスへ等しく分ける。
                for index in remaining:
                    column(index)[vertex] += value / len(remaining)
        columns[source] = [0.0] * vertex_count
        changed.add(source)
        changed.update(index for index in columns if index in remaining)
    # 先に足すと一時的に合計が1を超え、ngSkinToolsがほかのインフルエンスを縮めてしまう。そのため外す列から書く。
    removed = set(moves).union(redistributed)
    for index in sorted(changed, key=lambda item: item not in removed):
        layer.set_weights(index, columns[index], undo_enabled=undo)
