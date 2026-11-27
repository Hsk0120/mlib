# mlibのテスト

mlib本体とこのフォルダだけで実行できます。
外部ライブラリ・mlibを使う側のパッケージ・mlib拡張は、本体テストの必須依存に含めません。

書いた後に流す順番は[../CONTRIBUTING.md](../CONTRIBUTING.md)を正とします。バッチは2本です。

```powershell
..\_tools\format_mlib.bat --no-pause
..\_tools\test_mlib.bat --no-pause --versions 2027 --suite all
```

1本目がコードの静的解析と修正(整形・ruff・レイアウト・公開名の一致)、2本目がテストです。
`test_mlib.bat`は`noMaya/`を先に実行し、通ったら`inMaya/`をmayapyで実行します。`--no-maya`で前半だけ、
`format_mlib.bat --check`で書き換えずに検査だけ行います。
型スタブ(`..\_tools\generate_mlib_stubs.bat`)とSphinx(`..\_tools\build_mlib_docs.bat`)はその後の任意の工程で、
どちらの検査もこの2本には含まれません。入口のバッチはすべて`..\_tools\`にあり、このフォルダーにはテストの中身と
ランナー(`run*.py`)だけを置きます。

## フォルダ

```text
__tests__/
├─ README.md          この手順
├─ runMaya.py         mayapyで単体・結合テストを実行
├─ runNoMaya.py       Maya不要のテストを実行
├─ runGui.py          専用Maya GUIで単体・結合・表示を確認
├─ runAll.py          テスト探索・実行・ログ集計
├─ noMaya/           Mayaを起動せずに動くテスト(runNoMaya.py)
├─ inMaya/           mayapyで動くテスト(runMaya.py)
│  ├─ unit/          1つのモジュールを確かめるテスト。ソースと同じパッケージ名のフォルダーに分ける
│  │  ├─ cmds/ nodes/ plugs/ components/ maths/ common/ core/ json/
│  │  └─ root/       mlib直下のモジュール(decorator.py・util.py・logger.py・__init__.py 等)
│  └─ integration/   複数のパッケージにまたがる確認。フォルダーを作らず、名前の先頭に観点を書く
├─ support/          共通基底(namespaceCase.py)、引数の網羅(argumentSweep.py・argumentTable.py)、GUI内の実行・プロセス監視の補助
└─ _output/          結果・ログ・専用Maya設定（Git対象外）
```

テストの入口(`test_mlib.bat`)と、公開名・コード配置・生成文書の検査ツールは mlib の `_tools/` にあります。
単体テストでもOpenMayaやシーンを使うものはMayaが必要です。

## 準備

- Maya版: 検証対象のMayaと、その実行に必要なライセンスを用意します。GUIの事前起動は不要です。
- 静的検査: 通常のPython 3.11以上を使います。`_tools/setup.bat`が作る`_tools/.venv`のPythonでも実行できます。
- 以下のコマンドは**この`__tests__`フォルダ**から実行します。Mayaのテスト環境はランナーが用意します。

## 単体・結合を分けて実行

PowerShellで実行します。

```powershell
# Maya不要のテストだけ(リントは ..\_tools\format_mlib.bat が持つ)
..\_tools\test_mlib.bat --no-pause --no-maya
py -3 .\runNoMaya.py

# Mayaのインストール状況を確認するだけ
py -3 .\runMaya.py --list

# 個々のAPIの単体テスト
..\_tools\test_mlib.bat --no-pause --versions 2027 --suite unit

# 複数のmlib機能を組み合わせる結合テスト
..\_tools\test_mlib.bat --no-pause --versions 2027 --suite integration

# 両方を実行（--suite省略時もall）
..\_tools\test_mlib.bat --no-pause --versions 2027 --suite all

# 対象ファイルだけ実行。指定ミスは失敗として報告する
..\_tools\test_mlib.bat --no-pause --versions 2027 --tests test_joint.py
# 同じ名前のファイルが別のフォルダーにあるときは、フォルダー付きで絞る
..\_tools\test_mlib.bat --no-pause --versions 2027 --tests json/test_file.py

