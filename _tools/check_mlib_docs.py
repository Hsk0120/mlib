"""Sphinx生成物と公開済みPagesを、Chromiumで検証するCI用スクリプト。"""

import argparse
import ast
import base64
import binascii
import functools
import hashlib
import json
import os
import re
import threading
import time
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

CASES = [
    ("autoapi/mlib/nodes/joint/Joint.html", "mlib.nodes.transform.Transform"),
    ("autoapi/mlib/nodes/animCurve/AnimCurve.html", "mlib.nodes.animCurveTA.AnimCurveTA"),
    ("autoapi/mlib/maths/matrix/Matrix.html", "mlib.maths.matrix.Matrix"),
    ("autoapi/mlib/nodes/node/Node.html", "mlib.core.object.Object"),
]
ASSETS = ["_static/js/mermaid-init.js", "_static/css/theme.css", "_static/css/layout.css", "_static/css/code-dark-plus.css", "_static/css/mermaid.css"]
# Mermaid本体はリポジトリに同梱せず、版を固定したjsDelivrのURLからSRI付きで読み込む。
# 固定した版とハッシュの正は _docs/source/conf.py の _MERMAID_URL と _MERMAID_SRI。
_MLIB_ROOT = Path(__file__).resolve().parents[1]
DOCS_CONF = _MLIB_ROOT / "_docs/source/conf.py"
MERMAID_CDN_SCRIPT = re.compile(r"^https://cdn\.jsdelivr\.net/npm/mermaid@\d+\.\d+\.\d+/dist/mermaid\.min\.js$")
MERMAID_INIT_SCRIPT = "mermaid-init.js"


