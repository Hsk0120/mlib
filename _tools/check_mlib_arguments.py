"""mlib の公開 def の引数を、引数の表(``ARGUMENTS``)と突き合わせて検査・整形する。

同じ名前の引数が、メソッドによって受け方(位置かキーワード専用か)・既定値・型・説明の文で食い違わないように、
引数名ごとの決まりを1つの表に書き、署名と docstring をその表と比べる。``check_mlib_layout.py`` の L090・L094〜L096 が
「同じ名前のメソッドどうし」を比べるのに対して、このツールは「同じ名前の引数どうし」を比べる。

- A001: キーワード専用と決めた名前(表の ``kind="keyword"``)が、既定値つきの位置引数になっている
- A002: 既定値が表の ``default`` と違う
- A003: bool の既定値を持つ位置引数(表で位置と決めた ``worldSpace``・``state`` などを除く)
- A004: 表に無い名前が、2か所以上で受け方・既定値の食い違う使われ方をしている(表に足して決める)
- A005: 表の許可・名前が、もう使われていない(表から消す)
- A006: 引数の一覧のページ(``_docs/source/arguments.rst``)が表より古い(``--fix`` が作り直す)
- A010: docstring の型が既定値と合わない(None・bool・数・str)
- A011: 既定値つきの引数の説明に既定値の記述が無い、または署名と違う(省略を番兵で見分ける、Maya のフラグの入口は見ない)
- A012: 説明が表の決まり文句と違う
- A013: docstring の型の書き方が表と違う
- A014: キーワード専用の引数の並びが決まりと違う(その他 → fast → check → safe → 位置引数の短縮名。
  キーワード専用の引数の短縮名は、元の名前の直後)
- A015: ``Args:`` の並びが署名の順と違う(短縮名は元の名前の直後)

ast だけを使うため通常の Python で実行でき、mlib や Maya を import しない。``core/`` は内部の実装なので見ない。

--check  違反を一覧表示する(違反があれば終了コード1)。
--fix    動きを変えずに直せるもの(A010 の None・A011 の追記・A012・A013・A014・A015)を書き込み、引数の一覧のページを作り直して、残りを表示する。
--list   引数名ごとの使われ方(か所・受け方・既定値・型)を表示する。名前を渡すとその名前だけを、使う def つきで表示する。
--rst    引数の一覧のページ(reStructuredText)を、指定したファイルへ書く。
"""

import argparse
import ast
import collections
import fnmatch
import re
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
#: 引数の一覧のページ。``--fix`` が作り直し、``--check`` が古くないかを見る(A006)。
RST_PATH = PACKAGE_ROOT / "_docs" / "source" / "arguments.rst"
EXCLUDED_DIRS = {"__tests__", "tests", "docs", "_docs", "_tools", "__pycache__", ".logs", "core"}
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
SECTIONS = ("Args:", "Returns:", "Yields:", "Raises:", "Note:", "Examples:")
#: 省略を見分けるための番兵。本当の既定値は ``_pick_alias(..., default=X)`` から読む。
SENTINELS = ("_UNSET", "_OMITTED")
#: 既定値が種類ごとに違ってよい(表の ``default`` に書く)。
VARIES = "<VARIES>"
#: 表に既定値を書いていない(比べない)。
UNSPECIFIED = "<UNSPECIFIED>"
#: キーワード専用の引数の最後へ、この順に置く名前。
TAIL_ORDER = ("fast", "check", "safe")
#: docstring の既定値の記述(``既定False``・``既定は ``"deg"````・``既定値は3`` など)。
DEFAULT_NOTE = re.compile(r"既定(?:値)?(?:は|の)?\s*(``[^`]+``|[A-Za-z0-9_.+\-\"']+)")
#: 既定値の記述として認める言葉。
DEFAULT_WORDS = ("既定", "省略")
#: 短縮名の説明の書き出し。
ALIAS_TEXT = re.compile(r"^(?:``)?([A-Za-z_][A-Za-z0-9_]*)(?:``)?\s*の(?:短縮名|別名)")
INFORMATIONAL = frozenset()


class Argument:
    """引数名1つの決まり。

    Attributes:
        meaning (str): 働きの説明(引数の一覧のページに出す)。
        kind (str | None): ``"keyword"`` はキーワード専用、``"positional"`` は位置でも受ける、None は決めない。
        default (str): 既定値の式。``VARIES`` は種類ごとに違ってよい、``UNSPECIFIED`` は比べない。
        type (str | None): docstring の型の書き方(``None`` の部分は除いて比べる)。None は比べない。
        text (str | None): 説明の決まり文句。None は比べない。
        whole (bool): True なら説明の全体が ``text``、False なら書き出しが ``text``(後ろに足してよい)。
        variants (dict[str, str]): ``--fix`` が書き換える古い文と、書き換えた後の文。
        kindAllowed (dict[str, str]): 受け方が違ってよい def(``"Class.method"``・``"Class.*"``・``"maths:*"``)と理由。
        defaultAllowed (dict[str, str]): 既定値が違ってよい def と理由。
        reason (str): ``default=VARIES`` の理由。
    """

    def __init__(
        self, meaning, *, kind=None, default=UNSPECIFIED, type=None, text=None, whole=False, variants=None, kindAllowed=None, defaultAllowed=None, reason=""
    ):
        self.meaning = meaning
        self.kind = kind
        self.default = default
        self.type = type
        self.text = text
        self.whole = whole
        self.variants = dict(variants or {})
        self.kindAllowed = dict(kindAllowed or {})
        self.defaultAllowed = dict(defaultAllowed or {})
        self.reason = reason


#: まだ決めていない食い違いの理由の書き出し。決めたら揃えるか、理由を書き直す。
PENDING = "未決(2026-11-27): "
_KIND = "種類を選ぶ引数で、選べる種類と既定はメソッドごとに違う"
_VALUE = "そのメソッドの主な値。何を指すかはメソッドごとに違う"
_MAYA = "Maya のフラグをそのまま受ける入口"
_CHECK = "Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。"
_CHECK_OLD = "Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。"
_MATHS = "数学型は om2 と同じ位置引数のまま"