# 複数バージョンで同じテストを実行
..\_tools\test_mlib.bat --no-pause --versions 2022 2027 --suite all
```

`test_mlib.bat`は毎回`noMaya/`を先に実行し、その後に検出したmayapyを制御用Pythonに使って`runMaya.py`を呼びます。
実テストには各版のmayapyを使います。ダブルクリックで実行したときに結果を読めるよう最後にキー入力を待つので、ターミナルからは`--no-pause`を付けます。
`inMaya/`だけを実行するときは、通常Pythonから`py -3 .\runMaya.py --versions 2027 --suite unit`を使います。
`--versions`を付けずに実行すると、Maya 2025だけを対象にします(1回のテストが重くならないよう既定は1版です。
対応する2022〜2027すべてを確かめるときは`--versions 2022 2023 2024 2025 2026 2027`を指定します)。
未インストールは`missing`と記録します。`--allow-missing`はこの状態による終了コードだけを抑制します。

Mayaが標準配置にない場合は、`--install-root D:\Autodesk`、または
`$env:MAYA_TEST_LOCATION_2027 = 'D:\Autodesk\Maya2027'`で場所を指定します。
制御用Pythonを固定する場合は`MLIB_TEST_PYTHON`へ実行ファイルのパスを設定します。

## 基本操作を重点的に確認する

正常系に加え、失敗後の値・接続・ロック、通常のUndo/redo、fastとsafeの違いを確認します。
これらのテストは専用の名前空間を作り、終了時に削除します。

| 区分 | ファイル | 主な確認内容 |
| --- | --- | --- |
| 単体 | `inMaya/unit/cmds/test_delete.py` | 入力型、削除前の拒否、接続された子孫の保護、保持参照の復元 |
| 単体 | `inMaya/unit/plugs/test_plug_basics.py` | 基本型の値、接続の置換・切断、ロック、疎なマルチアトリビュート、内部単位 |
| 単体 | `inMaya/unit/nodes/test_transform.py` | ローカル/ワールド、TRS、回転順序、親変更、反転不能な親 |
| 結合 | `inMaya/integration/test_workflow_scene.py` | DG評価、接続と削除、親子変更、複数操作のUndoと例外時の巻戻し |

```powershell
# 基本操作の単体テストだけ
..\_tools\test_mlib.bat --no-pause --versions 2027 --suite unit --tests cmds/test_delete.py test_plug_basics.py nodes/test_transform.py

