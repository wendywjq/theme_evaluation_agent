"""Evidence-based, offline evaluation for meal-card previews."""

import hashlib
import json
import math
import re

RUBRIC = "午餐试点 / 1.0"
ENGINE = "local-evidence/1.0"
GROUPS = ("主题场景", "图内短标题", "图外长标题", "图片")
LIMITS = {"短标题": 11, "长标题": 20}
PRICE = re.compile(
    r"(?:不超(?:过)?|不高于|至多|最多|≤)\s*[¥￥]?\s*(\d+(?:\.\d+)?)\s*[元块]?|[¥￥]?\s*(\d+(?:\.\d+)?)\s*[元块]\s*(?:以内|以下|封顶|内)"
)
PEOPLE = re.compile(r"(单人|一人食|一人份|双人|两人餐)")
MEAL = re.compile(r"(午休|午市|午餐|午饭)")
WEEKDAY = re.compile(r"工作日")
KINDS = {
    "price": "价格",
    "people": "适用人数",
    "lunch": "午餐时段",
    "weekday": "工作日可用",
}
SOURCES = {
    "theme": "主题标签",
    "other": "卡面其他文字",
    "short": "图内短标题",
    "long": "图外长标题",
}


def digest(obj):
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


def claims(text):
    """Extract supported commitments, keeping original display quotes."""
    out = []
    for hit in PRICE.finditer(text):
        out.append(("price", float(hit[1] or hit[2]), hit[0]))
    for hit in PEOPLE.finditer(text):
        out.append(("people", 2 if hit[0] in ("双人", "两人餐") else 1, hit[0]))
    for kind, regex in (("lunch", MEAL), ("weekday", WEEKDAY)):
        for hit in regex.finditer(text):
            out.append((kind, True, hit[0]))
    return out


def observed(item, kind, target):
    value = item[kind]
    if value is None:
        return "未知"
    fits = value <= target if kind == "price" else value == target
    return "支持" if fits else "冲突"


