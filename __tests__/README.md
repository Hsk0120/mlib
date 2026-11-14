# mlibのテスト

mlib本体とこのフォルダだけで実行できます。
外部ライブラリ・mlibを使う側のパッケージ・mlib拡張は、本体テストの必須依存に含めません。

書いた後に流す順番は[../CONTRIBUTING.md](../CONTRIBUTING.md)を正とします。ゲートは1つの入口で通せます。

```powershell
..\_tools\verify.bat --no-pause
```

`verify.bat`は 整形とlint → 公開名の一致 → `runNoMaya.py` → `run.bat`(Maya 2027)を順に実行し、
最初に失敗した工程で止まります。`--check`は書き換えずに検査だけ、`--no-maya`は前半3つだけを実行します。
型スタブ(`..\_tools\generate_mlib_stubs.bat`)とSphinx(`..\_docs\rebuild.bat`)はその後の任意の工程で、
ゲートはどちらも検査しません。

## フォルダ

```text
__tests__/
├─ README.md          この手順
├─ run.bat            Maya版テストのWindows用入口
├─ runMaya.py         mayapyで単体・結合テストを実行
├─ runNoMaya.py       Maya不要のテストを実行
├─ runGui.py          専用Maya GUIで単体・結合・表示を確認
├─ runAll.py          テスト探索・実行・ログ集計
├─ noMaya/           Mayaを起動せずに動くテスト(runNoMaya.py)
├─ inMaya/           mayapyで動くテスト(run.bat・runMaya.py)
│  ├─ unit/          1つのモジュールを確かめるテスト。ソースと同じパッケージ名のフォルダーに分ける
│  │  ├─ cmds/ nodes/ plugs/ components/ maths/ common/ core/ json/
│  │  └─ root/       mlib直下のモジュール(decorator.py・util.py・logger.py・__init__.py 等)
│  └─ integration/   複数のパッケージにまたがる確認。フォルダーを作らず、名前の先頭に観点を書く
├─ support/          共通基底(namespaceCase.py)、GUI内の実行・プロセス監視の補助
└─ _output/          結果・ログ・専用Maya設定（Git対象外）
```

公開名・コード配置・生成文書の検査ツールは mlib の `_tools/` にあります。
単体テストでもOpenMayaやシーンを使うものはMayaが必要です。

## 準備

- Maya版: 検証対象のMayaと、その実行に必要なライセンスを用意します。GUIの事前起動は不要です。
- 静的検査: 通常のPython 3.11以上を使います。`_docs/.venv`のPythonでも実行できます。
- 以下のコマンドは**この`__tests__`フォルダ**から実行します。Mayaのテスト環境はランナーが用意します。

## 単体・結合を分けて実行

PowerShellで実行します。

```powershell
# Maya不要のテスト(リントは ..\_tools\verify.bat が持つ)
py -3 .\runNoMaya.py

# Mayaのインストール状況を確認するだけ
.\run.bat --list

# 個々のAPIの単体テスト
.\run.bat --versions 2027 --suite unit

# 複数のmlib機能を組み合わせる結合テスト
.\run.bat --versions 2027 --suite integration

# 両方を実行（--suite省略時もall）
.\run.bat --versions 2027 --suite all

# 対象ファイルだけ実行。指定ミスは失敗として報告する
.\run.bat --versions 2027 --tests test_joint.py
# 同じ名前のファイルが別のフォルダーにあるときは、フォルダー付きで絞る
.\run.bat --versions 2027 --tests json/test_file.py

# 複数バージョンで同じテストを実行
.\run.bat --versions 2022 2027 --suite all
```

`run.bat`は検出したmayapyを制御用Pythonに使い、実テストには各版のmayapyを使います。
通常Pythonからは`py -3 .\runMaya.py --versions 2027 --suite unit`でも実行できます。
引数を付けず`run.bat`を実行すると、2022〜2027の全版を対象にします。
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
.\run.bat --versions 2027 --suite unit --tests cmds/test_delete.py test_plug_basics.py nodes/test_transform.py

# 基本操作を組み合わせる結合テストだけ
.\run.bat --versions 2027 --suite integration --tests test_workflow_scene.py
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
  パッケージの `__init__.py` は `init`、先頭の `_` は付けません(`nodes/_calculation.py` → `test_calculation.py`)。
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
`setup.bat`は`_tools/.venv`を作ってそこへruffを入れます(Sphinxの`_docs/setup.bat`と同じ作りで、`py -3.14`〜`py -3.9`を新しい順に探し、Pythonが無ければMaya 2027〜2023のmayapyで`_tools/.mayapy-site`へ入れます)。
既存の`.venv`は再利用します。壊れたときは`.venv`を`.venv-backup`へ名前変更してから`setup.bat`を実行し直してください。
`format_mlib.bat`と`check_mlib_layout.bat`はこの`.venv`を優先して使い、無ければPATHのruffや`py`のPythonを探します。
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
```

Windowsでは`_tools\check_mlib_layout.bat`でも同じ検査と修正ができます。ダブルクリックすると本体全体を検査し、
最後にキー入力を待ちます(ターミナルや他のスクリプトからは`--no-pause`を付けます)。
`py`のPython 3.14〜3.9を新しい順に探し、無ければMaya 2027〜2023のmayapyを使います。

```powershell
# 本体全体、または指定ファイルを検査する(--checkは省ける)
..\_tools\check_mlib_layout.bat --no-pause
..\_tools\check_mlib_layout.bat ..\nodes\node.py --no-pause
# クラス内メンバーの順を直してから、残った違反を表示する(その後に`format_mlib.bat`で整形する)
..\_tools\check_mlib_layout.bat --fix --no-pause
..\_tools\check_mlib_layout.bat --fix ..\nodes\node.py --no-pause
```

`--fix-asserts`・`--outline`等のほかの引数は、そのまま`check_mlib_layout.py`へ渡します。

違反があればファイル・行番号・検査コード・内容を表示し、終了コード1を返します。
`L004`は定数、`L005`は文字列の並びの`__all__`(他の名前から組み立てる`__all__`は定義の後ろでもよい)、`L006`は`if TYPE_CHECKING:`の位置、
`L020`〜`L022`はクラス内メンバーの順と対になる操作の隣接、`L023`はその並び検査をスキップしたクラスです。
`--fix`が直すのはクラス内メンバーの順だけで、並べ替えた後の空行は`ruff format`が直します。
`..\_tools\verify.bat`からも同じ検査を実行します(`runNoMaya.py`はテストだけを実行します)。

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
..\_docs\.venv\Scripts\python.exe ..\_tools\check_mlib_docs.py --check-directory ..\_docs\_build\html
..\_docs\.venv\Scripts\python.exe ..\_tools\check_mlib_doc_getter_names.py ..\_docs\_build\html
```

ブラウザ自動確認を使う場合だけ`_docs/browser-requirements.txt`からPlaywrightを入れ、
`py -3 -m playwright install chromium`を実行します。静的検査やMayaテストには不要です。