#: 引数の表。2か所以上で使う引数名の決まりを書く(正本)。
ARGUMENTS = {
    # どのメソッドでも同じ働きの引数。
    "fast": Argument("TrueはUndoなしのOpenMaya更新。", kind="keyword", default="False", type="bool", text="TrueはUndoなしのOpenMaya更新。既定False。"),
    "check": Argument(
        "書き込む前に、値と書き込み先を確かめる。",
        kind="keyword",
        default="False",
        type="bool",
        text=_CHECK,
        variants={_CHECK_OLD: _CHECK + "確かめるのは、書き込めるか(ロック・入力の接続が無いか)。"},
    ),
    "safe": Argument("失敗しても例外にしない。", kind="keyword", default="False", type="bool", text="Trueなら、失敗しても例外にしない。既定はFalse。"),
    "skipExisting": Argument(
        "すでに目的の状態なら何もしない。", kind="keyword", default="False", type="bool", text="Trueなら、すでに目的の状態のときは何もしない。既定はFalse。"
    ),
    "skipConnected": Argument(
        "接続があるノードは削除しない。", kind="keyword", default="False", type="bool", text="Trueなら、接続があるノードは削除しない。既定はFalse。"
    ),
    "get": Argument("書き込まずに、書き込む予定の値を返す。", kind="keyword", default="False", type="bool"),
    "force": Argument("障害があっても実行する(Maya の force と同じ意味)。", kind="keyword", default="False", type="bool"),
    "unlock": Argument("ロックを一時的に外してから処理する。", kind="keyword", default="False", type="bool"),
    "repair": Argument("不正なウェイトを直してから処理する。", kind="keyword", default="False", type="bool"),
    "worldSpace": Argument(
        "Trueはワールド空間、Falseはローカル(オブジェクト)空間。",
        kind="positional",
        default="False",
        type="bool",
        defaultAllowed={
            "Joint.getBoneSegments": "ボーンの線分はワールドのマトリクスが元の値で、ローカルで使う場面がほぼ無い",
            "SkinCluster.restoreBindPose": "バインドポーズはワールドのマトリクスで保存してある",
        },
    ),
    "ws": Argument("worldSpace の短縮名。", kind="keyword", type="bool", text="worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。", whole=True),
    "state": Argument("オン・オフを設定する値。", kind="positional", default="True"),
    "unit": Argument(
        '角度の数値の単位(``"deg"`` は度、``"rad"`` はラジアン)。',
        kind="keyword",
        default="'deg'",
        type="str",
        defaultAllowed={
            "Quaternion.*": "クォータニオンは中身も om2 もラジアン。数学型は om2 に合わせる",
            "Node.setKey": "None は「指定しない」。アトリビュートが角度なら度(角度でないのに指定したら TypeError にするため)",
            "*Plug.*": "None は「指定しない」。アトリビュートが角度なら度(角度でないのに指定したら TypeError にするため)",
        },
    ),
    "timeUnit": Argument(
        '時間の数値の単位(``"frame"`` は今のUIの時間単位のフレーム、``"sec"`` は秒)。',
        kind="keyword",
        default="'frame'",
        type="str",
        defaultAllowed={"*Plug.*": "None は「指定しない」。アトリビュートが時間ならフレーム(時間でないのに指定したら TypeError にするため)"},
    ),
    "distanceUnit": Argument("距離の数値の単位。None は今のUIの距離単位。", kind="keyword", default="'cm'", type="str"),
    "uiUnits": Argument("今のUIの単位の数値で受け渡しする。", kind="keyword", default="False", type="bool"),
    "all": Argument("1つでなく全部を対象にする。", kind="keyword", default="False", type="bool"),
    "full": Argument("DAG のフルパスの名前にする。", kind="keyword", default="False", type="bool"),
    "add": Argument("置き換えずに、今あるものへ加える。", kind="keyword", default="False", type="bool"),
    "relative": Argument(
        "今の値からの相対で変える。", kind="keyword", default="False", defaultAllowed={"DagNode.reorder": "cmds.reorder -relative のフラグ名(動かす数)"}
    ),
    "normalize": Argument("ウェイトを正規化する。", kind="keyword", default="True", type="bool"),
    "transferToParent": Argument("外すインフルエンスのウェイトを親へ移す。", kind="keyword", default="True", type="bool"),
    "removeInfluence": Argument("skinCluster のインフルエンスから外してから削除する。", kind="keyword"),
    "influence": Argument("インフルエンス(対象として渡すとき)、またはインフルエンスとして使う側を調べる指定(bool)。", kind="keyword"),
    "leaves": Argument("コンパウンドアトリビュートの末端の子まで対象にする。", kind="keyword", default="False", type="bool"),
    "children": Argument(
        "子も対象にする。",
        kind="keyword",
        type="bool",
        default="True",
        defaultAllowed={
            "Node.setAttrFlags": "フラグの設定は、指定したアトリビュートだけが既定(Maya と同じ)",
            "Plug.setFlags": "フラグの設定は、指定したアトリビュートだけが既定(Maya と同じ)",
        },
    ),
    "includeSelf": Argument(
        "自身を結果に含める。",
        kind="keyword",
        default=VARIES,
        type="bool",
        reason="インスタンスの一覧は自身を含む(getInstances は True)、子の一覧は含まない(getChildren は False)のがふつう",
    ),
    "allDescendents": Argument("子孫まで含める。", kind="keyword", default="False", type="bool"),
    "intermediates": Argument("中間オブジェクトも含める。", kind="keyword", default="False", type="bool"),
    "removeNamespace": Argument("名前空間を取り除く。", kind="keyword", default="False", type="bool"),
    "sortBy": Argument("並べる順。", kind="keyword", default=VARIES, reason="選べる順がメソッドごとに違う"),
    "asPair": Argument("相手との組で返す。", kind="keyword", default="False", type="bool"),
    "asPlug": Argument("ノードでなく Plug で返す。", kind="keyword", default="False", type="bool"),
    "asNode": Argument("Plug でなくノードで返す。", kind="keyword", default="False", type="bool"),
    "input": Argument("入力側を対象にする(``AnimCurve`` ではカーブの入力の位置で、主な値として位置で渡す)。", kind="keyword"),
    "output": Argument(
        "出力側を対象にする(``ShadingEngine.setShader`` はシェーダーの出力のアトリビュート)。",
        kind="keyword",
        default=VARIES,
        reason="bool の指定と、出力のアトリビュートの名前",
    ),
    "locked": Argument("ロックの状態(None は変えない・絞り込まない)。", kind="keyword", default="None"),
    "keyable": Argument("キーを打てるかの状態(None は変えない)。", kind="keyword", default="None"),
    "channelBox": Argument(
        "チャンネルボックスに出すかの状態(None は変えない)。",
        kind="keyword",
        default="None",
        defaultAllowed={"Node.addAttr": "作るときの指定なので、変えないという値が無い"},
    ),
    "perFace": Argument("頂点ごとでなく、面頂点ごとに扱う。", kind="keyword", default="False", type="bool"),
    "outliner": Argument("描画色でなく、アウトライナーの色を扱う。", kind="keyword", default="False", type="bool"),
    "toShape": Argument("Transform でなく、その Shape の色を扱う。", kind="keyword", default="False", type="bool"),
    "uvSet": Argument("UVセットの名前。None は今のUVセット。", kind="keyword", default="None", type="str | None"),
    "colorSet": Argument("カラーセットの名前。None は今のカラーセット。", kind="keyword", default="None", type="str | None"),
    "geometryIndex": Argument("デフォーマーの形状の番号。None は最初の形状。", kind="keyword", default="None"),
    "faceVertices": Argument("対象の面頂点。None は全部。", kind="keyword", default="None"),
    "fullWeight": Argument("ウェイトが1のときの値。", kind="keyword", default="1.0"),
    "timeOffset": Argument("時刻へ足す値。", kind="keyword", default="0"),
    "valueOffset": Argument("値へ足す値。", kind="keyword", default="0"),
    "aimAxis": Argument("向ける軸。", kind="keyword", default="'x'"),
    "upAxis": Argument("上へ向ける軸。", kind="keyword", default="'y'"),
    "zeroScaleOrient": Argument("scaleOrient を0にする。", kind="keyword"),
    "missing": Argument("無くなった対象の扱い。", kind="keyword"),
    "nameMap": Argument(
        "名前空間を除いた名前の対応表。",
        kind="keyword",
        default="None",
        type="dict[str, str] | None",
        kindAllowed={"NameMapping.__init__": "この3つの指定を持つクラスの作り方"},
    ),
    "namespaceMap": Argument(
        "名前空間の対応。",
        kind="keyword",
        default="None",
        type="dict[str, str] | None",
        kindAllowed={"NameMapping.__init__": "この3つの指定を持つクラスの作り方"},
    ),
    "replace": Argument(
        "順に当てる文字列の置き換え(``select`` では今の選択を置き換える指定)。",
        kind="keyword",
        default="None",
        kindAllowed={"NameMapping.__init__": "この3つの指定を持つクラスの作り方"},
    ),
    "path": Argument("ファイルのパス。", type="str | os.PathLike"),
    # 種類を選ぶ引数。選べる値と既定はメソッドごとに違う。
    "kind": Argument("対象の種類を名前で選ぶ。", kind="keyword", default=VARIES, type="str", reason=_KIND),
    "what": Argument("取得するものを名前で選ぶ。", kind="keyword", default=VARIES, type="str", reason=_KIND),
    "type": Argument(
        "ノード型・アトリビュートの型・返すコンポーネントの種類。",
        kind="keyword",
        default=VARIES,
        reason="絞り込みの None と、返す種類の既定がメソッドごとに違う",
        kindAllowed={"Node.addAttr": _MAYA + "。名前と型を続けて書く", "NodeRef.__init__": "保存する値を並べる作り方"},
    ),
    "method": Argument("処理の方法を名前で選ぶ。", kind="keyword", default=VARIES, reason=_KIND),
    "mode": Argument("書き込み方・合わせ方を名前で選ぶ。", kind="keyword", default=VARIES, reason=_KIND),
    "index": Argument(
        "番号。",
        kind="keyword",
        default=VARIES,
        reason="None は全部・自動、番号の既定は対象ごと",
        kindAllowed={"Components.pop": "list.pop と同じ", "MultiPlug.getElement": "主な値(要素の番号)"},
    ),
    "tolerance": Argument(
        "同じとみなす誤差。",
        kind="keyword",
        default=VARIES,
        reason="比べるものが違う: 数学の値は 1e-10、Maya の関数へ渡すものは Maya の既定(1e-6・1e-7)、頂点の対応付けは形状の大きさ(0.01)。None と 0.0 は誤差で絞らない",
        kindAllowed={"maths:*": _MATHS},
    ),
    "vertices": Argument(
        "対象の頂点。None は全部。",
        kind="keyword",
        default="None",
        kindAllowed={"BlendShape.resetTargetVertices": "主な値を2通りで受ける(vertices か tolerance=)"},
    ),
    "time": Argument(
        "時刻・時刻の範囲。None は絞らない。",
        kind="keyword",
        default="None",
        kindAllowed={"bakeResults": "cmds.bakeResults の主な値(対象・アトリビュート・範囲)を順に受ける"},
    ),
    # 主な値として位置でも受ける引数。何を指すかはメソッドごとに違う。
    "value": Argument("書き込む値。", kind="positional", default=VARIES, reason=_VALUE),
    "name": Argument("名前。作るものの名前は None で Maya に任せる。", kind="positional", default=VARIES, reason='名前空間は ``":"`` (ルート)が既定'),
    "parent": Argument("親。None はワールド直下・指定しない。", kind="positional", default=VARIES, reason='名前空間は ``":"`` (ルート)が既定'),
    "axis": Argument(
        '軸(``"x"``/``"y"``/``"z"``・0/1/2、またはベクトル)。',
        kind="positional",
        default=VARIES,
        reason="軸の名前を受けるものと、向きのベクトルを受けるものがある",
    ),
    "base": Argument("blendShape のベースの形状。None は最初のベース。", kind="positional", default="None"),
    "at": Argument(
        "値を書く・読むアトリビュートの段(``Transform``)、またはアトリビュートの名前(Maya のフラグ)。",
        kind="positional",
        default=VARIES,
        reason="Transform の段の番号と、Maya のフラグの短縮名",
    ),
    "nodes": Argument("対象のノードの並び。None は指定なし。", kind="positional", default="None"),
    "members": Argument("対象のメンバーの並び。None は指定なし。", kind="positional", default="None"),
    "items": Argument("対象の並び。None は指定なし。", kind="positional", default="None"),
    "names": Argument("名前の並び。None は指定なし。", kind="positional", default="None"),
    "destination": Argument("出力側を対象にする指定(bool)、または移す先。", kind="positional", default=VARIES, reason="接続の向きの bool と、移す先の指定"),
    "source": Argument(
        "入力側を対象にする指定(bool)、または元になるもの。", kind="positional", default=VARIES, reason="接続の向きの bool と、元になるものの指定"
    ),
    "geometry": Argument("対象の形状。", kind="positional"),
    "weights": Argument("ウェイトの値、またはウェイトのファイル。", kind="positional", default="None"),
    "degree": Argument("カーブ・サーフェスの次数。", kind="positional", default="3", defaultAllowed={"NurbsCurve.rebuild": "None は今の次数のまま"}),
    "normal": Argument("法線の向き。", kind="positional", default=VARIES, reason="作る円の向きと、書き込む法線"),
    "radius": Argument("半径。", kind="positional"),
    "width": Argument("幅。", kind="positional", default=VARIES, reason="形状の大きさと、進捗の表示の桁数"),
    "curve": Argument(
        "カーブ(ノード)、またはイージングの種類の名前。", kind="positional", default=VARIES, reason="ノードを受けるものと、イージングの名前を受けるものがある"
    ),
    "up": Argument("上の向きのベクトル。", kind="positional", default=VARIES, reason="None は自動で決める"),
    "to": Argument("終わりのノード・移す先。", kind="positional"),
    "namespace": Argument("名前空間。None は今のまま・付けない。", kind="positional", default="None"),
    "layer": Argument("アニメーションレイヤー。None はレイヤーを通さない。", kind="positional"),
    "maxDistance": Argument("探す距離の上限。None は制限なし。", kind="positional", default="None"),
    "order": Argument("回転順序。", kind="positional", default=VARIES, reason="None は今の回転順序のまま"),
    "translate": Argument(
        "移動の値、または移動を対象にする指定。", kind="positional", default=VARIES, reason="値を受けるものと、対象にするかの bool を受けるものがある"
    ),
    "rotate": Argument(
        "回転の値、または回転を対象にする指定。", kind="positional", default=VARIES, reason="値を受けるものと、対象にするかの bool を受けるものがある"
    ),
    "scale": Argument(
        "スケールの値、またはスケールを対象にする指定。", kind="positional", default=VARIES, reason="値を受けるものと、対象にするかの bool を受けるものがある"
    ),
    "shear": Argument(
        "シアーの値、またはシアーを対象にする指定。", kind="positional", default=VARIES, reason="値を受けるものと、対象にするかの bool を受けるものがある"
    ),
    "position": Argument(
        "位置の値、または位置を対象にする指定。", kind="positional", default=VARIES, reason="値を受けるものと、対象にするかの bool を受けるものがある"
    ),
    "jointOrient": Argument(
        "jointOrient の値、または jointOrient を対象にする指定。",
        kind="keyword",
        default=VARIES,
        reason="値を受けるものと、対象にするかの bool を受けるものがある",
    ),
    "rotateAxis": Argument(
        "rotateAxis の値、または rotateAxis を対象にする指定。",
        kind="keyword",
        default=VARIES,
        reason="値を受けるものと、対象にするかの bool を受けるものがある",
    ),
    "inTangentType": Argument(
        "入る側の接線の種類。None は Maya の設定のまま。",
        kind="positional",
        default="None",
        defaultAllowed={"DrivenKey.setKey": "ドリブンキーは Maya の設定に左右されない linear が既定"},
    ),
    "outTangentType": Argument(
        "出る側の接線の種類。None は Maya の設定のまま。",
        kind="positional",
        default="None",
        defaultAllowed={"DrivenKey.setKey": "ドリブンキーは Maya の設定に左右されない linear が既定"},
    ),
    "threshold": Argument("しきい値。", kind="positional", default=VARIES, reason="比べるものがメソッドごとに違う"),
    "ndigits": Argument(
        "丸める小数の桁数。None は整数へ丸める(round と同じ)。",
        kind="positional",
        default="None",
        defaultAllowed={"SkinCluster.roundWeights": "ウェイトを整数へ丸める使い方は無いので、小数3桁が既定"},
    ),
    "start": Argument("始まりの番号・値。", kind="positional", default=VARIES, reason="list.index の始まりと、空きを探し始める番号"),
    "preserve": Argument(
        "変えたあとも見た目(ワールドの姿勢)を保つ。",
        kind="keyword",
        default=VARIES,
        reason="setRotateOrder は省けない(回転順序だけ変えるのか向きを保つのかで結果が大きく違う)、setQuaternion は False",
    ),
    "failed": Argument(
        "失敗した Edit を対象にする。",
        kind="keyword",
        default=VARIES,
        reason="Maya の referenceQuery・referenceEdit の既定と同じ(getEdits は False、removeEdits は True)",
    ),
    "unused": Argument(
        "使っていないものを対象にする。", kind="keyword", default=VARIES, reason="None は絞り込まない(getInfluences)、False は対象にしない(removeInfluences)"
    ),
    "maintain": Argument("上限を保つ。", kind="keyword", default=VARIES, reason="None は今の設定のまま(setMaxInfluences)"),
    "influenceAssociation": Argument("インフルエンスを対応付ける方法の並び。", kind="keyword", default=VARIES, reason="コピーとミラーで Maya の既定が違う"),
}

