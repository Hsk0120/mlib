"""名前や条件でMayaの対象を探し、結果の種類に合った集まり(コレクション)で返す(``cmds.ls`` 相当)。"""

import maya.cmds as cmds

from ..core.registry import _real_node_types
from ..decorator import _merge_flags
from ..util import _UNSET


def ls(
    *args,
    absoluteName=_UNSET,
    an=_UNSET,
    allPaths=_UNSET,
    ap=_UNSET,
    assemblies=_UNSET,
    cameras=_UNSET,
    ca=_UNSET,
    containerType=_UNSET,
    ct=_UNSET,
    containers=_UNSET,
    con=_UNSET,
    dagObjects=_UNSET,
    dag=_UNSET,
    defaultNodes=_UNSET,
    dn=_UNSET,
    dependencyNodes=_UNSET,
    dep=_UNSET,
    exactType=_UNSET,
    et=_UNSET,
    excludeType=_UNSET,
    ext=_UNSET,
    flatten=_UNSET,
    fl=_UNSET,
    geometry=_UNSET,
    g=_UNSET,
    ghost=_UNSET,
    gh=_UNSET,
    head=_UNSET,
    hd=_UNSET,
    hilite=_UNSET,
    hl=_UNSET,
    intermediateObjects=_UNSET,
    io=_UNSET,
    invisible=_UNSET,
    iv=_UNSET,
    leaf=_UNSET,
    lf=_UNSET,
    lights=_UNSET,
    lt=_UNSET,
    live=_UNSET,
    lv=_UNSET,
    lockedNodes=_UNSET,
    ln=_UNSET,
    long=_UNSET,
    l=_UNSET,
    materials=_UNSET,
    mat=_UNSET,
    modified=_UNSET,
    mod=_UNSET,
    noIntermediate=_UNSET,
    ni=_UNSET,
    nodeTypes=_UNSET,
    nt=_UNSET,
    objectsOnly=_UNSET,
    o=_UNSET,
    orderedComponentSelection=_UNSET,
    ocs=_UNSET,
    orderedSelection=_UNSET,
    os=_UNSET,
    partitions=_UNSET,
    pr=_UNSET,
    persistentNodes=_UNSET,
    pn=_UNSET,
    planes=_UNSET,
    pl=_UNSET,
    preSelectHilite=_UNSET,
    psh=_UNSET,
    readOnly=_UNSET,
    ro=_UNSET,
    recursive=_UNSET,
    r=_UNSET,
    referencedNodes=_UNSET,
    rn=_UNSET,
    references=_UNSET,
    rf=_UNSET,
    renderGlobals=_UNSET,
    rg=_UNSET,
    renderQualities=_UNSET,
    rq=_UNSET,
    renderResolutions=_UNSET,
    rr=_UNSET,
    renderSetups=_UNSET,
    rs=_UNSET,
    selection=_UNSET,
    sl=_UNSET,
    selectedKeyframes=_UNSET,
    sets=_UNSET,
    set=_UNSET,
    shapes=_UNSET,
    s=_UNSET,
    shortNames=_UNSET,
    sn=_UNSET,
    showNamespace=_UNSET,
    sns=_UNSET,
    showType=_UNSET,
    st=_UNSET,
    tail=_UNSET,
    tl=_UNSET,
    templated=_UNSET,
    tm=_UNSET,
    textures=_UNSET,
    tex=_UNSET,
    transforms=_UNSET,
    tr=_UNSET,
    type=_UNSET,
    typ=_UNSET,
    ufeObjects=_UNSET,
    ufe=_UNSET,
    undeletable=_UNSET,
    ud=_UNSET,
    untemplated=_UNSET,
    ut=_UNSET,
    uuid=_UNSET,
    uid=_UNSET,
    visible=_UNSET,
    v=_UNSET,
    query=_UNSET,
    q=_UNSET,
    edit=_UNSET,
    e=_UNSET,
    **kwargs,
):
    """Mayaの対象を探し、型に合ったオブジェクトとして返す。

    フラグの既定値 ``_UNSET`` は、省略されたかを見分けるためだけの値。省略したフラグはMayaへ渡さず、
    Mayaの既定の動きのままにする。長い名前と短い名前を同時に指定すると、入力を調べる前、
    Undoを始める前にエラーにする。その版のMayaに無いフラグは、Mayaがエラーにする。

    Args:
        *args (object): 名前・パターン、Node・Plug・Component・APIのオブジェクト、またはその並び。
            Noneや空の並びだけを渡した場合は、空の結果を返す。
        absoluteName (bool): Trueなら、名前空間を絶対表記にする。
        an (bool): absoluteNameの短縮名。absoluteNameと同時には指定できない。
        allPaths (bool): Trueなら、DAGのインスタンスのパスをすべて返す。
        ap (bool): allPathsの短縮名。allPathsと同時には指定できない。
        assemblies (bool): Trueなら、最上位のTransformを検索する。短縮名asはPythonの予約語のため、``**{"as": value}`` で渡す。
        cameras (bool): Trueなら、カメラを検索する。
        ca (bool): camerasの短縮名。camerasと同時には指定できない。
        containerType (str | Iterable[str]): コンテナの型の名前で絞る。
        ct (str | Iterable[str]): containerTypeの短縮名。containerTypeと同時には指定できない。
        containers (bool): Trueなら、コンテナを検索する。
        con (bool): containersの短縮名。containersと同時には指定できない。
        dagObjects (bool): Trueなら、DAGノードを検索する。
        dag (bool): dagObjectsの短縮名。dagObjectsと同時には指定できない。
        defaultNodes (bool): Trueなら、既定のノードを検索する。
        dn (bool): defaultNodesの短縮名。defaultNodesと同時には指定できない。
        dependencyNodes (bool): Trueなら、依存ノードを検索する。
        dep (bool): dependencyNodesの短縮名。dependencyNodesと同時には指定できない。
        exactType (str | Iterable[str]): 型が完全に一致するもので絞る。複数を指定したときの扱いはMayaに従う。
            type・excludeTypeと同じく、2026で名前が変わった型(``multDoubleLinear``/``multDL``・
            ``addDoubleLinear``/``addDL``)は、どちらの名前でもその版の型名で検索する。
        et (str | Iterable[str]): exactTypeの短縮名。exactTypeと同時には指定できない。
        excludeType (str | Iterable[str]): 検索から除くノード型。
        ext (str | Iterable[str]): excludeTypeの短縮名。excludeTypeと同時には指定できない。
        flatten (bool): Mayaの範囲を展開する指定。mlibのComponentの結果は、この値によらず1つずつに展開する。
        fl (bool): flattenの短縮名。flattenと同時には指定できない。
        geometry (bool): Trueなら、ジオメトリを検索する。
        g (bool): geometryの短縮名。geometryと同時には指定できない。
        ghost (bool): Trueなら、ゴースト表示されたノードを検索する。
        gh (bool): ghostの短縮名。ghostと同時には指定できない。
        head (int): 先頭から取得する件数。型ごとの上限の扱いはMayaに従う。
        hd (int): headの短縮名。headと同時には指定できない。
        hilite (bool): Trueなら、ハイライトされた対象を検索する。
        hl (bool): hiliteの短縮名。hiliteと同時には指定できない。
        intermediateObjects (bool): Trueなら、中間Shapeを検索する。
        io (bool): intermediateObjectsの短縮名。intermediateObjectsと同時には指定できない。
        invisible (bool): Trueなら、非表示の対象を検索する。
        iv (bool): invisibleの短縮名。invisibleと同時には指定できない。
        leaf (bool): Trueなら、末端のDAGノードを検索する。
        lf (bool): leafの短縮名。leafと同時には指定できない。
        lights (bool): Trueなら、ライトを検索する。
        lt (bool): lightsの短縮名。lightsと同時には指定できない。
        live (bool): Trueなら、ライブにした対象を検索する。
        lv (bool): liveの短縮名。liveと同時には指定できない。
        lockedNodes (bool): Trueなら、ロックされたノードを検索する。
        ln (bool): lockedNodesの短縮名。lockedNodesと同時には指定できない。
        long (bool): Trueなら、結果の名前を完全なDAGパスで受け取る。
        l (bool): longの短縮名。longと同時には指定できない。
        materials (bool): Trueなら、マテリアルを検索する。
        mat (bool): materialsの短縮名。materialsと同時には指定できない。
        modified (bool): Trueなら、変更されたノードを検索する。
        mod (bool): modifiedの短縮名。modifiedと同時には指定できない。
        noIntermediate (bool): Trueなら、中間Shapeを除く。
        ni (bool): noIntermediateの短縮名。noIntermediateと同時には指定できない。
        nodeTypes (bool): ノード型名の一覧を返すMayaのフラグ。シーンの対象を返さないため、mlibでは対応しない。
        nt (bool): nodeTypesの短縮名。nodeTypesと同時には指定できない。
        objectsOnly (bool): Trueなら、アトリビュートとコンポーネントを除き、ノードだけを検索する。
        o (bool): objectsOnlyの短縮名。objectsOnlyと同時には指定できない。
        orderedComponentSelection (bool): Trueなら、コンポーネントの選択順を使う。Maya2025以降で使える。
        ocs (bool): orderedComponentSelectionの短縮名。orderedComponentSelectionと同時には指定できない。
        orderedSelection (bool): Trueなら、選択した順に取得する。Mayaの選択順を記録する設定に従う。
        os (bool): orderedSelectionの短縮名。orderedSelectionと同時には指定できない。
        partitions (bool): Trueなら、パーティションを検索する。
        pr (bool): partitionsの短縮名。partitionsと同時には指定できない。
        persistentNodes (bool): Trueなら、永続的なノードを検索する。
        pn (bool): persistentNodesの短縮名。persistentNodesと同時には指定できない。
        planes (bool): Trueなら、プレーンを検索する(Mayaのフラグ)。
        pl (bool): planesの短縮名。planesと同時には指定できない。
        preSelectHilite (bool): Trueなら、選択前のハイライト(プリセレクト)の対象を検索する。
        psh (bool): preSelectHiliteの短縮名。preSelectHiliteと同時には指定できない。
        readOnly (bool): Trueなら、読み取り専用のノードを検索する(Mayaのフラグ)。
        ro (bool): readOnlyの短縮名。readOnlyと同時には指定できない。
        recursive (bool): Trueなら、名前空間を再帰的に検索する。
        r (bool): recursiveの短縮名。recursiveと同時には指定できない。
        referencedNodes (bool): Trueなら、リファレンスしたファイルのノードを検索する。
        rn (bool): referencedNodesの短縮名。referencedNodesと同時には指定できない。
        references (bool): Trueなら、リファレンスノードを検索する。
        rf (bool): referencesの短縮名。referencesと同時には指定できない。
        renderGlobals (bool): Trueなら、レンダーグローバルを検索する(Mayaのフラグ)。
        rg (bool): renderGlobalsの短縮名。renderGlobalsと同時には指定できない。
        renderQualities (bool): Trueなら、レンダー品質のノードを検索する(Mayaのフラグ)。
        rq (bool): renderQualitiesの短縮名。renderQualitiesと同時には指定できない。
        renderResolutions (bool): Trueなら、レンダー解像度のノードを検索する(Mayaのフラグ)。
        rr (bool): renderResolutionsの短縮名。renderResolutionsと同時には指定できない。
        renderSetups (bool): Trueなら、レンダーセットアップを検索する(Mayaのフラグ)。
        rs (bool): renderSetupsの短縮名。renderSetupsと同時には指定できない。
        selection (bool): Trueなら、現在の選択を検索する。
        sl (bool): selectionの短縮名。selectionと同時には指定できない。
        selectedKeyframes (bool): mlib独自の指定。Trueなら、Graph Editor・Dope Sheetで選んでいるキーを
            :class:`~mlib.common.keyframe.Keyframes` で返す(:meth:`Selection.getKeyframes
            <mlib.common.selection.Selection.getKeyframes>` と同じ)。ほかの位置引数・フラグとは同時に指定できない。
        sets (bool): Trueなら、セットを検索する。
        set (bool): setsの短縮名。setsと同時には指定できない。
        shapes (bool): Trueなら、Shapeを検索する。
        s (bool): shapesの短縮名。shapesと同時には指定できない。
        shortNames (bool): Trueなら、アトリビュート名を短い名前で受け取る。
        sn (bool): shortNamesの短縮名。shortNamesと同時には指定できない。
        showNamespace (bool): Trueなら、名前空間を一緒に返す。シーンの対象の名前以外を返す使い方には対応しない。
        sns (bool): showNamespaceの短縮名。showNamespaceと同時には指定できない。
        showType (bool): 型名を一緒に返すMayaのフラグ。シーンの対象の名前以外を返す使い方には対応しない。
        st (bool): showTypeの短縮名。showTypeと同時には指定できない。
        tail (int): 末尾から取得する件数。型ごとの上限の扱いはMayaに従う。
        tl (int): tailの短縮名。tailと同時には指定できない。
        templated (bool): Trueなら、テンプレート表示にした対象を検索する。
        tm (bool): templatedの短縮名。templatedと同時には指定できない。
        textures (bool): Trueなら、テクスチャを検索する。
        tex (bool): texturesの短縮名。texturesと同時には指定できない。
        transforms (bool): Trueなら、Transformを検索する。
        tr (bool): transformsの短縮名。transformsと同時には指定できない。
        type (str | Iterable[str]): ノード型、またはvertex/edge/face/uv/controlVertex。
            joint/skinClusterを指定すると、専用のコレクションを返す。
        typ (str | Iterable[str]): typeの短縮名。typeと同時には指定できない。
        ufeObjects (bool): UFEの項目を含めるMayaのフラグ。mlibのオブジェクトにできない結果には対応しない。
        ufe (bool): ufeObjectsの短縮名。ufeObjectsと同時には指定できない。
        undeletable (bool): Trueなら、削除できないノードを検索する。
        ud (bool): undeletableの短縮名。undeletableと同時には指定できない。
        untemplated (bool): Trueなら、テンプレートでない対象を検索する。
        ut (bool): untemplatedの短縮名。untemplatedと同時には指定できない。
        uuid (bool): UUIDの文字列を返すMayaのフラグ。シーンの対象を返さないため、mlibでは対応しない。
        uid (bool): uuidの短縮名。uuidと同時には指定できない。
        visible (bool): Trueなら、表示されている対象を検索する。
        v (bool): visibleの短縮名。visibleと同時には指定できない。
        query (bool): 問い合わせのモード。コマンドが対応していない場合はMayaがエラーにする。
        q (bool): queryの短縮名。queryと同時には指定できない。
        edit (bool): 編集のモード。コマンドが対応していない場合はMayaがエラーにする。
        e (bool): editの短縮名。editと同時には指定できない。
        **kwargs (object): 今後Mayaに追加される、mlibが知らないフラグ。そのままMayaへ渡す。

    Returns:
        Nodes | Joints | SkinClusters | Plugs | Vertices | Edges | Faces | UVs | CVs | Keyframes | list[Node | Plug | Component]:
            結果の種類に合った集まり。selectedKeyframes=Trueなら :class:`~mlib.common.keyframe.Keyframes`。

            * ノードだけ: :class:`~mlib.nodes.node.Nodes`。typeまたはtypがjointなら
              :class:`~mlib.nodes.joint.Joints`、skinClusterなら :class:`~mlib.nodes.skinCluster.SkinClusters`
              (0件でも同じ型)。
            * アトリビュートだけ: :class:`~mlib.plugs.plug.Plugs`。
            * 同じシェイプの同じ種類のコンポーネントだけ: :class:`~mlib.components.vertex.Vertices`・
              :class:`~mlib.components.edge.Edges`・:class:`~mlib.components.face.Faces`・
              :class:`~mlib.components.uv.UVs`・:class:`~mlib.components.cv.CVs`
              (typeでコンポーネントの型を指定したときも同じ)。
            * ノードとアトリビュート、複数のシェイプ、複数の種類のコンポーネントなどが混ざる場合:
              Mayaの結果の順に並べた list。
            * 上のどれでもなく0件の場合: 空の :class:`~mlib.nodes.node.Nodes`。typeでコンポーネントの型を
              指定して0件の場合も、シェイプが決まらないため空のNodesになる。

    Raises:
        TypeError: 長い名前と短い名前を同時に指定した場合、位置引数に対応していない型が含まれる場合、
            またはselectedKeyframes=Trueと、ほかの位置引数・フラグを同時に指定した場合。
        ValueError: 位置引数に削除済みの対象が含まれる場合。
        RuntimeError: 検索の結果から、ノードを取得できない場合。

    Note:
        型名などを返すMayaのフラグには対応しない。
        結果の名前はまとめてオブジェクトにするが、並び順はMayaが返した順のまま変えない。
        集まりで返す場合は、それぞれの集まりを作るときと同じ規則で、重なり(同じノード・同じDAGパス、
        同じアトリビュート、同じ番号)は先に出てきた方だけを残す。
        種類が混ざって list で返す場合は、重なりをまとめない。

    Examples:
        >>> import mlib
        >>> joints = mlib.ls(type="joint")
        >>> vertices = mlib.ls(selection=True, type="vertex")
    """
    if selectedKeyframes is not _UNSET:
        if not isinstance(selectedKeyframes, bool):
            raise TypeError("selectedKeyframesはboolで指定してください")
        if selectedKeyframes:
            flags = dict(locals())
            others = [name for name, value in flags.items() if name not in ("args", "kwargs", "selectedKeyframes") and value is not _UNSET]
            if args or kwargs or others:
                raise TypeError("selectedKeyframes=Trueは、ほかの引数と同時に指定できません")
            # common.selectionはcmdsを参照するため、循環importを避けて関数内で読み込む。
            from ..common.selection import Selection

            return Selection.getKeyframes()
    short_assemblies = kwargs.pop("as", _UNSET)
    _merge_flags(
        kwargs,
        (
            (absoluteName, an, "absoluteName", "an"),
            (allPaths, ap, "allPaths", "ap"),
            (assemblies, short_assemblies, "assemblies", "as"),
            (cameras, ca, "cameras", "ca"),
            (containerType, ct, "containerType", "ct"),
            (containers, con, "containers", "con"),
            (dagObjects, dag, "dagObjects", "dag"),
            (defaultNodes, dn, "defaultNodes", "dn"),
            (dependencyNodes, dep, "dependencyNodes", "dep"),
            (exactType, et, "exactType", "et"),
            (excludeType, ext, "excludeType", "ext"),
            (flatten, fl, "flatten", "fl"),
            (geometry, g, "geometry", "g"),
            (ghost, gh, "ghost", "gh"),
            (head, hd, "head", "hd"),
            (hilite, hl, "hilite", "hl"),
            (intermediateObjects, io, "intermediateObjects", "io"),
            (invisible, iv, "invisible", "iv"),
            (leaf, lf, "leaf", "lf"),
            (lights, lt, "lights", "lt"),
            (live, lv, "live", "lv"),
            (lockedNodes, ln, "lockedNodes", "ln"),
            (long, l, "long", "l"),
            (materials, mat, "materials", "mat"),
            (modified, mod, "modified", "mod"),
            (noIntermediate, ni, "noIntermediate", "ni"),
            (nodeTypes, nt, "nodeTypes", "nt"),
            (objectsOnly, o, "objectsOnly", "o"),
            (orderedComponentSelection, ocs, "orderedComponentSelection", "ocs"),
            (orderedSelection, os, "orderedSelection", "os"),
            (partitions, pr, "partitions", "pr"),
            (persistentNodes, pn, "persistentNodes", "pn"),
            (planes, pl, "planes", "pl"),
            (preSelectHilite, psh, "preSelectHilite", "psh"),
            (readOnly, ro, "readOnly", "ro"),
            (recursive, r, "recursive", "r"),
            (referencedNodes, rn, "referencedNodes", "rn"),
            (references, rf, "references", "rf"),
            (renderGlobals, rg, "renderGlobals", "rg"),
            (renderQualities, rq, "renderQualities", "rq"),
            (renderResolutions, rr, "renderResolutions", "rr"),
            (renderSetups, rs, "renderSetups", "rs"),
            (selection, sl, "selection", "sl"),
            (sets, set, "sets", "set"),
            (shapes, s, "shapes", "s"),
            (shortNames, sn, "shortNames", "sn"),
            (showNamespace, sns, "showNamespace", "sns"),
            (showType, st, "showType", "st"),
            (tail, tl, "tail", "tl"),
            (templated, tm, "templated", "tm"),
            (textures, tex, "textures", "tex"),
            (transforms, tr, "transforms", "tr"),
            (type, typ, "type", "typ"),
            (ufeObjects, ufe, "ufeObjects", "ufe"),
            (undeletable, ud, "undeletable", "ud"),
            (untemplated, ut, "untemplated", "ut"),
            (uuid, uid, "uuid", "uid"),
            (visible, v, "visible", "v"),
            (query, q, "query", "q"),
            (edit, e, "edit", "e"),
        ),
    )
    # 2026で改名された型(multDoubleLinear/multDL等)は、どちらの名前でもその版の型名で検索する。
    for key in ("type", "exactType", "excludeType"):
        if key in kwargs:
            kwargs[key] = _real_node_types(kwargs[key])
    # nodes・components・common.selectionはcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..common.selection import Selection
    from ..components import CV, UV, Edge, Face, Vertex
    from ..core.object import Object as _InputObject
    from ..nodes import Joints, SkinClusters
    from ..nodes.node import Nodes as _InputNodes

    component_types = {"vertex": Vertex, "edge": Edge, "face": Face, "uv": UV, "controlVertex": CV}
    node_type = kwargs.get("type")
    component = node_type if isinstance(node_type, str) and node_type in component_types else None
    if component is not None:
        kwargs.pop("type")

    targets = []
    for arg in _InputNodes._resolve_inputs([arg for arg in args if arg is not None]):
        if isinstance(arg, str):
            targets.append(arg)
        else:
            targets.extend(_InputObject._input_names(arg))
    # 空の列だけを渡した場合に maya.cmds.ls() の全ノード検索へ変わらないようにする。
    names = (cmds.ls(*targets, **kwargs) or []) if targets or not args else []
    node_type = kwargs.get("type")
    if component is None and node_type == "joint":
        return Joints(names)
    if component is None and node_type == "skinCluster":
        return SkinClusters(names)
    # Mayaの検索・並び順を維持し、解決だけを既存のOpenMaya経路へ任せる。
    # ノード名とアトリビュート名は、名前ごとに選択リストを作らずまとめて解決する(_resolve_names)。
    # 対応付けは cmds の結果の順に行い、対応付けられない名前(重複・統合・コンポーネント・
    # 複数一致・解決の失敗)は従来の名前ごとの経路で判定する。
    from ..common.selection import _resolve_names
    from ..components import Component
    from ..nodes.node import Node
    from ..plugs.plug import Plug

    if component is None:
        resolved_nodes = iter(_resolve_names([name for name in names if "." not in name]))
        resolved_plugs = iter(_resolve_names([name for name in names if "." in name], plugs=True))
    result = []
    for name in names:
        if "." not in name:
            if component is None:
                found = next(resolved_nodes)
                # Node(name) と同じ解決・型選択を、生成の入口の再判定なしで行う。
                result.append(Node._wrap_resolved(found[0], found[1]) if found is not None else Node._from_name(name))
            continue
        if component is None:
            # 1要素のアトリビュートだけに解決する名前は、下の Selection(name) と
            # Plug._resolve_input(name) が同じ手順で作る Plug をまとめた解決の結果から作る。
            found = next(resolved_plugs)
            if found is not None:
                result.append(Plug(Node._wrap_resolved(found[0], found[1]), found[2]))
                continue
        resolved = Selection(name).items
        if resolved and isinstance(resolved[0], Component):
            result.extend(resolved)
        elif component is None:
            result.append(Plug._resolve_input(name))
    if component is not None:
        result = [item for item in result if isinstance(item, component_types[component])]
    return _collect(result)


