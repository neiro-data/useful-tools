"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const base = $("base"), overlay = $("overlay");
  const bctx = base.getContext("2d"), octx = overlay.getContext("2d");

  let file = null;
  let img = null;
  let faces = [];      // {x,y,w,h,score,selected}
  let manual = [];     // {x,y,w,h}
  let mode = "select";
  let drag = null;
  let resultBlob = null;
  let resultImg = null;
  let dirty = true;
  let detectSeq = 0;
  let busy = false;

  const setStatus = (t) => { $("status").textContent = t; };
  const banner = (t) => { $("banner").hidden = !t; $("banner").textContent = t || ""; };
  const enable = (on) => ["auto", "clear", "preview", "download"].forEach((i) => { $(i).disabled = !on; });

  async function loadFile(f) {
    if (!f) return;
    detectSeq++;
    file = f; resultBlob = null; resultImg = null; dirty = true; faces = []; manual = [];
    banner("");
    $("showOriginal").checked = false;
    const url = URL.createObjectURL(f);
    const cur = new Image();
    img = cur;
    cur.onload = async () => {
      if (img !== cur) return;
      URL.revokeObjectURL(url);
      base.width = overlay.width = img.naturalWidth;
      base.height = overlay.height = img.naturalHeight;
      $("hint").hidden = true; $("stage").hidden = false;
      renderBase(); enable(true);
      await detect();
    };
    cur.onerror = () => {
      URL.revokeObjectURL(url);
      if (img !== cur) return;
      img = null; file = null; faces = []; manual = []; resultBlob = null; resultImg = null;
      $("stage").hidden = true; $("hint").hidden = false; enable(false); setStatus("");
      banner("Could not display this image.");
    };
    cur.src = url;
  }

  function renderBase() {
    const show = (!$("showOriginal").checked && resultImg) ? resultImg : img;
    bctx.clearRect(0, 0, base.width, base.height);
    bctx.drawImage(show, 0, 0, base.width, base.height);
    drawOverlay();
  }

  async function detect() {
    setStatus("Detecting...");
    const seq = detectSeq, current = img;
    const fd = new FormData(); fd.append("image", file);
    try {
      const r = await fetch("/api/detect", { method: "POST", body: fd });
      const j = await r.json();
      if (seq !== detectSeq || img !== current) return;
      if (!r.ok) { setStatus(""); banner(j.error || "Detection failed"); return; }
      if (j.width !== img.naturalWidth || j.height !== img.naturalHeight) {
        banner(`Warning: browser shows ${img.naturalWidth}x${img.naturalHeight} but the server decoded ${j.width}x${j.height} (EXIF orientation?). Boxes may be misaligned.`);
      }
      faces = j.faces.map((f) => ({ ...f, selected: true }));
      setStatus(`${faces.length} face(s) found`);
    } catch (e) {
      if (seq !== detectSeq) return;
      setStatus(""); banner("Server unreachable.");
    }
    drawOverlay();
  }

  function drawOverlay() {
    octx.clearRect(0, 0, overlay.width, overlay.height);
    const lw = Math.max(2, overlay.width / 400);
    octx.lineWidth = lw;
    for (const f of faces) {
      octx.setLineDash(f.selected ? [] : [lw * 4, lw * 3]);
      octx.strokeStyle = f.selected ? "#e00" : "#888";
      octx.strokeRect(f.x, f.y, f.w, f.h);
    }
    octx.setLineDash([]);
    octx.strokeStyle = "#e00";
    for (const m of manual) octx.strokeRect(m.x, m.y, m.w, m.h);
    if (drag) {
      octx.setLineDash([lw * 2, lw * 2]); octx.strokeStyle = "#07f";
      octx.strokeRect(drag.x, drag.y, drag.w, drag.h);
    }
  }

  function point(ev) {
    const r = overlay.getBoundingClientRect();
    return { x: (ev.clientX - r.left) * overlay.width / overlay.clientWidth,
             y: (ev.clientY - r.top) * overlay.height / overlay.clientHeight };
  }
  const inside = (b, p) => p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h;

  overlay.addEventListener("mousedown", (ev) => {
    if (!img) return;
    const p = point(ev);
    if (mode === "select") {
      const mi = manual.findIndex((m) => inside(m, p));
      if (mi >= 0) { manual.splice(mi, 1); markDirty(); return; }
      const hits = faces.filter((f) => inside(f, p)).sort((a, b) => a.w * a.h - b.w * b.h);
      if (hits.length) { hits[0].selected = !hits[0].selected; markDirty(); }
    } else {
      drag = { sx: p.x, sy: p.y, x: p.x, y: p.y, w: 0, h: 0 };
    }
  });
  window.addEventListener("mousemove", (ev) => {
    if (!drag) return;
    const p = point(ev);
    drag.x = Math.min(drag.sx, p.x); drag.y = Math.min(drag.sy, p.y);
    drag.w = Math.abs(p.x - drag.sx); drag.h = Math.abs(p.y - drag.sy);
    drawOverlay();
  });
  window.addEventListener("mouseup", () => {
    if (!drag) return;
    const scale = overlay.width / overlay.clientWidth;
    const minSize = 4 * scale;
    if (drag.w >= minSize && drag.h >= minSize) {
      const x = Math.max(0, drag.x), y = Math.max(0, drag.y);
      const x2 = Math.min(drag.x + drag.w, overlay.width), y2 = Math.min(drag.y + drag.h, overlay.height);
      const w = Math.round(x2 - x), h = Math.round(y2 - y);
      if (w > 0 && h > 0) manual.push({ x: Math.round(x), y: Math.round(y), w, h });
      markDirty();
    }
    drag = null; drawOverlay();
  });

  function markDirty() {
    dirty = true; resultBlob = null; resultImg = null;
    $("showOriginal").checked = false;
    if (img) renderBase(); else drawOverlay();
  }

  document.querySelectorAll("input[name=mode]").forEach((r) => r.addEventListener("change", () => {
    mode = document.querySelector("input[name=mode]:checked").value;
    overlay.classList.toggle("draw", mode === "draw");
  }));
  $("auto").addEventListener("click", () => { faces.forEach((f) => { f.selected = true; }); markDirty(); });
  $("clear").addEventListener("click", () => { faces.forEach((f) => { f.selected = false; }); manual = []; markDirty(); });
  ["method", "strength", "shape", "format"].forEach((i) => $(i).addEventListener("change", () => { dirty = true; }));
  $("showOriginal").addEventListener("change", () => { if (img) renderBase(); });
  $("file").addEventListener("change", (e) => loadFile(e.target.files[0]));

  const drop = $("drop");
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault(); drop.classList.remove("over");
    if (e.dataTransfer.files.length) loadFile(e.dataTransfer.files[0]);
  });

  function setBusy(on) {
    busy = on;
    ["auto", "clear", "preview", "download"].forEach((i) => { $(i).disabled = on || !file; });
  }

  async function runBlur() {
    const regions = [
      ...faces.filter((f) => f.selected).map((f) => ({ x: f.x, y: f.y, w: f.w, h: f.h, shape: $("shape").value, source: "auto" })),
      ...manual.map((m) => ({ ...m, shape: "rect", source: "manual" })),
    ];
    const params = { regions, method: $("method").value, strength: Number($("strength").value),
                     format: $("format").value, quality: 92 };
    const fd = new FormData();
    fd.append("image", file); fd.append("params", JSON.stringify(params));
    setBusy(true); setStatus("Blurring...");
    try {
      const r = await fetch("/api/blur", { method: "POST", body: fd });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        setStatus(""); banner(j.error || "Blur failed"); return false;
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const out = new Image();
      try {
        await new Promise((res, rej) => { out.onload = res; out.onerror = () => rej(new Error("decode")); out.src = url; });
      } finally { URL.revokeObjectURL(url); }
      resultBlob = blob; resultImg = out;
      dirty = false; setStatus("Preview ready");
      return true;
    } catch (e) {
      setStatus(""); banner("Blur failed: server unreachable or result not displayable.");
      return false;
    } finally { setBusy(false); }
  }

  $("preview").addEventListener("click", async () => {
    if (!file) return;
    if (await runBlur()) { $("showOriginal").checked = false; renderBase(); }
  });

  $("download").addEventListener("click", async () => {
    if (!file) return;
    if (dirty || !resultBlob) { if (!(await runBlur())) return; renderBase(); }
    const ext = { png: "png", jpeg: "jpg", webp: "webp" }[$("format").value];
    const stem = file.name.replace(/\.[^.]+$/, "") || "image";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(resultBlob); a.download = `${stem}-blurred.${ext}`;
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
})();
