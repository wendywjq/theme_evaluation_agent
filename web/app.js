import {
  el,
  safe,
  pill,
  groups,
  overall,
  api,
  dateTime,
  toast,
  modal,
  preview,
  revisionForm,
  newForm,
  fileData,
  parseCSV,
} from "./ui.js";
import { drawMeal } from "./art.js";

let current,
  config,
  sample,
  selected = 0,
  panel = "checks",
  routeSerial = 0;
const main = el("main");
const latest = () => current.versions.at(-1);
const active = () => current.versions[selected];
const btn = (name, action, cls = "", more = "") =>
  `<button class="${cls}" data-action="${action}" ${more}>${name}</button>`;
const empty = (t) => `<div class="empty">${safe(t)}</div>`;
function paintArt() {
  document.querySelectorAll("canvas[data-art]").forEach(drawMeal);
}
function tabs(items, chosen, action) {
  return `<div class="tabs">${items.map(([key, text]) => btn(safe(text), action, key === chosen ? "on" : "", "data-key='" + safe(key) + "'")).join("")}</div>`;
}

async function route() {
  const serial = ++routeSerial;
  const path = (location.hash.slice(1) || "/").split("/").filter(Boolean);
  const section =
    path[0] === "rules" ? "rules" : path[0] === "history" ? "history" : "desk";
  document
    .querySelectorAll("nav a")
    .forEach((a) => a.classList.toggle("active", a.dataset.page === section));
  el("dialog").close();
  try {
    if (section === "history") {
      const items = await api("cases");
      if (serial !== routeSerial) return;
      main.innerHTML = `<div class="pagehead"><div><h1>评测记录</h1><p>打开历史卡片，查看原始证据与复评版本。</p></div>${btn("＋ 新建评测", "new", "primary")}</div>
      <div class="box"><div class="box-head"><h2>全部记录</h2><span class="count">${items.length}</span></div><label class="search"><input id="historyQuery" placeholder="搜索主题或评测 ID"></label><div id="historyList"></div></div>`;
      const list = () => {
        const q = el("historyQuery").value.trim().toLowerCase();
        const rows = items.filter((i) =>
          (i.name + i.id).toLowerCase().includes(q),
        );
        el("historyList").innerHTML = rows.length
          ? `<div class="scroll"><table><thead><tr><th>主题</th><th>评测 ID</th><th>最近更新</th><th>状态</th><th></th></tr></thead><tbody>${rows.map((i) => `<tr><td><b>${safe(i.name)}</b></td><td class="mono">${safe(i.id)}</td><td>${safe(dateTime(i.updated))}</td><td>${pill(i.status)}</td><td><a href="#/case/${safe(i.id)}">查看评测 →</a></td></tr>`).join("")}</tbody></table></div>`
          : empty("没有匹配记录");
      };
      list();
      el("historyQuery").oninput = list;
      return;
    }
    if (section === "rules") {
      renderRules();
      return;
    }
    const id = path[0] === "case" ? path[1] : "sample-lunch";
    const data = await api("cases/" + encodeURIComponent(id));
    if (serial !== routeSerial) return;
    current = data;
    selected = data.versions.length - 1;
    panel = "checks";
    renderDesk();
  } catch (e) {
    if (serial === routeSerial)
      main.innerHTML = `<div class="box pad"><h2>无法打开此页面</h2><p>${safe(e.message)}</p><a href="#/history">返回评测记录</a></div>`;
  }
}