#: bool の既定値を持つ位置引数として残すもの(A003)。キーは ``"Class.method"`` の形、値は ``{引数名: 理由}``。
BOOL_POSITIONAL_ALLOWED = {}


class Param:
    """署名の引数1つ。"""

    def __init__(self, node, kind, default):
        self.node = node
        self.name = node.arg
        self.kind = kind
        self.default_node = default
        self.source_default = None if default is None else ast.unparse(default)
        self.default = self.source_default

    @property
    def required(self):
        return self.source_default is None

    @property
    def sentinel(self):
        return self.default in SENTINELS


class Entry:
    """docstring の ``Args:`` の1項目。"""

    def __init__(self, stars, name, type_text, lines):
        self.stars = stars
        self.name = name
        self.type = type_text
        self.lines = lines

    @property
    def text(self):
        head = split_head(self.lines[0].strip())[3]
        return head + "".join(line.strip() for line in self.lines[1:])


class Function:
    """公開 def 1つ(署名と docstring の Args)。"""

    def __init__(self, path, package, owner, node, lines):
        self.path = path
        self.package = package
        self.owner = owner
        self.node = node
        self.lines = lines
        arguments = node.args
        positional = arguments.posonlyargs + arguments.args
        defaults = [None] * (len(positional) - len(arguments.defaults)) + list(arguments.defaults)
        self.params = [Param(arg, "positional", default) for arg, default in zip(positional, defaults)]
        if self.params and self.params[0].name in ("self", "cls") and "." in owner:
            self.params = self.params[1:]
        self.params += [Param(arg, "keyword", default) for arg, default in zip(arguments.kwonlyargs, arguments.kw_defaults)]
        self.vararg = arguments.vararg.arg if arguments.vararg else None
        self.kwarg = arguments.kwarg.arg if arguments.kwarg else None
        picked = pick_alias_defaults(node)
        for param in self.params:
            if param.sentinel and param.name in picked:
                param.default = picked[param.name]
        self.block = None
        self.entries = None
        self.read_docstring()

    def matches(self, pattern):
        return fnmatch.fnmatchcase(self.owner, pattern) or fnmatch.fnmatchcase(f"{self.package}:{self.owner}", pattern)

    def read_docstring(self):
        """``Args:`` の項目と、その行の範囲(0始まり・終わりは含まない)を読む。読めない形なら項目は None。"""
        body = self.node.body
        if not (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str)):
            return
        first, last = body[0].lineno - 1, body[0].end_lineno - 1
        start = next((i for i in range(first, last + 1) if self.lines[i].strip() == "Args:"), None)
        if start is None:
            return
        depth = indent_of(self.lines[start]) + 4
        entries = []
        index = start + 1
        while index <= last:
            line = self.lines[index]
            stripped = line.strip()
            if not stripped or indent_of(line) < depth or stripped in SECTIONS or stripped.startswith('"""'):
                break
            if indent_of(line) == depth:
                head = split_head(stripped)
                if head is None:
                    return
                entries.append(Entry(head[0], head[1], head[2], [line]))
            elif entries:
                entries[-1].lines.append(line)
            else:
                return
            index += 1
        if '"""' in "".join(line for entry in entries for line in entry.lines):
            return
        self.block = (start + 1, index)
        self.entries = entries

    def entry(self, name):
        return next((entry for entry in self.entries or () if entry.name == name and not entry.stars), None)

    def aliases(self):
        """短縮名 → 元の名前(docstring の「Xの短縮名」から読む)。"""
        names = {param.name for param in self.params}
        result = {}
        for entry in self.entries or ():
            match = ALIAS_TEXT.match(entry.text)
            if match and match.group(1) in names and entry.name in names and match.group(1) != entry.name:
                result[entry.name] = match.group(1)
        return result


