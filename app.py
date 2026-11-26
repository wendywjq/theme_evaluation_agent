"""Single-user local theme-card review workbench. Python 3.9+, no dependencies."""

import argparse
import base64
import binascii
import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import evaluator as ev
import vision
from image_info import dimensions

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("QC_DATA_DIR", ROOT / ".data"))
STATIC = {
    "ui.js": ("ui.js", "text/javascript; charset=utf-8"),
    "": ("index.html", "text/html; charset=utf-8"),
    "app.js": ("app.js", "text/javascript; charset=utf-8"),
    "style.css": ("style.css", "text/css; charset=utf-8"),
    "art.js": ("art.js", "text/javascript; charset=utf-8"),
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pack(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def connect():
    db = sqlite3.connect(DATA / "workbench.db", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def clean_text(obj, k, maximum=2500):
    value = obj.get(k, "")
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError("%s 内容格式或长度无效" % k)
    return value.strip()


def clean_card(p):
    card = {
        k: clean_text(p, k)
        for k in (
            "name",
            "theme",
            "short",
            "long",
            "generation_input",
            "draft",
            "transcription",
        )
    }
    if not card["theme"] or not card["long"]:
        raise ValueError("请填写主题和图外长标题")
    card["name"] = card["name"] or card["theme"]
    image = clean_text(p, "image", 4_300_000)
    if image:
        match = re.fullmatch(
            r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)", image
        )
        if not match:
            raise ValueError("仅支持 PNG、JPEG、WebP 图片")
        try:
            raw = base64.b64decode(match[2], validate=True)
        except (ValueError, binascii.Error) as e:
            raise ValueError("图片编码无效") from e
        fmt = match[1]
        valid = (
            (fmt == "png" and raw.startswith(b"\x89PNG\r\n\x1a\n"))
            or (fmt == "jpeg" and raw.startswith(b"\xff\xd8\xff"))
            or (fmt == "webp" and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
        )
        if not valid or len(raw) > 3 * 1024 * 1024:
            raise ValueError("图片格式不符或超过 3 MiB")
    card["image_size"] = dimensions(raw) if image else None
    card.update(
        image=image,
        visual="upload" if image else "illustration",
        snapshot=ev.validate_snapshot(p.get("snapshot")),
        snapshot_at=clean_text(p, "snapshot_at", 64) or now(),
    )
    return card


def load_case(db, ident):
    row = db.execute("SELECT body FROM cases WHERE id=?", (ident,)).fetchone()
    if not row:
        raise KeyError("找不到评测记录")
    return json.loads(row[0])


def save_case(db, case):
    latest = case["versions"][-1]
    status = ev.conclusion(latest["result"]["checks"])
    db.execute(
        """INSERT INTO cases(id,name,updated,status,body) VALUES(?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET updated=excluded.updated,status=excluded.status,body=excluded.body""",
        (case["id"], case["name"], now(), status, pack(case)),
    )


def version(case, card, number, mode="local"):
    reading = None
    if mode == "vision":
        if case["model"] != vision.settings()[1] or case.get(
            "model_source"
        ) != ev.digest(vision.settings()[0]):
            raise ValueError("模型配置已变化，无法在相同模型版本下复评")
        reading = vision.run(card)
        card["transcription"] = reading["transcription"]
    if reading:
        card["other_text"] = reading["other_text"]
    result = ev.evaluate(card)
    if reading:
        result["visual_read"] = reading
        estimates = vision.grade(card, reading, result)
        ev.apply_assessments(result, estimates)
    return dict(
        n=number,
        at=now(),
        short=card["short"],
        long=card["long"],
        draft=card["draft"],
        generation_input=card["generation_input"],
        transcription=card["transcription"],
        result=result,
        reviews=[],
    )


def build(p, ident=None):
    card = clean_card(p)
    mode = p.get("mode", "local")
    if mode not in ("local", "vision"):
        raise ValueError("评测方式无效")
    case = {
        k: card[k]
        for k in (
            "theme",
            "name",
            "image",
            "image_size",
            "visual",
            "snapshot",
            "snapshot_at",
        )
    }
    case.update(
        id=ident or uuid.uuid4().hex[:16],
        created=now(),
        snapshot_id=ev.digest(card["snapshot"]),
        rubric=ev.RUBRIC,
        engine=ev.ENGINE,
        mode=mode,
        model=vision.settings()[1] if mode == "vision" else "本地规则 + 人工复核",
        model_source=ev.digest(vision.settings()[0]) if mode == "vision" else "",
    )
    case["versions"] = [version(case, card, 1, mode)]
    return case


def init():
    DATA.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db, db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,name TEXT,updated TEXT,status TEXT,body TEXT)"
        )
        if not db.execute("SELECT id FROM cases WHERE id='sample-lunch'").fetchone():
            save_case(db, build(ev.sample(), "sample-lunch"))


def require_latest(case, p):
    latest = case["versions"][-1]
    if p.get("base") != latest["n"]:
        raise ValueError("已有更新版本，请刷新后继续")
    return latest


def revise(case, p):
    latest = require_latest(case, p)
    if case["rubric"] != ev.RUBRIC or case["engine"] != ev.ENGINE:
        raise ValueError("评测器版本不同，请用原评测器复评")
    card = {
        **case,
        **{
            k: latest[k]
            for k in ("short", "long", "generation_input", "draft", "transcription")
        },
    }
    card["long"] = clean_text(p, "long")
    card["draft"] = clean_text(p, "draft")
    if not card["long"] or card["long"] == latest["long"]:
        raise ValueError("请输入修改后的长标题")
    new = version(case, card, latest["n"] + 1, case["mode"])
    diff = ev.comparison(latest["result"], new["result"])
    new["diff"] = dict(diff, before=latest["n"], after=new["n"])
    case["versions"].append(new)


def review(case, p):
    latest = require_latest(case, p)
    check = next(
        (x for x in latest["result"]["checks"] if x["key"] == p.get("key")), None
    )
    if not check:
        raise ValueError("检查项不存在")
    note = clean_text(p, "note")
    status = p.get("status")
    if not note or status not in ("通过", "需修改", "待复核", "不合规"):
        raise ValueError("请选择结论并填写依据")
    score = p.get("score")
    minimum = 1 if check["maximum"] == 3 else 0
    if score is not None and (
        type(score) != int
        or not check["maximum"]
        or not minimum <= score <= check["maximum"]
    ):
        raise ValueError("分值超出该项量表")
    if "machine" not in check:
        check["machine"] = {k: check[k] for k in ("status", "note", "score")}
    previous = {k: check[k] for k in ("status", "note", "score")}
    check.update(status=status, note=note, score=score)
    latest["reviews"].append(
        dict(
            key=check["key"],
            previous=previous,
            status=status,
            note=note,
            score=score,
            at=now(),
        )
    )
    result = latest["result"]
    issue = next((i for i in result["issues"] if i["key"] == check["key"]), None)
    if status in ("通过", "待复核"):
        result["issues"] = [i for i in result["issues"] if i["key"] != check["key"]]
    elif issue:
        issue.update(reason=note, certainty="人工确认")
    else:
        result["issues"].append(
            dict(
                key=check["key"],
                group=check["group"],
                title=check["title"],
                reason=note,
                owner="人工复核",
                action="根据复核意见调整后复评。",
                certainty="人工确认",
            )
        )
    if len(case["versions"]) > 1:
        prev = case["versions"][-2]
        latest["diff"] = dict(
            ev.comparison(prev["result"], result), before=prev["n"], after=latest["n"]
        )


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def reply(self, data, status=200):
        self.respond(status, pack(data).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        if urlsplit("//" + self.headers.get("Host", "")).hostname not in (
            "localhost",
            "127.0.0.1",
            "::1",
        ):
            return self.reply({"error": "仅支持本机工作区"}, 403)
        path = urlsplit(self.path).path.strip("/")
        if path in STATIC:
            file, typ = STATIC[path]
            return self.respond(200, (ROOT / "web" / file).read_bytes(), typ)
        if path == "api/sample":
            return self.reply(ev.sample())
        if path == "api/config":
            return self.reply(
                dict(vision=all(vision.settings()), rubric=ev.RUBRIC, limits=ev.LIMITS)
            )
        with closing(connect()) as db:
            if path == "api/cases":
                return self.reply(
                    [
                        dict(r)
                        for r in db.execute(
                            "SELECT id,name,updated,status FROM cases ORDER BY updated DESC"
                        )
                    ]
                )
            if path.startswith("api/cases/"):
                try:
                    return self.reply(load_case(db, path.split("/")[-1]))
                except KeyError:
                    pass
        self.reply({"error": "记录或页面不存在"}, 404)

    def do_POST(self):
        host = urlsplit("//" + self.headers.get("Host", "")).hostname
        origin = self.headers.get("Origin")
        if host not in ("localhost", "127.0.0.1", "::1") or (
            origin and urlsplit(origin).netloc != self.headers.get("Host")
        ):
            return self.reply({"error": "仅接受本机同源请求"}, 403)
        try:
            size = int(self.headers.get("Content-Length", 0))
            if (
                not 0 < size < 6_000_000
                or self.headers.get_content_type() != "application/json"
            ):
                raise ValueError("需要 JSON 请求，且请求大小应小于 6 MB")
            p = json.loads(self.rfile.read(size))
            if not isinstance(p, dict):
                raise ValueError("无效的请求对象")
            path = self.path.strip("/").split("/")
            if path == ["api", "cases"]:
                case = build(p)
                with closing(connect()) as db, db:
                    save_case(db, case)
                return self.reply(case, 201)
            if (
                len(path) != 4
                or path[:2] != ["api", "cases"]
                or path[3] not in ("revise", "review")
            ):
                return self.reply({"error": "未知操作"}, 404)
            # Optimistic write prevents overlapping edits and keeps model I/O outside a DB lock.
            with closing(connect()) as db:
                case = load_case(db, path[2])
                original = pack(case)
                if path[3] == "revise":
                    revise(case, p)
                else:
                    review(case, p)
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    if original != pack(load_case(db, path[2])):
                        return self.reply({"error": "记录已更新，请刷新后重试"}, 409)
                    save_case(db, case)
            self.reply(case)
        except (ValueError, TypeError, KeyError, OverflowError) as e:
            self.reply({"error": str(e)}, 400)
        except sqlite3.Error:
            self.reply({"error": "本地数据库繁忙，请重试"}, 503)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8776)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    init()
    print("主题卡评测工作台  http://127.0.0.1:%d" % server.server_port, flush=True)
    server.serve_forever()