# 基本操作を組み合わせる結合テストだけ
..\_tools\test_mlib.bat --no-pause --versions 2027 --suite integration --tests test_workflow_scene.py
```

これは既存テストを補う重点確認です。全体の回帰確認には`--suite all`を使います。
`undoChunk`の例外では先行更新を残し、`undoTransaction`では通常のUndo対象更新の巻戻しを試みます。
fastの更新はどちらのコンテキストでもUndo対象にしません。

## GUIで確認する

```powershell
py -3 .\runGui.py --versions 2027 --suite unit
py -3 .\runGui.py --versions 2027 --suite integration
py -3 .\runGui.py --versions 2027 --suite visual
```

`unit`・`integration`は同名フォルダのテスト、`visual`は実パネルへの適用と画像保存です。
`--suite all`では3つを別々の専用GUIで実行します。
`--versions`の既定は`runMaya.py`と同じMaya 2025の1版だけです。
各GUIは専用設定を使い、ランナーが起動したMayaだけを終了します。
自動判定と、保存画像の目視確認は別の結果です。

テストにはシーンの初期化があるため、**作業中のMayaへ一式を送信しないでください**。
GUI用スイートはランナーが設定する`MLIB_DISPOSABLE_GUI=1`を確認します。
通常のPreferencesや、起動中のMayaのシーンは変更しません。

## 結果を見る

テストが失敗すると、起動元のターミナルにも詳細ログの絶対パス・失敗ファイル名・
エラーの行番号と内容を表示します。成功したテストの詳しい出力はログにだけ保存します。
Mayaの起動・終了の異常や時間切れでは、取得できた例外と起動ログのパスを表示します。

- mayapy: `_output/maya/<日時>/summary.txt`と`summary.json`
- GUI: `_output/gui/<日時>/summary.txt`と`summary.json`
- 各版の`result.json`: 実際のMaya/API/Python版、実行件数、失敗、スキップ理由
- 詳細ログ: 失敗した検査とトレースバック

`passed`は対象検査の成功、`failed`は検査失敗、`error`は起動・初期化などの異常、
`timeout`は時間切れ、`missing`はMaya未インストールです。スキップは未確認として結果に残ります。
終了コードは成功0、失敗・異常1、未インストールだけで未完了なら2です。
`--timeout 1200`で各版の制限時間を変更できます（既定600秒）。

テストが通っていない行・分岐と、確かめていない観点は`..\_tools\measure_mlib_coverage.py`、
テストが結果まで確かめているかは`..\_tools\measure_mlib_mutations.py`で測れます(手順は`CONTRIBUTING.md`の「任意の工程」)。
結果は`_output/coverage/<日時>/`・`_output/mutations/<日時>/`に置きます。

## テストを追加する

フォルダーは「どう動かすか・どの範囲か」、ファイル名は「何を確かめるか」で決めます。
`noMaya/test_runAll.py` がこの規則を検査します。

| 置き場所 | 置くもの | ファイル名 |
|---|---|---|
| `noMaya/` | Mayaを起動せずに動くもの(`runNoMaya.py` が実行し、Maya版ランナーは探さない) | `test_<対象>[_<話題>].py` |
| `inMaya/unit/<パッケージ>/` | 1つのモジュールを確かめるもの | `test_<モジュール>[_<話題>].py` |
| `inMaya/integration/` | 複数のパッケージにまたがるもの | `test_<観点>[_<話題>].py` |

- `_` は区切りにだけ使い、各部分は lowerCamelCase にします(`test_skinCluster_weights.py`)。
- 対象はソースのファイル名をそのまま書きます(`nodes/skinCluster.py` → `inMaya/unit/nodes/test_skinCluster.py`)。
  パッケージの `__init__.py` は `init`、先頭の `_` は付けません。
  mlib直下のモジュールは `inMaya/unit/root/` に置きます。スネークケースのツール(`_tools/check_mlib_exports.py`)は
  lowerCamelCase に直して書きます(`noMaya/test_checkMlibExports.py`)。
- `inMaya/integration/` の観点は `naming`(公開名・引数名) `units`(角度・時間・長さ) `fast`(fast経路)
  `parity`(cmds・OpenMayaとの突き合わせ) `undo` `errors`(例外・案内文・事前検査) `interop`(cmdsとの受け渡し)
  `performance` `workflow`(実作業の流れ) `reload` `compat`(Mayaの版の違い) のどれかです。
- GUIが要るものは話題を `gui` にします(`inMaya/unit/common/test_scriptJobs_gui.py`)。
- 名前に `spec`・`refactoring`・`consolidated`・`changes`・`additions`・`backlog`・`misc`・`api`・`contracts`
  や `_A` などの記号・番号を使いません。何を確かめるかが分からなくなるためです。
- 調査用の使い捨てスクリプトはリポジトリに入れません。残す価値がある確認はテストとして書きます。

手順:

1. 上の表に従って、既存のファイルへ足すか、新しいファイルを作ります。
2. `unittest.TestCase`で期待値を判定し、末尾に`if __name__ == "__main__": unittest.main(argv=[sys.argv[0]])`を置きます
   (ランナーがファイル単位で実行します)。
3. `--tests ファイル名`で確認してから、同じスイート全体を実行します。

各テストは作ったノード・設定を後片付けしてください。他パッケージとの連携はmlib本体に混ぜず、利用側のリポジトリへ置きます。
公開APIの約束を確かめるときは、変えたAPIごとに`subTest`で、フラグの組合せ・cmds/om2の突き合わせ・
通常はUndo 1回/fastはUndoなし・不正入力の例外型・複数形(一括)を確かめます。

一時名前空間でノードを作るテストは`from support.namespaceCase import NamespaceCase`を基底にします。
名前空間・Undoの設定・UI単位(linear・angle)・選択を終了時に元へ戻し、`name()`・`make()`・
`flushUndo()`・`assertUndoesInOneStep()`・`assertUndoEmpty()`等の補助を持ちます。
ファイルごとの差分は薄い派生クラスのクラス属性(`PREFIX`・`ENABLE_UNDO`・`CLEAR_SELECTION`・
`UNLOCK_NODES`)と、そのファイルだけで使う作成の補助で表します。

### 引数を表から網羅する

公開メソッドの引数を網羅するときは、クラスごとに「正しい呼び方の表」を書き、
`support.argumentSweep.ArgumentSweepCase`(`NamespaceCase`の派生)の`METHODS`に置きます。
ファイル名の話題は`argumentSweep`です(`inMaya/unit/nodes/test_transform_argumentSweep.py`)。

```python
from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method, RoundTrip