class Violation:
    """検出した違反。"""

    def __init__(self, function, code, message, line=None):
        self.path = function.path if isinstance(function, Function) else function
        self.line = line or (function.node.lineno if isinstance(function, Function) else 1)
        self.code = code
        self.message = message

    def __str__(self):
        return f"{relative(self.path)}:{self.line}: {self.code} {self.message}"


def relative(path):
    try:
        return path.relative_to(PACKAGE_ROOT.parent).as_posix()
    except ValueError:
        return str(path)


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


def split_head(stripped):
    """``name (type): text`` の行を ``(星, 名前, 型またはNone, 文)`` に分ける。項目の形でなければ None。"""
    match = re.match(r"^(\*{0,2})([A-Za-z_]\w*)\s*", stripped)
    if not match:
        return None
    rest = stripped[match.end() :]
    type_text = None
    if rest.startswith("("):
        depth = 0
        for index, char in enumerate(rest):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    type_text = rest[1:index]
                    rest = rest[index + 1 :]
                    break
        else:
            return None
    if not rest.startswith(":"):
        return None
    return match.group(1), match.group(2), type_text, rest[1:].strip()


def pick_alias_defaults(node):
    """``_pick_alias(long, short, "long", "short", default=X)`` の X を、長い名前ごとに返す。"""
    found = {}
    for inner in ast.walk(node):
        if not (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "_pick_alias" and inner.args):
            continue
        if isinstance(inner.args[0], ast.Name):
            for keyword in inner.keywords:
                if keyword.arg == "default":
                    found[inner.args[0].id] = ast.unparse(keyword.value)
    return found


