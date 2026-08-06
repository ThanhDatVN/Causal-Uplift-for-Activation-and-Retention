"""Build a self-contained Sprint 2 decision dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.paths import OUTPUT_DIR


HTML = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Causal Targeting Lab — Sprint 2</title>
<style>
:root{--bg:#f4f1ea;--paper:#fffdf8;--ink:#17221d;--muted:#65716b;--line:#d9d5ca;--green:#126b51;--green2:#dcece5;--amber:#b05d22;--red:#a23c32;--navy:#273a58;--mono:"Cascadia Mono",Consolas,monospace;--sans:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;--serif:Georgia,"Times New Roman",serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.45}
.top{background:var(--ink);color:#f8f5ec;padding:20px 0;border-bottom:5px solid var(--green)}
.wrap{width:min(1180px,calc(100% - 32px));margin:auto}.toprow{display:flex;justify-content:space-between;gap:20px;align-items:end;flex-wrap:wrap}
h1{font:500 clamp(1.7rem,4vw,2.8rem)/1 var(--serif);margin:0}.kicker{font:700 .68rem var(--mono);letter-spacing:.14em;text-transform:uppercase;color:#8fd0b8;margin-bottom:8px}
.meta{font:.7rem var(--mono);color:#c5cec9;max-width:600px;text-align:right}.meta b{color:white}
.banner{margin:22px 0 18px;padding:12px 15px;background:#fff3db;border-left:4px solid var(--amber);font-size:.84rem}
.grid{display:grid;grid-template-columns:1.02fr .98fr;gap:18px}.card{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:18px;box-shadow:0 2px 8px #17221d0a}
.eyebrow{font:700 .65rem var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--green);margin-bottom:6px}
h2{font:500 1.25rem var(--serif);margin:0 0 4px}.hint{color:var(--muted);font-size:.8rem;margin:0 0 15px}
.budget{font:700 2.6rem var(--mono);color:var(--green);line-height:1}.budget small{font:500 .9rem var(--sans);color:var(--muted)}
input[type=range]{width:100%;accent-color:var(--green);margin:18px 0 8px}.ticks{display:flex;justify-content:space-between;font:.65rem var(--mono);color:var(--muted)}
.fields{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:18px;padding-top:15px;border-top:1px solid var(--line)}
label{font-size:.7rem;color:var(--muted)}input[type=number]{width:100%;margin-top:5px;border:1px solid var(--line);border-radius:7px;padding:8px;background:white;font:700 .78rem var(--mono);color:var(--ink)}
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.kpi{background:#f2f0e9;border:1px solid var(--line);border-radius:9px;padding:12px}.kpi .name{font:700 .62rem var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}.kpi .value{font:700 1.3rem var(--mono);margin-top:5px}.good{color:var(--green)}.bad{color:var(--red)}
.ci{margin-top:12px;font-size:.78rem;color:var(--muted)}.ci b{font-family:var(--mono);color:var(--ink)}.recommend{margin-top:14px;padding:12px;background:var(--green2);border-radius:9px;font-size:.84rem}
.row{display:grid;grid-template-columns:1.2fr .8fr;gap:18px;margin-top:18px}canvas{width:100%;height:auto}.legend{font:.68rem var(--mono);color:var(--muted);margin-top:8px}
.modelrow{display:grid;grid-template-columns:145px 1fr 64px;gap:9px;align-items:center;margin:11px 0;font-size:.76rem}.bar{height:14px;background:#e6e3dc;border-radius:4px;overflow:hidden}.fill{height:100%;background:var(--navy);border-radius:4px}.fill.champion{background:var(--green)}.num{text-align:right;font:700 .72rem var(--mono)}
.status{display:inline-block;padding:3px 7px;border-radius:99px;background:#eee9df;font:700 .62rem var(--mono);color:var(--amber)}
table{width:100%;border-collapse:collapse;font-size:.75rem;margin-top:10px}th,td{padding:8px 7px;border-bottom:1px solid var(--line);text-align:right;font-family:var(--mono)}th:first-child,td:first-child{text-align:left;font-family:var(--sans)}th{font-size:.6rem;text-transform:uppercase;color:var(--muted)}
details{margin:18px 0 40px;background:var(--paper);border:1px solid var(--line);border-radius:12px}summary{cursor:pointer;padding:14px 18px;font:700 .7rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--green)}.detail{padding:0 18px 18px;font-size:.8rem}.detail ul{padding-left:20px}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.btn{border:1px solid var(--green);background:transparent;color:var(--green);border-radius:7px;padding:7px 10px;font-weight:700;cursor:pointer}.btn:hover{background:var(--green);color:white}
@media(max-width:800px){.grid,.row{grid-template-columns:1fr}.fields{grid-template-columns:1fr}.meta{text-align:left}.modelrow{grid-template-columns:115px 1fr 55px}}
</style>
</head>
<body>
<header class="top"><div class="wrap toprow"><div><div class="kicker">Causal measurement · decision product</div><h1>Causal Targeting Lab</h1></div><div class="meta" id="meta"></div></div></header>
<main class="wrap">
  <div class="banner"><b>Phạm vi đúng:</b> đây là mô phỏng policy offline từ randomized experiment. “Giá trị” và “chi phí” bên dưới là input kịch bản; Criteo không có doanh thu hay margin thực tế, nên kết quả không phải actual revenue/profit.</div>
  <section class="grid">
    <div class="card">
      <div class="eyebrow">01 · Chọn ngân sách</div><h2>Nhắm top bao nhiêu khách hàng?</h2>
      <p class="hint">Score champion được chọn trên validation; confirmation chỉ dùng để báo cáo ngoài mẫu.</p>
      <div class="budget"><span id="budgetText">10</span><small>% population</small></div>
      <input id="budgetSlider" type="range" min="0" max="5" step="1" value="3">
      <div class="ticks" id="ticks"></div>
      <div class="fields">
        <label>Quy mô population<input id="audience" type="number" value="1000000" min="1"></label>
        <label>Giá trị / conversion<input id="conversionValue" type="number" value="1" min="0.000001" step="0.1"></label>
        <label>Chi phí / contact<input id="contactCost" type="number" value="0.0005" min="0" step="0.00025"></label>
      </div>
      <div class="actions"><button class="btn" data-scenario="low">Chi phí thấp</button><button class="btn" data-scenario="high">Chi phí cao</button><button class="btn" data-scenario="none">Không target</button><button class="btn" id="exportBtn">Xuất CSV kịch bản</button></div>
    </div>
    <div class="card">
      <div class="eyebrow">02 · Kết quả policy</div><div class="kpis">
        <div class="kpi"><div class="name">Khách được target</div><div class="value" id="targeted">—</div></div>
        <div class="kpi"><div class="name">Conversion tăng thêm</div><div class="value good" id="incremental">—</div></div>
        <div class="kpi"><div class="name">Chi phí kịch bản</div><div class="value" id="costKpi">—</div></div>
        <div class="kpi"><div class="name">Net value kịch bản</div><div class="value" id="netKpi">—</div></div>
      </div>
      <div class="ci">DR 95% CI cho incremental conversion: <b id="incCi">—</b></div>
      <div class="ci">Break-even contact cost / target: <b id="breakEven">—</b></div>
      <div class="recommend" id="recommend"></div>
    </div>
  </section>
  <section class="row">
    <div class="card"><div class="eyebrow">03 · Budget curve</div><h2>Incremental conversion tích lũy</h2><p class="hint" id="bootHint"></p><canvas id="curve" width="720" height="330"></canvas><div class="legend">● DR point estimate · vùng xanh: CI 95% · đường cam: net = 0 theo scenario hiện tại</div></div>
    <div class="card"><div class="eyebrow">04 · Model evidence</div><h2>Qini trên confirmation mới</h2><p class="hint">Qini đo ranking; không phải probability calibration.</p><div id="models"></div><div class="recommend" id="modelDecision"></div></div>
  </section>
  <section class="row">
    <div class="card"><div class="eyebrow">05 · Policy benchmark</div><h2>Budget 10%, cost ratio 0,0005</h2><div style="overflow:auto"><table id="policyTable"></table></div></div>
    <div class="card"><div class="eyebrow">06 · Release state</div><h2>Provenance & guardrails</h2><p><span class="status">CAUSAL FOREST PENDING</span></p><p class="hint" id="provenance"></p><div class="recommend">Không có principal stratum cá nhân quan sát được. Dashboard dùng operational top‑k policy; score âm không được gọi là “Sleeping Dog”.</div></div>
  </section>
  <details><summary>Giới hạn và cách đọc đúng</summary><div class="detail"><ul id="limitations"></ul><p><b>Formula:</b> gross incremental conversions = population × DR policy effect. Scenario net value = gross conversions × user value − targeted × user cost. Hai input value/cost phải cùng đơn vị.</p></div></details>
</main>
<script>
const DATA=__DATA__;
const curve=DATA.policy_budget_curve;
const fmt=(n,d=0)=>Number(n).toLocaleString("vi-VN",{maximumFractionDigits:d});
const compact=n=>Math.abs(n)>=1e6?(n/1e6).toFixed(2)+"M":Math.abs(n)>=1e3?(n/1e3).toFixed(1)+"K":fmt(n,3);
const meta=DATA.meta;
document.getElementById("meta").innerHTML=`<b>${meta.run_id}</b><br>${fmt(meta.confirmation_rows)} confirmation rows · ${meta.n_boot} bootstrap · ${meta.data_sha256.slice(0,12)}…`;
document.getElementById("bootHint").textContent=`Doubly robust estimate và percentile-bootstrap interval, ${meta.n_boot} resamples.`;
document.getElementById("ticks").innerHTML=curve.map(r=>`<span>${Math.round(r.budget_fraction*100)}%</span>`).join("");
const slider=document.getElementById("budgetSlider"),audience=document.getElementById("audience"),value=document.getElementById("conversionValue"),cost=document.getElementById("contactCost");
slider.max=curve.length-1;
function selected(){return curve[+slider.value]}
function render(){
 const r=selected(),A=+audience.value,V=+value.value,C=+cost.value;
 const target=A*r.target_fraction,gross=A*r.gross_incremental_conversions_per_customer_dr,lo=A*r.gross_dr_ci_low,hi=A*r.gross_dr_ci_high;
 const scenarioCost=target*C,net=gross*V-scenarioCost,ratio=C/V;
 document.getElementById("budgetText").textContent=Math.round(r.budget_fraction*100);
 document.getElementById("targeted").textContent=compact(target);
 document.getElementById("incremental").textContent=compact(gross);
 document.getElementById("costKpi").textContent=compact(scenarioCost);
 const netEl=document.getElementById("netKpi");netEl.textContent=compact(net);netEl.className="value "+(net>=0?"good":"bad");
 document.getElementById("incCi").textContent=`[${compact(lo)}; ${compact(hi)}]`;
 document.getElementById("breakEven").textContent=r.target_fraction?fmt(r.break_even_contact_cost_per_target_conversion_equivalent*V,6):"không áp dụng";
 const outside=ratio<0||ratio>.001;
 document.getElementById("recommend").innerHTML=(r.budget_fraction===0?"<b>Treat-none:</b> không có chi phí và không tạo incremental conversion.":net>=0?`<b>Scenario dương.</b> Policy top ${Math.round(r.budget_fraction*100)}% có net value ${compact(net)} đơn vị giả định.`:`<b>Scenario âm.</b> Contact cost vượt incremental value ước lượng ở budget này.`)+(outside?"<br><b>Cảnh báo:</b> cost/value ratio nằm ngoài grid sensitivity đã kiểm tra (0–0,001).":"");
 drawCurve();
}
[slider,audience,value,cost].forEach(x=>x.addEventListener("input",render));
document.querySelectorAll("[data-scenario]").forEach(b=>b.onclick=()=>{if(b.dataset.scenario==="low"){cost.value=.00025;slider.value=3}if(b.dataset.scenario==="high"){cost.value=.02;slider.value=3}if(b.dataset.scenario==="none"){slider.value=0}render()});
document.getElementById("exportBtn").onclick=()=>{
 const r=selected(),row={run_id:meta.run_id,policy:"Response top-k",budget_fraction:r.budget_fraction,target_fraction:r.target_fraction,audience:+audience.value,value_per_conversion_assumption:+value.value,contact_cost_assumption:+cost.value,gross_incremental_conversions_per_customer_dr:r.gross_incremental_conversions_per_customer_dr,monetary_outcome_available:false};
 const keys=Object.keys(row),csv=keys.join(",")+"\n"+keys.map(k=>JSON.stringify(row[k])).join(",");
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));a.download="causal_policy_scenario.csv";a.click();URL.revokeObjectURL(a.href);
};
function drawCurve(){
 const c=document.getElementById("curve"),x=c.getContext("2d"),W=c.width,H=c.height,P={l:58,r:18,t:20,b:42};x.clearRect(0,0,W,H);
 const A=+audience.value,V=+value.value,C=+cost.value;
 const vals=curve.map(r=>r.gross_incremental_conversions_per_customer_dr*A),los=curve.map(r=>r.gross_dr_ci_low*A),his=curve.map(r=>r.gross_dr_ci_high*A);
 const max=Math.max(...his,1),sx=i=>P.l+i/(curve.length-1)*(W-P.l-P.r),sy=v=>H-P.b-v/max*(H-P.t-P.b);
 x.strokeStyle="#d9d5ca";x.beginPath();x.moveTo(P.l,H-P.b);x.lineTo(W-P.r,H-P.b);x.stroke();
 x.fillStyle="#65716b";x.font="11px monospace";curve.forEach((r,i)=>x.fillText(Math.round(r.budget_fraction*100)+"%",sx(i)-10,H-17));
 x.beginPath();los.forEach((v,i)=>i?x.lineTo(sx(i),sy(v)):x.moveTo(sx(i),sy(v)));for(let i=his.length-1;i>=0;i--)x.lineTo(sx(i),sy(his[i]));x.closePath();x.fillStyle="#dcece5";x.fill();
 x.beginPath();vals.forEach((v,i)=>i?x.lineTo(sx(i),sy(v)):x.moveTo(sx(i),sy(v)));x.strokeStyle="#126b51";x.lineWidth=3;x.stroke();
 vals.forEach((v,i)=>{x.beginPath();x.arc(sx(i),sy(v),i===+slider.value?6:3,0,Math.PI*2);x.fillStyle=i===+slider.value?"#b05d22":"#126b51";x.fill()});
 const breakVals=curve.map(r=>r.target_fraction*A*C/V);x.beginPath();breakVals.forEach((v,i)=>i?x.lineTo(sx(i),sy(v)):x.moveTo(sx(i),sy(v)));x.strokeStyle="#b05d22";x.setLineDash([5,4]);x.lineWidth=1.5;x.stroke();x.setLineDash([]);
}
const models=DATA.model_comparison,maxQ=Math.max(...DATA.model_comparison.map(r=>r.qini_score));
document.getElementById("models").innerHTML=models.map(r=>`<div class="modelrow"><span>${r.model}${r.model===meta.champion?" ★":""}</span><div class="bar"><div class="fill ${r.model===meta.champion?"champion":""}" style="width:${Math.max(0,r.qini_score/maxQ*100)}%"></div></div><span class="num">${r.qini_score.toFixed(4)}</span></div>`).join("");
const d=DATA.decision;document.getElementById("modelDecision").innerHTML=`<b>Champion: ${meta.champion}.</b> X‑Renormalized − Response = ${d.x_minus_response_qini.toFixed(4)}, CI [${d.x_minus_response_ci_low.toFixed(4)}; ${d.x_minus_response_ci_high.toFixed(4)}]; chưa tách khỏi 0.`;
const policy=DATA.main_policy_comparison;document.getElementById("policyTable").innerHTML="<thead><tr><th>Policy</th><th>DR net</th><th>CI thấp</th><th>CI cao</th></tr></thead><tbody>"+policy.map(r=>`<tr><td>${r.policy}</td><td>${Number(r.dr_net_scenario_value_per_customer).toFixed(6)}</td><td>${Number(r.dr_ci_low).toFixed(6)}</td><td>${Number(r.dr_ci_high).toFixed(6)}</td></tr>`).join("")+"</tbody>";
document.getElementById("provenance").innerHTML=`Split: ${meta.split_protocol}.<br>Confirmation hash: ${meta.confirmation_index_sha256.slice(0,20)}…<br>Causal Forest: local 0,1% smoke passed; Kaggle 20%/30%/50% chưa chạy.`;
document.getElementById("limitations").innerHTML=DATA.limitations.map(x=>`<li>${x}</li>`).join("");
const preset=new URLSearchParams(location.search).get("scenario");
if(preset==="low"){cost.value=.00025;slider.value=3}
if(preset==="high"){cost.value=.02;slider.value=3}
if(preset==="none"){slider.value=0}
render();
</script>
</body></html>"""


def main():
    data_path = OUTPUT_DIR / "product" / "dashboard_data.json"
    if not data_path.exists():
        raise FileNotFoundError(
            "Thiếu output/product/dashboard_data.json; chạy scripts/export_dashboard_data.py trước."
        )
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "sprint2-dashboard-v1":
        raise ValueError("Dashboard data schema không đúng Sprint 2 release")
    output = OUTPUT_DIR / "product" / "dashboard.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False)),
        encoding="utf-8",
    )
    print(f"[write] {output} (self-contained)")


if __name__ == "__main__":
    main()
