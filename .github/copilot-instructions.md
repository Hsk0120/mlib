# mlib コーディングルール(GitHub Copilot 用)

mlib は `maya.api.OpenMaya`(API 2.0)を基盤にした Maya 用 Python ライブラリ。Node・Plug・Component・数学型と、
その隣接基盤(コマンド・共通処理・JSON 保存)を提供する。このファイルが「コードを書くときに守るルール」の正本。
個々の API の引数・戻り値・制限は各公開 API の docstring を正とする。

## 全体の原則

- リポジトリの直下がそのまま `mlib` パッケージ。テストは `__tests__/`、Sphinx 文書は `_docs/`、補助ツールは `_tools/`。
- 説明・作業報告・コメント・docstring は日本語。例外メッセージ・ログの文言は英語。
- Python 3.7(Maya 2022)で動く書き方にする(代入式 `:=`、`match`、`list[int]` 等の実行時の組込みジェネリクス、
  位置専用引数 `/`、`dict | dict` 等は使わない)。対象は Maya 2022〜2027。
- Qt 関連(PySide/PyQt/shiboken/qtpy 等)を import しない。Maya 標準 UI は利用側が cmds/mel で扱う。
- 独自の Maya プラグインを実装・同梱・自動ロードしない(`MPxCommand`・`MPxNode`・`MFnPlugin` による登録は
  Undo 対応やバージョン差の回避目的でも追加しない)。既存プラグインの状態照会・明示的なロード管理は可。
- 汎用 UI・設定ストア(OptionVar/Preferences)・シーン/プロジェクト/FBX 操作・専用 Color 型は本体へ追加しない。
- 旧名の互換別名・互換ファイルは残さない。改名したら使用側・テスト・docstring・Sphinx を同時に更新する。
- 同じ処理の別名を増やさない。正式な入口へ集約する。
- 版番号は `_version.py` の `__version__` だけに書く(`__init__.py` はそこから import する。`__all__` に入れない)。

## パッケージ構成と責務

| 場所 | 責務 |
| --- | --- |
| `cmds/` | Maya コマンド相当の関数(1関数1ファイル、関数名とファイル名は同じ) |
| `nodes/` | Node ラッパー(Maya の nodeType ごと)と複数形 `Nodes` 等 |
| `plugs/` | Plug ラッパー(アトリビュートの型ごと)と `Plugs` |
| `components/` | Mesh・NurbsCurve・NurbsSurface・Lattice のコンポーネント(単数/複数) |
| `maths/` | om2 を継承した数学型と `easing`(標準 `math` のみ) |
| `common/` | 選択・名前空間・参照関係・単位・プラグイン導入状態・イベント・遅延実行・汎用計算の型 |
| `core/` | 共通基底 `Object`・型登録 `NodeRegistry`・reload・拡張管理・編集基盤(`fastWrite`・`nodeEdit`・`geometryEdit`・`skinEdit`・`attributeEdit` 等) |
| `json/` | シーンのデータの JSON 保存・復元(codec・file・参照・`Snapshot`) |
| `logger.py` | 横断的な診断ログ・通知 |
| `decorator.py` | デコレーター・コンテキストマネージャーと、fast/safe・フラグ正規化・Undo 文脈の内部補助 |
| `util.py` | クラスに属さない小さな汎用関数と中立な値処理(標準ライブラリだけを import) |
| `_docs/` | Sphinx 文書 |

- `common` は直下へ置き、領域別のサブフォルダを作らない。`core` も通常の実行パッケージで、フォルダ名で公開/非公開を区分しない。
- 公開/非公開は明示 import・`__all__`・文書で示し、集約した内部補助は先頭 `_` で示す。`core` の全関数を正式 API にしない。
- `util.__all__` は `legalizeName`・`measure`・`mirrorArguments` の3件。util から Node/Plug/core/decorator を import しない。
- `decorator.__all__` は `undoChunk`・`undoTransaction`・`nativeUnits`・`preservedSelection`・`preservedSkinShape`・`viewportOff`。
- `Object`(`core/object.py`)は単数の `Node`・`Plug`・`Component` の共通基底。`from mlib.core.object import Object` で取得し、
  ルートへ再公開しない。数学値・複数形コレクション・保存データは `Object` の派生にしない。
- 拡張管理の正式入口は `from mlib.core import extensions`(ルートへ再公開しない)。
- クラスに関係する処理はそのクラスのメソッドへ置く。nodes/plugs/components に補助関数だけのファイルを増やさない。
- Maya 依存の有無は責務分離の基準にしない。対象に固有の取得・計算・更新は同じクラスに置く。

### 共通ヘルパーの置き場

| 置き場 | 主な内部ヘルパー |
| --- | --- |
| `decorator.py` | `_require_bool`・`_pick_alias`・`_merge_flags`・`_validated_flags`・`_edit_context`・`_undo_recording` |
| `util.py` | `_UNSET`・`_ArgumentError`・`_world_space`・`_finite`・`_finite_vector`・`_checked_tolerance`・`_checked_index`・`_unique_ordered`・`_mirror_axis`・`_angle_unit`・`_time_unit` |
| `core/object.py` | `_exists`・`_selection_plug`・`_selection_component` |
| `core/fastWrite.py` | `require_supported_type`・`require_writable`・`require_range`・`set_plug`・`set_attr`・`prepare_data` |
| `core/nodeEdit.py` | `require_editable`・`check_deletion` |
| `nodes/node.py` | `Node._from_name`・`Node._require_valid`・`Node._input_name`・`Nodes._resolve_inputs` |

- 単位変換の境界は `core.attributeType._convert_units`、型継承照会とそのキャッシュは `core.registry` に集約する。

