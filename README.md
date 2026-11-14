# mlib

Maya API 2.0(`maya.api.OpenMaya`)を土台にした、Maya用のPythonライブラリです。
ノード・アトリビュート(Plug)・コンポーネントのラッパー、マトリクスやクォータニオンなどの数学型、
選択・名前空間・単位・イベントなどの共通処理を提供します。

- 文書: https://hsk0120.github.io/mlib/
- 版: [`_version.py`](_version.py)
- ライセンス: [MIT](LICENSE)

## 動作環境

Maya 2022〜2027(Windows)のPython 3。Maya付属のPythonだけで動き、追加のパッケージは不要です。

## 導入

このリポジトリを `mlib` という名前のフォルダーとして置き、その親フォルダーをPythonの検索パスへ追加します。

```python
import sys
sys.path.insert(0, "C:/tools")  # C:/tools/mlib に置いた場合
import mlib
```

Mayaのモジュール(`.mod`)で読み込む場合は、親フォルダーを `PYTHONPATH` に通します。

```text
+ MAYAVERSION:2027 PLATFORM:win64 mlib 0.0.1 C:/tools
PYTHONPATH +:= ./
```

## 使い方

```python
import mlib

node = mlib.createNode("transform", name="mlibExample")
node.getPlug("translateX").set(10)
print(mlib.ls(type="transform"))
```

詳しくは文書の「mlib入門」を参照してください。

## フォルダー

| フォルダー | 内容 |
| --- | --- |
| `cmds/` | `createNode`・`ls` などのコマンドと作成関数 |
| `nodes/`・`plugs/`・`components/` | ノード・アトリビュート・コンポーネントのラッパー |
| `maths/` | ベクトル・マトリクス・クォータニオン等の数学型 |
| `common/` | 選択・名前空間・単位・プラグイン・イベント等 |
| `json/` | シーンのデータのJSON保存・復元 |
| `core/` | 共通基底・型の登録・編集の基盤 |
| `__tests__/` | テスト(手順は [`__tests__/README.md`](__tests__/README.md)) |
| `_docs/` | Sphinx文書(手順は [`_docs/README.md`](_docs/README.md)) |
| `_tools/` | 整形(ruff)の入口、型スタブ(`.pyi`)の生成スクリプト、公開名・文書の検査ツール |
| `ruff.toml` | 整形と検査の設定(ruff。行幅160) |

## 開発

- コードを書くときのルールは [`.github/copilot-instructions.md`](.github/copilot-instructions.md) にまとめています。
- ゲートを一括で通す: `_tools/verify.bat`(整形とlint → 公開名 → Maya不要のテスト → Maya 2027のテスト。手順は [CONTRIBUTING.md](CONTRIBUTING.md))
- Maya不要のテストだけ: `__tests__` で `py -3 runNoMaya.py`
- Mayaでのテスト: `__tests__` で `run.bat --versions 2027 --suite all`
- 型スタブ: docstringの型・引数・公開名を変えたら `_tools/generate_mlib_stubs.bat` で作り直し、一緒にコミットします(`py` の Python 3.14〜3.9 を新しい順に探し、無ければ Maya 2027〜2023 の mayapy を使います。最後にキー入力を待つので、ターミナルからは `--no-pause` を付けます)。
- コードの書式: `_tools/format_mlib.bat` が `ruff format`(空白・空行・改行位置・引用符) → `ruff check --fix`(import順・未使用名・Mayaのimport形式・文字コード・pathlib) → `check_mlib_layout.py --check`(ruffに無い検査) の順に実行します。`--check` を付けると何も変えずに検査します(コミット前の確認用)。ruffは `_tools/setup.bat` で `_tools/.venv` へ入れ(文書の `_docs/setup.bat` と同じ作りで、PCの環境は変えません)、版は固定しています(`ruff.toml` の `required-version` で、別の版は実行を拒否します)。
