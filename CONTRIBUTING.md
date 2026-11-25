# mlibへの変更の手順

コードを書いた後に何を順に実行するかを、この文書で正とします。
細かい使い方は、テストは[`__tests__/README.md`](__tests__/README.md)、文書は[`_docs/README.md`](_docs/README.md)、
コードを書くときの規則は[`.github/copilot-instructions.md`](.github/copilot-instructions.md)を参照してください。

## 1回だけ行う準備

```powershell
_tools\setup.bat
```

**セットアップはこの1本だけ**です。`_tools/.venv`へruffとSphinxをまとめて入れます。
PCの環境は変えず、Mayaにも書き込みません。Pythonが無い場合はmayapyを使って
`_tools/.mayapy-site`へ入れます。

必要なPythonは**3.11以上**(mayapyならMaya 2027〜2025)です。ruff単体なら3.9で足りますが、
Sphinx 8.2が3.11以上を要求するため、環境を1つにまとめた分だけ範囲が狭くなっています。

文書のブラウザ確認を行うときだけ、`_docs/browser-requirements.txt`のPlaywrightを追加します
(普段は不要。[`_docs/README.md`](_docs/README.md)参照)。

## コードを書いた後の流れ

**バッチは2本**です。その後に**任意の工程**が2つあります。

| | 工程 | 入口 | Maya |
|---|---|---|---|
| 1 | コードの静的解析と修正 | `_tools/format_mlib.bat` | 不要 |
| 2 | テスト | `_tools/test_mlib.bat` | 2027 |
| 任意 | 型スタブ | `_tools/generate_mlib_stubs.bat` | 不要 |
| 任意 | 文書 | `_tools/build_mlib_docs.bat` | 不要 |

```powershell
_tools\format_mlib.bat
_tools\test_mlib.bat --no-pause --versions 2027 --suite all
```

入口のバッチはすべて`_tools/`にあります(`setup.bat`を含めて5本)。`__tests__/`と`_docs/`には
テストと文書の中身だけを置き、動かす入口は置きません。

どのバッチも、最後に結果を日本語で表示してからキー入力を待ちます。最後の行が`[OK]`なら成功、`[NG]`なら失敗です。
`format_mlib.bat`と`test_mlib.bat`は手順ごとの`[OK]`・`[NG]`・`[--]`(実行していない)も並べます。
ターミナルやスクリプトから呼ぶときは`--no-pause`を付けます。終了コードは成功が0、失敗が0以外です。

バッチは**Shift-JIS(CP932)・CRLF**で保存します(日本語Windowsのcmdがそのまま読める形。UTF-8で保存すると、cmdが日本語の行を読み誤ります)。`.gitattributes`の指定で、リポジトリの中とGitHubの表示はUTF-8、cloneした作業フォルダーはShift-JISになります。GitHubからZIPでダウンロードした場合はUTF-8のままなので、バッチを使うときは`git clone`で取得してください。VS Codeは`.vscode/settings.json`の指定でShift-JISとして開きます。
バッチに書く日本語はコメントだけにし、表示する文は`_tools/messages.txt`(UTF-8)へ置きます(`_tools/_message.bat`が表示します。コンソールのコードページが違っても文字化けしません)。この決まりは`__tests__/noMaya/test_mlib_batchFiles.py`が検査します。

### 1. コードの静的解析と修正

`ruff format`(空白・空行・改行位置・引用符) → `ruff check --fix`(importの並び・未使用名・pathlib等)
→ `check_mlib_layout.py --check`(ruffに無い検査) → `check_mlib_exports.py`(公開名と明示宣言の一致)
を順に実行します。

| 引数 | 動き |
|---|---|
| なし | 整形して書き換え、残りを検査する |
| `--check` | 何も書き換えず検査だけ行う(コミット前の確認) |
| `--no-pause` | 最後にキー入力を待たない(ターミナル・スクリプトから) |

**コミットの前には、必ず`_tools\format_mlib.bat --check --no-pause`を実行し、最後の行が`[OK]`であることを確かめてください。**
コミット前のフックは置いていないので、人もエージェントも毎回自分で確かめます。`[NG]`なら、引数なしの`format_mlib.bat`で
直せるものを直し、残りを手で直してから、もう一度`--check`を通します。

### 2. テスト

`noMaya/`を先に実行し、通ったら`inMaya/`をmayapyで実行します。

| 引数 | 動き |
|---|---|
| `--versions 2027` | `noMaya/` → Maya 2027の`inMaya/` |
| `--versions 2022 2027` | 複数の版で`inMaya/`を回す |
| なし | `noMaya/` → Maya 2025の`inMaya/`(1回が重くならないよう既定は1版だけ。入っていなければ`missing`で失敗扱い) |
| `--suite unit\|integration\|all` | `inMaya/`の範囲を絞る |
| `--tests test_joint.py ...` | 指定ファイルだけ |
| `--no-maya` | `noMaya/`だけ(Mayaが無い環境・短く回したいとき) |
| `--no-pause` | 最後にキー入力を待たない(ターミナル・スクリプトから) |