def _collect(items):
    """lsの結果を、要素の種類がそろっていれば、その種類の集まりにまとめる。

    Args:
        items (list[Node | Plug | Component]): Mayaの結果の順に並べたオブジェクト。

    Returns:
        Nodes | Plugs | Components | list: ノードだけならNodes、アトリビュートだけならPlugs、
            同じシェイプの同じ種類のコンポーネントだけならそのComponents、混ざっていればitemsそのもの。
            0件なら空のNodes。
    """
    # nodes・plugs・componentsはcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..components import (
        CV,
        UV,
        Component,
        CVs,
        Edge,
        Edges,
        Face,
        Faces,
        LatticePoint,
        LatticePoints,
        SurfaceCV,
        SurfaceCVs,
        UVs,
        Vertex,
        VertexFace,
        VertexFaces,
        Vertices,
    )

    # 循環参照の回避: nodes は cmds を参照するため、使う時点で読み込む。
    from ..nodes.node import Node, Nodes
    from ..plugs.plug import Plug, Plugs

    if not items:
        return Nodes()
    if all(isinstance(item, Node) for item in items):
        return Nodes(items)
    if all(isinstance(item, Plug) for item in items):
        return Plugs._from_plugs(items)
    first = items[0]
    collections = {Vertex: Vertices, Edge: Edges, Face: Faces, UV: UVs, CV: CVs, SurfaceCV: SurfaceCVs, LatticePoint: LatticePoints, VertexFace: VertexFaces}
    collection = collections.get(type(first)) if isinstance(first, Component) else None
    if collection is not None and all(type(item) is type(first) and item.shape == first.shape for item in items):
        return collection(first.shape, [item.index for item in items])
    return items