function renderRules() {
  const rules = [
    [
      "供给规模",
      "底线",
      "总量不足 50 且各城市均不足 20。缺城市信息且可能影响结论时，转人工。",
    ],
    [
      "短标题 / 长标题",
      "底线",
      "本公开示例采用 11 / 20 字，按去空白字符计数。适用版本随评测保存。",
    ],
    [
      "事实承诺",
      "核验",
      "对照可用套餐的价格上限、人数、午餐时段和工作日字段，分别记录支持、冲突、未知及分母。",
    ],
    [
      "主题与素材解读",
      "图文",
      "先记录可见文案中的承诺，再与上游主题核对。可选视觉模型只读卡面及图外长标题。",
    ],
    [
      "语义与视觉质量",
      "人工",
      "主题吸引力、短标题易读性、长标题吸引力、图片相关性和呈现需依据实际卡面逐项复核。",
    ],
    [
      "结果汇总",
      "分项",
      "底线命中优先，其次是需修改和待复核。只在有评分依据时记录分值，未核验项单列。",
    ],
  ];
  main.innerHTML = `<div class="pagehead"><div><h1>评分标准</h1><p>${safe(config.rubric)} · 可执行检查与人工复核口径</p></div></div><div class="box"><div class="box-head"><h2>午餐场景</h2><span class="count">6 项</span></div>${rules.map(([name, type, body]) => `<div class="rule"><span class="tag">${type}</span><div><h3>${name}</h3><p>${body}</p></div></div>`).join("")}</div>`;
}
function metric(label, value, caption, cls = "") {
  return `<div class="metric ${cls}"><span>${label}</span><strong>${value}</strong><small>${caption}</small></div>`;
}
function renderDesk() {
  const c = current,
    v = active(),
    r = v.result,
    issues = r.issues;
  const conflict = new Set(r.evidence.flatMap((e) => e.ids["冲突"])).size;
  const manual = r.checks.filter((ch) => ch.status === "待复核").length;
  main.innerHTML = `<div class="pagehead"><div><div class="crumb">评测工作台 <span>/</span> 单卡评测</div><h1>单卡评测</h1></div>
  <div class="actions"><a class="button" href="#/history">评测记录</a>${btn("＋ 新建评测", "new", "primary")}</div></div>
  <div class="metrics">${metric("供给快照", c.snapshot_missing ? "未提供" : c.snapshot.length + " <em>个套餐</em>", "按落地页顺序核验")}${metric("冲突供给", c.snapshot_missing ? "待核验" : conflict + " <em>个套餐</em>", "合并各项承诺后去重", conflict ? "warm" : "")}
  ${metric("待修改问题", issues.length + " <em>项</em>", "含机器判定与人工改判")}${metric("待人工复核", manual + " <em>项</em>", "待补证据或主观评分")}</div>
  <div class="workspace"><aside class="box cardbox"><div class="box-head"><h2>卡面预览</h2><span class="tag">V${v.n}</span></div><div class="preview-wrap">${preview(c, v)}</div>
  <div class="metadata"><dl><dt>上游主题</dt><dd>${safe(c.theme)}</dd><dt>素材</dt><dd>${c.image ? "上传卡面" : "本地示意模板"}</dd><dt>供给快照</dt><dd class="mono">${safe(c.snapshot_id.slice(0, 10))}</dd><dt>标准版本</dt><dd>${safe(c.rubric)}</dd></dl>
  ${btn("查看输入与生产记录", "inputs", "full")}</div></aside>
  <section class="box results"><div class="result-head"><div><small>${c.id === "sample-lunch" ? "内置示例" : "主题卡"} · 评测报告</small><h2>${safe(c.name)} ${pill(overall(r))}</h2></div>
  <label class="version">版本<select aria-label="评测版本" id="version">${c.versions
    .map(
      (x, i) =>
        `<option value="${i}" ${selected === i ? "selected" : ""}>V${x.n}</option>`,
    )
    .reverse()
    .join("")}</select></label></div>
  ${tabs(
    [
      ["checks", "分项评测"],
      ["evidence", "供给证据"],
      ["issues", "问题归因 · " + issues.length],
      ["compare", "复评对比"],
    ],
    panel,
    "panel",
  )}
  <div class="panel" id="panel"></div><div class="result-footer"><small>${safe(dateTime(v.at))}</small>${selected === c.versions.length - 1 ? btn("修改长标题并复评 →", "revise", "primary") : btn("回到最新版本 →", "last")}</div></section></div>`;
  drawPanel();
  paintArt();
}
function drawPanel() {
  const v = active(),
    r = v.result,
    host = el("panel");
  if (panel === "checks") {
    host.innerHTML = `<div class="reading"><div class="line-title"><h3>用户看到的承诺</h3><span class="tag">只看卡面</span></div>
    <p>${safe(
      r.visual_read?.impression ||
        (r.first_read.length
          ? r.first_read
              .map((x) => x.quote)
              .filter((x, i, a) => a.indexOf(x) === i)
              .join(" · ")
          : "当前文案没有可自动提取的承诺"),
    )}</p>
    ${r.visual_read ? `<small>视觉观察：${safe(r.visual_read.visual_note)} · 其他文字：${safe(r.visual_read.other_text || "无")}</small>` : ""}</div>
    ${r.checks.some((x) => x.status === "不合规") ? '<p class="notice">本版命中合规底线。以下质量分用于定位问题，不计入合格卡均分。</p>' : ""}
    ${groups
      .map((group) => {
        const rows = r.checks.filter((i) => i.group === group);
        return `<details class="dimension" ${group === "图外长标题" ? "open" : ""}><summary><strong>${group}</strong><small>${rows.length} 项检查</small>${pill(overall({ checks: rows }))}</summary>
    ${rows
      .map(
        (
          ch,
        ) => `<div class="check"><div><b>${safe(ch.title)}</b> ${pill(ch.status)}<p>${safe(ch.note)}${ch.score !== null ? ` · ${ch.score}/${ch.maximum} 分` : ""}</p></div>
    <div class="row">${r.evidence.some((e) => e.key === ch.key) ? btn("证据", "evidence", "link", `data-key="${safe(ch.key)}"`) : ""}${selected === current.versions.length - 1 ? btn("复核", "review", "link", `data-key="${safe(ch.key)}"`) : ""}</div></div>`,
      )
      .join("")}</details>`;
      })
      .join("")}`;
  } else if (panel === "issues") {
    host.innerHTML = `<h3>问题归因</h3>${r.issues.length ? r.issues.map((i) => `<article class="finding"><div class="line-title"><span class="tag">${safe(i.group)}</span><small>${safe(i.certainty)}</small></div><h3>${safe(i.title)}</h3><p><b>归属环节</b>　${safe(i.owner)}</p><p>${safe(i.reason)}</p><div class="advice">${safe(i.action)}</div><div class="row">${r.evidence.some((x) => x.key === i.key) ? btn("查看冲突套餐 →", "evidence", "link", `data-key="${safe(i.key)}" data-filter="冲突"`) : ""}${btn("核对生产记录", "inputs", "link")}</div></article>`).join("") : empty("本版没有已确认的待修改问题。待复核项可在分项评测中查看。")}`;
  } else if (panel === "evidence") {
    host.innerHTML = `<div class="line-title"><h3>按承诺核验</h3><small>${current.snapshot_missing ? "缺少历史供给快照" : "全量 " + current.snapshot.length + " 个套餐"}</small></div>
    ${
      r.evidence
        .map(
          (e) =>
            `<button class="evidence-row" data-action="evidence" data-key="${safe(e.key)}"><div><small>${safe(e.source)}</small><b>${safe(e.quote)}</b></div><div>${Object.entries(
              e.counts,
            )
              .map(([k, n]) => `<span class="mini">${k} <b>${n}</b></span>`)
              .join("")} <span>›</span></div></button>`,
        )
        .join("") || empty("没有可核验的结构化承诺。")
    }`;
  } else {
    const d = v.diff;
    if (!d) {
      host.innerHTML = empty(
        "V1 是基线版本。修改长标题并复评后，在这里查看前后差异。",
      );
      return;
    }
    const old = current.versions[d.before - 1];
    host.innerHTML = `<div class="line-title"><h3>V${d.before} → V${d.after}</h3><span class="tag">同一供给快照</span></div><div class="two versions"><div><small>修改前 · V${d.before}</small><p>${safe(old.long)}</p></div><div><small>修改后 · V${d.after}</small><p>${safe(v.long)}</p></div></div>
    ${[
      ["resolved", "已解决"],
      ["remaining", "仍存在"],
      ["added", "新增问题"],
      ["pending", "待复核"],
    ]
      .map(
        ([k, label]) =>
          `<div class="diffline"><strong>${label} <span class="count">${d[k].length}</span></strong><span>${d[k].map((i) => safe(i.title)).join("、") || "—"}</span></div>`,
      )
      .join("")}
    <details class="dimension"><summary><strong>其他分项变化</strong></summary>${changes(old.result, v.result)}</details>
    <p class="muted">供给、标准、模型配置保持一致。新版的主观质量项需按新版卡面复核。</p>`;
  }
}
function changes(a, b) {
  const all = new Set([...a.checks, ...b.checks].map((c) => c.key));
  const rows = [];
  for (const key of all) {
    const x = a.checks.find((c) => c.key === key),
      y = b.checks.find((c) => c.key === key);
    if (x?.status !== y?.status || x?.score !== y?.score)
      rows.push(
        `<p>${safe((x || y).title)}　${safe(x?.status ?? "无此项")} → ${safe(y?.status ?? "无此项")}</p>`,
      );
  }
  return rows.join("") || empty("其他分项状态无变化");
}
function showEvidence(key, filter = "全部") {
  const e = active().result.evidence.find((x) => x.key === key);
  if (!e) return;
  const ids = new Set(e.ids[filter] || current.snapshot.map((x) => x.id));
  const rows = current.snapshot
    .map((x, i) => ({ ...x, position: i + 1 }))
    .filter((x) => ids.has(x.id));
  const status = new Map(
    Object.entries(e.ids).flatMap(([s, list]) => list.map((id) => [id, s])),
  );
  modal(
    "供给证据 · " + e.quote,
    `<p class="muted">${safe(e.source)} · ${safe(e.label)} · 分母 ${current.snapshot.length}</p>
  <div class="row filters">${["全部", "支持", "冲突", "未知"].map((s) => btn(s + " " + (e.counts[s] ?? current.snapshot.length), "evfilter", s === filter ? "selected" : "", "data-key='" + safe(key) + "' data-filter='" + s + "'")).join("")}</div>
  <div class="scroll evidence-table"><table><thead><tr><th>位置</th><th>套餐 / ID</th><th>城市</th><th>核验值</th><th>结论</th></tr></thead><tbody>${rows.map((i) => `<tr><td>${i.position}</td><td>${safe(i.name) || "—"}<small class="block mono">${safe(i.id)}</small></td><td>${safe(i.city) || "未知"}</td><td>${safe(fieldValue(i, e.kind))}</td><td>${pill(status.get(i.id))}</td></tr>`).join("")}</tbody></table>${rows.length ? "" : empty("此分类没有套餐")}</div>`,
    true,
  );
}
function fieldValue(row, kind) {
  const x = row[kind];
  if (x == null) return "未知";
  if (kind === "price") return "¥" + x.toFixed(2);
  if (kind === "people") return x + " 人";
  return x ? "是" : "否";
}
function inputs() {
  const c = current,
    v = active();
  modal(
    "输入与生产记录",
    `<dl class="records"><dt>主题与版本</dt><dd>${safe(c.theme)} · V${v.n}</dd><dt>生成输入</dt><dd>${safe(v.generation_input) || "未提供"}</dd>
  <dt>生成原稿</dt><dd>${safe(v.draft) || "未提供"}</dd><dt>实际展示长标题</dt><dd>${safe(v.long)}</dd><dt>图内文字</dt><dd>${safe(c.image ? v.transcription : v.short) || "未提供"}</dd>
  <dt>评测配置</dt><dd>${safe(c.rubric)} · ${safe(c.model)} · ${safe(c.engine)}</dd><dt>供给快照</dt><dd>${safe(c.snapshot_at)}<small class="block mono">${safe(c.snapshot_id)}</small></dd></dl>
  <details><summary>查看全部供给字段（${c.snapshot.length} 条）</summary><pre>${safe(JSON.stringify(c.snapshot, null, 2))}</pre></details>
  ${v.model_calls?.length ? `<details><summary>真实模型调用（${v.model_calls.length} 次）</summary><p>${safe(v.vision_rubric)}</p><pre>${safe(JSON.stringify(v.model_calls, null, 2))}</pre></details>` : ""}
  <details><summary>人工复核记录（${v.reviews.length} 条）</summary>${v.reviews.map((x) => `<p>${safe(x.key)} · ${safe(x.previous.status)} → ${safe(x.status)} · ${safe(x.note)}</p>`).join("") || empty("暂无人工改判")}</details>`,
    true,
  );
}
function showReview(key) {
  const c = active().result.checks.find((x) => x.key === key);
  if (!c) return;
  modal(
    "人工复核 · " + c.title,
    `<form id="reviewForm" class="stack"><input type="hidden" name="key" value="${safe(key)}"><div class="notice">原判：${safe((c.machine || c).status)} · ${safe((c.machine || c).note)}</div>
  <label>复核结论<select name="status">${["通过", "需修改", "待复核", "不合规"].map((s) => `<option ${c.status === s ? "selected" : ""}>${s}</option>`).join("")}</select></label>
  ${c.maximum ? `<label>分数（0–${c.maximum}）<input type="number" name="score" min="0" max="${c.maximum}" value="${c.score ?? ""}"></label>` : ""}<label>复核依据<textarea name="note" required rows="3"></textarea></label>
  <p class="form-error" role="alert"></p><footer><button type="button" data-action="close">取消</button><button class="primary">保存复核</button></footer></form>`,
  );
}

