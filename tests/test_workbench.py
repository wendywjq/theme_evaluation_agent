import copy
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app
import evaluator as ev
import vision


class ReviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.card = ev.sample()

    def test_evidence_is_from_ordered_snapshot(self):
        c = app.build(self.card)
        v = c["versions"][0]["result"]
        e = next(x for x in v["evidence"] if x["key"].startswith("long/price"))
        self.assertEqual(e["counts"], {"支持": 42, "冲突": 18, "未知": 0})
        by_id = {row["id"]: row for row in c["snapshot"]}
        self.assertTrue(all(by_id[i]["price"] > 20 for i in e["ids"]["冲突"]))
        self.assertEqual(v["issues"][0]["owner"], "文案生成")
        self.assertTrue(all(x["source"] != "主题标签" for x in v["first_read"]))

    def test_revision_is_paired_and_preserves_prior_evidence(self):
        c = app.build(self.card)
        old = copy.deepcopy(c["versions"][0])
        snapshot = c["snapshot_id"]
        app.revise(
            c,
            dict(
                base=1,
                long="工作日午餐，单人套餐随心选",
                draft="工作日午餐，单人套餐随心选",
            ),
        )
        self.assertEqual(c["versions"][0], old)
        diff = c["versions"][-1]["diff"]
        self.assertEqual(
            (len(diff["resolved"]), len(diff["added"]), len(diff["remaining"])),
            (1, 0, 0),
        )
        self.assertEqual(c["snapshot_id"], snapshot)
        self.assertEqual(ev.conclusion(c["versions"][-1]["result"]["checks"]), "待复核")
        with self.assertRaisesRegex(ValueError, "已有更新"):
            app.revise(c, dict(base=1, long="第三稿", draft=""))
        with self.assertRaisesRegex(ValueError, "修改后的"):
            app.revise(c, dict(base=2, long="工作日午餐，单人套餐随心选", draft=""))

    def test_revision_can_keep_and_add_problems(self):
        c = app.build(self.card)
        app.revise(
            c, dict(base=1, long="20元以内的双人午餐", draft="20元以内的双人午餐")
        )
        diff = c["versions"][-1]["diff"]
        self.assertEqual((len(diff["remaining"]), len(diff["added"])), (1, 1))

    def test_pending_is_distinct_from_resolved(self):
        c = app.build(self.card)
        app.revise(c, dict(base=1, long="部分套餐20元以内", draft="部分套餐20元以内"))
        diff = c["versions"][-1]["diff"]
        self.assertEqual((len(diff["resolved"]), len(diff["pending"])), (0, 1))

    def test_trace_follows_observed_stage(self):
        for orig, inputs, expected in [
            ("", "", "待补生成原稿"),
            ("单人午餐", "摘要", "渲染或素材选用"),
            ("20元以内", "", "待补生成输入"),
            ("20元以内", "全部20元以内", "素材组装"),
            ("20元以内", "未结构化素材", "待人工归因"),
        ]:
            with self.subTest(expected=expected):
                c = {**self.card, "draft": orig, "generation_input": inputs}
                self.assertEqual(ev.evaluate(c)["issues"][0]["owner"], expected)
        self.card["theme"] = "20元以内的单人套餐"
        self.assertIn(
            "主题与供给组装", [x["owner"] for x in ev.evaluate(self.card)["issues"]]
        )

    def test_unknown_facts_and_quantity_boundaries(self):
        for r in self.card["snapshot"]:
            r["price"] = None
        self.card["snapshot"] = self.card["snapshot"][:20]
        result = ev.evaluate(self.card)
        checks = {r["key"]: r for r in result["checks"]}
        self.assertEqual(checks["long/price/20.0"]["status"], "待复核")
        self.assertEqual(checks["theme/volume"]["status"], "通过")
        self.card["snapshot"].pop()
        check = lambda: next(
            x for x in ev.evaluate(self.card)["checks"] if x["key"] == "theme/volume"
        )
        self.assertEqual(check()["status"], "不合规")
        self.card["snapshot"][0]["city"] = ""
        self.assertEqual(check()["status"], "待复核")

    def test_theme_mismatch_uses_theme_only_and_strict_boundaries(self):
        for count, expected in [(6, None), (7, 1), (12, 1), (13, 0)]:
            with self.subTest(count=count):
                card = ev.sample()
                for i, item in enumerate(card["snapshot"]):
                    item["people"] = 2 if i < count else 1
                row = next(
                    c for c in ev.evaluate(card)["checks"] if c["key"] == "theme/fit"
                )
                self.assertEqual(row["score"], expected)

    def test_snapshot_validation(self):
        row = {"id": "id", "price": "0", "weekday": "否", "people": "1", "lunch": ""}
        clean = ev.validate_snapshot([row])[0]
        self.assertEqual(
            (clean["price"], clean["weekday"], clean["people"], clean["lunch"]),
            (0, False, 1, None),
        )
        for data in (
            [],
            [row, row],
            [{**row, "price": "NaN"}],
            [{**row, "people": "1.5"}],
            [{**row, "weekday": "unknown"}],
        ):
            with self.assertRaises(ValueError):
                ev.validate_snapshot(data)

    def test_manual_review_preserves_machine_result_and_writes_audit(self):
        c = app.build(self.card)
        app.review(
            c,
            dict(
                base=1,
                key="long/price/20.0",
                status="通过",
                note="人工核对限定条件",
                score=None,
            ),
        )
        latest = c["versions"][0]
        check = next(
            x for x in latest["result"]["checks"] if x["key"] == "long/price/20.0"
        )
        self.assertEqual(check["machine"]["status"], "需修改")
        self.assertEqual(latest["reviews"][0]["previous"]["status"], "需修改")
        self.assertEqual(latest["result"]["issues"], [])
        with self.assertRaises(ValueError):
            app.review(
                c,
                dict(base=1, key="long/read", status="通过", note="超出量表", score=4),
            )

    def test_storage_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "DATA", Path(tmp)):
            app.init()
            with closing(app.connect()) as db, db:
                c = app.load_case(db, "sample-lunch")
                app.revise(c, dict(base=1, long="单人午餐", draft="单人午餐"))
                app.save_case(db, c)
            app.init()
            with closing(app.connect()) as db:
                saved = app.load_case(db, "sample-lunch")
            self.assertEqual(saved["versions"][1]["n"], 2)
            self.assertEqual(len(saved["versions"][0]["result"]["issues"]), 1)

    def test_visual_adapter_is_blind_then_grounded(self):
        png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j3QAAAABJRU5ErkJggg=="
        self.card.update(image=png, mode="vision", theme="隐藏主题Tag")
        reqs = []

        def mock_request(instruction, content):
            reqs.append(content)
            if len(reqs) == 1:
                return {
                    "transcription": "午休一人食",
                    "other_text": "双人餐",
                    "impression": "午餐",
                    "visual_note": "文字清楚",
                }
            return {
                "long/read": {"score": 3, "reason": "语序通顺", "status": "通过"},
                "image/fit": {"score": 200, "reason": "越界", "status": "通过"},
            }

        with (
            patch.object(
                vision,
                "settings",
                return_value=("https://example.invalid/chat", "example"),
            ),
            patch.object(vision, "request", side_effect=mock_request),
        ):
            c = app.build(self.card)
        self.assertNotIn("隐藏主题Tag", json.dumps(reqs[0], ensure_ascii=False))
        self.assertIn("隐藏主题Tag", json.dumps(reqs[1], ensure_ascii=False))
        r = c["versions"][0]["result"]
        self.assertTrue(any(e["source"] == "卡面其他文字" for e in r["evidence"]))
        checks = {x["key"]: x for x in r["checks"]}
        self.assertEqual(checks["long/read"]["score"], 3)
        self.assertEqual(checks["image/fit"]["status"], "待复核")
        self.assertEqual(checks["image/spec"]["status"], "不合规")


if __name__ == "__main__":
    unittest.main()
