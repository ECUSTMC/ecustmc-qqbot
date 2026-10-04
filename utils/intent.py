"""默认 @ 的意图判定：这句话是「找群」还是「问学校的事」

背景：机器人原来的兜底逻辑是「@我但没命中指令 → 一律当找群关键词搜飞书群表」，
现在改成先判断意图：**是找群就找群，不是就走校园问答（乐享知识库）**。

判定用规则而不是大模型，原因：
1. 快且确定性 —— 不额外花一次大模型往返（校园问答本身就要好几秒）；
2. 可以离线自检（见 selfcheck.py），不依赖网络与凭据；
3. 判错的代价可控 —— 判成「找群」的最坏结果是搜群搜不到；
   判成「问答」的最坏结果是知识库答不上，此时还有 ``is_bare_keyword``
   兜底再退回去找群。

规则覆盖的典型说法：
* 找群：``/找群``、``有没有计算机群``、``求个新生群``、``群号多少``、
  ``怎么加群``、``拉我进群``、``QQ群``、``计算机群``、``32433群``
* 问答：``转专业怎么申请``、``宿舍几点熄灯``、``食堂好吃吗``、``军训要带什么``
"""

import re

# 「找群」信号：命中任意一条即认为是找群。
# 只保留「用户怎么说找群」的句式；不再维护「新生|迎新|交流|老乡|社团…」那种
# 长长的群名前缀表 —— 一来真实群名五花八门（"乌冬理工鼠鼠聚集地"这种），
# 前缀表根本盖不住；二来这类词由下面「整句就是一个群名」那条兜住了。
# 注意 \S 不跨越中文标点，长度也要限制，避免把长句子误判。
_GROUP_PATTERNS = (
    # 找群 / 找个群 / 找一下新生群 / 我要找计算机群
    r"找(?:个|一下|一个)?\S{0,10}?群",
    # 有没有XX群 / 有木有群 / 求个群 / 谁有群 / 推荐群 / 来个群
    r"(?:有没有|有木有|有无|求|谁有|推荐|来个|给个)\S{0,8}?群",
    # 加群 / 加个社团群 / 进群 / 入群 / 拉我进群
    r"(?:加入|加|进|入)\S{0,4}?群",
    r"拉我",
    # 群号 / 群链接 / 群二维码 / 群在哪 / 群怎么加 / 篮球群有吗
    r"群(?:号|聊|链接|二维码|在哪|怎么加|怎么进|多少|几号|有吗|有么|吗|呢)",
    # QQ群 / 企鹅群 / 微信群
    r"(?:qq|QQ|q群|企鹅|微信)\s*群",
    # 整句就是一个群名（"计算机群"/"老乡群"/"新生群"/"羽毛球群"）
    r"^[\w\u4e00-\u9fff]{1,10}群\s*[?？!！。]*$",
)

_GROUP_PATTERNS_COMPILED = tuple(re.compile(p) for p in _GROUP_PATTERNS)

# 「明确找群」信号：全量消息模式（群里每条消息都能看到）只认这几条，
# 因为自动回复要多花一次群表查询、还可能打扰群聊，必须是很确定在找群才响应。
# 与 _GROUP_PATTERNS 的区别：这里只保留「请求式」说法，
# 不含 "篮球群有吗"/"老乡群在哪"/以群名结尾的裸词组等更宽泛的形态。
_EXPLICIT_GROUP_PATTERNS = (
    r"找(?:个|一下|一个)?\S{0,10}?群",
    r"(?:有没有|有木有|有无|谁有|求|求个|来个|给个|推荐)\S{0,8}?群",
    r"(?:想|要|准备|打算)?(?:加入|加|进|入|拉(?:我)?(?:进|入))群",
    r"拉我",
    r"群(?:号|链接|二维码)",
)
_EXPLICIT_GROUP_COMPILED = tuple(re.compile(p) for p in _EXPLICIT_GROUP_PATTERNS)

# 「群号：123456」这种是在报群号，不是在找群
_PROVIDING_GROUP_ID_RE = re.compile(r"群号[:：]?\s*\d{5,}")

# 出现这些词说明是在提问/描述，不像在报群名
_QUESTION_WORDS = (
    "怎么", "怎样", "如何", "为什么", "为啥", "什么", "啥", "哪里", "哪儿",
    "多少", "几点", "几号", "哪", "吗", "呢", "请问", "介绍", "区别", "要求",
    "条件", "规定", "流程", "攻略", "咋", "能不能", "可不可以", "值得",
)

