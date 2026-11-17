import {heading} from '../components/common/header.js';import {table} from '../components/common/table.js';import {esc,fmt,time} from '../utils/format.js';import {GREEN_STATUSES} from '../constants/green.js';
const gstatus=s=>'<span class="status '+esc(s)+'">'+esc(GREEN_STATUSES[s]||s)+'</span>';
export function green(c,d){
 const g=d.green;
 const certRows=g.certificates.map(x=>({编号:x.id,凭证号:x.code,适用月份:x.month,部门:x.department,
  排放因子:x.factor+' kgCO₂e/kWh',登记电量:x.kwh_total,可用余额:x.kwh_remaining,登记时间:time(x.created)}));
 const reportRows=g.reports.map(x=>({编号:x.id,名称:x.name,月份:x.month,部门:x.department,用电量:x.kwh+' kWh',
  电网因子:x.grid_factor,轮次:x.attempt,状态:GREEN_STATUSES[x.status]||x.status,
  预占:(x.reservations||[]).map(r=>'凭证'+r.certificate_id+'×'+r.kwh+'kWh').join('；')||'—',
  结果:x.result?('覆盖'+x.result.covered_kwh+'/'+(x.result.covered_kwh+x.result.uncovered_kwh)+'kWh，排放'+fmt(x.result.emissions_total_kg)):'—'}));
 const ledgerRows=g.ledger.map(x=>({时间:time(x.created),凭证:x.certificate_id,报告:x.report_id??'—',
  动作:x.action,变动kWh:x.kwh_delta,变动后余额:x.balance_after,轮次:x.attempt}));
 return heading('GREEN POWER DESK / 07','限额绿电凭证用电核算','登记电量、排放因子、适用月份与部门；各报告共用余额，先最大化覆盖电量再最小化排放。排队即冻结底稿/因子/分配并预占额度，成功核销、失败或取消释放。')
 +`<div class="conservation ${g.conservation.ok?'ok':'bad'}">额度守恒核对：${g.conservation.ok?'通过（登记额 = 可用余额 + 在途预占 + 已核销）':'异常凭证 '+esc((g.conservation.problem_certificate_ids||[]).join(','))}</div>`
 +`<details open><summary>登记绿电凭证</summary><form id="cert-form" class="form-grid">
  <label>凭证编号<input name="code" placeholder="GC-2026-11-001" required></label>
  <label>适用月份（YYYY-MM）<input name="month" value="2026-11" pattern="\\d{4}-\\d{2}" required></label>
  <label>适用部门<input name="department" value="材料试验室" required></label>
  <label>排放因子 kgCO₂e/kWh<input name="factor" type="number" step="any" min="0" value="0.05" required></label>
  <label>凭证电量 kWh（整数）<input name="kwh_total" type="number" step="1" min="1" value="100" required></label>
  <button>登记凭证</button></form></details>`
 +`<details open><summary>登记用电报告并发起核算</summary><form id="green-report-form" class="form-grid">
  <label>报告名称<input name="name" value="十一月绿电核算" required></label>
  <label>用电月份（YYYY-MM）<input name="month" value="2026-11" pattern="\\d{4}-\\d{2}" required></label>
  <label>用电部门<input name="department" value="材料试验室" required></label>
  <label>用电量 kWh（整数）<input name="kwh" type="number" step="1" min="1" value="120" required></label>
  <label>电网排放因子<input name="grid_factor" type="number" step="any" min="0" value="0.57" required></label>
  <button>登记用电</button></form></details>`
 +`<h2>凭证余额（跨报告共用）</h2>`+table(certRows)
 +`<h2>用电报告与预占/核销追查</h2>`+table(reportRows)
 +`<div class="green-actions">`+g.reports.map(r=>`<div class="green-card"><b>${esc(r.name)}</b> ${gstatus(r.status)}
   <p>轮次 #${r.attempt} · ${esc(r.month)} · ${esc(r.department)}</p>
   ${r.status==='completed'&&r.result?`<p class="method">绿电覆盖 ${r.result.covered_kwh} kWh，电网补 ${r.result.grid_kwh} kWh；总排放 ${fmt(r.result.emissions_total_kg)} kg（基准 ${fmt(r.result.baseline_grid_kg)}，减排 ${fmt(r.result.saved_kg)}）</p>`:''}
   ${r.error?`<p class="error">${esc(r.error)}</p>`:''}
   ${(r.status==='queued'||r.status==='running')?`<button class="green-cancel" data-id="${r.id}">取消并释放预占</button>`:''}
   ${r.status==='draft'||r.status==='failed'?`<button class="green-enqueue" data-id="${r.id}">发起核算（冻结并预占）</button>`:''}
   ${r.status==='completed'?`<p class="checksum">已完成报告保留原分配，不可重新核算</p>`:''}
   ${r.frozen?`<details><summary>冻结底稿、因子与最优分配（SHA256 ${esc(r.frozen.checksum?.slice(0,16)||'')}…）</summary><pre class="snapshot">${esc(JSON.stringify(r.frozen,null,2))}</pre></details>`:''}
  </div>`).join('')+`</div>`
 +`<h2>额度流水（register/reserve/release/consume）</h2>`+table(ledgerRows);
}