## 命名

| 対象 | 規則 | 例 |
| --- | --- | --- |
| クラス | PascalCase | `SkinCluster`・`EulerRotate` |
| 公開関数・メソッド・プロパティ | lowerCamelCase | `getMatrix()`・`orderName` |
| 公開の独自引数 | lowerCamelCase。Maya のフラグと同名ならその表記 | `worldSpace`・`uiUnits`・`transferToParent` |
| 内部関数・内部メソッド・ローカル変数 | snake_case | `_resolve_input`・`namespace_map` |
| core 層の関数 | snake_case | `set_positions`・`require_writable` |
| 定数 | UPPER_SNAKE_CASE、説明は `#:` | `LOAD_FAILED` |
| Maya コマンドのファイル | Maya と同じ camelCase | `cmds/createNode.py` |
| Maya ノードのファイル | nodeType と同じ表記 | `skinCluster.py`・`animCurveTL.py` |
| その他のファイル | lowerCamelCase | `scriptJobs.py`・`multiPlug.py` |
| パッケージ | 小文字 | `nodes`・`common` |

- 公開引数は `__tests__/unit/test_static_public_args.py` が検査する。`*args`/`**kwargs` と既存の登録プロトコル(`NodeRegistry`・`reload_package` 等)は対象外。
- om2 から継承・オーバーライドする名前、Python の特殊メソッド、`dump`/`load` 等の標準 API 名は維持する。
- 動詞: `get`/`set` は値の取得・設定、`is`/`has` は判定、`create`/`add`/`remove` は作成・追加・除外。
  独自の取得は `getName()`・`getChildren()` のように `get` を付ける。判定は正式な `isX` に一本化する(is 省略入口は作らない)。
- シーン照会には get を付ける(`getNumVertices`・`getCvPositions`)。数学演算・保持値のプロパティ・om2 標準名は一律 get 化しない。
- 型変換は `as` 接頭辞。コピーを返す数学操作は `inverse`/`normal`/`mirror`、自身の更新は `invertIt`/`mirrorIt`(om2 標準の `normalize()` は例外)。
- 変換は Maya の表記に揃える: `Translate`/`EulerRotate`/`Scale`/`Shear`、`getTranslation`/`setTranslation`・`getRotate`/`setRotate`・
  `getScale`/`setScale`・`getShear`/`setShear`。`getT`・`getQ` 等の短縮アクセサーは作らない。
- アトリビュートを扱うメソッド名は `Attr`/`Attrs`。子クラスで基底メソッドと同名の別機能を公開しない。
- 状態の切替は `setVisibility(state)`・`setLocked(state)`・`setMuted(state)` の形。排他的な選択は `mode=` で指定する。
- 名前の取得は `getName()`(最短一意名)/`getFullName()`(完全パス)。生 API 取得は `mnode()`・`mpath()`・`mplug()`、
  function set は `mfn()`(毎回新規の最も具体的な MFn)。

### 内部名の規則

- 検証(例外を送出)は `_require_<条件>`。bool を返す判定は `_is_*`/`_has_*`。検査済みの値を返す検証は `_validated_*`。
  例外を送出する `_validate_*`・`_check_*` は新規に作らない(既存の登録プロトコル名 `Nodes._validate_inputs` 等は維持)。
- 変換・解決は `_resolve_<対象>`(`_as_*`・`_coerce_*` は使わない)。
- 書込みの実装分岐は `_<method>_fast` / `_<method>_cmds`(`_direct`・`_fast_xxx` は使わない)。
- function set の取得は `_<kind>_fn`(`_dependency_fn`・`_geometry_fn`)。`om2.MFnDependencyNode(self.mnode())` を直接書かない。
- 内部専用の引数は先頭 `_`(`_fn=None`)。公開 def には置かない。
- 略語を使わず完全語にする(`_influence_index`・`_all_vertices`)。
- 入力の名前解決は `Node._from_name`・`Node._input_name`・`Nodes._resolve_inputs` を使い、`Node(n)` で二重解決しない。
  cmds へ渡す名前は DAG ノードでは `getFullName()`。

## メソッドとプロパティ

- Maya へ問い合わせる操作はメソッド、オブジェクトが保持する値はプロパティ。シーン更新は明示的なメソッドで行う。

| 対象 | 形式 | 例 |
| --- | --- | --- |
| Maya の現在の状態・名前・アトリビュート情報 | メソッド | `node.getFullName()`・`plug.isLocked()` |
| 評価済みの座標など | メソッド | `vertex.getPosition()`・`mesh.getNumVertices()` |
| Maya の状態の変更 | 明示的なメソッド | `plug.set(value)`・`node.rename(name)` |
| 保持している参照・番号 | プロパティ | `component.shape`・`component.index` |
| 数学値の成分 | プロパティ/フィールド | `vector.x`・`matrix.translate` |

- 引数が無い・軽い・戻り値が数値という理由だけでプロパティにしない。内部でキャッシュしていても現在のシーン状態ならメソッド。
- プロパティの getter で Maya への問い合わせ・ノード作成・シーン更新を行わない。
- シーン編集用の property setter は追加しない(数学型のローカル値の setter は可)。
- 例外: `node.tx` は `node.getPlug("tx")` の省略アクセスで、`node.tx = 10` は `getPlug("tx").set(10)` と同じ書込み(Undo あり、角度は度)。
  Maya アトリビュートの無い名前への代入は AttributeError(Node のインスタンスへ任意の Python 属性を足さない)。
- シーンの作成・更新 API は基本として生成物や操作対象を返す(`Node.addAttr()` は Plug)。値を返さないものは docstring に `None`。

## cmds と OpenMaya の使い分け