def decorator_name(node):
    if isinstance(node, ast.Call):
        node = node.func
    return ast.unparse(node)


def is_checked(node):
    """検査する def か(公開の名前か ``__init__`` で、property・setter・overload でない)。"""
    if node.name.startswith("_") and node.name != "__init__":
        return False
    names = [decorator_name(d) for d in node.decorator_list]
    return not any(name in ("property", "cached_property", "overload") or name.endswith((".setter", ".deleter")) for name in names)


def source_files(root):
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).parts
        if any(part in EXCLUDED_DIRS or part.startswith(".") for part in parts[:-1]):
            continue
        yield path


def collect(root, files=None):
    """パッケージの公開 def を集める。

    Args:
        root (Path): パッケージのフォルダー。
        files (list[Path] | None): 読むファイル。None なら全部。

    Returns:
        list[Function]: 集めた def。
    """
    functions = []
    for path in files or source_files(root):
        text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
        lines = text.split("\n")
        tree = ast.parse(text, filename=str(path))
        parts = path.relative_to(root).parts
        package = parts[0] if len(parts) > 1 else "root"
        for node in tree.body:
            if isinstance(node, FUNCTIONS) and is_checked(node) and node.name != "__init__":
                functions.append(Function(path, package, node.name, node, lines))
            elif isinstance(node, ast.ClassDef):
                functions.extend(
                    Function(path, package, f"{node.name}.{item.name}", item, lines) for item in node.body if isinstance(item, FUNCTIONS) and is_checked(item)
                )
    return functions


# ---------------------------------------------------------------- 検査


def literal_kind(default):
    """既定値の式の種類(``"none"``・``"bool"``・``"number"``・``"str"``)。ほかは None。"""
    if default == "None":
        return "none"
    if default in ("True", "False"):
        return "bool"
    if re.fullmatch(r"-?\d+(\.\d*)?(e-?\d+)?", default or ""):
        return "number"
    if re.fullmatch(r"'[^']*'|\"[^\"]*\"", default or ""):
        return "str"
    return None


def union_parts(type_text):
    parts, depth, current = [], 0, ""
    for char in type_text:
        if char in "[(":
            depth += 1
        elif char in "])":
            depth -= 1
        if char == "|" and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    parts.append(current.strip())
    return [part for part in parts if part]


def without_none(type_text):
    return " | ".join(part for part in union_parts(type_text) if part != "None")


def type_problem(type_text, default):
    """docstring の型が既定値を含まないなら、足りない種類の名前を返す。"""
    heads = {part.split("[")[0].split(".")[-1] for part in union_parts(type_text)}
    if heads & {"object", "Any"}:
        return None
    kind = literal_kind(default)
    if kind == "none" and "None" not in heads:
        return "None"
    if kind == "bool" and "bool" not in heads:
        return "bool"
    if kind == "number" and not heads & {"int", "float"}:
        return "数"
    if kind == "str" and "str" not in heads:
        return "str"
    return None


def format_default(default):
    """既定値を説明に書く形にする。"""
    if literal_kind(default) in ("none", "bool", "number"):
        return default
    # 日本語の文に続けて書くので、reStructuredText のインラインリテラルになるよう前に空白を置く。
    if literal_kind(default) == "str":
        return f' ``"{default[1:-1]}"``'
    return f" ``{default}``"


def noted_default(text):
    """説明に書いてある既定値(比べられる値だけ)を返す。無ければ None。"""
    match = DEFAULT_NOTE.search(text)
    if not match:
        return None
    token = match.group(1).strip("`").strip()
    if literal_kind(token) or (literal_kind(f'"{token}"') and token.startswith(("'", '"'))):
        return token
    return None


def same_default(noted, default):
    if literal_kind(noted) == "str" and literal_kind(default) == "str":
        return noted[1:-1] == default[1:-1]
    if literal_kind(noted) == "number" and literal_kind(default) == "number":
        return float(noted) == float(default)
    return noted == default


