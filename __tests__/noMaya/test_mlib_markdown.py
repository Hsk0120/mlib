"""Markdown出力で署名・継承図・数値表記を保持することを検証する。"""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

_EXTENSION = Path(__file__).resolve().parents[2] / "_docs/_ext/mlibMarkdown.py"
_HAS_BUILDER = importlib.util.find_spec("sphinx_markdown_builder") is not None


@unittest.skipUnless(_HAS_BUILDER, "Markdown検証には_tools/setup.batの文書環境が必要")
class MarkdownOutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("mlibMarkdownTest", _EXTENSION)
        cls.extension = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.extension)
        # 文書用の依存は、セットアップ済みのときだけ読み込む。
        from docutils import nodes

        cls.nodes = nodes

    def test_mermaid_preserves_lines_and_external_urls(self):
        nodes = self.nodes
        source = '<pre class="mermaid">\nclassDiagram\nA &lt;|-- B\nclick A href "A.html#A"\nclick B href "https://example.com/B.html"\n</pre>'
        tree = nodes.document("", "")
        tree += nodes.raw("", source, format="html")
        self.extension._prepare_markdown(SimpleNamespace(builder=SimpleNamespace(name="markdown")), tree, "example")
        block = tree[0]
        self.assertIsInstance(block, nodes.literal_block)
        self.assertEqual(block["language"], "mermaid")
        self.assertIn('A <|-- B\nclick A href "A.md#A"', block.astext())
        self.assertIn('href "https://example.com/B.html"', block.astext())

    def test_html_is_not_modified(self):
        nodes = self.nodes
        tree = nodes.document("", "")
        raw = nodes.raw("", '<pre class="mermaid">classDiagram</pre>', format="html")
        tree += raw
        self.extension._prepare_markdown(SimpleNamespace(builder=SimpleNamespace(name="html")), tree, "example")
        self.assertIs(tree[0], raw)

    def test_signature_separator_and_index_anchor_survive(self):
        nodes = self.nodes
        tree = nodes.document("", "")
        tree += nodes.abbreviation("", "*")
        section = nodes.section(ids=["indices-and-tables"])
        section += nodes.title("", "Indices and tables")
        section += nodes.paragraph("", "古いリンク")
        tree += section
        self.extension._prepare_markdown(SimpleNamespace(builder=SimpleNamespace(name="markdown")), tree, "modules")
        self.assertEqual(tree[0].astext(), "*")
        self.assertIsInstance(tree[0], nodes.inline)
        self.assertIn("indices-and-tables", tree[1]["ids"])
        self.assertNotIn("古いリンク", tree.astext())

    def test_table_keeps_version_and_leading_zero(self):
        table = self.extension._TextTableContext()
        table.headers = [[["version"], ["number"]]]
        table.body = [[["3.10"], ["001"]]]
        output = table.make()
        self.assertIn("3.10", output)
        self.assertIn("001", output)

    def test_table_escapes_pipes_without_double_escape(self):
        cells = self.extension._TextTableContext.make_row([["`a | b`"], [r"a \| b"]])
        self.assertEqual(cells, [r"`a \| b`", r"a \| b"])


if __name__ == "__main__":
    unittest.main()
