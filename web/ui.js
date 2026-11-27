export const el = (id) => document.getElementById(id);
export const safe = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
export const stateClass = (s) =>
  ({
    通过: "good",
    需修改: "warn",
    不合规: "bad",
    待复核: "neutral",
    冲突: "bad",
    支持: "good",
    未知: "neutral",
  })[s] || "neutral";
export const pill = (s) =>
  `<span class="pill ${stateClass(s)}">${safe(s)}</span>`;
export const groups = ["主题场景", "图内短标题", "图外长标题", "图片"];
export function overall(result) {
  return (
    ["不合规", "需修改", "待复核"].find((s) =>
      result.checks.some((c) => c.status === s),
    ) || "通过"
  );
}
export async function api(path, data) {
  const response = await fetch(
    "/api/" + path,
    data
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      : {},
  );
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "读取失败，请重试");
  return body;
}
export function dateTime(stamp) {
  const d = new Date(stamp);
  return isNaN(d) ? stamp : d.toLocaleString("zh-CN", { hour12: false });
}
let toastTimer;
export function toast(message) {
  const box = el("toast");
  box.textContent = message;
  box.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.remove("show"), 3500);
}
export function modal(title, body, wide = false) {
  const d = el("dialog");
  d.classList.toggle("wide", wide);
  el("dialogBody").innerHTML =
    `<div class="dialog-head"><h2 id="modalTitle">${safe(title)}</h2><button data-action="close" class="close" aria-label="关闭">×</button></div><div class="dialog-content">${body}</div>`;
  d.setAttribute("aria-labelledby", "modalTitle");
  if (!d.open) d.showModal();
}
export function preview(c, v, compact = false) {
  const media = c.image
    ? `<img src="${safe(c.image)}" alt="本次上传的实际渲染卡面">`
    : `<canvas data-art aria-label="示例餐品插画"></canvas><strong class="poster-title">${safe(v.short)}</strong>`;
  return `<article class="feed-card ${compact ? "compact" : ""}"><div class="poster">${media}</div><div class="feed-copy"><span class="feed-type">主题精选</span><b>${safe(v.long)}</b></div></article>`;
}
export function revisionForm(c, v) {
  return `<form id="revisionForm" class="stack"><div class="notice">复评沿用 V${v.n} 的主题、供给快照、渲染图和标准；本次修改图外长标题。</div>
  <label>原长标题<output>${safe(v.long)}</output></label>
  <label>新版展示长标题<textarea required maxlength="200" name="long" rows="2">${safe(v.long)}</textarea></label>
  <label>新版生成原稿 <small>用于判断生成和展示哪个环节引入问题</small><textarea name="draft" rows="2">${safe(v.draft)}</textarea></label>
  <p class="muted">如果新版长标题就是生成原稿，可将两项填成相同文本。供给 ${c.snapshot_missing ? "未提供" : c.snapshot.length + " 条"} · 快照 ${safe(c.snapshot_id.slice(0, 8))}</p>
  <p class="form-error" role="alert"></p><footer><button type="button" data-action="close">取消</button><button class="primary">保存并复评 →</button></footer></form>`;
}
export function newForm(sample, config) {
  return `<form id="newForm" class="stack"><div class="row split"><span class="muted">导入卡面和当时可用的套餐。</span><button type="button" data-action="fillSample">填入午餐样例</button></div>
  <div class="two"><label>主题标签<input required name="theme" placeholder="例如：工作日单人午餐"></label><label>图内短标题<input name="short" placeholder="午休一人食"></label></div>
  <label>图外长标题<input required name="long" placeholder="用户实际看到的完整长标题"></label>
  <label>实际卡面 <small>PNG、JPEG 或 WebP，最大 3 MiB；未上传时使用示意模板</small><input type="file" name="imageFile" accept="image/png,image/jpeg,image/webp"></label>
  <label>图片来源<select name="image_source"><option value="original">原始素材</option><option value="capture">展示截图（原图规格待核验）</option></select></label>
  <label>图内短标题转录 <small>上传卡面时填写，未提供则标记待复核</small><input name="transcription"></label>
  <label>评测方式<select name="mode"><option value="local">本地核验 + 人工视觉评分</option>${config.vision ? '<option value="vision">视觉模型评测（发送卡面、标题、主题、证据计数）</option>' : ""}</select></label>
  <label>供给快照 <small>导入 CSV / JSON，保留落地页顺序；未知字段留空</small><input type="file" name="supplies" accept=".csv,.json"></label>
  <label>供给 JSON <small>未取得历史快照时留空，供给相关项转为待复核</small><textarea name="snapshot" class="code" rows="5" placeholder='[{"id":"M01","name":"午餐套餐","city":"示例城","price":19,"people":1,"lunch":true,"weekday":true}]'></textarea></label>
  <label>快照时间 <small>留空采用导入时间</small><input type="datetime-local" name="snapshot_at"></label>
  <div class="two"><label>实际生成输入<textarea name="generation_input" rows="3" placeholder="例如：60 个套餐中有 42 个不超过20元"></textarea></label>
  <label>生成原稿<textarea name="draft" rows="3" placeholder="用于和展示长标题对照"></textarea></label></div>
  <p class="form-error" role="alert"></p><footer><button type="button" data-action="close">取消</button><button class="primary">开始评测 →</button></footer></form>`;
}
export function fileData(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("读取图片失败"));
    reader.readAsDataURL(file);
  });
}
export function parseCSV(text) {
  const rows = [];
  let row = [],
    field = "",
    quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c == '"') {
      if (quoted && text[i + 1] == '"') {
        field += '"';
        i++;
      } else quoted = !quoted;
    } else if (c == "," && !quoted) {
      row.push(field);
      field = "";
    } else if (c == "\n" && !quoted) {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else field += c;
  }
  if (quoted) throw new Error("CSV 引号未闭合");
  row.push(field.replace(/\r$/, ""));
  rows.push(row);
  const headers = rows.shift().map((x) => x.trim().replace(/^\uFEFF/, ""));
  const alias = {
    套餐ID: "id",
    名称: "name",
    城市: "city",
    价格: "price",
    人数: "people",
    午餐: "lunch",
    工作日: "weekday",
  };
  const keys = headers.map((h) => alias[h] || h);
  if (!keys.includes("id")) throw new Error("CSV 缺少 id 列");
  return rows
    .filter((r) => r.some(Boolean))
    .map((r) => Object.fromEntries(keys.map((key, i) => [key, r[i] ?? ""])));
}
