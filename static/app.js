const state = { data: null, ticker: "TCS", suggestions: [], activeSuggestion: -1, searchController: null, companyController: null, comparisonController: null, companyCache: new Map() };
const $ = (id) => document.getElementById(id);
const fmt = (value, suffix = "", digits = 1) => value == null ? "—" : `${Number(value).toFixed(digits)}${suffix}`;
const metricRow = (label, value) => `<div class="metric-row"><span>${label}</span><strong>${value}</strong></div>`;
async function responseJson(response, fallback) {
  let data;
  try { data=await response.json(); } catch { throw new Error(fallback); }
  if(!response.ok) throw new Error(data?.error||fallback);
  return data;
}

async function loadCompany(ticker, refresh = false) {
  state.companyController?.abort();
  const controller=new AbortController(); state.companyController=controller;
  $("loading-text").textContent="Fetching current Screener data...";
  $("loading").hidden = false; $("error").hidden = true; $("dashboard").hidden = true; $("insights").hidden = true; $("comparison").hidden = true; $("audit").hidden = true;
  const slowTimer=setTimeout(()=>{$("loading-text").textContent="Still working: direct-peer pages can take a little longer to verify.";},5000);
  try {
    let data=!refresh&&state.companyCache.get(ticker.toUpperCase());
    if(!data){
      const response = await fetch(`/api/company/${encodeURIComponent(ticker)}${refresh ? "?refresh=1" : ""}`,{signal:controller.signal});
      data = await responseJson(response,"Unable to load company data. Please try again.");
      state.companyCache.set(ticker.toUpperCase(),data);
    }
    state.data = data; state.ticker = ticker.toUpperCase(); render(data); switchView("dashboard");
  } catch (error) { if(error.name!=="AbortError") { $("error").textContent = error.message; $("error").hidden = false; } }
  finally { clearTimeout(slowTimer); if(state.companyController===controller) $("loading").hidden = true; }
}

function render(data) {
  const analysis = data.analysis, metrics = analysis.metrics, summary = data.summary;
  $("company-name").textContent = data.company; $("fetched-at").textContent = `Fetched ${new Date(data.fetched_at).toLocaleString()}`;
  [$("source-link"), $("audit-source-link")].forEach(link => link.href = data.source_url);
  const marketLabels = ["Current Price", "Market Cap", "Stock P/E", "ROCE", "ROE", "Dividend Yield"];
  $("market-strip").innerHTML = marketLabels.filter(label => summary[label]).map(label => `<div class="market-chip"><span>${label}</span><strong>${summary[label].displayed}</strong></div>`).join("");
  $("total-score").textContent = analysis.score; $("score-ring").style.setProperty("--score", `${analysis.score}%`);
  $("decision").textContent = analysis.decision; $("decision").className = `decision ${analysis.tone}`;
  $("strengths").innerHTML = analysis.strengths.map(item => `<li>${item}</li>`).join("");
  $("risks").innerHTML = analysis.risks.map(item => `<li>${item}</li>`).join("");
  $("score-note").textContent = analysis.methodology;
  $("modules").innerHTML = analysis.modules.map(module => `<article class="module"><div class="module-head"><h3>${module.name}</h3><strong>${module.score}<small>/${module.max}</small></strong></div><div class="bar"><i style="width:${module.score / module.max * 100}%"></i></div><small>${Math.round(module.score / module.max * 100)}% of maximum score</small></article>`).join("");
  renderChart(data); renderAnalysis(metrics); renderFlags(metrics); renderBusinessInsights(data); renderAudit(data);
}

