"""Mayaのノードを作り、実際のノード型に合ったオブジェクトを返す(``cmds.createNode`` 相当)。"""

from contextlib import nullcontext

from ..decorator import _edit_context, _merge_flags, _require_bool
from ..util import _UNSET


def createNode(
    type,
    *,
    fast=False,
    name=_UNSET,
    n=_UNSET,
    parent=_UNSET,
    p=_UNSET,
    shared=_UNSET,
    s=_UNSET,
    skipSelect=_UNSET,
    ss=_UNSET,
    asShader=False,
    asTexture=False,
    asUtility=False,
    asLight=False,
    asPostProcess=False,
    asRendering=False,
    **kwargs,
):
    """Mayaのノードを作り、実際の型に合ったオブジェクトを返す。

    mlibでノードを作る入口はこれだけで、``Node.create`` や ``Node(name, create=True)`` のような作り方は無い。
    戻り値は、作ったノードの実際のnodeTypeに合ったクラスのオブジェクト。登録済みの型はそのクラス、
    登録の無い型は登録表の規則で選んだクラスになる。``getType()`` はMayaのnodeType名を返す。

    通常はMayaのUndoに対応し、1回のUndoで作成を戻せる(shapeと一緒に自動で作られたtransformも戻る)。
    ``fast=True`` なら、対応している作成条件をOpenMayaで直接処理し、Undoの履歴に残さない。
    対応していない条件は、ノードを作る前にエラーにする。

    フラグの既定値 ``_UNSET`` は、省略されたかを見分けるためだけの値。省略したフラグはMayaへ渡さず、
    Mayaの既定の動きのままにする。長い名前と短い名前を同時に指定すると、入力を調べる前、
    Undoを始める前にエラーにする。その版のMayaに無いフラグは、Mayaがエラーにする。
    ``cmds.createNode`` に無い ``query``/``edit`` は受け付けない(ほかのフラグと同じく、MayaがTypeErrorにする)。

    shapeの型(``"mesh"``・``"nurbsCurve"``・``"locator"`` など)を指定するとshapeが返り、``name=`` も
    shapeの名前になる。親を省略した場合、``getParent()``・``getTransform()`` はMayaが自動で作った
    transformになる(transformの名前は ``rename()`` で付け直す)。

    作ったノードは、``cmds.createNode`` と同じく選択される(``skipSelect=True`` の場合を除く)。
    作る前の選択を使う場合は、先に ``mlib.ls(selection=True)`` で取得しておく。

    ``shared=True`` で、同じ名前・同じ型のノードがすでにある場合は、作らずにそのノードを返す
    (cmds.createNodeが作らずにNoneを返す場合にあたる)。cmdsはルート名前空間の名前だけを使い回し、
    名前空間付きの名前では連番の名前で新しく作る。
    fast=Trueでは、名前で既存の同じ型のノードを探す近い動きになる。名前空間付きでも既存のノードを返す。
    同じ名前のノードの型が違う場合は、連番の名前で新しく作らず、RuntimeErrorにする。

    jointの下へjointを作ると、``cmds.joint`` と同じく親の ``scale`` を ``inverseScale`` へ接続する
    (通常は作成と同じ1回のUndoで戻る。fastでも接続する)。
    2026で名前が変わった型は、どの版でも ``multDoubleLinear``/``multDL``・``addDoubleLinear``/``addDL`` の
    どちらの名前でも作れる。作られるのは、その版での実際の型のノード。

    ``asShader``・``asTexture``・``asUtility``・``asLight``・``asPostProcess``・``asRendering`` のどれかを
    Trueにすると、``cmds.shadingNode`` で作る(Hypershadeで作るのと同じく、``defaultShaderList1`` などの
    既定のリストへつなぐ)。同時にTrueにできるのは1つだけ。``name``・``parent``・``shared``・``skipSelect`` は
    同じ意味で渡し、そのほかのフラグはMayaが受け付けない。fast=Trueとは同時に指定できない。
    これらの指定は短縮名を持たない(``cmds.shadingNode`` の ``s`` は ``shared`` の ``s`` と重なるため)。

    Args:
        type (str): Mayaのノード型名。
        fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
        name (str): Mayaへ渡すノード名。DAGパスの区切り ``|`` は含められない
            (Mayaは黙って置き換えてしまうため、エラーにする)。
        n (str): nameの短縮名。nameと同時には指定できない。
        parent (object): 親のノード。Node・Plug・Component・APIのオブジェクトは、持ち主のノードの完全パスに変える。
        p (object): parentの短縮名。parentと同時には指定できない。
        shared (bool): Maya標準の共有の指定。同じ名前の共有ノードがある場合に使う。
        s (bool): sharedの短縮名。sharedと同時には指定できない。
        skipSelect (bool): Trueなら、作ったノードを選択しない。
        ss (bool): skipSelectの短縮名。skipSelectと同時には指定できない。
        asShader (bool): Trueなら、シェーダーとして作る(``cmds.shadingNode(asShader=True)``)。既定False。
        asTexture (bool): Trueなら、テクスチャとして作る。既定False。
        asUtility (bool): Trueなら、ユーティリティとして作る。既定False。
        asLight (bool): Trueなら、ライトとして作る。既定False。
        asPostProcess (bool): Trueなら、ポストプロセスとして作る。既定False。
        asRendering (bool): Trueなら、レンダリングのノードとして作る。既定False。
        **kwargs (object): 通常の処理では、そのほかのMayaのフラグとしてそのまま渡す。
            fast=Trueでは、対応していないフラグを作る前にエラーにする。

    Returns:
        Node: 作ったノードの、実際のnodeTypeに合ったオブジェクト。

    Raises:
        TypeError: 長い名前と短い名前を同時に指定した場合、fastがboolでない場合、parentが対応していない型の場合、
            cmds.createNodeに無いフラグ(query/editなど)を指定した場合、asShaderなどの指定がboolでない場合、
            またはasShaderなどを2つ以上Trueにした場合。
        ValueError: typeが空文字列か文字列でない場合、nameに ``|`` を含む場合、parent が空文字列の場合、
            または削除済みの対象を指定した場合。
        RuntimeError: Mayaが知らないノード型名の場合(unknownノードは残さない。この版に無い型は
            「not available in this Maya version」と示す)、parent が見つからない場合、
            fast=Trueでロックされた親かリファレンスされた親を指定した場合、またはMayaが作成を拒否した場合。
        NotImplementedError: fast=Trueで、対応していないフラグを指定した場合、またはasShaderなどを指定した場合。

    Examples:
        >>> import mlib
        >>> node = mlib.createNode("transform", name="example")
        >>> child = mlib.createNode("joint", n="child", p=node, ss=True)
        >>> # shape型はshapeが返り、name= はshapeに付く。transformは getTransform() で取得する。
        >>> selected = mlib.ls(selection=True)  # 作成したノードが選択されるため、選択は先に取る。
        >>> shape = mlib.createNode("locator", name="exampleShape")
        >>> transform = shape.getTransform()
        >>> shader = mlib.createNode("blinn", name="exampleMat", asShader=True)
    """
    _merge_flags(kwargs, ((name, n, "name", "n"), (parent, p, "parent", "p"), (shared, s, "shared", "s"), (skipSelect, ss, "skipSelect", "ss")))
    classification = _shading_classification(
        asShader=asShader, asTexture=asTexture, asUtility=asUtility, asLight=asLight, asPostProcess=asPostProcess, asRendering=asRendering
    )
    _require_bool(fast, "fast")
    if classification is not None and fast:
        raise NotImplementedError(f"fastのcreateNodeは{classification}に対応していません")
    # 親を指定しない作成は1回のcreateNodeなので、チャンクを開かない(親がjointなら inverseScale の接続もまとめる)。
    chunk = kwargs.get("parent") is not None or kwargs.get("p") is not None
    context = _edit_context("mlibCreateNode", fast)
    with context if chunk or fast else nullcontext():
        # 作成の実体はNodeの内部ヘルパー。nodesはcmdsを参照するため循環importを避けて関数内で読み込む。
        from ..nodes import Node

        return Node._create_node(type, kwargs, fast=fast, classification=classification)


def _shading_classification(**flags):
    """``cmds.shadingNode`` の分類の指定を確かめ、Trueにしたフラグの名前を返す。

    Args:
        **flags (bool): ``asShader`` などの指定。

    Returns:
        str | None: Trueにしたフラグの名前。どれもFalseならNone。

    Raises:
        TypeError: 指定がboolでない場合、または2つ以上Trueにした場合。
    """
    for key, value in flags.items():
        _require_bool(value, key)
    chosen = [key for key, value in flags.items() if value]
    if len(chosen) > 1:
        raise TypeError(f"{'と'.join(chosen)}は同時に指定できません")
    return chosen[0] if chosen else None
