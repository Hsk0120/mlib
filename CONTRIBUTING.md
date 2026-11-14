# mlibへの変更の手順

コードを書いた後に何を順に実行するかを、この文書で正とします。
細かい使い方は、テストは[`__tests__/README.md`](__tests__/README.md)、文書は[`_docs/README.md`](_docs/README.md)、
コードを書くときの規則は[`.github/copilot-instructions.md`](.github/copilot-instructions.md)を参照してください。

## 1回だけ行う準備

```powershell
_tools\setup.bat
_docs\setup.bat
```

`_tools/.venv`へruff、`_docs/.venv`へSphinxを入れます。PCの環境は変えません。
Pythonが無い場合はmayapyを使って`_tools/.mayapy-site`・`_docs/.mayapy-site`へ入れます。

## コードを書いた後の流れ

**ゲート**(必ず通す)と**任意の工程**(通したいときに通す)に分かれます。

| | 工程 | 入口 | Maya |
|---|---|---|---|
| ゲート | 1. 整形とlint | `_tools/format_mlib.bat` | 不要 |
| ゲート | 2. 公開名の一致 | `_tools/check_mlib_exports.py` | 不要 |
| ゲート | 3. Maya不要のテスト | `__tests__/runNoMaya.py` | 不要 |
| ゲート | 4. Mayaのテスト | `__tests__/run.bat` | 2027 |
| 任意 | 5. 型スタブ | `_tools/generate_mlib_stubs.bat` | 不要 |
| 任意 | 6. 文書 | `_docs/rebuild.bat` | 不要 |

### ゲートは1つの入口で通す

```powershell
_tools\verify.bat
```

1〜4を順に実行し、最初に失敗した工程で止まります。引数は3つです。

| 引数 | 動き |
|---|---|
| なし | 整形して書き換え、残りを検査する |
| `--check` | 何も書き換えず検査だけ行う(コミット前の確認) |
| `--no-maya` | 1〜3だけ実行する(Mayaが無い環境・短く回したいとき) |
| `--no-pause` | 最後にキー入力を待たない(ターミナル・スクリプトから) |

2027以外のバージョンで確かめるときは`__tests__\run.bat --versions 2022 2027`を直接実行します。

### 任意の工程

**docstringの型・引数・公開名を変えたら、型スタブを作り直して`.py`と一緒にコミットします。**

```powershell
_tools\generate_mlib_stubs.bat --no-pause
```

`--check`で作り直さずに最新かだけを確かめ、古ければ終了コード1になります。
`--report`は注釈にできなかった型を一覧表示します。**ゲートはスタブを検査しません**。

**docstringや文書を変えたら、Sphinxをビルドして検査します。**

```powershell
_docs\rebuild.bat --no-pause
_docs\.venv\Scripts\python.exe _tools\check_mlib_docs.py --check-directory _docs\_build\html
_docs\.venv\Scripts\python.exe _tools\check_mlib_doc_getter_names.py _docs\_build\html
```

ビルドは`-n -W`付きなので、参照切れがあれば失敗します。**ゲートは文書を検査しません**。

### なぜスタブと文書をゲートから外すのか

どちらも「解析」でも「テスト」でもなく**生成物のビルド**です。コードの正しさとは別の工程なので、
ゲートを短く保つために後ろへ置いています。そのかわり、生成物が古いままコミットされても誰も止めません。
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
それ以外はローカルの`verify.bat`で必ず通す前提だからです。
**CIが緑でも「Mayaで動く」保証にはなりません。**

## テストの置き場所

Mayaが要るかどうかで分けます。

```text
__tests__/
├─ noMaya/            Mayaを起動せずに動くテスト(runNoMaya.py)
├─ inMaya/            mayapyで動くテスト(run.bat・runMaya.py)
│  ├─ unit/<パッケージ>/   1つのモジュールを確かめる
│  └─ integration/         複数のパッケージにまたがる確認
└─ support/           共通基底・GUI用の補助(テストではない)
```

ファイル名の規則と追加のしかたは[`__tests__/README.md`](__tests__/README.md)を正とします。