- 読み取り・内部の照会・数値計算は om2 を基本とする。読み取りに `fast` を要求しない。
- 書き込みの通常経路は Undo 可能な `maya.cmds`。対応する `fast=True` は om2 による Undo なしの直接更新。
- `fast` は通常経路より実際に速くなる書き込みにだけ付ける。速くならない(約1.1倍以下)ものには付けず、
  docstring に「fast引数は持たない(理由)」と書く。1回の cmds で全体を処理するもの・om2 に同等機能が無いものも同様。
- `fast` は検証を省く指定ではない。入力検証・例外型・単位・戻り値の意味は通常経路と同じ。
- fast で扱えない操作・フラグは変更前に `NotImplementedError` で拒否する。Undo のグローバル設定変更や独自プラグインで補わない。
- 複数の om2 操作は1つの modifier に積んで `doIt` を1回にする。DAG 削除と DG 操作を同じ modifier に混在させない。
- 生の `om2.MPlug` 等は削除を検出できないので、削除操作をまたいで保持しない。有効性を確かめられる mlib のオブジェクトを保持する。
- cmds→om2 の読み取り置換は `__tests__/integration/test_cmds_parity.py` に cmds の生値との突き合わせを同時に追加し、
  一致しないものは cmds に戻す。om2 に対応 API が無い照会(`attributeName -nice`・`nodeType` の継承照会・`ls` の検索と並び順・
  `referenceQuery` の edit 系・`keyTangent -g`・環境系)は cmds のまま。

### fast の定型

```python
def setFoo(self, value, *, fast=False):
    _require_bool(fast, "fast")
    with _edit_context("mlibTransformSetFoo", fast):
        target = self._resolve_foo(value)   # 対象解決・検証は with の内側に1回だけ
        if fast:
            self._set_foo_fast(target)
        else:
            self._set_foo_cmds(target)
    return self
```

- 署名は `*, fast=False` を keyword-only の先頭に置く。本体の冒頭で `_require_bool(fast, "fast")`(委譲型でも省かない)。
- Undo 文脈は `with _edit_context("mlib<Class><Method>", fast):`(fast なら nullcontext、通常は `undoChunk`)。
- `undoTransaction`(`transaction=True`)は Undo 無効時に拒否する必要がある構築処理だけに使い、理由コメントを付ける。
- 内側の更新先へは `fast=fast` を明示的に渡す。呼出元の状態で `fast` を上書きしない。デコレーター・コンテキストで fast を切り替えない。
- Undo チャンク名はメソッドが `mlib<Class><Method>`(短縮しない。単数クラスは自身のクラス名)、モジュール関数が `mlib<Func>`
  (`mlibCreateNode`・`mlibDelete`)。ドット区切りは使わない。

### Undo

- 通常の公開書き込みは1回の呼び出しを Undo 1回にまとめる(複数形・一括更新も1回)。
- `undoChunk` は例外時に先行更新を残す。自動ロールバックを意味しない。巻き戻しが必要なものは `undoTransaction`。
- 一括更新では、検証できる項目(対象名・所属・入力値)を更新前に全件検証する。

## 例外と通知

- 公開 API の入力検証は `assert` を使わず、型付きの `raise` にする(テスト・内部整合性の assert は可)。

| 分類 | 例外型 | 対象 |
| --- | --- | --- |
| 型違い・別名競合・必須欠落 | `TypeError`(別名系は `util._ArgumentError`。TypeError の派生) | bool でない fast、長短名の同時指定、必須引数の不足、受け付けない入力型 |
| 値違い | `ValueError` | 空文字、範囲外、特異マトリクス、空集合、fast と無関係な非対応値 |
| シーンの状態 | `RuntimeError` | ロック、接続済み、参照、削除済み・無効ノード、不在 |
| 実装上の未対応 | `NotImplementedError` | fast 経路で扱えない操作・フラグ(変更前に拒否) |

- 「空でない文字列」の検証は、非 str を TypeError、空文字を ValueError に分ける。
- 文言は英語の f-string(`+` 連結は不可)。対象名は末尾に `: <getFullName() または plug.name()>`。
  - 型違い `<arg> must be <型>`(`fast must be a bool`)/ 値違い `<arg> must be <条件>` または `Expected <条件>`
  - 別名競合 `Specify only one of '<long>' and '<short>'` / 必須欠落 `Missing required argument: '<long>'`
  - 状態 `<対象> is locked|connected|referenced: <名前>`、`Cannot <action> an invalid <type>`(`Node._require_valid(action)`)
  - fast 非対応 `fast <publicMethodName> does not support <条件>`(公開メソッド名を書く)
- 名前を解決できない(存在しない・複数に一致)場合は最初の一致を返さず例外。名前変換の内部処理では、対応しない型は TypeError、
  空・削除済みは ValueError、解決できない文字列は RuntimeError。`Node(...)`/`mlib.getNode` の削除済みは RuntimeError のまま。
- アトリビュートが無い場合は `MissingAttributeError(AttributeError, RuntimeError)`、削除済みのアトリビュートは
  `DeletedAttributeError(ValueError, RuntimeError)`(どちらも `plugs/plug.py`)。
- Maya が範囲外の番号を黙って別の番号へ変換する場合も、読み替えずに例外にする。扱えないノード種別へ解決したら TypeError。
- 公開例外型の変更は破壊的変更。テストが `assertRaisesRegex` で文言を見ている箇所も同時に更新する。
- mlib 本体は例外を送出するだけで、同じ内容を `logger.error` で重ねて表示しない。通知して中断する利用側の入口は `logger.raiseWithNotify`。
- 捕捉して戻り値・検証結果へ変換する失敗に画面通知を足さない。広い `except` は拡張単位の隔離・後始末・再送出の境界だけ。
- ログは `mlib.logger` に集約し、`logger.warning("Failed: %s", error)` のように標準 logging の遅延書式へ渡す。
- Script Editor のエラー表示は mlib 内部のフレームを省く(`MLIB_FULL_TRACEBACK=1` で省略しない)。例外オブジェクト自体は変えない。