function renderBusinessInsights(data) {
  const insights=data.analysis.business_insights;
  const industry=insights.industry_comparison;
  $("insights-company").textContent=`${data.company}: research view`;
  $("download-report").href=`/api/company/${encodeURIComponent(state.ticker)}/report`;
  $("download-report").download=`${state.ticker}-analyst-report.pdf`;
  $("insights-confidence").textContent=insights.confidence;
  $("insights-stance").textContent=insights.stance;
  $("insights-action").textContent=insights.action;
  $("insights-wait").textContent=insights.wait_window;
  $("insights-summary").innerHTML=insights.executive_summary.map((item,index)=>`<article><span>0${index+1}</span><p>${item}</p></article>`).join("");
  $("insights-dimensions").innerHTML=insights.dimensions.map((item,index)=>`<article class="dimension-card"><div class="dimension-head"><span>${String(index+1).padStart(2,"0")}</span><strong>${item.rating}</strong></div><h3>${item.title}</h3><p>${item.analysis}</p>${item.detail?`<p>${item.detail}</p>`:""}</article>`).join("");
  $("insights-industry-name").textContent=industry.industry;
  $("insights-industry-sample").textContent=`${industry.sample_size} direct peers · ${industry.accounting_period}${industry.excluded_count?` · ${industry.excluded_count} excluded`:""}`;
  $("insights-industry-method").textContent=`${industry.methodology} ${industry.price_basis}`;
  $("insights-industry-link").href=industry.industry_url;
  $("insights-industry-grid").innerHTML=industry.comparisons.map(item=>`<article class="benchmark-card ${item.signal}"><div><span>${item.label}</span><strong>${item.assessment}</strong></div><dl><div><dt>Company (annual period)</dt><dd>${fmt(item.company,item.unit,item.unit==="x"?2:1)}</dd></div><div><dt>Peer median (same period)</dt><dd>${fmt(item.peer_median,item.unit,item.unit==="x"?2:1)}</dd></div></dl><p>${item.difference_percent>=0?"+":""}${item.difference_percent.toFixed(1)}% vs median</p></article>`).join("");
  $("insights-choose").innerHTML=insights.why_choose.map(item=>`<li>${item}</li>`).join("");
  $("insights-avoid").innerHTML=insights.why_not.map(item=>`<li>${item}</li>`).join("");
  $("insights-confirm").innerHTML=insights.confirmations.map(item=>{const met=item.startsWith("✓");return`<li class="${met?"met":"unmet"}">${item.replace(/^[✓✗] /,"")}</li>`;}).join("");
  $("insights-invalidate").innerHTML=insights.invalidations.map(item=>`<li>${item}</li>`).join("");
  $("insights-gaps").innerHTML=insights.research_gaps.map((item,index)=>`<article><strong>${String(index+1).padStart(2,"0")}</strong><p>${item}</p></article>`).join("");
  $("insights-disclaimer").textContent=insights.disclaimer;
}

function annual(data, section, row) {
  const statement = data.statements[section], values = statement?.rows[row] || [];
  return statement.periods.map((period, index) => ({ period, value: values[index]?.value })).filter(point => point.period.startsWith("Mar ") && point.value != null).slice(-5);
}

