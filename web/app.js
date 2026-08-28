const dataRoot = "../data";
const formatArea = (v) => `${Number(v).toFixed(3)} km²`;
const noData = (text) => `<p class="empty">${text}</p>`;

function metric(label, value, detail = "") {
  return `<div class="metric"><span>${label}</span><b>${value}</b>${detail ? `<span>${detail}</span>` : ""}</div>`;
}

function drawChart(rows) {
  const target = document.querySelector("#chart");
  if (!rows.length) { target.innerHTML = noData("No reviewed observations have been published yet."); return; }
  const width = 800, height = 250, pad = {l:55, r:20, t:18, b:35};
  const values = rows.map(r => r.area), min = Math.min(...values), max = Math.max(...values), spread = max - min || 0.01;
  const x = i => pad.l + i * (width-pad.l-pad.r) / Math.max(rows.length - 1, 1);
  const y = v => height-pad.b - ((v-min)/spread)*(height-pad.t-pad.b);
  const line = rows.map((r,i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(r.area).toFixed(1)}`).join(" ");
  target.innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"><line x1="${pad.l}" y1="${height-pad.b}" x2="${width-pad.r}" y2="${height-pad.b}" stroke="#cdd7d5"/><path d="${line}" fill="none" stroke="#247d8d" stroke-width="3"/>${rows.map((r,i)=>`<circle cx="${x(i)}" cy="${y(r.area)}" r="4" fill="#247d8d"><title>${r.date}: ${formatArea(r.area)}</title></circle>`).join("")}<text x="${pad.l}" y="${height-8}" fill="#617276" font-size="11">${rows[0].date}</text><text x="${width-pad.r}" y="${height-8}" text-anchor="end" fill="#617276" font-size="11">${rows.at(-1).date}</text><text x="4" y="${pad.t+8}" fill="#617276" font-size="11">${max.toFixed(3)} km²</text><text x="4" y="${height-pad.b}" fill="#617276" font-size="11">${min.toFixed(3)} km²</text></svg>`;
}

function drawBoundary(featureCollection) {
  const target = document.querySelector("#map");
  const points = [];
  const collectPairs = (node) => {
    if (Array.isArray(node) && typeof node[0] === "number" && typeof node[1] === "number") points.push(node);
    else if (Array.isArray(node)) node.forEach(collectPairs);
  };
  featureCollection.features.forEach(f => collectPairs(f.geometry.coordinates));
  if (!points.length) { target.innerHTML = noData("Boundary geometry is unavailable."); return; }
  const xs = points.map(p=>p[0]), ys=points.map(p=>p[1]), minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(...ys), maxY=Math.max(...ys);
  const sx = x => 20 + (x-minX)/(maxX-minX || 1)*360, sy = y => 280-(y-minY)/(maxY-minY || 1)*250;
  const polygon = points.map(p=>`${sx(p[0])},${sy(p[1])}`).join(" ");
  target.innerHTML = `<svg viewBox="0 0 400 300" aria-label="Latest derived lake boundary"><rect width="400" height="300" fill="#e8efec"/><path d="M20 280H380M20 20V280" stroke="#b7c6c2"/><polygon points="${polygon}" fill="#247d8d" fill-opacity=".72" stroke="#125563" stroke-width="2"/><text x="24" y="38" fill="#617276" font-size="11">DERIVED WATER EXTENT</text></svg>`;
}

async function load() {
  const [latestResponse, csvResponse] = await Promise.all([fetch(`${dataRoot}/latest/imja-tsho.json`), fetch(`${dataRoot}/processed/imja-tsho/lake-area.csv`)]);
  if (!latestResponse.ok) throw new Error("Latest observation file could not be read.");
  const latest = await latestResponse.json();
  const rows = csvResponse.ok ? (await csvResponse.text()).trim().split("\n").slice(1).map(line => { const c=line.split(","); return {date:c[0],area:Number(c[1]),publicationStatus:c[8] || "candidate"}; }).filter(r=>r.date && Number.isFinite(r.area) && r.publicationStatus === "published") : [];
  drawChart(rows);
  const target = document.querySelector("#latest-content"), provenance = document.querySelector("#provenance");
  if (latest.status !== "valid_observation" || !latest.latest_observation) {
    target.innerHTML = noData("No reviewed satellite observation is published. This interface will not substitute an assumed value.");
    document.querySelector("#map").innerHTML = noData("No reviewed derived boundary is published.");
    provenance.innerHTML = `<dt>Publication status</dt><dd>${latest.status || "UNKNOWN"}</dd><dt>As of</dt><dd>${latest.as_of || "UNKNOWN"}</dd><dt>Note</dt><dd>${latest.message || "No record available."}</dd>`;
    return;
  }
  const obs=latest.latest_observation, previous=rows.filter(r => r.date < obs.observed_at.slice(0,10)).at(-1), yearAgo=rows.filter(r=>Math.abs(new Date(r.date)-new Date(obs.observed_at)) < 380*864e5 && Math.abs(new Date(r.date)-new Date(obs.observed_at)) > 300*864e5).at(-1);
  const delta = r => r ? `${(obs.value-r.area >= 0 ? "+" : "")}${(obs.value-r.area).toFixed(3)} km²` : "—";
  target.innerHTML = metric("AREA", formatArea(obs.value), "Derived probable-water extent") + metric("OBSERVED", new Date(obs.observed_at).toISOString().slice(0,10), obs.source) + metric("CHANGE / PREVIOUS", delta(previous), previous ? previous.date : "No prior valid observation") + metric("FRESHNESS", `<span class="fresh">${obs.freshness.status}</span>`, `${obs.freshness.age_days} days old · data age only`) + metric("CHANGE / ~1 YEAR", delta(yearAgo), yearAgo ? yearAgo.date : "No comparable annual record");
  provenance.innerHTML = `<dt>Source product</dt><dd>${obs.source_product}</dd><dt>Method</dt><dd>${obs.method} · v${obs.method_version}</dd><dt>Parameters</dt><dd>${JSON.stringify(obs.parameters)}</dd><dt>Quality flags</dt><dd>${obs.quality_flags.join(", ") || "None"}</dd><dt>Processed</dt><dd>${obs.processed_at}</dd><dt>Code revision</dt><dd>${obs.provenance.code_version}</dd>`;
  if (obs.boundary_geojson_url) { try { drawBoundary(await (await fetch(`../${obs.boundary_geojson_url}`)).json()); } catch { document.querySelector("#map").innerHTML=noData("Boundary file could not be loaded."); } }
}
load().catch(error => { document.querySelector("#latest-content").innerHTML=noData(error.message); document.querySelector("#map").innerHTML=noData("Data files unavailable; serve the repository through a web server."); });