# 提取群关键词时要剥掉的语气词/动词（按长度从长到短依次剥）
# 标点不在这里列 —— 上面 _PUNCT_RE 已经把它们换成空格了
_KEYWORD_STOPWORDS = (
    "麻烦帮忙", "帮我", "帮忙", "我想", "我要", "我想要", "想找", "想加", "想进",
    "求拉", "拉我", "找一下", "找找", "找一个", "找个", "找群", "有没有", "有木有",
    "有无", "谁有", "推荐", "来个", "给个", "求个", "加个", "个", "求", "找",
    "加群", "进群", "入群", "加入", "群号", "群聊", "群链接", "群二维码",
    "一下", "一个", "qq", "QQ", "企鹅", "微信", "群", "号", "的", "是",
    "在", "和", "与", "我", "你", "有", "吗", "呢", "啊", "吧", "呀", "嘛",
)

# 标点/空白全集（用于判断「裸关键词」）
_PUNCT_RE = re.compile(r"""[\s，。！？、；：“”‘’（）()【】\[\]…~～\-—_/\\|]+""")

_ASCII_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def looks_like_group_search(text: str) -> bool:
    """这句话是不是「找群」意图"""
    if not text:
        return False
    content = _PUNCT_RE.sub(" ", str(text)).strip()
    if not content:
        return False
    return any(p.search(content) for p in _GROUP_PATTERNS_COMPILED)


def is_explicit_group_search(text: str) -> bool:
    """是不是「很明确在找群」（全量消息模式只认这个，用来省掉 AI/知识库开销）

    全量模式下机器人能看到群里每一句话，这里必须比 :func:`looks_like_group_search`
    更严格：只认 ``有没有XX群`` / ``找XX群`` / ``求个XX群`` / ``拉我进群`` / ``群号``
    这类请求式说法；``篮球群有吗``、单独一个 ``计算机群`` 之类不在此列，保持静默。
    """
    if not text:
        return False
    raw = str(text)
    if _PROVIDING_GROUP_ID_RE.search(raw):
        return False
    content = _PUNCT_RE.sub(" ", raw).strip()
    if not content or len(content) > 30:
        return False
    return any(p.search(content) for p in _EXPLICIT_GROUP_COMPILED)


def extract_group_keyword(text: str) -> str:
    """从找群的话里抽出要搜的关键词

    ``"有没有计算机群"`` → ``"计算机"``；``"/找群 原神"`` → ``"原神"``；
    抽不出内容时返回空串（调用方按「列出所有群」处理）。
    """
    if not text:
        return ""
    keyword = str(text).strip()
    # 去掉命令前缀
    keyword = re.sub(r"^[/／]\S*\s*", "", keyword)
    keyword = _PUNCT_RE.sub(" ", keyword)

    changed = True
    while changed:
        changed = False
        for word in _KEYWORD_STOPWORDS:
            if word and word in keyword:
                keyword = keyword.replace(word, " ")
                changed = True
    keyword = _PUNCT_RE.sub(" ", keyword).strip()
    keyword = re.sub(r"\s+", " ", keyword)

    # 再把疑问词剥掉（"群号多少" → ""、"老乡群在哪" → "老乡"）；
    # 剥完什么都不剩说明用户没给具体关键词
    for word in sorted(_QUESTION_WORDS, key=len, reverse=True):
        if word in keyword:
            keyword = keyword.replace(word, " ")
    keyword = re.sub(r"\s+", " ", keyword).strip()
    return keyword


def looks_like_question(text: str) -> bool:
    """像不像在问一件事（用于大模型不可用时的规则降级）

    有疑问词（怎么/多少/在哪…），或是一句超过 6 个字的话 → 按提问处理，
    交给知识库；否则（"原神""三角洲"这类短词）更像在报一个名字。
    """
    if not text:
        return False
    content = _PUNCT_RE.sub(" ", str(text)).strip()
    if not content:
        return False
    if any(word in content for word in _QUESTION_WORDS):
        return True
    return len(content.replace(" ", "")) >= 7


def is_bare_keyword(text: str) -> bool:
    """像不像「一个词」（而不是一个问题）

    用于兜底：校园问答答不上来时，如果用户只丢了一个词（``原神``、``计算机``），
    就按老规矩去群表里搜一把，而不是回一句「没找到」。
    """
    if not text:
        return False
    content = _PUNCT_RE.sub(" ", str(text)).strip()
    if not content or len(content) > 16:
        return False
    if any(word in content for word in _QUESTION_WORDS):
        return False
    # 太多空格说明是句子而不是词
    if len(content.split()) > 3:
        return False
    return bool(_ASCII_WORD_RE.search(content) or re.search(r"[\u4e00-\u9fff]", content))
