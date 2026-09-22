"""Wiki 目录分类与单页/多页拆分启发式。"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 内置业务目录（跨 KB 复用）；兜底：未分类。
BUILTIN_WIKI_FOLDERS: tuple[str, ...] = (
    "理财产品",
    "贷款产品",
    "信用卡",
    "存款业务",
    "保险产品",
    "基金投资",
    "售后服务",
    "客服话术",
    "投诉处理",
    "退换货政策",
    "物流配送",
    "商品咨询",
    "商品保养",
    "正品保障",
    "支付结算",
    "账户安全",
    "合规风控",
    "反洗钱",
    "信息披露",
    "营销活动",
    "内部制度",
    "培训教材",
    "未分类",
)

# 关键词 → 目录得分（示例，非穷举）。
_FOLDER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "理财产品": ("理财", "净值", "业绩比较基准", "产品说明书", "托管人", "理财计划", "非保本"),
    "贷款产品": ("贷款", "年利率", "额度", "抵押", "还款方式", "授信", "借款人"),
    "信用卡": ("信用卡", "分期", "账单", "信用额度", "手续费率"),
    "存款业务": ("存款", "定期", "活期", "大额存单", "利率上浮"),
    "保险产品": ("保险", "保单", "投保", "理赔", "保费", "身故"),
    "基金投资": ("基金", "申购", "赎回", "净值估值", "基金份额"),
    "售后服务": ("售后", "保修", "维修", "服务政策"),
    "客服话术": ("话术", "接待用语", "开场白", "结束语", "服务禁语"),
    "投诉处理": ("投诉", "信访", "升级处理", "安抚"),
    "退换货政策": ("退货", "换货", "七天无理由", "运费承担", "退款"),
    "物流配送": ("物流", "快递", "配送", "签收", "拒收"),
    "商品咨询": ("尺码", "规格参数", "商品咨询", "选购"),
    "商品保养": ("保养", "清洗", "存放", "养护"),
    "正品保障": ("正品", "防伪", "鉴定", "假货"),
    "支付结算": ("支付", "结算", "转账", "代扣", "清算"),
    "账户安全": ("账户安全", "密码", "盗刷", "核身", "登录异常"),
    "合规风控": ("合规", "风控", "风险评估", "内控"),
    "反洗钱": ("反洗钱", "尽职调查", "可疑交易", "身份识别"),
    "信息披露": ("信息披露", "公告", "披露频率", "报告"),
    "营销活动": ("促销", "优惠", "活动规则", "满减", "券"),
    "内部制度": ("制度", "管理办法", "操作规程", "岗位职责"),
    "培训教材": ("培训", "考核", "学习材料", "知识要点"),
}

_SECTION_RE = re.compile(
    r"(?m)^(?:#{1,3}\s+\S+|([一二三四五六七八九十百]+)、\S+|\d+[、.．]\s*\S+)",
)
_TITLE_SPLIT_HINTS = ("说明书", "协议", "手册", "合集", "指引", "须知")
# Numbered H2 products: ``## 1. 个人信用贷款`` / ``## 2、房屋抵押贷款``
_CATALOG_H2_RE = re.compile(r"(?m)^##\s+(\d+)[、.．]\s*(.+?)\s*$")
_CATALOG_SKIP_TITLES = ("概述", "简介", "前言", "目录", "常见问题", "联系方式", "附录", "总结")
# Manual chapters: ``一、风险揭示`` / ``十四、重要提示`` (line-start after optional spaces)
_CHAPTER_CN_RE = re.compile(r"(?m)^[ \t]*([一二三四五六七八九十百]+)[、．.]\s*(\S.+?)\s*$")
_CHAPTER_MD_RE = re.compile(r"(?m)^##\s+(?!\d+[、.．])(.+?)\s*$")
_CHAPTER_SKIP_TITLES = _CATALOG_SKIP_TITLES


@dataclass(frozen=True)
class CatalogItem:
    """目录型源文档中的一个编号产品/章节。"""

    slug: str
    title: str
    body: str


@dataclass(frozen=True)
class ChapterItem:
    """长文档产品手册中的一个顶层章节。"""

    slug: str
    title: str
    body: str


@dataclass(frozen=True)
class WikiLayoutDecision:
    """源文档在 Wiki 树中的落点决策。"""

    category: str
    folder: str
    default_slug: str
    split_mode: str  # single | product_bundle | catalog_bundle
    product_name: str


def _title_stem(source_title: str) -> str:
    title = (source_title or "").strip()
    if title.lower().endswith(".md"):
        title = title[:-3]
    return title.strip() or "未命名"


def extract_catalog_items(text: str) -> list[CatalogItem]:
    """从目录型文档解析 ``## 1. 产品名`` 式章节。"""
    if not text:
        return []
    matches = list(_CATALOG_H2_RE.finditer(text))
    if len(matches) < 2:
        return []
    items: list[CatalogItem] = []
    for idx, match in enumerate(matches):
        title = (match.group(2) or "").strip()
        if not title or title in _CATALOG_SKIP_TITLES:
            continue
        start = match.end()
        if idx + 1 < len(matches):
            end = matches[idx + 1].start()
        else:
            end = len(text)
            tail = text[start:end]
            non_catalog = re.search(r"(?m)^##\s+(?!\d+[、.．])", tail)
            if non_catalog:
                end = start + non_catalog.start()
        items.append(CatalogItem(slug=title, title=title, body=text[start:end].strip()))
    return items


