"""Maya不要で、_toolsのバッチがcmdで安全に読める形で保存されていることを検証する。"""

import re
import unittest
from pathlib import Path

_MLIB_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _MLIB_ROOT / "_tools"
_COMMENT = re.compile(r"^\s*(::|rem\s)", re.IGNORECASE)


def _batch_files():
    """_tools直下のバッチを名前順で返す。"""
    return sorted(_TOOLS.glob("*.bat"))


class BatchFileEncodingTest(unittest.TestCase):
    """バッチはShift-JIS(CP932)・CRLFで保存し、日本語はコメントだけに書く。"""

    def test_batch_files_exist(self):
        """検査の対象が空にならないことを確かめる。"""
        self.assertGreaterEqual(len(_batch_files()), 6)

    def test_saved_as_cp932_with_crlf(self):
        """UTF-8で保存し直すとcmdが日本語の行を読み誤るので、CP932として読めることを確かめる。"""
        for path in _batch_files():
            with self.subTest(file=path.name):
                raw = path.read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "BOMを付けない")
                text = raw.decode("cp932")
                has_japanese = any(ord(character) > 127 for character in text)
                if has_japanese:
                    # 日本語を含むUTF-8のファイルは、UTF-8としても読めてしまう。CP932ならUTF-8としては読めない。
                    with self.assertRaises(UnicodeDecodeError, msg="UTF-8で保存されている"):
                        raw.decode("utf-8")
                self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "改行はCRLFにする")

    def test_japanese_only_in_comments(self):
        """表示する文はmessages.txtへ置き、バッチの命令の行には日本語を書かない。"""
        for path in _batch_files():
            for number, line in enumerate(path.read_bytes().decode("cp932").splitlines(), 1):
                if any(ord(character) > 127 for character in line):
                    with self.subTest(file=path.name, line=number):
                        self.assertRegex(line, _COMMENT, "日本語はコメント(:: か rem)の行だけに書く")

    def test_gitattributes_declares_the_encoding(self):
        """取り出すときの文字コードと改行を.gitattributesで固定している。"""
        text = (_MLIB_ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^\*\.bat\s+.*\bworking-tree-encoding=CP932\b")
        self.assertRegex(text, r"(?m)^\*\.bat\s+.*\beol=crlf\b")

    def test_messages_are_utf8_and_referenced(self):
        """バッチが渡すキーがmessages.txtにあり、使われないキーが残っていない。"""
        lines = (_TOOLS / "messages.txt").read_text(encoding="utf-8").splitlines()
        defined = {line.split("=", 1)[0] for line in lines if line and not line.startswith("#")}
        used = set()
        for path in _batch_files():
            text = path.read_bytes().decode("cp932")
            for line in text.splitlines():
                if line.upper().startswith("%SAY% "):
                    used.update(word for word in line.split()[1:] if not word.startswith("%"))
            # 変数へ入れてから渡すキー(SET "..._MESSAGE=<キー>" と、種類に .ok/.ng を付けるもの)。
            used.update(re.findall(r'_MESSAGE=([a-z][A-Za-z.]+)"', text))
            for kind in re.findall(r'_KIND=([a-z][A-Za-z.]+)"', text):
                used.update({kind + ".ok", kind + ".ng"})
        self.assertEqual(sorted(used - defined), [], "messages.txtに無いキー")
        self.assertEqual(sorted(defined - used), [], "どのバッチも使っていないキー")


if __name__ == "__main__":
    unittest.main()