def _string_constant(node, known):
    """代入の右辺が文字列として確定できればその値を、できなければNoneを返す。

    文字列リテラル、既に読んだ名前、それらだけを埋め込んだf文字列に対応する。
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return known.get(node.id)
    if isinstance(node, ast.FormattedValue) and node.conversion == -1 and node.format_spec is None:
        return _string_constant(node.value, known)
    if isinstance(node, ast.JoinedStr):
        parts = [_string_constant(part, known) for part in node.values]
        if None not in parts:
            return "".join(parts)
    return None


def read_mermaid_pin(conf_path=DOCS_CONF):
    """_docs/source/conf.py で固定したMermaid本体のURLとSRIを、conf.pyを実行せずに読み取る。

    conf.py はSphinx拡張をimportするため、ブラウザ検証だけを行う環境
    (公開後の確認ジョブ)でも使えるよう、構文木からモジュール直下の文字列定数だけを求める。

    Returns:
        dict: ``src`` (版を固定したCDNのURL)と ``integrity`` (``sha384-`` で始まるSRI)。
    """
    tree = ast.parse(conf_path.read_text(encoding="utf-8"), filename=str(conf_path))
    known = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                value = _string_constant(statement.value, known)
                if value is not None:
                    known[target.id] = value
    pin = {"src": known.get("_MERMAID_URL"), "integrity": known.get("_MERMAID_SRI")}
    assert pin["src"] and pin["integrity"], f"{conf_path}: _MERMAID_URL / _MERMAID_SRI が見つかりません"
    assert MERMAID_CDN_SCRIPT.match(pin["src"]), f"{conf_path}: MermaidのURLが、版を固定したjsDelivrのURLではありません: {pin['src']}"
    algorithm, _, digest = pin["integrity"].partition("-")
    try:
        digest_size = len(base64.b64decode(digest, validate=True))
    except binascii.Error:
        digest_size = 0
    assert algorithm == "sha384" and digest_size == hashlib.sha384().digest_size, (
        f"{conf_path}: _MERMAID_SRI はbase64のsha384ダイジェスト1つにしてください: {pin['integrity']}"
    )
    return pin


def _is_mermaid_engine(src):
    """初期化用の mermaid-init.js 以外で、Mermaid を含むscriptを本体とみなす。"""
    return "mermaid" in src and MERMAID_INIT_SCRIPT not in src


def _check_script_list(scripts, pin, source):
    """1ページ分のscript属性の並びが、固定したMermaid本体の読み込み方どおりか確かめる。"""
    engines = [index for index, script in enumerate(scripts) if _is_mermaid_engine(script.get("src") or "")]
    assert len(engines) == 1, f"{source}: Mermaidのスクリプトは1つにしてください: {[scripts[i] for i in engines]}"
    engine = scripts[engines[0]]
    assert engine.get("src") == pin["src"], f"{source}: MermaidのURLが _docs/source/conf.py と違います: {engine.get('src')}"
    assert engine.get("integrity") == pin["integrity"], f"{source}: MermaidのSRIが _docs/source/conf.py と違います: {engine.get('integrity')}"
    assert engine.get("crossorigin") == "anonymous", f"{source}: Mermaidのスクリプトには crossorigin=anonymous が必要です"
    # どちらも defer なので記述順に実行される。初期化が本体より先だと図が描かれない。
    initializers = [index for index, script in enumerate(scripts) if MERMAID_INIT_SCRIPT in (script.get("src") or "")]
    assert initializers and min(initializers) > engines[0], f"{source}: {MERMAID_INIT_SCRIPT} はMermaidのスクリプトより後で読み込んでください"


class _ScriptTags(HTMLParser):
    """HTML中のscript要素の属性を、出現順に集める。"""

    def __init__(self):
        super().__init__()
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.scripts.append(dict(attrs))


def _cases(package_name):
    """対象パッケージ名に対応するAPIページとクラス名を返す。

    Args:
        package_name (str): 対象のコアパッケージ名。

    Returns:
        list[tuple[str, str]]: APIページとリンク先クラスの組。
    """
    return [(path.replace("mlib", package_name), target.replace("mlib", package_name)) for path, target in CASES]


def check_built_html(directory, pin, package_name="mlib"):
    """ビルド済みHTMLを、ブラウザもネットワークも使わずに検査する。

    - Mermaid本体(mermaid.min.js など)がビルド出力に含まれていないこと。
      以前のビルドの残りがあると、同梱をやめた本体を配布してしまうため。
    - Mermaidを使う各ページが、_docs/source/conf.py で固定したURL・SRIどおりに本体を1回だけ読み込み、
      その後に初期化スクリプトを読み込んでいること。

    Returns:
        int: 検査したHTMLページ数。
    """
    directory = Path(directory)
    bundled = sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("mermaid*")
        if path.is_file() and path.suffix in {".js", ".mjs"} and path.name != MERMAID_INIT_SCRIPT
    )
    assert not bundled, f"ビルド結果にMermaid本体を含めないでください(古いビルドが残っていませんか): {bundled}"
    checked = set()
    for path in sorted(directory.rglob("*.html")):
        parser = _ScriptTags()
        parser.feed(path.read_text(encoding="utf-8"))
        source = path.relative_to(directory).as_posix()
        if any("mermaid" in (script.get("src") or "") for script in parser.scripts):
            _check_script_list(parser.scripts, pin, source)
            checked.add(source)
    missing = sorted({source for source, _ in _cases(package_name)} - checked)
    assert not missing, f"クラス図のあるページがMermaidを読み込んでいません: {missing}"
    return len(checked)


def stamp(directory, sha, package_name="mlib"):
    paths = sorted({path for path, _ in _cases(package_name)} | set(ASSETS))
    payload = {"commit": sha, "files": {path: hashlib.sha256((directory / path).read_bytes()).hexdigest() for path in paths}}
    (directory / "build-info.json").write_text(json.dumps(payload), encoding="utf-8")


def wait_for_release(base, sha, timeout):
    """公開反映の遅延を有限時間リトライ。HTML/JSも同じ生成物であることを確認。"""
    deadline = time.monotonic() + timeout
    last_error = None
    while True:
        try:

            def fetch(path):
                url = urljoin(base, path) + f"?revision={sha}&check={time.time_ns()}"
                request = Request(url, headers={"Cache-Control": "no-cache"})
                with urlopen(request, timeout=20) as response:
                    return response.read()

            info = json.loads(fetch("build-info.json"))
            if info["commit"] != sha:
                raise ValueError(f"Expected {sha}, got {info['commit']}")
            for path, digest in info["files"].items():
                if hashlib.sha256(fetch(path)).hexdigest() != digest:
                    raise ValueError(f"公開されたファイルが古いか、一致しません: {path}")
            return
        except Exception as error:
            last_error = error
            if time.monotonic() >= deadline:
                raise RuntimeError(f"公開の確認に失敗しました: {last_error}") from error
            print(f"公開の反映を待っています: {error}", flush=True)
            time.sleep(10)


def check_mermaid_script(page, source, pin):
    """表示中のページが、_docs/source/conf.py で固定したURL・SRIどおりにMermaid本体を読み込んでいるか確かめる。

    ブラウザはintegrityの値と取得したファイルが一致しない場合に実行を拒否するため、
    この後の図の描画確認と合わせて、固定した版・ハッシュどおりに動いていることを保証する。
    """
    scripts = page.evaluate("""() => Array.from(document.scripts, script => ({
        src: script.getAttribute("src"),
        integrity: script.getAttribute("integrity"),
        crossorigin: script.getAttribute("crossorigin"),
    }))""")
    _check_script_list(scripts, pin, source)


def check_browser(base, output, pin, package_name="mlib"):
    from playwright.sync_api import expect, sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for label, options in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}),
            ]:
                context = browser.new_context(**options)
                context.tracing.start(screenshots=True, snapshots=True, sources=True)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
                try:
                    for index, (source, destination) in enumerate(_cases(package_name)):
                        response = page.goto(urljoin(base, source), wait_until="networkidle")
                        assert response and response.ok, f"開けません: {source}"
                        check_mermaid_script(page, source, pin)
                        expect(page.locator(".mermaid svg").first).to_be_visible(timeout=30000)
                        # SVGの実リンクをクリックする。テキストソースのURL検査だけでは済ませない。
                        links = page.locator(".mermaid svg a")
                        expect(links.first).to_be_attached(timeout=30000)
                        chosen = None
                        for i in range(links.count()):
                            candidate = links.nth(i)
                            href = candidate.get_attribute("href") or candidate.get_attribute("xlink:href")
                            if href and href.endswith("#" + destination):
                                chosen = candidate
                                break
                        assert chosen is not None, f"SVGのリンクがありません: {source} -> {destination}"
                        # 空のメンバー欄を含むSVG枠の中心ではなく、ユーザーが読むクラス名を押す。
                        # 大きな全体図でも文字の位置を基準にスクロール・クリックする。
                        # (Mermaid 11 ではクラス名が .label-group 内の .nodeLabel に描かれる)
                        label_element = chosen.locator(".label-group .nodeLabel")
                        expect(label_element).to_be_visible()
                        label_element.scroll_into_view_if_needed()
                        page.screenshot(path=str(output / f"{label}-{index}.png"))
                        if chosen.get_attribute("target") == "_blank":
                            with page.expect_popup() as popup:
                                label_element.click()
                            landed = popup.value
                            landed.wait_for_load_state()
                        else:
                            label_element.click()
                            landed = page
                        expect(landed).to_have_url(re.compile(re.escape("#" + destination) + "$"))
                        expect(landed.locator('[id="' + destination + '"]')).to_be_visible()
                        if landed is not page:
                            landed.close()
                        assert not errors, errors
                        print(f"PASS {label}: {source} -> {destination}", flush=True)
                except Exception as error:
                    page.screenshot(path=str(output / f"{label}-failure.png"), full_page=True)
                    geometry = page.locator(".mermaid").evaluate_all("""elements => elements.map(el => ({
                        box: el.getBoundingClientRect().toJSON(), scrollLeft: el.scrollLeft,
                        scrollTop: el.scrollTop, width: el.clientWidth, height: el.clientHeight,
                        svg: el.querySelector('svg')?.getBoundingClientRect().toJSON()
                    }))""")
                    raise RuntimeError(f"{label} {source}: {error}\n図の配置: {geometry}") from error
                finally:
                    context.tracing.stop(path=str(output / f"{label}-trace.zip"))
                    context.close()
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--directory", type=Path)
    target.add_argument("--url")
    target.add_argument("--stamp-directory", type=Path)
    target.add_argument("--check-directory", type=Path, help="ビルドしたHTMLをブラウザなしで検査する(Mermaidの版の固定と、本体を同梱していないこと)")
    parser.add_argument("--sha", help="build-info.json にあるはずのコミット(--check-directory では使わない)")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "__tests__/_output/docs-browser")
    parser.add_argument("--package-name", default="mlib", help="対象のコアパッケージ名")
    parser.add_argument("--docs-conf", type=Path, help="対象のconf.py。省略時はパッケージ内の_docs/source/conf.pyを使用")
    args = parser.parse_args()
    if not args.check_directory and not args.sha:
        parser.error("--check-directory 以外では --sha が必要です")
    conf_path = args.docs_conf or _MLIB_ROOT.parent / args.package_name / "_docs/source/conf.py"
    pin = read_mermaid_pin(conf_path)
    if args.check_directory:
        pages = check_built_html(args.check_directory, pin, args.package_name)
        print(
            f"{pages}個のHTMLページを確認しました: Mermaidの読み込み元は {pin['src']} だけで、SRIは _docs/source/conf.py の指定と一致し、本体は同梱されていません。"
        )
        return
    if args.stamp_directory:
        stamp(args.stamp_directory, args.sha, args.package_name)
        return
    server = None
    try:
        if args.directory:
            check_built_html(args.directory, pin, args.package_name)
            handler = functools.partial(SimpleHTTPRequestHandler, directory=str(args.directory.resolve()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_port}/"
        else:
            base = args.url.rstrip("/") + "/"
        wait_for_release(base, args.sha, args.timeout)
        check_browser(base, args.output, pin, args.package_name)
        message = f"コミット{args.sha}を確認しました: 公開されたファイルと、Chromiumでのクリック8件が通りました。"
        print(message)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
                summary.write(message + "\n")
    finally:
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # CIの公開チェックにも原因を残し、ログ権限がない場合にも診断できるようにする。
        message = str(error).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=文書のブラウザ確認::{message}", flush=True)
        raise