## 引数の規則

- mlib 独自メソッドは長名だけを持ち、通常の既定値を置く(`index=0` 等)。短縮名の別名・`_UNSET` の省略判定を追加しない。
- 短縮名の別名は Maya コマンドのフラグを受ける入口だけに置く: `cmds/` の関数(`ls`・`createNode`・`duplicate`・`select`・
  作成関数の Maya の短縮フラグ。`parent` の `p` は付けない)、`Node.addAttr`・`Transform.addConstraint`・`Transform.makeIdentity`・
  `Plug.setKey`・`DagNode.reorder`(`f/b/r`)、`getConnections` の `s/d/c/t/et/scn`、`Plug.connect/disconnect` の `f/l/na`。`delete` はフラグを受けない。
- 例外: `worldSpace` を受ける公開メソッドはすべて keyword-only の短縮名 `ws` も受ける(`test_world_space_has_short_alias` が検査)。

```python
def getFoo(self, worldSpace=_UNSET, *, ws=_UNSET):
    """..."""
    worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
```

- 長短の選択は `_pick_alias(long, short, longName, shortName, default=_UNSET)` で行い、インラインの `is not _UNSET` 展開は書かない。
  `_UNSET` の定義は `util` だけで、False/None の明示指定と省略の区別にだけ使う。`**kwargs` で渡すフラグ群は `_merge_flags` でよい。
- 空間指定は `worldSpace=True/False`(True はワールド、False はローカル)。bool 検査は `util._world_space()` に一本化する。
  既定値は各メソッドの仕様を維持する。om2 の `MSpace` 引数は変えない。
- 内部関数へ渡すときも `fast`・`worldSpace` 等の同じ名前を使い、`world_space` のような別名を増やさない。
- ミラーの `axis` は反転軸(`"x"`/`"y"`/`"z"`、0/1/2)とミラー面(`"YZ"`/`"XZ"`/`"XY"`)の両方を受け、解釈は `util._mirror_axis` に集約する。
- `safe=True` は API ごとに意味が違う(`Plug.set` は失敗数を返す、Transform の set 系は書けるチャンネルだけ更新、
  `addAttr`・`connect`・`connectTo`・`setAlias` は既に目的の状態なら何もしない)。意味の違う safe を安易に増やさない。
- 戻り値の型・単位・更新対象・破壊性が違う操作は、名前が似ていてもフラグで統合しない。

## 単位

- オブジェクト層: 距離 cm、角度の数値は度、時間の数値は現在の UI 時間単位のフレーム。数学層は om2 の概念(角度 rad)。コマンド層は maya.cmds の単位・フラグ。
- 角度の数値を受け渡す公開 API は `unit="deg"|"rad"`(既定は度)、時間は `timeUnit="frame"|"sec"`(既定はフレーム)を別の引数で受ける。
  単位名を逆の引数へ渡したら正しい引数名を示す ValueError。`uiUnits=True` は UI 単位で、`unit`/`timeUnit` と同時指定は ValueError。
- `EulerRotate`・`Quaternion`・`MTime`・`MAngle` は値自身が単位を持つので換算しない。数学型の生成は既定 rad(`unit="deg"` で度)。
- 内部は rad で計算し、公開境界で一度だけ換算する(通常・fast・safe で同じ)。fast は同じ内部単位の値を om2 へ直接渡す。
- `Plug.get()` の既定は内部単位、`get(uiUnits=True)` で UI 単位。Maya コマンド自体の単位解釈の例外(`addAttr` の範囲は内部単位等)に注意し、全コマンドへ UI 単位変換を機械的に当てない。
- 形状の作成関数の大きさは cm(UI 単位に依存しない)。

## 公開名と型の登録

- 公開名は所属パッケージの `__init__.py` に通常の import と `__all__` で明示する。ファイルを置くだけでは公開されない。
  クラスの走査・登録デコレーター・実行時の注入は使わない。漏れを実行時に黙って補わない。
- `common` は初期化順と reload のため遅延公開の `_exports` と `if TYPE_CHECKING:` を更新する。
- Node/Plug の型対応は `nodes/__init__.py`・`plugs/__init__.py` の `_WRAPPER_CLASSES`(Maya 型名 → クラス)に宣言する。
  `"constraint"` は `Constraint` として登録し、`"node"` は登録しない。
- ルートの `__getattr__` が `nodes`・`plugs`・`components`・`maths`・`common` の `__all__` にあるクラスを `mlib.Joint` のように
  毎回所属パッケージから返す(推奨の書き方)。ルートへ import して保持しない。名前が重なればルート→nodes→plugs→components→maths→common→生成クラスの順。
  定数・関数・`Object` は対象外。ルートの `__all__` は `_names + sorted(_classes)`。
- コマンドの追加は `cmds/__init__.py` とルート `__init__.py` の両方の import と `__all__`(`_names`)へ足す。
- 追加・削除後は `__tests__/checks/check_mlib_exports.py`(`runStatic.py` に含まれる)を通す。
- `mlib.reload()` は依存順に再読み込みする。reload 後は保持中の Node/Plug・クラス・生成クラスを取り直す。改名・移動は reload 後も廃止名が残らないことを確かめる。

### 動的クラス