def validate_snapshot(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2000:
        raise ValueError("供给表需包含 1–2000 条记录")
    clean, seen = [], set()
    for n, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError("第 %d 行应为对象" % n)
        ident = str(row.get("id") or "").strip()
        if not ident or ident in seen:
            raise ValueError("第 %d 行套餐 ID 为空或重复" % n)
        seen.add(ident)
        item = {k: str(row.get(k) or "").strip()[:200] for k in ("name", "city")}
        item["id"] = ident[:160]
        if item["id"] != ident:
            raise ValueError("套餐 ID 太长")
        for field in ("price", "people", "weekday", "lunch"):
            v = row.get(field)
            if v in ("", None):
                item[field] = None
            elif field in ("price", "people"):
                try:
                    num = float(v)
                except (TypeError, ValueError):
                    num = -1
                if (
                    isinstance(v, bool)
                    or not math.isfinite(num)
                    or num < 0
                    or (field == "people" and (not num.is_integer() or num < 1))
                ):
                    raise ValueError("第 %d 行 %s 数值无效" % (n, field))
                item[field] = num if field == "price" else int(num)
            else:
                booleans = {
                    "true": True,
                    "false": False,
                    "1": True,
                    "0": False,
                    "是": True,
                    "否": False,
                }
                if str(v).lower() not in booleans:
                    raise ValueError(
                        "第 %d 行 %s 需填写 true / false 或留空" % (n, field)
                    )
                item[field] = booleans[str(v).lower()]
        clean.append(item)
    return clean


def sample():
    dishes = [
        "菌菇鸡肉饭",
        "香煎豆腐饭",
        "照烧鸡肉饭",
        "时蔬咖喱饭",
        "番茄牛肉饭",
        "彩蔬拌饭",
    ]
    # Positions intentionally mix supporting and contradictory examples.
    rows = []
    for i in range(60):
        slot = i * 7 % 60
        rows.append(
            dict(
                id="MEAL-%03d" % (i + 1),
                name=dishes[i % 6],
                city="示例城",
                price=16 + slot % 5 if slot < 42 else 22 + slot % 6,
                people=1,
                weekday=True,
                lunch=True,
            )
        )
    return dict(
        theme="工作日单人午餐",
        short="午休一人食",
        long="20元以内，工作日午餐轻松选",
        generation_input="全量60个单人午餐，42个价格不超过20元，18个高于20元。",
        draft="20元以内，工作日午餐轻松选",
        visual="illustration",
        image="",
        transcription="",
        snapshot=rows,
        snapshot_at="",
        name="工作日单人午餐",
    )


def trace(card, source, kind, target):
    """Conservative local attribution. A free-form input alone cannot prove correctness."""
    if source == "theme":
        return (
            "主题与供给组装",
            "主题本身提出该条件，落地套餐存在反例。",
            "检查筛选条件、字段口径及快照时间。",
        )
    if source == "other":
        return (
            "渲染或素材选用",
            "承诺出现于短标题之外的卡面文字。",
            "核对原商品图及促销贴纸是否扩大整卡承诺。",
        )
    if source == "short":
        return (
            "待核对素材",
            "可见短标题提出该条件；当前没有图内标题的生成原稿。",
            "核对原始素材、排版及图片中的附加文字。",
        )
    draft = card.get("draft", "")
    if not draft:
        return (
            "待补生成原稿",
            "当前只能定位到展示长标题，缺少可比较的原稿。",
            "补充原稿，以区分生成问题与展示问题。",
        )
    if (kind, target) not in [(k, v) for k, v, _ in claims(draft)]:
        return (
            "渲染或素材选用",
            "生成原稿没有同一项承诺，实际展示的长标题引入了它。",
            "对照模板、文案绑定和最终展示版本。",
        )
    input_text = card.get("generation_input", "")
    if not input_text:
        return (
            "待补生成输入",
            "生成原稿已经包含该承诺，缺少当时的生成输入。",
            "补齐模型输入后核查摘要是否扩大适用范围。",
        )
    if kind == "price":
        limited = re.search(
            r"(\d+)\s*个(?:价格)?(?:不超过|≤)\s*(\d+(?:\.\d+)?)元", input_text
        )
        if limited and float(limited[2]) == target:
            rows = card["snapshot"]
            ok = sum(observed(x, kind, target) == "支持" for x in rows)
            if int(limited[1]) == ok and ok < len(rows):
                return (
                    "文案生成",
                    "生成输入保留了符合价格条件的数量，原稿将局部条件表述为整卡承诺。",
                    "保留适用范围，或移除覆盖不足的价格承诺。",
                )
        all_limit = re.search(
            r"(?:全部|全量|均为|均在|均不超过|全部不超过)\s*(\d+(?:\.\d+)?)元(?:以内|以下)?",
            input_text,
        )
        if all_limit and float(all_limit[1]) == target:
            return (
                "素材组装",
                "摘要已将价格条件描述为全量适用，与供给快照相冲突。",
                "在生成输入中保留支持数、总数和例外。",
            )
    return (
        "待人工归因",
        "原稿已含该承诺，现有证据不足以判定是输入摘要还是生成引入。",
        "逐项对照生成输入与原稿，再确认修改环节。",
    )


def evaluate(card):
    checks, issues = [], []
    evidence = []

    def check(key, group, title, status, note, score=None, maximum=None):
        checks.append(
            dict(
                key=key,
                group=group,
                title=title,
                status=status,
                note=note,
                score=score,
                maximum=maximum,
            )
        )

    def issue(key, group, title, reason, owner, action, certainty="有证据"):
        issues.append(
            dict(
                key=key,
                group=group,
                title=title,
                reason=reason,
                owner=owner,
                action=action,
                certainty=certainty,
            )
        )

    visible = card["transcription"] if card.get("image") else card["short"]
    shown = {"short": visible, "long": card["long"], "theme": card["theme"]}
    if card.get("other_text"):
        shown["other"] = card["other_text"]
    # Card-only read: the displayed promise list is frozen before looking at the theme or supplies.
    first_read = [
        {"source": SOURCES[src], "quote": q}
        for src in ("short", "long", "other")
        if src in shown
        for _, _, q in claims(shown[src])
    ]
    for src, text in shown.items():
        group = {"theme": "主题场景", "other": "图片"}.get(src, SOURCES[src])
        seen = set()
        for kind, target, quote in claims(text):
            if (kind, target) in seen:
                continue
            seen.add((kind, target))
            key = "%s/%s/%s" % (src, kind, target)
            if card.get("snapshot_missing"):
                check(
                    key,
                    group,
                    "「" + quote + "」供给核验",
                    "待复核",
                    "缺少当时的供给快照。",
                )
                continue
            buckets = {s: [] for s in ("支持", "冲突", "未知")}
            for row in card["snapshot"]:
                buckets[observed(row, kind, target)].append(row["id"])
            counts = {k: len(v) for k, v in buckets.items()}
            evidence.append(
                dict(
                    key=key,
                    source=SOURCES[src],
                    kind=kind,
                    label=KINDS[kind],
                    quote=quote,
                    counts=counts,
                    ids=buckets,
                )
            )
            ambiguous = any(
                w in text
                for w in (
                    "部分",
                    "低至",
                    "起价",
                    "可选",
                    "或选",
                    "并非",
                    "不含",
                    "另有",
                    "仅限部分",
                    "也有",
                    "可达",
                )
            ) or bool(re.search(r"\d+\s*(?:个|款|种).{0,8}" + re.escape(quote), text))
            status = (
                "需修改" if counts["冲突"] else "待复核" if counts["未知"] else "通过"
            )
            note = "支持 %d · 冲突 %d · 未知 %d" % (
                counts["支持"],
                counts["冲突"],
                counts["未知"],
            )
            if ambiguous:
                check(
                    key,
                    group,
                    "「" + quote + "」范围核验",
                    "待复核",
                    note + "。文本含数量或限定语，请核对承诺的适用范围。",
                )
                continue
            check(key, group, "「" + quote + "」供给核验", status, note)
            if counts["冲突"]:
                owner, reason, action = trace(card, src, kind, target)
                issue(
                    key,
                    group,
                    "「" + quote + "」与供给冲突",
                    reason,
                    owner,
                    action,
                    "待验证" if owner.startswith("待") else "有证据",
                )
        if not seen:
            check(
                src + "/scope",
                group,
                "事实覆盖",
                "待复核",
                "未提取到本地试点评测器支持的承诺。",
            )
    for src, caption in (("short", "短标题"), ("long", "长标题")):
        text = shown[src]
        if not text:
            continue
        size = len(re.sub(r"\s", "", text))
        over = size > LIMITS[caption]
        key = src + "/length"
        check(
            key,
            SOURCES[src],
            "字数底线",
            "不合规" if over else "通过",
            "%d 字，试点上限 %d 字" % (size, LIMITS[caption]),
        )
        if over:
            draft = card.get("draft", "") if src == "long" else ""
            provenance = (
                "缺少对应生成原稿，无法区分生成与展示环节。"
                if not draft
                else (
                    "生成原稿和展示长标题一致。"
                    if draft == text
                    else "生成原稿与展示文本不同，需核对展示模板。"
                )
            )
            issue(
                key,
                SOURCES[src],
                "标题超出试点字数",
                "实测 %d 字。%s" % (size, provenance),
                "标题表达" if draft else "标题表达 · 生产环节待核验",
                "压缩重复表达并重新检查卡面。",
            )
    cities = {}
    for row in card["snapshot"]:
        if row["city"]:
            cities[row["city"]] = cities.get(row["city"], 0) + 1
    few = len(card["snapshot"]) < 50 and max(cities.values(), default=0) < 20
    missing = any(not row["city"] for row in card["snapshot"])
    quantity = "待复核" if few and missing else "不合规" if few else "通过"
    check(
        "theme/volume",
        "主题场景",
        "可用供给规模",
        "待复核" if card.get("snapshot_missing") else quantity,
        "供给快照未提供，数量未知。"
        if card.get("snapshot_missing")
        else "%d 个可用套餐，已知单城最多 %d 个。"
        % (len(card["snapshot"]), max(cities.values(), default=0)),
    )
    if quantity == "不合规" and not card.get("snapshot_missing"):
        issue(
            "theme/volume",
            "主题场景",
            "供给规模不足",
            "总量不足 50 且各单城均不足 20。",
            "主题与供给组装",
            "扩充适用供给或调整主题。",
        )
    size = card.get("image_size")
    if size and card.get("image_source") == "capture":
        check(
            "image/spec",
            "图片",
            "原图尺寸",
            "待复核",
            "仅有展示截图，无法由截图像素推定原素材规格。",
        )
    elif size:
        good = size[0] == size[1] and max(size) >= 750
        check(
            "image/spec",
            "图片",
            "卡面尺寸",
            "通过" if good else "不合规",
            "%d × %d px；试点要求方图且长边至少 750 px。" % tuple(size),
        )
        if not good:
            issue(
                "image/spec",
                "图片",
                "上传卡面的尺寸不符",
                "实际素材尺寸未满足试点规格。",
                "渲染或素材选用",
                "核对导出尺寸及裁切比例。",
            )
    for group, title, maximum in [
        ("主题场景", "场景吸引力", 4),
        ("图内短标题", "表达易读性", 3),
        ("图外长标题", "文案吸引力", 4),
        ("图片", "视觉表现与吸引力", 4),
    ]:
        check(
            "manual/" + group,
            group,
            title,
            "待复核",
            "请根据实际卡面和判分依据完成人工评分。",
            maximum=maximum,
        )
    for key, group, title, maximum in [
        ("theme/fit", "主题场景", "场景与供给合理性", 4),
        ("short/fact", "图内短标题", "内容合理性", 2),
        ("short/appeal", "图内短标题", "短标题吸引力", 4),
        ("long/fact", "图外长标题", "内容合理性", 2),
        ("long/read", "图外长标题", "文案易读性", 3),
        ("image/fit", "图片", "图片与主题相关性", 4),
    ]:
        check(
            key, group, title, "待复核", "结合供给与卡面证据进行分档。", maximum=maximum
        )
    # Only theme-level requirements participate in the topic mismatch ratio.
    classified = {c["key"]: c for c in checks}
    mismatch = set()
    for e in evidence:
        if e["source"] == "主题标签" and classified[e["key"]]["status"] == "需修改":
            mismatch.update(e["ids"]["冲突"])
    fraction = len(mismatch) / len(card["snapshot"]) if card["snapshot"] else 0
    if fraction > 0.10:
        fit = classified["theme/fit"]
        fit.update(
            status="需修改",
            score=0 if fraction > 0.20 else 1,
            note="主题核心条件至少有 %d/%d 个套餐已确认错配（%.1f%%）。"
            % (len(mismatch), len(card["snapshot"]), fraction * 100),
        )
    if card.get("image") and not card["transcription"]:
        check(
            "short/transcription",
            "图内短标题",
            "卡面读字",
            "待复核",
            "上传图缺少人工转录；图内文字承诺待核验。",
        )
    return dict(first_read=first_read, evidence=evidence, checks=checks, issues=issues)


def conclusion(checks):
    for status in ("不合规", "需修改", "待复核"):
        if any(c["status"] == status for c in checks):
            return status
    return "通过"


def comparison(before, after):
    old = {i["key"]: i for i in before["issues"]}
    new = {i["key"]: i for i in after["issues"]}
    pending = {r["key"] for r in after["checks"] if r["status"] == "待复核"}
    return {
        "resolved": [v for k, v in old.items() if k not in new and k not in pending],
        "remaining": [v for k, v in new.items() if k in old],
        "added": [v for k, v in new.items() if k not in old],
        "pending": [v for k, v in old.items() if k in pending and k not in new],
    }


def apply_assessments(result, assessments):
    """Supplement subjective checks; measured evidence and bottom lines stay authoritative."""
    for check in result["checks"]:
        entry = assessments.get(check["key"])
        if not entry or not check["maximum"] or check["status"] != "待复核":
            continue
        score, reason = entry["score"], entry["reason"]
        if score is None:
            check["note"] = reason
            continue
        status = entry["status"]
        check.update(score=score, status=status, note=reason)
        if status == "需修改":
            result["issues"].append(
                dict(
                    key=check["key"],
                    group=check["group"],
                    title=check["title"],
                    reason=reason,
                    owner="待人工归因",
                    action="核对模型引用的卡面证据后，确认修改环节。",
                    certainty="模型建议",
                )
            )
