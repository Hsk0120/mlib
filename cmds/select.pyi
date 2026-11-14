# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ノード・アトリビュート・コンポーネントの選択を変える(``cmds.select`` 相当)。"""

import maya.cmds as cmds
from ..decorator import _merge_flags, undoChunk
from ..util import _UNSET


def select(nodes: object = ..., *, add: bool = ..., addFirst: bool = ..., af: bool = ..., all: bool = ..., allDagObjects: bool = ..., ado: bool = ..., allDependencyNodes: bool = ..., adn: bool = ..., clear: bool = ..., cl: bool = ..., containerCentric: bool = ..., cc: bool = ..., deselect: bool = ..., d: bool = ..., hierarchy: bool = ..., hi: bool = ..., noExpand: bool = ..., ne: bool = ..., replace: bool = ..., r: bool = ..., symmetry: bool = ..., sym: bool = ..., symmetrySide: int = ..., sys: int = ..., toggle: bool = ..., tgl: bool = ..., visible: bool = ..., vis: bool = ..., query: bool = ..., q: bool = ..., edit: bool = ..., e: bool = ..., **kwargs: object) -> None:
    """指定したノード・アトリビュート・コンポーネントを選択する。

    mlibのオブジェクトやコレクションを名前に変えて、``maya.cmds.select`` へ渡す。
    MayaのUndoに対応する。fast引数は無い。

    フラグの既定値 ``_UNSET`` は、省略されたかを見分けるためだけの値。省略したフラグはMayaへ渡さず、
    Mayaの既定の動きのままにする。長い名前と短い名前を同時に指定すると、入力を調べる前、
    Undoを始める前にエラーにする。その版のMayaに無いフラグは、Mayaがエラーにする。

    Args:
        nodes (object): 選択する対象、またはその並び。NoneならフラグだけでMayaを呼ぶ。
            空の並びは、空の並びのまま渡す。
        add (bool): Trueなら、今の選択に追加する。
        addFirst (bool): Trueなら、今の選択の先頭へ追加する。
        af (bool): addFirstの短縮名。addFirstと同時には指定できない。
        all (bool): Trueなら、削除できるノードをすべて選択する(Mayaのフラグ)。
        allDagObjects (bool): Trueなら、DAGの対象をすべて選択する。
        ado (bool): allDagObjectsの短縮名。allDagObjectsと同時には指定できない。
        allDependencyNodes (bool): Trueなら、依存ノードをすべて選択する。
        adn (bool): allDependencyNodesの短縮名。allDependencyNodesと同時には指定できない。
        clear (bool): Trueなら、選択を解除する。
        cl (bool): clearの短縮名。clearと同時には指定できない。
        containerCentric (bool): Trueなら、コンテナを中心にした選択の規則を使う。
        cc (bool): containerCentricの短縮名。containerCentricと同時には指定できない。
        deselect (bool): Trueなら、指定した対象を選択から外す。
        d (bool): deselectの短縮名。deselectと同時には指定できない。
        hierarchy (bool): Trueなら、子の階層も選択する。
        hi (bool): hierarchyの短縮名。hierarchyと同時には指定できない。
        noExpand (bool): Trueなら、セットをメンバーへ展開しない。
        ne (bool): noExpandの短縮名。noExpandと同時には指定できない。
        replace (bool): Trueなら、今の選択を置き換える。省略したときのMayaの既定の動きは変えない。
        r (bool): replaceの短縮名。replaceと同時には指定できない。
        symmetry (bool): Trueなら、対称の選択を使う(Mayaのフラグ)。
        sym (bool): symmetryの短縮名。symmetryと同時には指定できない。
        symmetrySide (int): 対称の選択で使う側。
        sys (int): symmetrySideの短縮名。symmetrySideと同時には指定できない。
        toggle (bool): Trueなら、指定した対象の選択を切り替える。
        tgl (bool): toggleの短縮名。toggleと同時には指定できない。
        visible (bool): Trueなら、表示されている対象だけを選択する。
        vis (bool): visibleの短縮名。visibleと同時には指定できない。
        query (bool): 問い合わせのモード。コマンドが対応していない場合はMayaがエラーにする。
        q (bool): queryの短縮名。queryと同時には指定できない。
        edit (bool): 編集のモード。コマンドが対応していない場合はMayaがエラーにする。
        e (bool): editの短縮名。editと同時には指定できない。
        **kwargs (object): 今後Mayaに追加される、mlibが知らないフラグ。そのままMayaへ渡す。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: 長い名前と短い名前を同時に指定した場合、またはnodesの要素が対応していない型の場合。
        ValueError: nodes の要素に空文字列、または削除済みの対象が含まれる場合。
        RuntimeError: Maya が選択を拒否した場合。

    Examples:
        >>> import mlib
        >>> mlib.select(mlib.ls(type="joint"))
        >>> mlib.select(clear=True)
    """
    ...
