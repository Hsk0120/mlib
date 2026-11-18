"""Markdown出力で、継承図とHTML専用の案内を調整する。"""

import html
import re
import textwrap
from urllib.parse import urlsplit, urlunsplit

from docutils import nodes
from sphinx_markdown_builder.contexts import SubContext, SubContextParams, TableContext
from sphinx_markdown_builder.translator import MarkdownTranslator, pushing_context
from tabulate import tabulate


class _TextTableContext(TableContext):
    """バージョン番号などの文字列を数値へ変換せず表にする。"""

    @staticmethod
    def make_row(row):
        """本文の縦棒を、Markdown表の列区切りとして扱わせない。"""
        return [re.sub(r"(?<!\\)\|", r"\|", cell) for cell in TableContext.make_row(row)]

    def make(self):
        """0.6.11の表出力に、数値の自動解釈を無効にする指定を足す。"""
        context = SubContext()
        prefix = self.internal_context.make()
        if prefix:
            context.add(prefix)
        rows = self.headers + self.body
        if rows:
            headers = self.make_row(rows[0])
            body = [self.make_row(row) for row in rows[1:]]
            context.add(tabulate(body, headers=headers, tablefmt="github", disable_numparse=True), prefix_eol=2)
        return context.make()


class _MarkdownTranslator(MarkdownTranslator):
    """表だけを、原文の数値表記を保持する出力へ差し替える。"""

    @pushing_context
    def visit_table(self, node):
        """表のセルを文字列のまま受け取る。"""
        self._push_context(_TextTableContext(params=SubContextParams(2, 1)))


def _markdown_link(match):
    """MermaidのローカルHTMLリンクだけをMarkdownへ向ける。"""
    target = urlsplit(match.group(1))
    if not target.scheme and not target.netloc and target.path.endswith(".html"):
        target = target._replace(path=target.path[:-5] + ".md")
    return 'href "' + urlunsplit(target) + '"'


def _prepare_markdown(app, doctree, docname):
    """Sphinxで参照解決した本文を、Markdown builderが扱えるノードにする。"""
    if app.builder.name != "markdown":
        return
    for node in list(doctree.findall(nodes.abbreviation)):
        # AutoAPIのキーワード専用引数を表す *。説明用のHTML装飾だけを外す。
        node.replace_self(nodes.inline("", "", *node.children))
    for node in list(doctree.findall(nodes.raw)):
        match = re.fullmatch(r'\s*<pre class="mermaid">(.*?)</pre>\s*', node.astext(), re.S)
        if match:
            source = textwrap.dedent(html.unescape(match.group(1))).strip()
            source = re.sub(r'href "([^"]+)"', _markdown_link, source)
            node.replace_self(nodes.literal_block(source, source, language="mermaid"))
    # Markdownには検索UI・自動索引が無い。リンク切れの入口を出力しない。
    if docname == "modules":
        for section in list(doctree.findall(nodes.section)):
            if "indices-and-tables" in section.get("ids", []):
                section.children[1:] = [nodes.paragraph("", "検索・索引はHTML版を利用してください。")]


def setup(app):
    """Markdown builderと、Markdownだけに適用する本文調整を登録する。"""
    app.setup_extension("sphinx_markdown_builder")
    app.set_translator("markdown", _MarkdownTranslator, override=True)
    app.connect("doctree-resolved", _prepare_markdown)
    return {"version": "1", "parallel_read_safe": True, "parallel_write_safe": True}
