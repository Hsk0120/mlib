# mlib ドキュメントの編集

初回は「初回セットアップ」、通常は「編集するファイル」と「HTMLを作って開く」を参照してください。
Mayaの起動は不要です。SphinxとAutoAPIがPythonソースから説明ページを作ります。
文書は日本語のみで管理します。

## 初回セットアップ（Windows）

| 必要なもの | 用意する方法 |
| --- | --- |
| Python 3.11〜3.14 | [Python公式のWindows版](https://www.python.org/downloads/windows/)をインストール。手元の確認は3.12・3.13、CIの指定は3.11です。3.15以降は使いません(pipがPyYAMLのビルド済みパッケージを取得できず、ビルドが必要になって止まるため)。無い場合はMaya 2027〜2025のmayapyを使います。 |
| Sphinx・sphinx-autoapi | `..\_tools\setup.bat`が`requirements.txt`からインストールします(ruffと同じ環境へ入れます)。 |
| インターネット接続 | 初回のパッケージ取得と、ブラウザでの継承図表示に使います。 |

現在の継承図はMermaidをブラウザで描画するため、**Graphviz（dot）・Node.js・Mayaは不要**です。
Mermaid自体もバッチでインストールする必要はありません。

1. Python 3.11〜3.14をインストールし、PowerShellで`py -0p`の一覧に3.11〜3.14のどれかが出ることを確認します。`python`は使いません(Pythonを入れていても、Microsoft Storeを開くだけの`python`が先に見つかることがあるため)。
2. [`_tools/setup.bat`](../_tools/setup.bat)をダブルクリックします(整形・検査用のruffも同じ環境へ入ります。済んでいれば不要です)。
3. 最後に`[OK] ツールの準備ができました。`が出たら[`_tools/build_mlib_docs.bat`](../_tools/build_mlib_docs.bat)を実行します。
4. 最後に`[OK] 文書のビルドに成功しました。`が出たら`_build/html/index.html`をブラウザで開きます。

セットアップとビルドのバッチは、ほかの入口と一緒に`_tools/`にあります。このフォルダーには文書の中身だけを置きます。
`setup.bat`は、`_tools/.venv`だけにパッケージを入れます(環境はこの1つだけです)。
Pythonは`py -3.14`→`py -3.13`→`py -3.12`→`py -3.11`の順に探し、最初に動いた版で`.venv`を作ります。どれも見つからないときは、Maya 2027→2026→2025の順に見つかったmayapyを使い、`_tools/.mayapy-site`へ`pip install --target`で入れます（mayapyではvenvを作れないため）。使ったmayapyの場所は`.mayapy-site/mayapy-path.txt`に記録し、`build_mlib_docs.bat`は`.venv`が無ければそのmayapyでビルドします。
既存の`.venv`・`.mayapy-site`は再利用し、Python本体のインストールやシステムのPATH変更は行いません。
PowerShellから実行するときは、リポジトリルート(mlibのフォルダー)で次を使います。

```powershell
& .\_tools\setup.bat --no-pause
if ($LASTEXITCODE -eq 0) { & .\_tools\build_mlib_docs.bat --no-pause }
if ($LASTEXITCODE -eq 0) { Invoke-Item .\_docs\_build\html\index.html }
```

バッチはどちらも成功時に終了コード0、失敗時に非0を返します。
`--no-pause`は終了時のキー入力待ちを省く指定です。

### セットアップで止まる場合

- **Pythonが見つからない**: インストール後にPowerShellを開き直し、上のバージョン確認を行ってください。`setup.bat`は`py -3.14`〜`py -3.11`(新しい順)、最後にMaya 2027〜2025のmayapyを探します。
- **古い・壊れた`.venv`がある**: ビルドを終了し、`_tools/.venv`を`.venv-backup`などへ名前変更してから`setup.bat`を再実行します。別PCからコピーした`.venv`も作り直してください。`_tools/.mayapy-site`も同じです。
- **`.venv`がPython 3.15以降**: `The existing .venv must use Python 3.11 to 3.14`と出ます。Python 3.14以前をインストールし、`_tools/.venv`を削除してから`setup.bat`を再実行します。
- **mayapyからPythonへ切り替える**: Pythonをインストールしてから`_tools/.mayapy-site`を削除し、`setup.bat`を再実行します。`.venv`があれば`build_mlib_docs.bat`は`.venv`を優先します。
- **パッケージの取得に失敗する**: 表示されたpipのエラーとネット接続・プロキシ設定を確認し、`setup.bat`を再実行します。
- **本文は出るが図が出ない**: ブラウザから`cdn.jsdelivr.net`に接続できるか確認してください。Graphvizを入れる必要はありません。

## 編集するファイル

| 変更したい内容 | 編集するファイル |
| --- | --- |
| トップページの目次・並び順 | [source/index.rst](source/index.rst) |
| 「なぜ mlib ?」の本文・例 | [source/whymlib.rst](source/whymlib.rst) |
| 「mlib入門」の本文・例 | [source/getting_started.rst](source/getting_started.rst) |
| APIの分類・モジュールへの入口 | [source/modules.rst](source/modules.rst) |
| 「なぜ mlib ?」に載せる図 | `source/_includes/`の各RST |
| クラス・関数・引数・戻り値の説明 | 対象のPythonファイルのdocstring（`../nodes/joint.py`など） |
| ページの幅・右目次・スマホ表示 | [source/_static/css/layout.css](source/_static/css/layout.css) |
| 配色・文字・見出しの装飾 | [source/_static/css/theme.css](source/_static/css/theme.css) |
| 各クラスページの共通レイアウト | `source/_templates/autoapi/python/class.rst` |

APIの本文は日本語Google形式で書きます。新しいクラスやメソッドは、ビルド時にAutoAPIが検出します。
ノード型の登録・公開名への追加は、文書生成とは別にmlib本体で行ってください。

`source/autoapi/`のRSTと`_build/`のHTMLは生成物です。説明を直すときは元のRSTかdocstringを編集します。

## HTMLを作って開く

以下はWindowsのPowerShellの例で、リポジトリルート(mlibのフォルダー)で実行します。

通常は初回セットアップ後、そのまま`_tools\build_mlib_docs.bat`を実行できます。
バッチを使わず環境を作る場合は、Python 3.11〜3.14で次を実行します(`-3.14`は入っている版に合わせます)。
既存の`.venv`は作り直す必要はありません。

```powershell
py -3.14 -m venv _tools\.venv
& .\_tools\.venv\Scripts\python.exe -m pip install -r _tools\requirements-dev.txt -r _docs\requirements.txt
```

Sphinxを直接実行してHTMLを作り、ブラウザで開きます。

```powershell
& .\_tools\.venv\Scripts\python.exe -P -m sphinx -E -a -b html -n -W --keep-going .\_docs\source .\_docs\_build\html
if ($LASTEXITCODE -eq 0) { Invoke-Item .\_docs\_build\html\index.html }
```

`-E -a`は全ページを作り直す指定、`-b html`は出力形式、`-n`は解決しない参照(リンク切れ)も警告にする指定、
`-W`は警告も失敗として扱う指定です。
終了時の`build succeeded`と、警告・エラーの有無を確認してください。

Sphinxは出力先に残った古いHTMLを削除しません。ページを削除した場合は空の出力先を指定するか、
次のバッチを使います。バッチは`_build/html`を削除してから日本語版を作り直します。

```powershell
& .\_tools\build_mlib_docs.bat --no-pause
```

## フォルダの役割

```text
_docs/
├─ README.md          この手順
├─ requirements.txt   文書用の依存パッケージ(`_tools/setup.bat`が読む)
├─ browser-requirements.txt  ブラウザ確認用の追加パッケージ(普段は不要)
├─ source/            文書と表示素材
│  ├─ conf.py         Sphinx設定
│  ├─ index.rst       トップページの目次
│  ├─ whymlib.rst     なぜ mlib ?
│  ├─ getting_started.rst  mlib入門
│  ├─ modules.rst     モジュールリファレンスの入口
│  ├─ _includes/     本文へ差し込む図（nodes/plugs/components/maths.rst）
│  ├─ _static/
│  │  ├─ css/        theme・layout・code-dark-plus・mermaid.css
│  │  └─ js/         mermaid-init.js
│  └─ _templates/autoapi/python/  class.rst・module.rst
├─ _ext/              継承図・署名表示など、mlib固有のビルド処理
└─ _build/            生成したHTMLなど（Git対象外）
```

環境(`_tools/.venv`、mayapyのときは`_tools/.mayapy-site`)と、セットアップ・ビルドのバッチは`_tools/`にあります。

生成の流れは、`source/conf.py`の設定 → RSTとPythonソースの読取り → テンプレートへの展開 → HTMLです。
`_includes`の図は`whymlib.rst`の`include`指定で差し込み、独立したページは作りません。
日常の本文編集では`_ext`を変更する必要はありません。内部を調べる場合は[_ext/README.md](_ext/README.md)を参照してください。
調査資料は公開ページに混ぜず、このリポジトリにも置きません。

## 変更後の検査と公開

以下のコマンドは、リポジトリルート(mlibのフォルダー)で実行します。

```powershell
& .\_tools\.venv\Scripts\python.exe _tools/check_mlib_exports.py
& .\_tools\.venv\Scripts\python.exe _tools/check_mlib_docs.py --check-directory _docs/_build/html
& .\_tools\.venv\Scripts\python.exe _tools/check_mlib_doc_getter_names.py _docs/_build/html
```

HTMLの確認では目次・APIリンク・継承図も見ます。Mermaid本体はCDNから読み込むため、図の表示にはネット接続が必要です。
文書のビルド成功は、Maya内でのAPI動作確認とは別です。

対象変更を`main`へpushすると、`.github/workflows/docs.yml`がビルド・検査・GitHub Pagesへの公開を行います。
ローカルでビルドするだけでは公開版は変わりません。生成HTMLや`.venv`はGitへ登録しません。