- `_WRAPPER_CLASSES` に無い nodeType は要求時にクラスを生成する(型名の先頭を大文字にした名前。`pointLight` → `PointLight`)。
  `Node` へのフォールバックは Maya が認識しない型名だけ。手書きクラスの明示登録を優先し、生成はその補完に限る。
- 生成クラスの基底は Maya の継承チェーン上で最も近い登録クラス。間の抽象型のクラスは生成しない。
- `mlib.nodes.<TypeName>`・`mlib.<TypeName>` でも取得できる。認識しない型名は AttributeError(それ以外の例外を出さない)。
- 生成クラスは `__all__`・モジュール属性・Sphinx に載せない。登録表の変更・reload・`Plugin.load/unload` で廃棄される。
  テストの期待値は `type(node).__name__`・`issubclass` で書き、クラスの同一性に依存しない。
- Maya の継承に基づく判定は `isType()`、Maya 型名は `getType()`(Node は nodeType 名、`inherited=True` で基底→自身の list。
  Plug はアトリビュートの定義型名で generic は None)。Python クラスは `type()`/`isinstance`。
- 手書きクラスの基底は Maya の親に揃える。具体型を明示した構築(`mlib.Joint("pointLight1")`)は型が合わなければ TypeError で、別の型へ差し替えない。

### 拡張

- 任意拡張は `MLIB_EXTENSION_API = 1` を宣言したパッケージを `mlib.core.extensions` が検出・登録する。
- 拡張も `nodes`・`plugs` の明示 import・`__all__`・`_WRAPPER_CLASSES` を使う。拡張の明示登録は生成クラスより優先する。
- 拡張は mlib の公開 API に依存し、他の拡張を import・継承しない。`__init__.py` は宣言を先に完了し、mlib を先行 import しない。
- `mlib.reload()` は拡張の解除 → 本体の再読み込み → 再検出・登録の順。外部 SDK と Maya プラグインは再ロードしない。

## Node・Plug・Component

- ノードの作成は `mlib.createNode(type, name=, parent=, shared=, skipSelect=, fast=False)` だけで行う。`Node.create`・
  型付き create・`Node(name, create=True)` は作らない。constructor `Node(node)` は既存ノードの取得専用。
- createNode 以上の処理をする作成は `cmds/` の作成関数(`createIkHandle`・`createBlendShape`・`createCurve`・`bindSkin` 等)。
  単なる createNode の言い換えは追加しない。形状の作成関数は Shape を返す。既存ノードへの操作(`Container.createNode`・`Joint.mirror`・
  `Transform.addConstraint`)と common の作成(`Namespace.create`)はクラス側に置く。
- その他の Maya コマンドは利用側で直接使い、結果を `getNode`/`getPlug` で包む。汎用の cmds 転送クラスは作らない。
- 入力解決は各基底(`Node._resolve_input`・`Plug._resolve_input`・`Component._resolve_input`)に集約し、各 API で判定を複製しない。
- ノード対象列で文字列と Node の混在は変更前に TypeError(名前だけ/Node だけは可)。
- Node の `==` は生存中の同じ Maya 対象(DAG はインスタンスパスも含む)。`sameNode` はパスに関係なく同じノードか。
  hash は生成時の値を保持し、改名・削除で変えない。永続 ID として保存しない。
- 保持 DAG パスの消失を別インスタンスへの自動切替で補わない。
- 具象 Node は対象 Plug・値の意味・更新順を決め、値の設定は Plug へ委譲する。型付き書込みと単位境界をノードごとに再実装しない。

### maya.cmds との受け渡し

- `Node`・`Plug`・`Component` はそのまま `maya.cmds` に渡せる。`__str__` は呼ぶたびに現在のシーンから一意な名前を求める
  (Node は最短一意名、Plug は「ノードの一意名.ロング名のアトリビュートパス」、Component はシェイプの完全パス付き)。
- 単一の対象を表すクラスを str の派生にしない。`__len__`/`__iter__` を持たせない(cmds がシーケンスとして展開する)。
- `MultiPlug` も `__len__` を持たない(cmds が位置 0〜len-1 として展開し、論理番号と違う値を黙って返すため)。要素数は
  `len(multi.getIndices())`、`in` は論理番号の存在。MultiPlug と `om2.MObject` は cmds に直接渡せない(`str(multi)` で渡す)。
- 複数の対象を表すコレクションは反復可能にしてよい(cmds が各要素へ展開する)。
- mlib のコマンド・メソッドは文字列・mlib オブジェクト・`MObject`・`MDagPath`・`MPlug` を受ける。
  ノードが必要な引数は Plug を所有ノード、Component を所有シェイプへ解決する。
- `repr` は実際のラッパー型名を表示する(`MultiPlug('pma.input1D')`)。
- オブジェクトの取得・接続の列挙は値を評価せず、マルチアトリビュートの要素を作らない。要素の作成は `multi[i].set()` か接続で明示する。

### Plug

- 用語: 要素を持つものは「マルチアトリビュート」(`MultiPlug`・`isMulti()`、要素は `isMultiElement()`・`getMulti()`・論理番号 `getIndex()`)、
  子を持つものは「コンパウンドアトリビュート」(`CompoundPlug`・`isCompound()`、子は `isChild()`・`getParent()`)。
  om2 の `MPlug.isArray`/`isElement` の名前を mlib 側に持ち込まない。英語の文言は「multi attribute」「multi element」「compound attribute」。