document.addEventListener("click", (e) => {
  const button = e.target.closest("[data-action]");
  if (!button) return;
  const { action, key, filter } = button.dataset;
  switch (action) {
    case "new":
      modal("新建单卡评测", newForm(sample, config), true);
      break;
    case "close":
      el("dialog").close();
      break;
    case "inputs":
      inputs();
      break;
    case "evidence":
    case "evfilter":
      showEvidence(key, filter);
      break;
    case "review":
      showReview(key);
      break;
    case "revise":
      modal("修改长标题并复评", revisionForm(current, active()));
      break;
    case "last":
      selected = current.versions.length - 1;
      renderDesk();
      break;
    case "panel":
      panel = key;
      renderDesk();
      break;
    case "fillSample": {
      const f = el("newForm");
      for (const k of ["theme", "short", "long", "generation_input", "draft"])
        f.elements[k].value = sample[k];
      f.elements.snapshot.value = JSON.stringify(sample.snapshot, null, 2);
      break;
    }
  }
});
document.addEventListener("change", async (e) => {
  if (e.target.id === "version") {
    selected = Number(e.target.value);
    renderDesk();
  }
  if (e.target.name === "supplies" && e.target.files[0]) {
    const file = e.target.files[0],
      f = el("newForm");
    try {
      if (file.size > 2_500_000) throw new Error("供给文件超过 2.5 MB");
      const raw = (await file.text()).replace(/^\uFEFF/, "");
      const rows = file.name.toLowerCase().endsWith(".json")
        ? JSON.parse(raw)
        : parseCSV(raw);
      if (!Array.isArray(rows)) throw new Error("供给表需要数组");
      f.elements.snapshot.value = JSON.stringify(rows, null, 2);
      f.querySelector(".form-error").textContent = "";
    } catch (err) {
      f.querySelector(".form-error").textContent = err.message;
    }
  }
});
document.addEventListener("submit", async (e) => {
  const f = e.target;
  if (!["newForm", "reviewForm", "revisionForm"].includes(f.id)) return;
  e.preventDefault();
  const button = f.querySelector("button.primary");
  if (button.disabled) return;
  button.disabled = true;
  const fields = Object.fromEntries(new FormData(f));
  f.querySelector(".form-error").textContent = "";
  try {
    if (f.id === "newForm") {
      const file = f.elements.imageFile.files[0];
      if (file?.size > 3 * 1024 * 1024) throw new Error("卡面图片需小于 3 MiB");
      const data = {
        ...fields,
        image: file ? await fileData(file) : "",
        snapshot: fields.snapshot.trim() ? JSON.parse(fields.snapshot) : [],
        snapshot_missing: !fields.snapshot.trim(),
      };
      delete data.imageFile;
      delete data.supplies;
      current = await api("cases", data);
      el("dialog").close();
      location.hash = "/case/" + current.id;
    } else {
      const revision = f.id === "revisionForm";
      const data = { ...fields, base: active().n };
      if (!revision) data.score = fields.score ? Number(fields.score) : null;
      current = await api(
        "cases/" + current.id + "/" + (revision ? "revise" : "review"),
        data,
      );
      selected = current.versions.length - 1;
      panel = revision ? "compare" : "checks";
      el("dialog").close();
      renderDesk();
      toast(revision ? "新版已保存，复评完成" : "已记录人工复核");
    }
  } catch (err) {
    f.querySelector(".form-error").textContent = err.message;
  } finally {
    button.disabled = false;
  }
});
try {
  [config, sample] = await Promise.all([api("config"), api("sample")]);
  window.addEventListener("hashchange", route);
  await route();
} catch (e) {
  main.textContent = "无法连接本地服务：" + e.message;
}