def canonical_keywords(function):
    """キーワード専用の引数の決まりの並びを返す。"""
    aliases = function.aliases()
    kinds = {param.name: param.kind for param in function.params}
    keywords = [param.name for param in function.params if param.kind == "keyword"]
    late = [name for name in keywords if kinds.get(aliases.get(name)) == "positional"]
    tail = [name for name in TAIL_ORDER if name in keywords]
    followers = collections.defaultdict(list)
    for name in keywords:
        if name in aliases and name not in late:
            followers[aliases[name]].append(name)
    ordered = []
    for name in [n for n in keywords if n not in tail and n not in late and n not in aliases] + tail:
        ordered.append(name)
        ordered.extend(followers.pop(name, ()))
    positional = [param.name for param in function.params if param.kind == "positional"]
    late.sort(key=lambda name: positional.index(aliases[name]))
    leftovers = [name for name in keywords if name not in ordered and name not in late]
    return ordered + leftovers + late


def canonical_entries(function, keywords=None):
    """``Args:`` の決まりの並び(署名の順。短縮名は元の名前の直後、可変長は最後)。"""
    aliases = function.aliases()
    keywords = canonical_keywords(function) if keywords is None else keywords
    names = [param.name for param in function.params if param.kind == "positional"] + keywords
    ordered = []
    for name in names:
        if name in aliases:
            continue
        ordered.append(name)
        ordered.extend(short for short in names if aliases.get(short) == name)
    documented = [entry.stars + entry.name for entry in function.entries]
    result = [name for name in ordered if name in documented]
    extras = [name for name in documented if name not in result and not name.startswith("*")]
    stars = [name for name in documented if name.startswith("**")] or []
    single = [name for name in documented if name.startswith("*") and not name.startswith("**")]
    return result + extras + single + stars


def allowed_reason(function, table, used, key):
    for pattern in table:
        if function.matches(pattern):
            used.add((key, pattern))
            return table[pattern]
    return None


def check(functions):
    """集めた def を表と比べ、違反を返す。

    Args:
        functions (list[Function]): 集めた def。

    Returns:
        list[Violation]: 違反。
    """
    violations = []
    used = set()
    seen = set()
    usages = collections.defaultdict(list)
    for function in functions:
        aliases = function.aliases()
        for param in function.params:
            usages[param.name].append((function, param))
            spec = ARGUMENTS.get(param.name)
            label = f"{function.owner}({param.name})"
            if spec:
                seen.add(param.name)
                misplaced = spec.kind == "keyword" and param.kind == "positional" and not param.required
                if misplaced and not allowed_reason(function, spec.kindAllowed, used, (param.name, "kind")):
                    violations.append(
                        Violation(function, "A001", f"{label} はキーワード専用にする(表の決まり)。主な値として位置で受けるなら kindAllowed に理由を書く")
                    )
                differs = spec.default not in (VARIES, UNSPECIFIED) and not param.required and not param.sentinel and param.default != spec.default
                if differs and not allowed_reason(function, spec.defaultAllowed, used, (param.name, "default")):
                    violations.append(
                        Violation(function, "A002", f"{label} の既定値 {param.default} が表の {spec.default} と違う。揃えるか defaultAllowed に理由を書く")
                    )
            if param.kind == "positional" and literal_kind(param.default) == "bool" and not (spec and spec.kind == "positional"):
                reasons = BOOL_POSITIONAL_ALLOWED.get(function.owner, {})
                if param.name in reasons:
                    used.add(("bool", function.owner, param.name))
                else:
                    violations.append(Violation(function, "A003", f"{label} は bool の位置引数。キーワード専用にする(f(True, False) と書けて読み違えるため)"))
            entry = function.entry(param.name) if function.entries is not None else None
            if entry is None:
                continue
            text = entry.text
            is_alias = param.name in aliases
            if entry.type is not None and not param.required and not param.sentinel:
                missing = type_problem(entry.type, param.default)
                if missing:
                    violations.append(Violation(function, "A010", f"{label} の型 ({entry.type}) に、既定値 {param.default} の {missing} が無い"))
            if spec and spec.type and entry.type is not None and without_none(entry.type) != without_none(spec.type):
                violations.append(Violation(function, "A013", f"{label} の型 ({entry.type}) の書き方が表の ({spec.type}) と違う"))
            if spec and spec.text and ((spec.whole and text != spec.text) or (not spec.whole and not text.startswith(spec.text))):
                violations.append(Violation(function, "A012", f"{label} の説明は決まり文句{'にする' if spec.whole else 'で始める'}: {spec.text}"))
            # 省略を番兵で見分ける引数(Maya のフラグをそのまま受ける入口)は、既定値を Maya に任せるので見ない。
            if not param.required and not is_alias and not param.sentinel and not (spec and spec.text and spec.whole):
                noted = noted_default(text)
                if noted is not None and not same_default(noted, param.default):
                    violations.append(Violation(function, "A011", f"{label} の説明の既定値 {noted} が署名の {param.default} と違う"))
                elif not any(word in text for word in DEFAULT_WORDS) and f"{param.default}(既定)" not in text:
                    violations.append(Violation(function, "A011", f"{label} の説明に既定値が無い(「既定は{format_default(param.default)}。」を足す)"))
        keywords = [param.name for param in function.params if param.kind == "keyword"]
        if function.entries is not None:
            wanted = canonical_keywords(function)
            if keywords != wanted:
                violations.append(Violation(function, "A014", f"{function.owner}: キーワード専用の引数の並び {', '.join(keywords)} → {', '.join(wanted)}"))
            documented = [entry.stars + entry.name for entry in function.entries]
            if documented != canonical_entries(function):
                violations.append(Violation(function, "A015", f"{function.owner}: Args: の並びを署名の順にする({', '.join(canonical_entries(function))})"))
    for name, items in sorted(usages.items()):
        if name in ARGUMENTS or len(items) < 2:
            continue
        optional = [(function, param) for function, param in items if not param.required]
        kinds = {param.kind for _function, param in optional}
        defaults = {param.default for _function, param in optional if not param.sentinel}
        problems = []
        if len(kinds) > 1:
            problems.append("受け方(位置 {}・キーワード専用 {})".format(*(sum(1 for _f, p in optional if p.kind == k) for k in ("positional", "keyword"))))
        if len(defaults) > 1:
            problems.append("既定値(" + "・".join(sorted(defaults)) + ")")
        if problems:
            function = items[0][0]
            violations.append(
                Violation(function, "A004", f"引数 {name} は {len(items)} か所で使われ、{' と '.join(problems)} が食い違う。ARGUMENTS に足して決める")
            )
    here = Path(__file__)
    for name, spec in ARGUMENTS.items():
        if name not in seen:
            violations.append(Violation(here, "A005", f"ARGUMENTS の {name} は、もう使われていない。表から消す", table_line(name)))
        for aspect, table in (("kind", spec.kindAllowed), ("default", spec.defaultAllowed)):
            violations.extend(
                Violation(here, "A005", f"ARGUMENTS の {name} の {aspect}Allowed の {pattern} は、もう違いが無い。表から消す", table_line(name))
                for pattern in table
                if ((name, aspect), pattern) not in used
            )
    for owner, reasons in BOOL_POSITIONAL_ALLOWED.items():
        violations.extend(
            Violation(here, "A005", f"BOOL_POSITIONAL_ALLOWED の {owner}・{name} は、もう bool の位置引数でない。表から消す", table_line(owner))
            for name in reasons
            if ("bool", owner, name) not in used
        )
    violations.sort(key=lambda v: (relative(v.path), v.line, v.code))
    return violations