- `multi[index]` は未作成の要素も参照を返す。既存要素だけは `getElements()`、存在は `index in multi`。
- コンパウンドアトリビュートの子は `compound[index]`・`compound[name]`。
- `Plug.get/set` は対象アトリビュートだけを扱い、マトリクスアトリビュートから所有ノードの TRS 更新へ暗黙に切り替えない(ノードの変換は `Transform.getMatrix/setMatrix`)。
- 演算子は `src >> dst`・`dst << src`・`src // dst` の3つだけ。`__len__`・`__add__` 等を足さない。
- 接続元・接続先は `getSource`/`getDestinations`、方向付きの照会は `getConnections`。`skipConversionNodes`(`scn`)の既定は False。

### 複数形

- ノードコレクションは `Nodes` 基底(`Joints`・`SkinClusters` は派生)。`Nodes` は `Node` を継承しない。
- `item_class` で受け入れる型を宣言する。型の不一致は黙って除外せず例外。重複は同一ノードかつ同一 DAG パスで判定する。
- `Nodes`・コンポーネントの複数形は、自分に無い公開メソッド名を `__getattr__` で各要素の同名メソッドへ転送し、戻り値を保持順の
  list で返す(書込みも常に list。明示メソッドが優先。通常は Undo 1回)。`Nodes.callEach(method, ...)` も同じ。`Plugs` は転送しない。
- 複数形に置く明示メソッドは list としての振る舞い・入力検証・一括の書込みと、必要最小限の専用メソッドに限る。
- `mlib.ls` は常に集まりで返す(`Nodes`/`Joints`/`SkinClusters`、`Plugs`、同じシェイプ・同じ種類なら `Vertices` 等。混在のみ list)。

### Component

- 作成時に番号を固定した参照。座標は都度シーンから取得する。トポロジー変更後の番号の同一性は保証しない。
- 点の位置は単体なら `mlib.Vector`、複数なら `list[Vector]`(w で割らない)。UV は `(u, v)` の tuple。
- 座標の書込み(`setPosition` 系・`mirror`)は `worldSpace`・`fast` を持つ。形状の座標書込みは `core/geometryEdit` を共有する。
- 周期カーブの末尾の重複 CV は先頭の対応 CV へ写す。

## 数学型(maths)

- `Vector`/`Translate`/`Scale`/`Shear` は `om2.MVector`、`Quaternion` は `MQuaternion`、`EulerRotate` は `MEulerRotation`
  (`Vector` の派生ではない)、`Matrix` は `MMatrix` を継承する。om2 の関数へそのまま渡せ、演算は om2 の実装で行う。
- 意味は om2 に合わせる: `q1 * q2` は q1 を先に適用、`v * m` は行ベクトルの方向変換、`m * v` は列ベクトルの積、
  位置の変換は `Matrix.transformPoint()`、分解は `MTransformationMatrix` の規約。
- 値は可変でハッシュ不可。`EulerRotate` は内部 rad、`order` は om2 の番号(名前は `orderName`)。
- 継承メソッドの数学値の戻り型も対応する mlib 型へ揃える。対応型の無いもの(MPoint・単位値・クラス定数)はそのまま。
- 独自の正規化・分解補助は `asUnitMatrix`・`asCanonicalAxisAngle`・`asDecomposedEulerRotate` 等の独自名で標準名と区別する。
  ゼロ値を拒否する正規化は `unit`/`unitIt`、標準のコピー正規化は `normal`。
- 型付きデータ配列の getter は常に list(空は `[]`)。点・ベクトルは 1 要素でも外側の list を省かない。

## JSON 保存・復元(json)

- 下の層: `codec`(数学型を `{"type": ..., "value": [...]}` で書く。EulerRotate は度と回転順の名前)、`file`(`{"header", "data"}`。
  ヘッダーは形式名・版・mlib/Maya の版・単位(cm・度・保存時の UI フレームと fps))、`NodeRef`・`PlugRef`・`ComponentRef`(名前・完全パス・型で記録。UUID は持たない)、`NameMapping`。
- 中の層: `Snapshot` 基底と `ValidationReport`。
- 1つのノードが持つデータはノードクラスのメソッドに直接書く(`SkinCluster.exportWeights`・`Transform.exportCurveShapes`・
  `BlendShape.exportTargets` と、それぞれの `get…Data`・`set…Data`・`import…`)。`exportData` のような汎用名にしない。
  json 側に中間の内部クラスを置かず、nodes からはメソッド内で `mlib.json` を import する(循環参照の回避)。
- 複数ノードのデータは `mlib.json` の `Snapshot` 派生(`PoseSnapshot`・`AnimationSnapshot`・`AttributesSnapshot`・
  `DrivenKeysSnapshot`・`SelectionSnapshot`)。流れは `capture` → `save`/`load` → `validate`/`apply`。
  各種類は `capture`・`toData`・`fromData`・`_validate`・`_apply` を書き、`apply` は引数を明示して基底の `_run_apply` に渡す
  (検査 → errors があれば何も変えず ValueError → 1回の Undo で適用・失敗時は巻き戻し → 警告)。
- 形式名・版が期待と違うファイルは ValueError で読まない(版の変換は持たない)。書き出しは UTF-8 で一時ファイル経由、失敗しても既存のファイルを壊さない。
- 名前の対応付けは `nameMap`(名前空間を除いた名前)→ `replace`(順に置換)→ `namespaceMap` の順。見つからないノードは飛ばして最後にまとめて警告する。
  型が違うノード・1つに絞れない名前は対応させない。
- 時間は保存時のフレームで書き、読み込み時に `timing="frame"`(既定)か `"second"` を選ぶ。
- 保存キー・保存フィールド・外部形式は公開メソッドの改名に巻き込まない。通常の JSON 文字列は標準 `json` を使う。
- `mlib/json` は標準の `json` と同名なので、mlib のフォルダ自体を `sys.path` に入れる実行方法を作らない。

