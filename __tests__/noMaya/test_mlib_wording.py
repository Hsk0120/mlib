"""Maya不要で、紹介文で挙げる他のライブラリの名前が紹介文以外に書かれていないことを検証する。"""

import subprocess
import unittest
from pathlib import Path

_MLIB_ROOT = Path(__file__).resolve().parents[2]
#: 名前を書いてよいファイル(文書の紹介文)。
_ALLOWED = ("_docs/source/whymlib.rst",)
#: 紹介文以外に書かない名前(大文字と小文字を区別しない)。このファイルが検査に掛からないよう、分けて書く。
_WORDS = ("py" + "mel",)
#: Gitを使えないときに探さないフォルダー(生成物・ローカルの作業用)。
_SKIPPED_DIRECTORIES = {".git", "__pycache__", "_build", "autoapi", ".venv", ".mayapy-site", "_output", ".logs", "research"}


def _repository_files():
    """検査するファイルの相対パス(``/`` 区切り)を取得する。

    Gitの管理下ではGitが追跡するファイル、そうでなければ生成物のフォルダーを除く全ファイルを対象にする。

    Returns:
        list[str]: リポジトリの直下からの相対パス。
    """
    try:
        found = subprocess.run(["git", "ls-files", "-z"], cwd=str(_MLIB_ROOT), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        found = None
    if found is not None and found.returncode == 0 and found.stdout:
        names = [name.decode("utf-8") for name in found.stdout.split(b"\0") if name]
        return sorted(name for name in names if (_MLIB_ROOT / name).is_file())
    names = []
    for path in _MLIB_ROOT.rglob("*"):
        relative = path.relative_to(_MLIB_ROOT)
        if path.is_file() and not _SKIPPED_DIRECTORIES.intersection(relative.parts[:-1]):
            names.append(relative.as_posix())
    return sorted(names)


class LibraryNameTest(unittest.TestCase):
    """他のライブラリの名前を書く場所が、文書の紹介文だけであることを確かめる。"""

    def test_names_are_written_only_in_the_introduction(self):
        """コード・コメント・docstring・テスト・ほかの文書の内容に名前が無い。"""
        hits = []
        for name in _repository_files():
            if name in _ALLOWED:
                continue
            lines = (_MLIB_ROOT / name).read_bytes().lower().split(b"\n")
            for number, line in enumerate(lines, 1):
                for word in _WORDS:
                    if word.encode("ascii") in line:
                        hits.append(f"{name}:{number}")
        self.assertEqual(hits, [], "library name outside the introduction")

    def test_names_are_not_used_in_file_names(self):
        """ファイル・フォルダーの名前に名前が無い。"""
        hits = [name for name in _repository_files() for word in _WORDS if word in name.lower()]
        self.assertEqual(hits, [])

    def test_introduction_exists(self):
        """名前を書いてよいファイルが実在する(移動・改名したら一覧を直す)。"""
        for name in _ALLOWED:
            with self.subTest(name=name):
                self.assertTrue((_MLIB_ROOT / name).is_file())


if __name__ == "__main__":
    unittest.main()
