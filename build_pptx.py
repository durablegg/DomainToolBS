# -*- coding: utf-8 -*-
"""生成 DomainToolBS 产品介绍单页 PPT（16:9）。"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---- 颜色 ----
NAVY      = RGBColor(0x1E, 0x27, 0x61)   # 主色 深海军蓝
NAVY_DK   = RGBColor(0x16, 0x21, 0x3E)   # 深蓝（左侧栏）
ICE       = RGBColor(0xCA, 0xDC, 0xFC)   # 冰蓝
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
PANEL_TX  = RGBColor(0xE8, 0xEC, 0xF7)   # 左侧栏文字
CARD_TX   = RGBColor(0x3A, 0x43, 0x58)   # 卡片正文
BG        = RGBColor(0xF4, 0xF6, 0xFB)   # 浅底
C_SEC     = RGBColor(0x0E, 0x7C, 0x86)   # 安全 青
C_CMP     = RGBColor(0x25, 0x63, 0xA8)   # 合规 蓝
C_AUD     = RGBColor(0x7A, 0x3F, 0xA0)   # 审计 紫
C_COST    = RGBColor(0x2E, 0x8B, 0x57)   # 降本 绿
FONT      = "微软雅黑"

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = BG


# ---- 工具函数 ----
def add_shadow(shape):
    sh = shape.shadow
    sh.inherit = False
    sh.type = 2  # outer
    sh.blur = Pt(7)
    sh.offset = Pt(3)
    sh.angle = 135
    sh.color = RGBColor(0x00, 0x00, 0x00)
    sh.alpha = 0.18  # 18%


def rect(x, y, w, h, fill, line=None, rounded=False, radius=0.08):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    if rounded:
        shp.adjustments[0] = radius
    shp.shadow.inherit = False
    return shp


def txt(x, y, w, h, text, size, color, bold=False, align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.TOP, font=FONT, margin=0.05):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(margin * 72)
    tf.margin_right = Pt(margin * 72)
    tf.margin_top = Pt(margin * 72)
    tf.margin_bottom = Pt(margin * 72)
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = font
    r.font.color.rgb = color
    return tb


def set_bullet(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    for tag in ('a:buNone', 'a:buChar', 'a:buAutoNum'):
        e = pPr.find(qn(tag))
        if e is not None:
            pPr.remove(e)
    buFont = pPr.makeelement(qn('a:buFont'), {'typeface': 'Arial'})
    buChar = pPr.makeelement(qn('a:buChar'), {'char': '•'})
    pPr.append(buFont)
    pPr.append(buChar)


def bullets(x, y, w, h, items, size, color, gap=6, font=FONT, left_indent=0.18):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = it
        p.level = 0
        p.space_after = Pt(gap)
        pPr = p._p.get_or_add_pPr()
        pPr.set('marL', str(Emu(Inches(left_indent)).emu))
        pPr.set('indent', str(-Emu(Inches(left_indent)).emu))
        set_bullet(p)
        r = p.runs[0]
        r.font.size = Pt(size)
        r.font.name = font
        r.font.color.rgb = color
    return tb


def icon_circle(x, y, d, fill, char, char_color=WHITE, size=26):
    el = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    el.fill.solid()
    el.fill.fore_color.rgb = fill
    el.line.fill.background()
    el.shadow.inherit = False
    tf = el.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    r = p.add_run()
    r.text = char
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.name = FONT
    r.font.color.rgb = char_color
    return el


# ============ 顶部标题带 ============
rect(0, 0, 13.333, 1.12, NAVY)
txt(0.5, 0.16, 12.3, 0.55, "DomainToolBS 企业域控集中管理平台",
    size=30, color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
txt(0.5, 0.70, 12.3, 0.34, "从分散运维到统一管控  ——  安全 · 合规 · 审计 · 降本",
    size=14, color=ICE, anchor=MSO_ANCHOR.MIDDLE)

# ============ 左侧「现状痛点」栏 ============
LV_X, LV_Y, LV_W, LV_H = 0.4, 1.35, 3.6, 5.8
rect(LV_X, LV_Y, LV_W, LV_H, NAVY_DK, rounded=True, radius=0.10)
txt(LV_X, LV_Y + 0.18, LV_W, 0.5, "现状痛点", size=19, color=WHITE,
    bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
# 分隔细条
rect(LV_X + 0.9, LV_Y + 0.74, LV_W - 1.8, 0.04, C_SEC)

pain = [
    "各分公司 IT 各自为政，标准不统一",
    "直接 RDP 登录 Windows Server 操作域控",
    "域管凭据分散、长期有效、难回收",
    "操作无审计留痕，误删 / 越权难追溯",
    "重复劳动，人力成本高",
]
bullets(LV_X + 0.28, LV_Y + 0.95, LV_W - 0.55, 3.7, pain,
        size=12, color=PANEL_TX, gap=8, left_indent=0.16)

# 底部转化语
rect(LV_X + 0.25, LV_Y + LV_H - 0.78, LV_W - 0.5, 0.58, C_COST, rounded=True, radius=0.10)
txt(LV_X + 0.25, LV_Y + LV_H - 0.78, LV_W - 0.5, 0.58,
    "→ 平台统一纳管，化「分散」为「可控」",
    size=12, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# 产品首页截图（左侧栏中部留白区）
SHOT = (r"C:\Users\epro\AppData\Local\CodeBuddyExtension\Data\20dd4a94-c1bf-4f70-87eb-a38ff7bca2cd"
        r"\JetBrains\20dd4a94-c1bf-4f70-87eb-a38ff7bca2cd\history\a039cd4322404462b41d3029e5e87011"
        r"\2a69cf2d693a42ce812aabb2b85e3de4\assets\首页.6757ad7701.png")
SHOT_W = 2.9
SHOT_H = SHOT_W * 396 / 1080          # ≈1.06
SHOT_X = LV_X + 0.35
SHOT_Y = 4.60
# 白色相框
rect(SHOT_X - 0.06, SHOT_Y - 0.06, SHOT_W + 0.12, SHOT_H + 0.12, WHITE,
     rounded=False)
slide.shapes.add_picture(SHOT, Inches(SHOT_X), Inches(SHOT_Y),
                         Inches(SHOT_W), Inches(SHOT_H))
txt(SHOT_X - 0.06, SHOT_Y + SHOT_H + 0.10, SHOT_W + 0.12, 0.26,
    "平台首页 · 多域概览与快捷入口",
    size=10, color=ICE, align=PP_ALIGN.CENTER)

# ============ 右侧 2x2 优势卡片 ============
RX0, RY0 = 4.2, 1.35
GAP = 0.35
RW = (12.933 - RX0 - GAP) / 2      # 卡片宽
RH = (7.15 - RY0 - GAP) / 2        # 卡片高

cards = [
    ("安", C_SEC, "安全 · Security", [
        "凭据分离：登录与域连接双重加密",
        "四角色最小权限 + 域 / OU 范围化授权",
        "强制 LDAPS+CA 加密；密码防重用",
    ]),
    ("规", C_CMP, "合规 · Compliance", [
        "集中统一管控，替代分散运维",
        "域账号仅委派所需权限（禁用域管）",
        "CA 双通道可信；多域统一策略基线",
    ]),
    ("审", C_AUD, "审计 · Audit", [
        "全量审计：用户 / 组 / 计算机 / OU / 批量",
        "记录操作者·对象·时间·结果·错误",
        "审计员独立职责分离，可检索导出",
    ]),
    ("降", C_COST, "降本 · Cost", [
        "Web 控制台免逐台 RDP 登录",
        "批量 CSV 增 / 删 / 改用户与计算机",
        "多域一键切换；自动证书巡检降本",
        "对接 WorkBuddy 等智能体自动降本增效",
    ]),
]

for idx, (ch, col, title, items) in enumerate(cards):
    col_i = idx % 2
    row_i = idx // 2
    cx = RX0 + col_i * (RW + GAP)
    cy = RY0 + row_i * (RH + GAP)
    rect(cx, cy, RW, RH, WHITE, line=RGBColor(0xD9, 0xE0, 0xEC),
         rounded=True, radius=0.09)
    add_shadow(slide.shapes[-1])
    # 图标圆
    icon_circle(cx + 0.28, cy + 0.26, 0.78, col, ch, WHITE, 26)
    # 标题
    txt(cx + 1.22, cy + 0.26, RW - 1.4, 0.78, title,
        size=17, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    # 要点
    bullets(cx + 0.32, cy + 1.18, RW - 0.6, RH - 1.35, items,
            size=11.5, color=CARD_TX, gap=7, left_indent=0.16)

out = r"d:/PycharmProjects/DomainToolBS/DomainToolBS_产品介绍.pptx"
prs.save(out)
print("saved:", out)