## ファイル・クラスのレイアウト

- 原則1クラス1ファイル。単数クラスと対応する複数クラスは単数形のファイルにまとめる(`joint.py` に `Joint`/`Joints`、`vertex.py` に `Vertex`/`Vertices`)。
- ファイル内の順: docstring → `from __future__` → import → `if TYPE_CHECKING:` → `__all__`・定数 → 関数・クラス。
  `__all__` は import 群の直後に置く。定数は原則 import 群の直後(先行定義を参照するものは依存先の後)。
- import は標準ライブラリ → `maya.*` 等の外部 → mlib 内部(相対 import・`mlib.*`)の3グループ、間に空行1行。
  グループ内は `import x` を先、続けて `from x import y`、それぞれモジュール名順(大文字小文字を区別しない。`..` は `.` より先)。
- Maya は `import maya.cmds as cmds`・`import maya.mel as mel`・`import maya.api.OpenMaya as om2`(個別名の `from` import は可)。
- `import os, sys` は分離する。`from x import A, B` は可、`from x import *` は禁止。
- 関数内 import は循環参照の回避・任意依存・Maya 非依存の維持など理由がある場合だけ使い、直前に短い理由コメントを付ける(連続した同じ理由の群は1つ)。
- 初期化順が仕様の `__init__.py`(ルート・`core`・`cmds`・`nodes`・`plugs`)は import の並び替え対象外。理由のある遅延 import・
  `try/except ImportError`・`TYPE_CHECKING` の中身を機械的に先頭へ移さない。
- 空白: 代入・複合代入・比較演算子の前後は空白1つ。カンマの後は空白1つ(末尾カンマ・括弧内改行は可)。括弧の内側に空白を置かない。
- 既定値・キーワード指定は型注釈なしなら `fast=False`、型注釈付きなら `fast: bool = False`。
- 行末コメントはコードとの間に空白2つ以上、`#` の後に空白1つ(`index += 1  # 次の要素へ`)。Sphinx の `#:` は維持する。
- 名前へ直接代入する lambda(`f = lambda ...`)は `def` にする。コールバック引数等の lambda は可。
- インデントはスペース4、末尾空白なし、長い式は括弧内で改行する。行の長さは規則の対象外。ファイル末尾は改行1つ。
- 文字列は原則ダブル引用符、単純な埋込みは f-string。改行形式は Git の設定を尊重し、書式整理だけで全ファイルの改行を変えない。
- 空行: トップレベルの定義間は2行、クラス内のメンバー間は1行、`class` 行と docstring の間・デコレーターと `def` の間は0行、3行以上は不可。
  クラス内に区切り線のコメントを置かない。
- クラス内の順: docstring → クラス属性 → `__new__`/`__init__`/`__post_init__` → その他の特殊メソッド → 公開 classmethod/staticmethod →
  property → 公開メソッド → 非公開メソッド。公開メソッドをアルファベット順に並べ替えない。
- 対になる操作は隣接させる(`getX`/`setX`、`isX`/`setX`、`connect`/`disconnect*`、`show`/`hide`、`addX`/`removeX`、`__eq__`/`__ne__`/`__hash__`、
  `__repr__`/`__str__`、演算子と `__r*__`/`__i*__`)。property の setter は getter の直後。
- `@dataclass` のフィールド順、先行定義を参照する代入(`__str__ = __repr__`)、`item_class = Node` 等は参照先の後の位置を保つ。
- 単純な番号と要素の列挙は `enumerate`、ファイルパスは `pathlib`、テキストの読み書きは明示的な `encoding`。
  Maya の DAG パス・アトリビュート名をファイルパスとして扱わない。外部ファイルの文字コードを UTF-8 と推測しない。
- 検査は `__tests__/checks/check_mlib_layout.py --check`(L030〜L034 は空白・lambda、L040 は公開入口の入力 assert、L043 は encoding 未指定。
  L041/L042 は確認候補の表示)。`--fix` は import 順・クラス内の順・空行だけを直す。入力 assert の修正は
  `--fix-asserts TypeError|ValueError <ファイル> --line <行>` で対象を明示し、例外型を推測しない。

## docstring とコメント

- Google 形式・日本語。項目順は 概要 → 詳細 → `Args:` → `Returns:`(`Yields:`)→ `Raises:` → `Note:` → `Examples:`、見出し間に空行。
  非標準の見出しや見出し無しの自由文(Returns/Raises の後)は置かず、Note へ移す。
- 1行目は動詞文「〜する。」。get 系は「〜を取得する。」、set 系は「〜を設定する。」。Returns は型と値の説明にし、概要と逐語一致させない。
- 引数は署名の順に、self/cls を除く公開引数・単位・既定動作・別名を書く。値を返さない処理も `None: 値を返さない。`、必ず例外を送出する処理は `NoReturn`。
- `fast`/`safe`/`get` 等で返却・副作用が変わる場合は条件ごとに書く。fast を持たない書き込みは「fast引数は持たない」と理由を書く。
- 固定文:
  - `fast (bool): TrueはUndoなしのOpenMaya更新。既定False。`
  - `worldSpace (bool): Trueはワールド空間、Falseはローカル空間。`(Shape 系は「Falseはオブジェクト空間」)
  - `e (bool): editの別名。同時指定は不可。`(Maya フラグの短名)
  - Raises の `TypeError: fastがbool以外の場合。`
- Raises の並びは `TypeError → ValueError → IndexError → RuntimeError → NotImplementedError`。
- 型表記は `list[Node]`・`tuple[float, float, float]`・`dict[str, Any]` のように要素型を書き、裸の `list`/`tuple`/`dict` を使わない
  (スタブ生成が docstring の型を読む)。型注釈の全面導入はしない。