`--no-maya`・`--no-pause`以外の引数は`__tests__/runMaya.py`へそのまま渡ります。
ダブルクリックで実行したときに結果を読めるよう、成功・失敗のどちらでも最後にキー入力を待ちます。

### 任意の工程

**docstringの型・引数・公開名を変えたら、型スタブを作り直して`.py`と一緒にコミットします。**

```powershell
_tools\generate_mlib_stubs.bat --no-pause
```

`--check`で作り直さずに最新かだけを確かめ、古ければ終了コード1になります。
`--report`は注釈にできなかった型を一覧表示します。**2本のバッチはスタブを検査しません**。

**docstringや文書を変えたら、Sphinxをビルドして検査します。**

```powershell
_tools\build_mlib_docs.bat --no-pause
_tools\.venv\Scripts\python.exe _tools\check_mlib_docs.py --check-directory _docs\_build\html
_tools\.venv\Scripts\python.exe _tools\check_mlib_doc_getter_names.py _docs\_build\html
```

ビルドは`-n -W`付きなので、参照切れがあれば失敗します。**2本のバッチは文書を検査しません**。

Wikiへ貼り付けるMarkdownが必要な場合は、`_tools/build_mlib_markdown.bat --no-pause`を実行します。
出力先・リンク・継承図の制限は[_docs/README.md](_docs/README.md)を参照してください。

**テストを足したら、テストがmlibのどこをどう確かめているかを測れます。**

```powershell
py -3 _tools\measure_mlib_coverage.py --versions 2022 2027
py -3 _tools\measure_mlib_coverage.py --tests test_joint.py --only nodes/joint.py
```

Mayaのテストをトレース付きで実行し、`__tests__/_output/coverage/<日時>/` へ次を書き出します。版を並べると、版ごとの値と合わせた値を出します
(版ごとの分岐は、その版でしか通りません)。標準ライブラリだけで動き、追加のパッケージは要りません。トレース付きなので、ふつうのテストより時間がかかります。

- `summary.txt`: パッケージごとの、実行された行・両側を通った分岐の割合と、観点の抜けの数。
- `gaps/`: 実行されなかった行。`branches/`: 片側しか通っていない `if`・`for`・`while`。
- `viewpoints/`: 公開メソッドごとの、テストで確かめていない観点(boolの引数の両方の値・docstringの `Raises:` の型・Undo・fastのUndoなし・cmdsとの突き合わせ)。

**テストが結果まで確かめているかは、ミューテーションテストで確かめられます。**

```powershell
py -3 _tools\measure_mlib_mutations.py --only nodes/joint.py --limit 30 --workers 4
```

mlibの写しを少し書き換え(比較の向き・`and`/`or`・`not`・定数・`raise`・`return` の値)、その行を通るテストがその変化に気づくかを確かめます。
気づかなかった書き換え(`__tests__/_output/mutations/<日時>/survived.md`)は、テストの確かめ方が弱い場所です。
書き換え1つごとにテストを流すので時間がかかります。`--only` と `--limit` で範囲を絞ってください。

### なぜスタブと文書を2本から外すのか

どちらも「解析」でも「テスト」でもなく**生成物のビルド**です。コードの正しさとは別の工程なので、
2本を短く保つために後ろへ置いています。そのかわり、生成物が古いままコミットされても誰も止めません。
`--check`と`-n -W`で自分で確かめてください。

## コミットの順番

1. mlibのリポジトリでコミットし、pushする
2. 使う側のリポジトリ(submoduleとして置いている親)で、mlibの参照を更新する

スタブ(`.pyi`)はGitで管理しているので、作り直したら`.py`と同じコミットに入れます。
`.pyi`は手で編集しません。

## CIがやること

GitHub Actionsは[`.github/workflows/docs.yml`](.github/workflows/docs.yml)の1つだけで、
**GitHub Pagesへの文書の公開**を行います。これはビルド結果をコミットしない限りローカルからはできません。

整形・lint・テストはCIに置いていません。runnerにMayaが無いためMayaのテストは実行できず、
それ以外はローカルの2本(`_tools/format_mlib.bat`と`_tools/test_mlib.bat`)で必ず通す前提だからです。
**CIが緑でも「Mayaで動く」保証にはなりません。**

## テストの置き場所

Mayaが要るかどうかで分けます。

```text
__tests__/
├─ noMaya/            Mayaを起動せずに動くテスト(runNoMaya.py)
├─ inMaya/            mayapyで動くテスト(runMaya.py)
│  ├─ unit/<パッケージ>/   1つのモジュールを確かめる
│  └─ integration/         複数のパッケージにまたがる確認
└─ support/           共通基底・GUI用の補助(テストではない)
```

ファイル名の規則と追加のしかたは[`__tests__/README.md`](__tests__/README.md)を正とします。