function renderChart(data) {
  const sets = [{name:"Sales",className:"sales",points:annual(data,"Profit & Loss","Sales")},{name:"Net profit",className:"profit",points:annual(data,"Profit & Loss","Net Profit")},{name:"Operating cash",className:"cfo",points:annual(data,"Cash Flows","Cash from Operating Activity")}];
  const indexed=sets.map(set=>({...set,points:set.points.map((point,index,points)=>({...point,indexed:points[0].value ? point.value/points[0].value*100 : 100}))}));
  const values=indexed.flatMap(set=>set.points.map(point=>point.indexed)), min=Math.floor(Math.min(...values)/20)*20, max=Math.ceil(Math.max(...values)/20)*20, width=720, height=230, left=48, right=25, top=18, bottom=35;
  const x = index => left + index * ((width - left - right) / 4), y = value => height - bottom - (value-min)/Math.max(max-min,20)*(height-top-bottom);
  const ticks=Array.from({length:5},(_,index)=>min+(max-min)*index/4);
  const grid = ticks.map(value => `<line class="chart-grid" x1="${left}" y1="${y(value)}" x2="${width-right}" y2="${y(value)}"/><text class="chart-text" x="${left-8}" y="${y(value)+3}" text-anchor="end">${Math.round(value)}</text>`).join("");
  const lines = indexed.map(set => { const path = set.points.map((point,index) => `${index ? "L":"M"}${x(index)},${y(point.indexed)}`).join(" "); return `<path class="chart-line-${set.className}" d="${path}"/><g>${set.points.map((point,index) => `<circle class="chart-dot chart-line-${set.className}" cx="${x(index)}" cy="${y(point.indexed)}" r="3"/>`).join("")}</g>`; }).join("");
  const labels = sets[0].points.map((point,index) => `<text class="chart-text" x="${x(index)}" y="${height-8}" text-anchor="middle">${point.period.replace("Mar ","")}</text>`).join("");
  $("trend-chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Five-year sales, net profit and operating cash trends indexed to 100">${grid}${lines}${labels}<text class="chart-axis-title" x="${left}" y="11">Index (first year = 100)</text></svg>`;
  const colors = ["var(--green)","var(--navy)","var(--coral)"]; $("chart-legend").innerHTML = sets.map((set,index) => `<span><i class="legend-dot" style="background:${colors[index]}"></i>${set.name}</span>`).join("");
}

function renderAnalysis(m) {
  $("operating-metrics").innerHTML = metricRow("Sales growth",fmt(m.sales_growth,"%"))+metricRow("Operating margin",fmt(m.opm,"%"))+metricRow("Net margin",fmt(m.npm,"%"))+metricRow("Profit growth",fmt(m.profit_growth,"%"));
  $("operating-insight").textContent = m.npm < m.opm*.6 ? "A wide operating-to-net margin gap warrants review of interest, tax and non-operating effects." : "Operating performance is carrying through to the bottom line without an unusually wide margin gap.";
  $("dupont-npm").textContent=fmt(m.npm,"%"); $("dupont-turnover").textContent=fmt(m.asset_turnover,"x",2); $("dupont-leverage").textContent=fmt(m.equity_multiplier,"x",2);
  $("dupont-insight").textContent = m.equity_multiplier > 2.5 ? "ROE has meaningful leverage support; operating quality should be assessed separately." : "ROE is not primarily dependent on an excessive equity multiplier.";
  $("cash-metrics").innerHTML=metricRow("CFO / net profit",fmt(m.cash_conversion,"x",2))+metricRow("CFO growth",fmt(m.cfo_growth,"%"))+metricRow("Profit growth",fmt(m.profit_growth,"%"));
  $("cash-insight").textContent=m.cash_conversion>=.9?"Reported profit is substantially supported by operating cash flow.":"Operating cash flow is not fully supporting reported profit; inspect working capital and accruals.";
  $("leverage-metrics").innerHTML=metricRow("Debt / equity",fmt(m.debt_equity,"x",2))+metricRow("Interest coverage",fmt(m.interest_cover,"x",1))+metricRow("ROCE",fmt(m.roce,"%"));
  $("leverage-insight").textContent=m.debt_equity<=.5&&m.interest_cover>=5?"Balance-sheet leverage appears controlled with healthy interest capacity.":"Debt burden or interest capacity requires closer review.";
  $("valuation-metrics").innerHTML=metricRow("Trailing P/E (Screener)",fmt(m.pe,"x",1))+metricRow("P/E / five-year profit CAGR",fmt(m.peg,"x",2))+metricRow("Price / book",fmt(m.price_to_book,"x",2))+metricRow("Trailing ROE (Screener)",fmt(m.roe,"%"));
  $("valuation-insight").textContent=m.peg==null?"Growth-adjusted P/E is not meaningful because five-year profit CAGR is 3% or lower.":m.peg>2?"Price-to-earnings is high relative to five-year profit CAGR; compare the exact-period peer benchmark before interpreting it.":"Current earnings multiple is reasonably aligned with five-year profit CAGR in this model.";
}

function renderFlags(m) {
  const flags=[
    [m.cash_conversion<.8,"Profit-to-cash divergence",m.cash_conversion<.8?"Review":"Clear"],
    [(m.profit_growth||0)-(m.cfo_growth||0)>15,"Profit growth ahead of CFO",(m.profit_growth||0)-(m.cfo_growth||0)>15?"Review":"Clear"],
    [m.other_income_watch,"Other-income swing",m.other_income_watch?"Review":"Normal"],
    [m.debtor_days_watch,"Receivable collection trend",m.debtor_days_watch?"Review":"Stable"],
    [m.debt_equity>1,"Balance-sheet leverage",m.debt_equity>1?"Elevated":"Controlled"],
    [m.interest_cover<3,"Interest servicing capacity",m.interest_cover<3?"Weak":"Healthy"]
  ];
  $("red-flags").innerHTML=flags.map(([risk,label,status])=>`<div class="flag ${risk?"risk":""}"><i class="flag-dot"></i><strong>${label}</strong><span>${status}</span></div>`).join("");
}

function renderAudit(data) {
  const rows=[]; Object.values(data.summary).forEach(point=>rows.push({metric:point.label,period:"Current",...point}));
  Object.entries(data.statements).forEach(([section,statement])=>Object.entries(statement.rows).forEach(([label,points])=>points.forEach((point,index)=>{ if(point.value!=null) rows.push({metric:`${section} · ${label}`,period:statement.periods[index]||"—",...point}); })));
  const verified=rows.filter(row=>row.verified).length; $("verified-count").textContent=`${verified} / ${rows.length}`; $("audit-count").textContent=`${verified}/${rows.length}`; $("audit-time").textContent=`Fetched ${new Date(data.fetched_at).toLocaleString()}`;
  $("audit-body").innerHTML=rows.map(row=>{ const normalized=row.values?.length>1?row.values.join(" / "):row.value; return `<tr><td><a href="${row.source_url}" target="_blank" rel="noopener">${row.metric} ↗</a></td><td>${row.period}</td><td>${normalized}${row.unit?` ${row.unit}`:""}</td><td>${row.displayed}</td><td class="status ${row.verified?"matched":"review"}">${row.verified?"Matched":"Review"}</td></tr>`; }).join("");
}

const comparisonMetrics=[
  ["Fundamental score",d=>d.analysis.score,"",0,true],["Sales growth",d=>d.analysis.metrics.sales_growth,"%",1,true],["Profit growth",d=>d.analysis.metrics.profit_growth,"%",1,true],["Operating margin",d=>d.analysis.metrics.opm,"%",1,true],["ROE",d=>d.analysis.metrics.roe,"%",1,true],["ROCE",d=>d.analysis.metrics.roce,"%",1,true],["Cash conversion",d=>d.analysis.metrics.cash_conversion,"x",2,true],["Interest coverage",d=>d.analysis.metrics.interest_cover,"x",1,true],["P/E",d=>d.analysis.metrics.pe,"x",1,false],["Price / book",d=>d.analysis.metrics.price_to_book,"x",2,false],["Growth-adjusted P/E",d=>d.analysis.metrics.peg,"x",2,false],["Debt / equity",d=>d.analysis.metrics.debt_equity,"x",2,false],["Debtor days",d=>d.analysis.metrics.debtor_days," days",0,false]
];
function metricLeader(a,b,higher,left,right){if(a==null||b==null)return["none","Insufficient data"];if(Math.abs(a-b)/Math.max(Math.abs(a),Math.abs(b),1)<.05)return["tie","Broadly similar"];const leftWins=higher?a>b:a<b;return[leftWins?"left":"right",`${leftWins?left:right} leads`];}
function renderComparison(left,right){
  $("comparison-left-heading").textContent=left.company;$("comparison-right-heading").textContent=right.company;
  $("comparison-summary").innerHTML=[left,right].map(d=>`<article><div><p class="eyebrow">Consolidated Screener data</p><h2>${d.company}</h2><a href="${d.source_url}" target="_blank" rel="noopener">Open source ↗</a></div><div class="comparison-score"><strong>${d.analysis.score}</strong><span>/100</span><small>${d.analysis.decision}</small></div></article>`).join("");
  $("comparison-metrics").innerHTML=comparisonMetrics.map(([label,get,unit,digits,higher])=>{const a=get(left),b=get(right),[side,text]=metricLeader(a,b,higher,left.company,right.company);return`<tr><td><strong>${label}</strong><small>${higher?"Higher":"Lower"} is generally favorable</small></td><td class="${side==="left"?"leader":""}">${fmt(a,unit,digits)}</td><td class="${side==="right"?"leader":""}">${fmt(b,unit,digits)}</td><td><span class="comparison-result ${side}">${text}</span></td></tr>`;}).join("");
  const rightModules=new Map(right.analysis.modules.map(m=>[m.name,m]));$("comparison-modules").innerHTML=left.analysis.modules.map(a=>{const b=rightModules.get(a.name);return`<article><div><strong>${a.name}</strong><span>${a.score}/${a.max} · ${b?.score??"—"}/${b?.max??a.max}</span></div><progress max="${a.max}" value="${a.score}"></progress><progress max="${b?.max??a.max}" value="${b?.score??0}"></progress><small>${left.company} / ${right.company}</small></article>`;}).join("");$("comparison-results").hidden=false;
}
async function comparisonCompany(query,signal){const search=await fetch(`/api/companies?q=${encodeURIComponent(query)}`,{signal}),matches=await responseJson(search,"Company search is temporarily unavailable.");const ticker=(matches.find(x=>x.ticker===query.toUpperCase())||matches[0])?.ticker;if(!ticker)throw new Error(`No company found for “${query}”.`);const cached=state.companyCache.get(ticker);if(cached)return{ticker,data:cached};const response=await fetch(`/api/company/${encodeURIComponent(ticker)}`,{signal}),data=await responseJson(response,`Unable to load ${query}. Please try again.`);state.companyCache.set(ticker,data);return{ticker,data};}
async function compareCompanies(){state.comparisonController?.abort();const controller=new AbortController();state.comparisonController=controller;$("comparison-loading").hidden=false;$("comparison-error").hidden=true;$("comparison-results").hidden=true;try{const [left,right]=await Promise.all([comparisonCompany($("compare-left").value.trim(),controller.signal),comparisonCompany($("compare-right").value.trim(),controller.signal)]);if(left.ticker===right.ticker)throw new Error("Choose two different companies.");$("compare-left").value=left.ticker;$("compare-right").value=right.ticker;renderComparison(left.data,right.data);}catch(error){if(error.name!=="AbortError"){$("comparison-error").textContent=error.message;$("comparison-error").hidden=false;}}finally{if(state.comparisonController===controller)$("comparison-loading").hidden=true;}}

function setupComparisonAutocomplete(inputId,listId) {
  const input=$(inputId), list=$(listId);
  let matches=[], active=-1, timer, controller;
  const close=()=>{matches=[];active=-1;list.hidden=true;list.replaceChildren();input.setAttribute("aria-expanded","false");input.removeAttribute("aria-activedescendant");};
  const activate=index=>{if(!matches.length)return;active=(index+matches.length)%matches.length;list.querySelectorAll(".autocomplete-option").forEach((option,optionIndex)=>{const selected=optionIndex===active;option.classList.toggle("active",selected);option.setAttribute("aria-selected",String(selected));});const option=list.children[active];input.setAttribute("aria-activedescendant",option.id);option.scrollIntoView({block:"nearest"});};
  const select=index=>{const match=matches[index];if(!match)return;input.value=match.ticker;input.dataset.ticker=match.ticker;close();};
  const render=items=>{matches=items;active=-1;list.replaceChildren();items.forEach((match,index)=>{const option=document.createElement("li");option.id=`${listId}-option-${index}`;option.className="autocomplete-option";option.role="option";const name=document.createElement("span");name.textContent=match.name;const ticker=document.createElement("strong");ticker.textContent=match.ticker;option.append(name,ticker);option.addEventListener("mousedown",event=>{event.preventDefault();select(index);});list.append(option);});list.hidden=!items.length;input.setAttribute("aria-expanded",String(Boolean(items.length)));};
  input.addEventListener("input",()=>{delete input.dataset.ticker;clearTimeout(timer);controller?.abort();close();const query=input.value.trim();if(query.length<2)return;timer=setTimeout(async()=>{controller=new AbortController();try{const response=await fetch(`/api/companies?q=${encodeURIComponent(query)}`,{signal:controller.signal});const items=await responseJson(response,"Company search is temporarily unavailable.");if(input.value.trim()===query)render(items);}catch(error){if(error.name!=="AbortError")close();}},220);});
  input.addEventListener("keydown",event=>{if(event.key==="ArrowDown"&&matches.length){event.preventDefault();activate(active+1);}else if(event.key==="ArrowUp"&&matches.length){event.preventDefault();activate(active<0?matches.length-1:active-1);}else if(event.key==="Enter"&&matches.length){event.preventDefault();select(active<0?0:active);}else if(event.key==="Escape")close();});
  input.addEventListener("blur",()=>setTimeout(close,100));
}

function switchView(view) { document.querySelectorAll(".view").forEach(el=>el.hidden=el.id!==view); document.querySelectorAll(".nav-tab").forEach(tab=>tab.classList.toggle("active",tab.dataset.view===view)); window.scrollTo({top:0}); }

function closeSuggestions() {
  state.suggestions=[]; state.activeSuggestion=-1; $("company-suggestions").hidden=true; $("ticker").setAttribute("aria-expanded","false"); $("ticker").removeAttribute("aria-activedescendant");
}

function renderSuggestions(matches) {
  state.suggestions=matches; state.activeSuggestion=-1;
  const list=$("company-suggestions"); list.replaceChildren();
  matches.forEach((match,index)=>{
    const option=document.createElement("li"); option.id=`company-option-${index}`; option.className="autocomplete-option"; option.role="option";
    const name=document.createElement("span"); name.textContent=match.name;
    const ticker=document.createElement("strong"); ticker.textContent=match.ticker;
    option.append(name,ticker); option.addEventListener("mousedown",event=>{ event.preventDefault(); selectSuggestion(index); }); list.append(option);
  });
  list.hidden=matches.length===0; $("ticker").setAttribute("aria-expanded",String(matches.length>0));
}

function setActiveSuggestion(index) {
  if (!state.suggestions.length) return;
  state.activeSuggestion=(index+state.suggestions.length)%state.suggestions.length;
  document.querySelectorAll(".autocomplete-option").forEach((option,optionIndex)=>{ const active=optionIndex===state.activeSuggestion; option.classList.toggle("active",active); option.setAttribute("aria-selected",String(active)); });
  const id=`company-option-${state.activeSuggestion}`; $("ticker").setAttribute("aria-activedescendant",id); $(id).scrollIntoView({block:"nearest"});
}

function selectSuggestion(index) {
  const match=state.suggestions[index]; if (!match) return;
  state.searchController?.abort(); $("ticker").value=match.ticker; $("ticker").dataset.ticker=match.ticker; closeSuggestions(); loadCompany(match.ticker);
}

let searchTimer;
$("ticker").addEventListener("input",event=>{
  const input=event.currentTarget;
  delete input.dataset.ticker; clearTimeout(searchTimer); state.searchController?.abort(); closeSuggestions();
  const query=input.value.trim(); if (query.length<2) { closeSuggestions(); return; }
  searchTimer=setTimeout(async()=>{
    state.searchController=new AbortController();
    try { const response=await fetch(`/api/companies?q=${encodeURIComponent(query)}`,{signal:state.searchController.signal}); const matches=await responseJson(response,"Company search is temporarily unavailable."); if(input.value.trim()===query) renderSuggestions(matches); }
    catch(error) { if(error.name!=="AbortError") closeSuggestions(); }
  },220);
});
$("ticker").addEventListener("keydown",event=>{
  if(event.key==="ArrowDown"){ event.preventDefault(); setActiveSuggestion(state.activeSuggestion+1); }
  else if(event.key==="ArrowUp"){ event.preventDefault(); setActiveSuggestion(state.activeSuggestion<0?state.suggestions.length-1:state.activeSuggestion-1); }
  else if(event.key==="Escape") closeSuggestions();
  else if(event.key==="Enter"&&state.suggestions.length){ event.preventDefault(); selectSuggestion(state.activeSuggestion<0?0:state.activeSuggestion); }
});
document.addEventListener("click",event=>{ if(!event.target.closest(".search-shell")) closeSuggestions(); });
document.querySelectorAll(".nav-tab").forEach(tab=>tab.addEventListener("click",()=>state.data&&switchView(tab.dataset.view)));
setupComparisonAutocomplete("compare-left","compare-left-suggestions");
setupComparisonAutocomplete("compare-right","compare-right-suggestions");
$("comparison-form").addEventListener("submit",event=>{event.preventDefault();compareCompanies();});
$("search-form").addEventListener("submit",async event=>{
  event.preventDefault(); clearTimeout(searchTimer); state.searchController?.abort();
  const input=$("ticker"), query=input.value.trim(), selected=input.dataset.ticker;
  if(!query) return;
  if(selected) { closeSuggestions(); loadCompany(selected); return; }
  if(state.suggestions.length) { selectSuggestion(state.activeSuggestion<0?0:state.activeSuggestion); return; }
  closeSuggestions();
  const controller=new AbortController(); state.searchController=controller;
  try {
    const response=await fetch(`/api/companies?q=${encodeURIComponent(query)}`,{signal:controller.signal}), matches=await responseJson(response,"Company search is temporarily unavailable.");
    if(state.searchController!==controller) return;
    const match=matches.find(item=>item.ticker===query.toUpperCase())||matches[0];
    if(match) { input.value=match.ticker; input.dataset.ticker=match.ticker; loadCompany(match.ticker); }
    else { $("error").textContent=`No company found for “${query}”. Try a company name or NSE ticker.`; $("error").hidden=false; }
  } catch(error) { if(error.name!=="AbortError") { $("error").textContent="Company search is temporarily unavailable. Please try again."; $("error").hidden=false; } }
});
$("refresh").addEventListener("click",()=>loadCompany(state.ticker,true));
loadCompany("TCS");