class TransformArgumentSweepTest(ArgumentSweepCase):
    METHODS = (
        Method(
            "setTranslation",
            _make_child,                      # case を受け取り、メソッドを呼ぶ対象を作って返す
            args=((1.0, 2.0, 3.0),),          # 正しい呼び方(位置引数も名前でキーワードとして渡す)
            values={"value": POSITIONS, "at": (-1, 0, 1, 2, 3, 4, 5)},  # 引数ごとの値の候補
            replace=("at",),                  # values だけを候補にする引数
            invalid={"value": ((1.0, 2.0), "abc")},  # 段2の違う型の値(省略時は型から作る)
            conflicts=(("worldSpace", "ws"), _relative_at),  # 同時に指定できない組(名前の組か、引数の辞書を受ける関数)
            expect=_expect,                   # expect(case, call): 結果を cmds・om2 で確かめる(省略可)
            roundTrip=RoundTrip("getTranslation", shared=("worldSpace", "ws", "at"), skip=_skip),
            plural=_make_children,            # case → (複数形, 単数の並び)
            known={"invalid:safe=1": "bool でない値を受け付ける"},  # 本体との食い違い(fnmatch の * が使える)
        ),
    )
```

メソッドごとに次のテストができ、件数・上限で切った数・秒数を`[argumentSweep]`の行でログへ出します。

| テスト | 確かめること |
|---|---|
| `test_<メソッド>_values` | 段1: 引数ごとに候補を1つずつ差し替えて呼ぶ(引数の無いメソッドは1回呼ぶ)。例外は docstring の Raises の型だけ(そのときシーンは変わらない)、`expect` に合う |
| `test_<メソッド>_invalid` | 段2: 違う型の値(bool へ`1`・`"yes"`、数へ`"a"`・NaN・inf、文字列へ数、選べる値へ選べない文字列、ノード・Plug へ削除済み・存在しない名前、並びへ数でない物)で、Raises の型になりシーンが変わらない |
| `test_<メソッド>_pairs` | 段3: 2つの引数の組(1メソッド200組まで。`limit`で変える。引数が1つなら候補を1つずつ、無ければ1回。`combos`の組は必ず通す)で、Raises の型だけ・同時に指定できない組は TypeError・Undo 1回で戻り redo で同じ・`fast=True`と通常で同じ(fast は Undo なし)・短縮名(docstring の「Xの短縮名」)と長い名前で同じ・`roundTrip`・`plural` |
| `test_<メソッド>_calling` | 段4(呼び方): 正しい呼び方を、渡し方だけ変えても同じ結果になる。`defaults`=省いた引数へ既定値を明示しても同じ(署名・docstring の既定値が実際の動きと同じ)、`positional`=位置で渡せる引数を位置で渡しても名前で渡したときと同じ、`keywordOnly`=キーワード専用の引数を位置で渡すと TypeError でシーンが変わらない。本体の食い違いは `known={"calling:defaults": "理由"}`、2回の結果を比べられない行(名前の番号が進む・ファイルが残る)は `skipCalling={"defaults": "理由"}` と書く |
| `test_<メソッド>_errors` | `errors`に書いた状態(削除済み・アンロード中など)で、決めた例外になりシーンが変わらない |
| `test_<メソッド>_known` | `known`に書いた場合が、まだ食い違っていること(expectedFailure。直ったら known から外す) |

- 候補は docstring の Args の型(bool・int・float・None・``"x"``の選べる値)と既定値から作り、`values`を足します。
  並び・ノードなど型から作れない引数は`values`に書きます(`Lazy(lambda case: ..., "名前")`で呼ぶ直前に作る値も置けます)。
- 書き込むメソッド(名前が get・is・has・list・find で始まらないもの。`writes=`で変える)は、呼ぶたびに名前空間の中身を作り直します。
  シーンの状態は名前空間のノード・keyable の値・ワールドのマトリクス・接続と全体のノードの数で比べます(`state=`で変える)。
- 段3の「`fast=True`と通常で同じ」は、`fast`を指定した組・`get=True`・`safe=True`・`fast`を足すと`conflicts`になる組では比べず、
  `fast=True`が docstring の Raises の`NotImplementedError`(fast と同時に使えない引数)になった組も比べません。
- 書き込むメソッドの戻り値(Node・Plug・Component とその並び)は、呼んだ直後の名前に置き換えて比べます(作り直しで消えても比べられる)。
- 複数形(`plural`)の書き込みは、作り直した後のノードから値(Lazy)を作り直し、表の`state`で比べます。
- 並び・辞書の中の`Lazy`も呼ぶ直前に作ります。`Lazy(make, "名前", args=True)`は`make(case, kwargs)`でほかの引数の値も受け取ります(3つの引数がそろって決まる値)。
- Maya を使わない部分(docstring の読み取り・候補・組・Lazy の作り直し・可変長の引数の展開)は`support/argumentTable.py`にあり、`noMaya/test_argumentTable.py`が確かめます。

`Method`のそのほかの指定と、テストケースの補助:

| 指定 | 使い方 |
|---|---|
| `function=` | 対象のメソッドの代わりに呼ぶ関数(`mlib.createNode`・クラスメソッド・静的メソッド)。対象(setup の戻り値)は state・expect にだけ使う。setup がクラス・モジュールを返せば、`function`なしでもそのクラスメソッド・静的メソッド・関数を呼ぶ |
| `values={"targets": ((a, b),)}`・`"*"`・`"**"` | `*args`・`**kwargs`の候補(`*`は並び、`**`は辞書)。values・invalid に書いた可変長の引数だけを網羅し、呼ぶときに展開する。`args=`の余りの位置引数・`kwargs=`の余りも展開して渡す。docstring の`*targets (Node)`も読む |
| `variant="vertex"` | 同じメソッドを別の呼び方で2行置くときのテスト名の接尾辞(`test_getWeights_vertex_values`)。省いて重なった行は`_2`・`_3`を付ける |
| `known={"invalid:members=[<a>]": "理由"}` | `[`はそのままの文字(以前の`[[]`と`[!x]`はそのまま使える)。キーを`(段, 引数の辞書)`を受け取る関数にしてもよい。理由を`Known("理由", versions=(2022,))`にすると、その版だけに当てはめる(当てはまる版が無ければ known のテストは skip) |
| `undoable=False` | Undo に記録しないメソッド(docstring に「Undoには記録されない」と書いたもの)。段3で Undo の記録が無いことを確かめ、Undo・redo は確かめない |
| `reset=` | 呼び出しごとの後始末`reset(case, target)`(登録を増やすメソッドの解除など) |
| `context=True` | 戻り値を with で入って出てから状態を読む(コンテキストマネージャーを返すメソッド) |
| `combos=({...}, ...)` | 段3で上限によらず必ず通す組(3つ以上の引数でもよい) |
| `errors=(ErrorState("削除済み", prepare, RuntimeError),)` | 状態で決まる例外。`prepare(case, target)`で対象をその状態にし(値を返せばそれを対象にする)、正しい呼び方で決めた例外になり、シーンが変わらないことを確かめる |
| クラス属性`STATE` | `state`を省いた行で使う状態の関数`STATE(case, target)`(クラスの表全体の既定) |
| `case.inNamespace()` | with の中ではテストの名前空間が今の名前空間になる(`cmds.polyCube`などのシェイプも名前空間の中にできる) |

- `expect`に渡す`Call`は`before`(呼ぶ前の状態)も持ちます。
- docstring の型が`object`・`Any`の引数は、どの値も受け付けるとして段2を作りません(説明にノード・Plug と書いた`object`はノードとして作る)。
- 既定の状態(`sceneState`)は、読めないアトリビュート(TypeError も)を None として読み、値をノード・アトリビュートの名前の順に並べて比べます。

## コードの書式を検査する

Mayaは不要です。整形はruffが行うので、初回だけ`_tools\setup.bat`を実行し、普段は`_tools\format_mlib.bat`を使います。

```powershell
# 整形して、ruffが直せない分を表示する
..\_tools\format_mlib.bat --no-pause
# 何も変えずに検査する(コミット前・workflowと同じ)
..\_tools\format_mlib.bat --check --no-pause
```

`ruff format`が空白・空行・改行位置・引用符を直し、`ruff check --fix`がimportの並び・未使用名・Mayaのimport形式・
文字コードの明示(`PLW1514`)・`os.path`から`pathlib`への置換(`PTH`)・`.format()`から f-string への置換(`UP`)を直します。
選んでいるルールと除外の理由は`ruff.toml`に1行ずつ書いてあります。別の版のruffは`required-version`で実行を拒否し、
previewのルールは`explicit-preview-rules`でコードを明示したものだけ有効にしています。
日本語の文中でも括弧は半角`()`で書きます(`RUF001`〜`003`。「ノ」「×」等は`allowed-confusables`で許可しています)。
未使用の引数(`ARG`)も報告します。互換のために残す引数は置かず削除し、基底クラスの契約・Mayaのコールバック等で必要なものだけ
`# noqa: ARG002`と理由を書いて残します。
設定は`ruff.toml`(行幅160)、ruffの版は`_tools/requirements-dev.txt`で固定しています。
`logger.py`・`decorator.py`はフレームのファイル名を`os.path.normcase`で大小を無視して比べるため`PTH`の対象外で、
テストはパスをMayaのコマンドへ文字列で渡すため`PTH`と`B023`(ループ内で作って同じ周回で呼び切る関数)の対象外です。
`setup.bat`は`_tools/.venv`を作り、ruffとSphinxを**まとめて**入れます(環境はこの1つだけです)。`py -3.14`〜`py -3.11`を新しい順に探し、Pythonが無ければMaya 2027〜2025のmayapyで`_tools/.mayapy-site`へ入れます(Sphinx 8.2がPython 3.11以上を必要とするため、ruff単体より範囲が狭くなります)。
既存の`.venv`は再利用します。壊れたときは`.venv`を`.venv-backup`へ名前変更してから`setup.bat`を実行し直してください。
`format_mlib.bat`はこの`.venv`を優先して使い、無ければPATHのruffや`py`のPythonを探します。
`.pyi`(生成物)・`_docs`・`*.md`は対象外です。

以下は、ruffが扱わない検査(定数・`__all__`・`if TYPE_CHECKING:`の位置、クラス内メンバー順、公開入口の入力assert、列挙、
内部名とfunction setの取得・関数内importの理由コメント、例外の文言とUndoチャンク名・fastの受け取り、docstringの見出し・
Raisesの並び・固定文・用語・公開定数の説明・`Args:`の名前と位置引数の順・残った`TODO`、
Python 3.7で動く書き方とpropertyのgetter)を
個別に見るときの実行方法です。
この`__tests__`フォルダから実行します。

```powershell
# 本体全体、または指定ファイルを検査する
py -3 ..\_tools\check_mlib_layout.py --check
py -3 ..\_tools\check_mlib_layout.py --check ..\nodes\node.py
# クラス内メンバーの順を直してから、残った違反を表示する(その後に`format_mlib.bat`で整形する)
py -3 ..\_tools\check_mlib_layout.py --fix
py -3 ..\_tools\check_mlib_layout.py --fix ..\nodes\node.py
```

このスクリプトは標準ライブラリだけで動くので、専用のバッチは置いていません(`py`のPython 3.9以降、またはmayapyで実行します)。

違反があればファイル・行番号・検査コード・内容を表示し、終了コード1を返します。
`L004`は定数、`L005`は文字列の並びの`__all__`(他の名前から組み立てる`__all__`は定義の後ろでもよい)、`L006`は`if TYPE_CHECKING:`の位置、
`L020`〜`L022`はクラス内メンバーの順と対になる操作の隣接、`L023`はその並び検査をスキップしたクラスです。
`--fix`が直すのはクラス内メンバーの順だけで、並べ替えた後の空行は`ruff format`が直します。
`..\_tools\format_mlib.bat`からも同じ検査を実行します(`runNoMaya.py`はテストだけを実行します)。

`L040`は公開入口の冒頭にある入力検証のassertを報告し、`L041`（単純な列挙）は確認候補の情報表示です。
これらはコードの意図を完全には判別しません。テスト・内部整合性のassertや添字更新は一律に変更しません。

入力assertを確認した後、適切な例外型と報告された行番号を指定すると、その行だけを修正できます。
次は`node.py`の12行目がL040として報告された場合の例です。実際の対象と行番号へ置き換えてください。

```powershell
py -3 ..\_tools\check_mlib_layout.py --fix-asserts TypeError ..\nodes\node.py --line 12
py -3 ..\_tools\check_mlib_layout.py --check ..\nodes\node.py
```

docstringが無い`def`には、署名と本文から組み立てた雛形を入れられます。
書けない説明は`TODO`で残り、埋め忘れは`L077`(情報表示)に出ます。既存のdocstringは書き換えません。

```powershell
py -3 ..\_tools\check_mlib_layout.py --template-docstrings ..\nodes\joint.py
```

`TODO`は型として読まれない形(引数は型を省き、戻り値はコロンを書かない)にしてあるため、
埋める前でも型スタブの生成とSphinxのビルドは止まりません。

値の範囲等の検証には`ValueError`も選べます。`--line`は繰り返し指定できます。
例外型は推測せず、選択されたassertの条件とメッセージをraiseへ移します。
コメントを含む場合や同じ行に他の文がある場合は、保存前に拒否します。
修正後は例外型が変わるため、呼出し側と該当APIのテストも確認してください。
`enumerate`への置換は、内容を確認して手動で行います。

## 文書の検査

`_docs`のビルド後、同じ文書用Pythonで実行します。
`check_mlib_doc_getter_names.py`はSphinxがビルド時に保存したpickleを読み込むので、自分でビルドした結果だけに使います。
この検査も任意の工程で、静的解析とMayaのテストには含まれません。

```powershell
..\_tools\.venv\Scripts\python.exe ..\_tools\check_mlib_docs.py --check-directory ..\_docs\_build\html
..\_tools\.venv\Scripts\python.exe ..\_tools\check_mlib_doc_getter_names.py ..\_docs\_build\html
```

ブラウザ自動確認を使う場合だけ`_docs/browser-requirements.txt`からPlaywrightを入れ、
`py -3 -m playwright install chromium`を実行します。静的検査やMayaテストには不要です。