- 用語: アトリビュート、マトリクス(determinant は「行列式」)、コンストレイント、クォータニオン、ワールド空間/ローカル空間/オブジェクト空間、
  番号(インデックス・添字は使わない)、ウェイト、マルチアトリビュート/要素/論理番号/コンパウンドアトリビュート/子。
  「配列」「multi」「複合」等の略称は使わない(Python の list・`doubleArray` 等のデータ型・om2 の API 名はそのまま)。
- 括弧は半角、文の区切りは句点。モジュール定数には `#:` を付ける。
- 使用例のノード検索は `mlib.ls` を中心にし、`Object` の直接呼び出しを推奨例にしない。クラスは `mlib.Joint` の形で書く。
- OpenMaya への文書リンクは Maya 2027 の公式リファレンスを使う。
- `cmds/` の各関数の docstring は Synopsis / Return value / Flags / Examples 形式(Sphinx の専用テンプレートへ渡す)。

## 型スタブ(.pyi)

- 公開 API の型は docstring にしか無いので、`_tools/generate_mlib_stubs.py`(`.bat`)が docstring から各 `.py` の隣に `.pyi` を生成する。
- `.pyi` は手で編集しない。docstring の型・引数・公開名を変えたら `_tools/generate_mlib_stubs.bat`(`py -3 _tools/generate_mlib_stubs.py`)で作り直し、`.py` と一緒にコミットする
  (`--check` で最新か確認、`--report` で省いた注釈を表示)。Python 3.9 以降で動き、Maya 2023 以降の mayapy でも同じ内容を生成する(`.bat` は `py -3.14`〜`py -3.9` を新しい順 → mayapy の順に探し、最後に pause する。端末・スクリプトからは `--no-pause`)。生成スクリプトは 3.9 で動く書き方を保つ。古いスタブは `__tests__/unit/test_static_stub_generation.py` が検出する。
- 引数で戻り値が変わる API(`ls`・`createNode`・`getConnections` 等)の `@overload`、ルートの `__init__.pyi` の再公開、
  複数形の転送メソッドは同スクリプトに書く。`Nodes` は要素の型を引数に取る(`Nodes[Transform]`)。

## テスト

- pytest は使わない。Maya のテストは mayapy 経由で実行する。すべて `__tests__` フォルダから実行する。
  - Maya 不要の検査: `py -3 runStatic.py`(`unit/test_static_*.py` と `check_mlib_exports.py`・`check_mlib_layout.py --check`)。
    公開名の追加・削除、レイアウト変更の後は必ず通す。
  - Maya: `.\run.bat --versions 2027 --suite all`(`py -3 runMaya.py ...` も同じ)。`--suite unit|integration|all`、
    `--tests test_xxx.py`、`--versions 2022 2027` で複数版。結果は `_output/`(Git 対象外)。
  - GUI 限定の確認: `py -3 runGui.py --versions 2027 --suite unit|integration|visual`(使い捨ての専用 Maya GUI)。
- Windows でコマンドを書くときは `python` でなく `py -3`(Python ランチャー)を使う。`python` は Microsoft Store を開くだけの
  ものが先に見つかることがある。バッチは `py -3.14` から新しい順に探し、3.15 以降は使わない(Sphinx の依存の PyYAML をpipが
  ビルド済みで取得できず止まるため)。GitHub Actions の `python` はそのままでよい。
- テストはシーンを初期化するので、作業中の Maya GUI へ一式を送らない。`manual/` は自動実行しない調査用。
- 配置: 単体は `unit/`、結合は `integration/`、`test_<名前>.py`。Maya 不要のものは `unit/test_static_<名前>.py`。
  各ファイルの末尾に `if __name__ == "__main__": unittest.main()` を置く(ランナーがファイル単位で実行する)。
- 仕様テストは `test_spec_<領域>_*.py`(`calc`・`plug`・`node`・`dag`・`transform`・`joint`・`skin`・`common`・`components`・`core`・
  `decorator`・`maths`・`cmds` 等)。Maya 不要なら `unit/test_static_spec_<領域>_<名前>.py`。
- 一時名前空間でノードを作るテストは `support/specCase.py` の `NamespaceCase` を基底にし、tearDown で後片付けする
  (名前空間・Undo 設定・UI 単位・選択を戻す)。補助は `name()`・`make()`・`flushUndo()`・`assertUndoesInOneStep()`・`assertUndoEmpty()`。
- 変えた API ごとに `subTest` で、フラグの組合せ・cmds/om2 の突き合わせ・通常は Undo 1回/fast は Undo なし・不正入力の例外型・
  複数形(一括)を確かめる。
- cmds→om2 の読み取り置換は `integration/test_cmds_parity.py` に cmds の生値との突き合わせを同時に追加する(既存の一覧はファイル冒頭の docstring)。
- 生成クラスの期待値は `type(x).__name__`・`issubclass` で書く。テストも Python 3.7 で動く書き方にする。

## Sphinx 文書(_docs)

- 初回は `_docs/setup.bat`、ビルドは `_docs/rebuild.bat --no-pause`(`_build/html/` に出力。生成物の `source/autoapi/`・`_build/` は編集しない)。
- 検査は `__tests__/checks/check_mlib_docs.py --check-directory ..\_docs\_build\html` と `check_mlib_doc_getter_names.py`(文書用の Python で実行)。
- API の本文は docstring から AutoAPI が作る。説明を直すときは docstring か `source/` の元の RST を編集する。
- 公開文書には実装済み機能の仕様・使い方だけを書く。検討中の案・経緯・調査メモ・変更履歴は載せない。