def extract_chapter_items(text: str) -> list[ChapterItem]:
    """从长文档解析顶层章节（``一、…`` 或 Markdown ``##``）。"""
    if not text:
        return []

    cn_matches = list(_CHAPTER_CN_RE.finditer(text))
    if len(cn_matches) >= 2:
        items: list[ChapterItem] = []
        for idx, match in enumerate(cn_matches):
            title = (match.group(2) or "").strip()
            if not title or title in _CHAPTER_SKIP_TITLES:
                continue
            start = match.end()
            end = cn_matches[idx + 1].start() if idx + 1 < len(cn_matches) else len(text)
            body = text[start:end].strip()
            if len(body) < 40:
                continue
            items.append(ChapterItem(slug=title, title=title, body=body))
        if len(items) >= 2:
            return items

    md_matches = list(_CHAPTER_MD_RE.finditer(text))
    if len(md_matches) < 2:
        return []
    items = []
    for idx, match in enumerate(md_matches):
        title = (match.group(1) or "").strip()
        if not title or title in _CHAPTER_SKIP_TITLES:
            continue
        start = match.end()
        end = md_matches[idx + 1].start() if idx + 1 < len(md_matches) else len(text)
        body = text[start:end].strip()
        if len(body) < 40:
            continue
        items.append(ChapterItem(slug=title, title=title, body=body))
    return items if len(items) >= 2 else []


def classify_folder(text: str, title: str | None = None) -> str:
    """根据标题/正文关键词选择内置目录；无匹配则未分类。"""
    blob = f"{title or ''}\n{text or ''}"
    best_folder = "未分类"
    best_score = 0
    for folder, keywords in _FOLDER_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in blob)
        if score > best_score:
            best_score = score
            best_folder = folder
    if best_score <= 0:
        return "未分类"
    return best_folder


def count_major_sections(text: str) -> int:
    if not text:
        return 0
    return sum(1 for _ in _SECTION_RE.finditer(text))


def should_split_source(
    text: str,
    *,
    title: str | None = None,
    chunk_count: int = 0,
    claim_subject_count: int = 0,
    min_chars: int = 5000,
) -> bool:
    """判断是否拆成产品子目录（多 Wiki 页）。"""
    body = text or ""
    chars = len(body)
    sections = count_major_sections(body)
    title_text = title or ""
    title_hint = any(token in title_text for token in _TITLE_SPLIT_HINTS)

    # 强信号
    if chars >= min_chars:
        return True
    if sections >= 4:
        return True
    if chunk_count >= 12:
        return True
    if len(extract_catalog_items(body)) >= 2:
        return True

    # 弱信号：至少满足两条
    weak = 0
    if chars >= max(2500, min_chars // 2):
        weak += 1
    if sections >= 3:
        weak += 1
    if claim_subject_count >= 5:
        weak += 1
    if title_hint:
        weak += 1
    return weak >= 2


def resolve_wiki_layout(
    source_id: str,
    source_title: str,
    source_text: str = "",
    *,
    chunk_count: int = 0,
    claim_subject_count: int = 0,
    min_chars: int = 5000,
) -> WikiLayoutDecision:
    """解析类目/目录/slug 及是否 product_bundle 拆分。"""
    if "__" in source_id:
        folder, slug = source_id.split("__", 1)
        return WikiLayoutDecision(
            category=folder,
            folder=folder,
            default_slug=slug,
            split_mode="single",
            product_name=slug,
        )

    product = _title_stem(source_title)
    category = classify_folder(source_text, source_title)
    catalog_items = extract_catalog_items(source_text)
    split = should_split_source(
        source_text,
        title=source_title,
        chunk_count=chunk_count,
        claim_subject_count=claim_subject_count,
        min_chars=min_chars,
    )
    if len(catalog_items) >= 2 and (split or len(catalog_items) >= 3):
        bundle_folder = f"{category}/{product}"
        return WikiLayoutDecision(
            category=category,
            folder=bundle_folder,
            default_slug="_index",
            split_mode="catalog_bundle",
            product_name=product,
        )
    if split:
        bundle_folder = f"{category}/{product}"
        return WikiLayoutDecision(
            category=category,
            folder=bundle_folder,
            default_slug="_index",
            split_mode="product_bundle",
            product_name=product,
        )
    return WikiLayoutDecision(
        category=category,
        folder=category,
        default_slug=product,
        split_mode="single",
        product_name=product,
    )