def table_line(key):
    for number, line in enumerate(Path(__file__).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith(f'"{key}"'):
            return number
    return 1


# ---------------------------------------------------------------- 整形


def fixed_entry_lines(entry, param, spec, aliases):
    """項目1つを決まりの形へ直した行を返す(直す所が無ければ元の行)。"""
    lines = list(entry.lines)
    indent = " " * indent_of(lines[0])
    type_text = entry.type
    text = entry.text
    changed = False
    if type_text is not None:
        new_type = type_text
        if spec and spec.type and without_none(type_text) != without_none(spec.type):
            new_type = without_none(spec.type) + (" | None" if "None" in union_parts(type_text) else "")
        if not param.required and not param.sentinel and type_problem(new_type, param.default) == "None":
            new_type += " | None"
        if new_type != type_text:
            head = lines[0].strip()
            lines[0] = indent + head.replace(f"({type_text}):", f"({new_type}):", 1)
            type_text = new_type
            changed = True
    is_alias = param.name in aliases
    if spec and spec.text:
        replacement = spec.text if spec.whole and text != spec.text else spec.variants.get(text)
        if replacement:
            head = f"{entry.name} ({type_text}): " if type_text is not None else f"{entry.name}: "
            return [indent + head + replacement], True
    described = noted_default(text) is not None or any(word in text for word in DEFAULT_WORDS) or f"{param.default}(既定)" in text
    # バックスラッシュを含む既定値は、docstring を raw にする必要があるので自動では足さない(A011 が報告する)。
    described = described or chr(92) in (param.default or "")
    if not param.required and not is_alias and not param.sentinel and not (spec and spec.text and spec.whole) and not described:
        last = lines[-1].rstrip()
        if text and not last.endswith(("。", ".")):
            last += "。"
        lines[-1] = last + ("" if text else " ") + f"既定は{format_default(param.default)}。"
        changed = True
    return lines, changed


def fix_file(path, functions):
    """1ファイルの def を直し、直した数を返す。"""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
    edits = []
    for function in functions:
        if function.entries is None:
            continue
        aliases = function.aliases()
        params = {param.name: param for param in function.params}
        keywords = [param for param in function.params if param.kind == "keyword"]
        wanted = canonical_keywords(function)
        if [param.name for param in keywords] != wanted and same_line_slots(keywords):
            slots = [slot_of(param) for param in keywords]
            texts = {param.name: slot_text(lines, slot) for param, slot in zip(keywords, slots)}
            edits.extend((slot, texts[name]) for slot, name in zip(slots, wanted))
        blocks = {}
        changed = False
        for entry in function.entries:
            param = params.get(entry.name) if not entry.stars else None
            if param is None:
                blocks[entry.stars + entry.name] = entry.lines
                continue
            new_lines, entry_changed = fixed_entry_lines(entry, param, ARGUMENTS.get(entry.name), aliases)
            blocks[entry.name] = new_lines
            changed = changed or entry_changed
        order = canonical_entries(function, wanted)
        if changed or order != [entry.stars + entry.name for entry in function.entries]:
            start, end = function.block
            replacement = [line for name in order for line in blocks[name]]
            edits.append((((start, 0), (end - 1, len(lines[end - 1]))), "\n".join(replacement)))
    if not edits:
        return 0
    for ((start_line, start_col), (end_line, end_col)), replacement in sorted(edits, key=lambda edit: edit[0], reverse=True):
        before = lines[start_line][:start_col]
        after = lines[end_line][end_col:]
        lines[start_line : end_line + 1] = (before + replacement + after).split("\n")
    path.write_bytes(newline.join(lines).encode("utf-8"))
    return len(edits)


def byte_column(line, offset):
    """ast の列(UTF-8 のバイト数)を、文字の位置へ直す。"""
    return len(line.encode("utf-8")[:offset].decode("utf-8"))


def slot_of(param):
    end = param.default_node if param.default_node is not None else param.node
    return ((param.node.lineno - 1, param.node.col_offset), (end.end_lineno - 1, end.end_col_offset))


def same_line_slots(params):
    """引数の区画がそれぞれ1行に収まっているか(複数行の既定値は入れ替えない)。"""
    return all(slot_of(param)[0][0] == slot_of(param)[1][0] for param in params)


def slot_text(lines, slot):
    (line, start), (_end_line, end) = slot
    raw = lines[line].encode("utf-8")
    return raw[start:end].decode("utf-8")


def fix(functions):
    """直せるものを書き込み、直したファイルの数を返す。"""
    by_path = collections.defaultdict(list)
    for function in functions:
        by_path[function.path].append(function)
    count = 0
    for path, items in by_path.items():
        # 区画の列は UTF-8 のバイト数なので、文字の位置へ直してから書き換える。
        if fix_file_bytes(path, items):
            count += 1
    return count


def fix_file_bytes(path, functions):
    """列をバイトから文字へ直す下ごしらえをして :func:`fix_file` を呼ぶ。"""
    lines = path.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
    for function in functions:
        for param in function.params:
            for node in (param.node, param.default_node):
                if node is not None and not getattr(node, "_columns_fixed", False):
                    node.col_offset = byte_column(lines[node.lineno - 1], node.col_offset)
                    node.end_col_offset = byte_column(lines[node.end_lineno - 1], node.end_col_offset)
                    node._columns_fixed = True
    return fix_file(path, functions)


# ---------------------------------------------------------------- 一覧


def list_usages(functions, names):
    """引数名ごとの使われ方を表示する。"""
    usages = collections.defaultdict(list)
    for function in functions:
        for param in function.params:
            usages[param.name].append((function, param))
    if names:
        for name in names:
            print(f"## {name}({len(usages.get(name, []))} か所)")
            for function, param in usages.get(name, []):
                entry = function.entry(name) if function.entries is not None else None
                default = "必須" if param.required else param.default
                print(f"  {function.package}:{function.owner}  {param.kind}  ={default}  ({entry.type if entry else '-'})  {entry.text if entry else ''}")
        return
    for name, items in sorted(usages.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(items) < 2:
            continue
        optional = [param for _function, param in items if not param.required]
        kinds = collections.Counter(param.kind for param in optional)
        defaults = collections.Counter(param.default for param in optional)
        mark = "表" if name in ARGUMENTS else "  "
        print(
            f"{mark} {name}: {len(items)} か所(必須 {len(items) - len(optional)})  位置 {kinds['positional']}・専用 {kinds['keyword']}  "
            + "既定 "
            + ", ".join(f"{d}×{n}" for d, n in defaults.most_common(6))
        )


def reference(function):
    """def へのリンク(Sphinx のロール)を返す。"""
    module = ".".join(function.path.relative_to(PACKAGE_ROOT.parent).with_suffix("").parts)
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]
    role = "meth" if "." in function.owner else "func"
    if function.owner.split(".")[0].startswith("_") or function.owner.endswith(".__init__"):
        return f"``{function.owner}``"
    return f":{role}:`{function.owner} <{module}.{function.owner}>`"


def render_rst(functions):
    """引数の一覧のページ(reStructuredText)を組み立てて返す。

    Args:
        functions (list[Function]): 集めた def。

    Returns:
        str: ページの全文。
    """
    usages = collections.defaultdict(list)
    for function in functions:
        for param in function.params:
            usages[param.name].append((function, param))
    names = sorted(ARGUMENTS, key=str.lower)

    def default_text(spec):
        if spec.default == VARIES:
            return "メソッドごと"
        return "" if spec.default == UNSPECIFIED else f"``{spec.default}``"

    def kind_text(spec):
        return {"keyword": "キーワード専用", "positional": "位置でも渡せる"}.get(spec.kind, "")

    out = [
        ".. このページは _tools/check_mlib_arguments.py が引数の表(ARGUMENTS)から作る。手で編集しない。",
        "",
        "引数の一覧",
        "==========",
        "",
        "2か所以上のメソッド・関数で使う引数の名前と、その決まりの一覧です。",
        "同じ名前の引数は、どのメソッドでも同じ働き・同じ受け方(位置で渡せるか、キーワード専用か)・同じ既定値にしてあります。",
        "そうでないものは、各引数の「例外」に理由を書いています。",
        "",
        "決まり",
        "------",
        "",
        "- 位置で渡すのは、そのメソッドの主な値(書き込む値・対象)と ``worldSpace``・``state`` だけです。",
        '  ほかの指定はキーワードで渡します(``node.rename("a", ignoreShape=True)``)。',
        "- オン・オフを選ぶ bool の引数は、``worldSpace``・``state`` を除いてキーワード専用です。",
        "  bool の引数に ``0``・``1``・``None`` を渡すと TypeError になります。",
        "- ``fast``・``check``・``safe`` は、キーワード専用の引数の最後にこの順で並びます。",
        "- ``worldSpace`` を受けるメソッドは、短縮名 ``ws`` も受けます(同時には指定できません)。",
        "- 角度は ``unit``、時間は ``timeUnit``、距離は ``distanceUnit`` で単位を選びます。",
        "",
        "早見表",
        "------",
        "",
        ".. list-table::",
        "   :header-rows: 1",
        "   :widths: 18 14 14 54",
        "",
        "   * - 引数",
        "     - 受け方",
        "     - 既定値",
        "     - 働き",
    ]
    for name in names:
        spec = ARGUMENTS[name]
        out += [f"   * - :ref:`{name} <argument-{name}>`", f"     - {kind_text(spec)}", f"     - {default_text(spec)}", f"     - {spec.meaning}"]
    out += ["", "引数ごとの決まり", "----------------", ""]
    for name in names:
        spec = ARGUMENTS[name]
        items = usages.get(name, [])
        out += [f".. _argument-{name}:", "", f"``{name}``", "~" * (len(name) + 4), "", spec.meaning, ""]
        if spec.kind:
            out.append(f"- 受け方: {kind_text(spec)}")
        if spec.default == VARIES:
            out.append(f"- 既定値: メソッドごとに違う({spec.reason.replace(PENDING, '')})")
        elif spec.default != UNSPECIFIED:
            out.append(f"- 既定値: ``{spec.default}``")
        if spec.type:
            out.append(f"- 型: ``{spec.type}``")
        if spec.text:
            out.append(f"- 説明の決まり文句: {spec.text}")
        for title, table in (("受け方の例外", spec.kindAllowed), ("既定値の例外", spec.defaultAllowed)):
            for pattern, reason in table.items():
                matched = sorted({function.owner for function, _param in items if function.matches(pattern)})
                out.append(f"- {title}: " + "・".join(f"``{owner}``" for owner in matched) + f" — {reason.replace(PENDING, '')}")
        seen = {}
        for function, _param in items:
            seen.setdefault(function.owner, function)
        out.append(f"- 使う所({len(seen)}): " + "、".join(reference(seen[owner]) for owner in sorted(seen)))
        out.append("")
    return "\n".join(out)


def write_rst(functions, target):
    """引数の一覧のページを書く。"""
    Path(target).write_text(render_rst(functions), encoding="utf-8", newline="\n")


def is_rst_current(functions):
    """文書のフォルダーにある引数の一覧のページが、今の表と同じかを返す(フォルダーが無ければ True)。"""
    if not RST_PATH.parent.is_dir():
        return True
    return RST_PATH.is_file() and RST_PATH.read_text(encoding="utf-8") == render_rst(functions)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--list", nargs="*", metavar="NAME")
    parser.add_argument("--rst", metavar="FILE")
    parser.add_argument("--codes", nargs="*", metavar="CODE", help="表示する違反のコードを絞る")
    parser.add_argument("--summary", action="store_true", help="コードごとの件数だけを表示する")
    options = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    functions = collect(PACKAGE_ROOT)
    if options.list is not None:
        list_usages(functions, options.list)
        return 0
    if options.rst:
        write_rst(functions, options.rst)
        return 0
    if options.fix:
        count = fix(functions)
        print(f"check_mlib_arguments: {count} ファイルを直しました。")
        functions = collect(PACKAGE_ROOT)
        if RST_PATH.parent.is_dir() and not is_rst_current(functions):
            write_rst(functions, RST_PATH)
            print(f"check_mlib_arguments: {relative(RST_PATH)} を作り直しました。")
    violations = check(functions)
    if not is_rst_current(functions):
        violations.append(Violation(RST_PATH, "A006", "引数の一覧のページが表より古い。format_mlib.bat(--check なし)で作り直す", 1))
    if options.codes:
        violations = [v for v in violations if v.code in options.codes]
    counts = collections.Counter(v.code for v in violations)
    if not options.summary:
        for violation in violations:
            print(violation)
    failing = [v for v in violations if v.code not in INFORMATIONAL]
    print(
        f"check_mlib_arguments: {len(functions)} 個の公開defを調べました。"
        + (" 違反: " + ", ".join(f"{c}×{n}" for c, n in sorted(counts.items())) if counts else " 違反はありません。")
    )
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
