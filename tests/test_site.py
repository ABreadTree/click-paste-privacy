from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICIES = (
    (ROOT / "index.html", "en", "https://abreadtree.github.io/click-paste-privacy/"),
    (ROOT / "zh-cn" / "index.html", "zh-CN", "https://abreadtree.github.io/click-paste-privacy/zh-cn/"),
)
SUPPORT_PAGES = (
    (ROOT / "support" / "index.html", "en"),
    (ROOT / "zh-cn" / "support" / "index.html", "zh-Hans"),
)


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.start_tags = []
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        self.start_tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        value = " ".join(data.split())
        if value:
            self.text_parts.append(value)

    @property
    def text(self):
        return " ".join(self.text_parts)


def parse(path):
    parser = DocumentParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


class PrivacySiteTests(unittest.TestCase):
    def test_required_files_exist(self):
        for relative in (
            "index.html",
            "zh-cn/index.html",
            "support/index.html",
            "zh-cn/support/index.html",
            "404.html",
            "styles.css",
            "assets/click-paste-icon.png",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_policy_metadata_and_semantics(self):
        for path, language, canonical in POLICIES:
            parser = parse(path)
            html = next(attrs for tag, attrs in parser.start_tags if tag == "html")
            self.assertEqual(html.get("lang"), language)
            self.assertEqual(sum(tag == "h1" for tag, _ in parser.start_tags), 1)
            for landmark in ("header", "main", "article", "nav", "footer"):
                self.assertTrue(any(tag == landmark for tag, _ in parser.start_tags), (path, landmark))
            links = [attrs for tag, attrs in parser.start_tags if tag == "link"]
            self.assertIn(canonical, [attrs.get("href") for attrs in links if attrs.get("rel") == "canonical"])
            alternates = {
                attrs.get("hreflang"): attrs.get("href")
                for attrs in links
                if attrs.get("rel") == "alternate"
            }
            self.assertEqual(
                alternates,
                {
                    "en": "https://abreadtree.github.io/click-paste-privacy/",
                    "zh-Hans": "https://abreadtree.github.io/click-paste-privacy/zh-cn/",
                },
            )

    def test_policy_has_local_only_assets_and_no_active_content(self):
        for path, _, _ in POLICIES:
            parser = parse(path)
            tags = [tag for tag, _ in parser.start_tags]
            for forbidden in ("script", "form", "iframe", "object", "embed"):
                self.assertNotIn(forbidden, tags, (path, forbidden))
            for tag, attrs in parser.start_tags:
                if tag == "img":
                    self.assertFalse(attrs["src"].startswith(("http://", "https://")))
                if tag == "link" and attrs.get("rel") in ("stylesheet", "icon"):
                    self.assertFalse(attrs["href"].startswith(("http://", "https://")))
            source = path.read_text(encoding="utf-8")
            self.assertIn("Content-Security-Policy", source)
            self.assertIn("script-src 'none'", source)

    def test_policy_contains_required_facts_and_links(self):
        english = parse(ROOT / "index.html")
        chinese = parse(ROOT / "zh-cn" / "index.html")
        for value in ("50", "7 days", "200 MB", "1C8F.1", "GitHub Pages"):
            self.assertIn(value, english.text)
        for value in ("50", "7 天", "200 MB", "1C8F.1", "GitHub Pages"):
            self.assertIn(value, chinese.text)
        for value in ("requires a GitHub account", "governed by GitHub's policies"):
            self.assertIn(value, english.text)
        for value in ("需要登录 GitHub", "受 GitHub 的相关政策约束"):
            self.assertIn(value, chinese.text)
        for parser in (english, chinese):
            hrefs = [attrs.get("href", "") for tag, attrs in parser.start_tags if tag == "a"]
            self.assertTrue(any("/issues/new" in href for href in hrefs))
            self.assertTrue(any("github-general-privacy-statement" in href for href in hrefs))

    def test_simplified_chinese_copy_is_natural_and_omits_image_actions(self):
        chinese = parse(ROOT / "zh-cn" / "index.html")
        source = (ROOT / "zh-cn" / "index.html").read_text(encoding="utf-8")
        self.assertIn(
            "Click Paste 隐私政策，说明应用如何在 iPhone 和 iPad 本地处理剪贴板内容。",
            source,
        )
        for value in (
            "跳至正文",
            "所有处理均在本机完成。",
            "网址也会作为普通文本保存和输入。",
            "需要登录 GitHub",
            "受 GitHub 的相关政策约束",
        ):
            self.assertIn(value, chinese.text)
        for value in (
            "隐私源于本地设计",
            "类似网址的字符串",
            "处于活跃状态",
            "图片插入属于尽力而为",
            "唯一声明的必需原因 API",
            "复制图片",
            "粘贴图片",
            "插入图片",
            "图片处理",
        ):
            self.assertNotIn(value, chinese.text)
        self.assertFalse(
            any(attrs.get("id") == "images" for _, attrs in chinese.start_tags)
        )

    def test_public_pages_omit_image_insertion_copy(self):
        for path, _, *_ in POLICIES + SUPPORT_PAGES:
            source = path.read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(
                    r"image[ -]?(?:paste|insert(?:ion)?)|"
                    r"paste (?:an )?image|insert (?:an )?image|"
                    r"图片(?:粘贴|插入)|(?:粘贴|插入)图片",
                    source,
                    re.IGNORECASE,
                ),
                path,
            )

    def test_language_routes_are_reciprocal(self):
        english_hrefs = [attrs.get("href") for tag, attrs in parse(ROOT / "index.html").start_tags if tag == "a"]
        chinese_hrefs = [attrs.get("href") for tag, attrs in parse(ROOT / "zh-cn" / "index.html").start_tags if tag == "a"]
        self.assertIn("./zh-cn/", english_hrefs)
        self.assertIn("../", chinese_hrefs)

    def test_styles_cover_accessibility_and_responsiveness(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        for contract in (
            ":focus-visible",
            "prefers-color-scheme: dark",
            "prefers-reduced-motion: reduce",
            "@media (max-width:",
            "max-width: 760px",
        ):
            self.assertIn(contract, css)
        self.assertIsNone(re.search(r"@import|https?://", css))

    def test_404_links_to_both_languages(self):
        parser = parse(ROOT / "404.html")
        hrefs = [attrs.get("href") for tag, attrs in parser.start_tags if tag == "a"]
        self.assertIn("/click-paste-privacy/", hrefs)
        self.assertIn("/click-paste-privacy/zh-cn/", hrefs)

    def test_pages_workflow_is_minimal_and_main_only(self):
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        for contract in (
            "branches: [main]",
            "pages: write",
            "id-token: write",
            "actions/configure-pages@v5",
            "actions/upload-pages-artifact@v4",
            "actions/deploy-pages@v4",
            "environment:",
            "github-pages",
            "cp -R assets support zh-cn _site/",
        ):
            self.assertIn(contract, workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("workflow_dispatch:", workflow)

    def test_privacy_issue_form_warns_against_sensitive_content(self):
        issue_form = (
            ROOT / ".github" / "ISSUE_TEMPLATE" / "privacy-question.yml"
        ).read_text(encoding="utf-8")
        for contract in (
            "Privacy question",
            "Do not include clipboard contents",
            "validations:",
            "required: true",
        ):
            self.assertIn(contract, issue_form)

    def test_repository_has_nojekyll_and_documents_verification(self):
        self.assertTrue((ROOT / ".nojekyll").is_file())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest discover -s tests -v", readme)
        self.assertIn("https://abreadtree.github.io/click-paste-privacy/", readme)


if __name__ == "__main__":
    unittest.main()
