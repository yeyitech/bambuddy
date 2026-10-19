import MaterialAccounting from '../components/MaterialAccounting';
import { useEffect, useState } from 'react';
import { getAuthToken } from '../api/client';
type Order = { id:string; item:string; shop:string; category:string; status:string; paid_cny:number|null; due_cny:number|null; quantity:number|null; notes:string; order_no:string|null; date:string|null };
type Spool = { id:string; purchase_id:string; material:string; color:string|null; nominal_g:number|null; remaining_g:number|null; packaging:string; brand?:string; location?:string|null; opening_status?:string; usage_status?:string; device_metadata_sync?:string; estimated_used_g?:number|null; estimated_remaining_g?:number|null; pending_print_g?:number; estimated_remaining_after_pending_g?:number|null; inventory_spool_id?:number };
type Task = { archive_id?:number; archive_status?:string; display_name?:string; filename:string; classification:string; evidence: {state:string; progress:number|null}[] };
type Case = { id:string; project:string; part:string; status:string; human_reviews:{observation:string}[] };
type Ledger = { revision:number; data:{orders:Order[]; filament_units:Spool[]; history:Task[]; quality:Case[]} };
const money=(n:number|null|undefined)=>n==null?'待核对':new Intl.NumberFormat('zh-CN',{style:'currency',currency:'CNY'}).format(n);
const tabs=['采购与配件','已登记耗材','打印历史核对','质量记录','用料与损耗'];
async function request(method='GET',path='',body?:unknown):Promise<Ledger>{
 const r=await fetch('/api/v1/home-ledger'+path,{method,headers:{'Authorization':'Bearer '+getAuthToken(),'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const data=await r.json();if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;
}
export default function HomeLedgerPage({inventoryOnly=false}:{inventoryOnly?:boolean}={}){
 const [ledger,setLedger]=useState<Ledger|null>(null),[error,setError]=useState(''),[tab,setTab]=useState(inventoryOnly?1:0),[search,setSearch]=useState(''),[edit,setEdit]=useState<Order|null>(null),[saving,setSaving]=useState(false);
 async function refresh(){try{setLedger(await request());setError('');}catch(e){setError(String(e));}}
 useEffect(()=>{void refresh();},[]);
 const orders=ledger?.data.orders??[];
 const total=orders.reduce((s,o)=>s+(o.paid_cny??0),0);
 const match=(x:unknown)=>JSON.stringify(x).toLowerCase().includes(search.toLowerCase());
 async function save(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!edit||!ledger)return;setSaving(true);setError('');
 const f=new FormData(e.currentTarget);const body:Record<string,unknown>={revision:ledger.revision};
 for(const k of ['item','shop','status','notes','order_no','date'])body[k]=f.get(k)||null;
 for(const k of ['paid_cny','due_cny','quantity']){const v=f.get(k);body[k]=v===''?null:Number(v);}
 try{setLedger(await request('PATCH','/orders/'+edit.id,body));setEdit(null);}catch(err){setError(String(err));}finally{setSaving(false);}}
 const cell='px-4 py-3 text-left align-top border-b border-black/10 dark:border-white/10';
 return <div className="p-4 md:p-8 space-y-6 max-w-[1600px] mx-auto">
  <div className="flex flex-wrap justify-between items-start gap-4"><div><h1 className="text-2xl font-semibold">{inventoryOnly?'已登记耗材':'家庭打印台账'}</h1><p className="text-sm opacity-60 mt-2">采购、耗材与实际打印记录。金额采用实付款，未知信息保留待核对。</p></div><button className="rounded-lg border px-4 py-2" onClick={()=>void refresh()}>刷新</button></div>
  {!inventoryOnly&&<div className="grid grid-cols-2 lg:grid-cols-4 gap-4">{[['累计已付款',money(total)],['采购记录',String(orders.length)],['耗材采购份数',String(ledger?.data.filament_units.length??0)],['历史记录',String(ledger?.data.history.length??0)]].map(([k,v])=><div className="rounded-xl border border-black/10 dark:border-white/10 p-5" key={k}><div className="text-sm opacity-60">{k}</div><div className="text-2xl mt-2 font-semibold">{v}</div></div>)}</div>}
  {!inventoryOnly&&<div className="flex gap-2 flex-wrap">{tabs.map((t,i)=><button key={t} onClick={()=>{setTab(i);setSearch('');}} className={'px-4 py-2 rounded-lg '+(tab===i?'bg-emerald-600 text-white':'bg-black/5 dark:bg-white/5')}>{t}</button>)}</div>}
  <input aria-label="搜索台账" className="border rounded-lg p-3 w-full md:max-w-lg bg-transparent" placeholder="搜索名称、材料、颜色或编号" value={search} onChange={e=>setSearch(e.target.value)}/>
  {error&&<p role="alert" className="text-red-500 whitespace-pre-wrap">{error}</p>}
  {!ledger&&!error&&<p>正在读取台账…</p>}
  {tab===0&&<div className="overflow-x-auto rounded-xl border border-black/10 dark:border-white/10"><table className="w-full text-sm"><thead className="bg-black/5 dark:bg-white/5"><tr>{['编号／类别','商品与店铺','实付／待付','状态','备注','维护'].map(h=><th className={cell} key={h}>{h}</th>)}</tr></thead><tbody>{orders.filter(match).map(o=><tr key={o.id}><td className={cell}>{o.id}<div className="opacity-60">{o.category}</div></td><td className={cell+' min-w-64'}><div className="font-medium">{o.item}</div><div className="opacity-60 mt-1">{o.shop}</div><div className="opacity-60">{o.quantity==null?'数量待核对':o.quantity+' 份'} · {o.date??'日期待核对'}</div></td><td className={cell+' whitespace-nowrap'}>{money(o.paid_cny)}<div className="opacity-60 text-xs mt-1">待付 {money(o.due_cny)}</div></td><td className={cell+' min-w-28'}>{o.status}</td><td className={cell+' min-w-64 max-w-md'}>{o.notes}</td><td className={cell}><button className="text-emerald-600 whitespace-nowrap" onClick={()=>{setError('');setEdit(o);}}>编辑</button></td></tr>)}</tbody></table></div>}
  {tab===4&&<MaterialAccounting />}
  {tab===1&&<><MaterialAccounting compact /><p className="text-sm opacity-70">全部耗材已关联原生库存，包含在途采购和无盘补充装。首箱按已确认打印估算，备用卷按标称净重登记；未知净重保留待核对。套装成本按份数均摊。</p><div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{ledger?.data.filament_units.filter(match).map(s=>{const o=orders.find(x=>x.id===s.purchase_id);const count=ledger.data.filament_units.filter(x=>x.purchase_id===s.purchase_id).length;const cost=o?.paid_cny==null?null:o.paid_cny/count;return <div key={s.id} className="border border-black/10 dark:border-white/10 rounded-xl p-5 space-y-2"><div className="text-xs opacity-60">{s.id} · {s.purchase_id}</div><h2 className="font-semibold">{s.material} · {s.color??'颜色待核对'}</h2><p>{s.packaging} · {o?.status}</p><p className="text-sm">{s.brand??'品牌见采购记录'} · {s.opening_status??'开封状态待核对'}</p>{s.location&&<p className="font-medium text-emerald-600 dark:text-emerald-400">{s.location} · {s.usage_status??'状态待核对'}</p>}{s.device_metadata_sync&&<p className="text-xs text-amber-600 dark:text-amber-400">{s.device_metadata_sync}</p>}<p>标称 {s.nominal_g==null?'待核对':s.nominal_g+'g'}　估算余量 {s.estimated_remaining_g==null?'待核对':Math.round(s.estimated_remaining_g)+'g'}</p>{s.estimated_used_g!=null&&<p className="text-sm">已结算估算消耗 {Math.round(s.estimated_used_g)}g · 非称重</p>}{!!s.pending_print_g&&<p className="text-sm text-amber-500">当前盘预计 {Math.round(s.pending_print_g)}g，完成后预计剩 {s.estimated_remaining_after_pending_g==null?'待核对':Math.round(s.estimated_remaining_after_pending_g)+'g'}</p>}{s.inventory_spool_id&&<p className="text-xs opacity-60">已入库存 #{s.inventory_spool_id} · 空卷／称重后可校准</p>}<p className="text-sm opacity-70">分摊成本 {money(cost)} · {s.nominal_g&&cost!=null?money(cost/s.nominal_g*1000)+'/kg':'单价待核对'}</p></div>})}</div></>}
  {tab===2&&<><p className="text-sm opacity-70">依据历史状态快照整理。同名任务尚待区分运行批次；设备报告完成不代表外观验收通过。首箱已依据核对结果建立消耗估算。</p><div className="space-y-3">{ledger?.data.history.filter(match).map(t=><div className="p-5 rounded-xl border border-black/10 dark:border-white/10" key={t.filename}><h2 className="font-medium break-all">{t.display_name??t.filename}</h2><p className="mt-2 text-sm">{t.archive_status==='completed'?'已归档 · 设备报告完成':t.archive_status==='printing'?'正在打印 · 已关联切片':'待核对'} · {t.evidence.length} 条证据</p></div>)}</div></>}
  {tab===3&&<div className="space-y-3">{ledger?.data.quality.filter(match).map(c=><div key={c.id} className="rounded-xl border border-black/10 dark:border-white/10 p-5"><h2 className="font-semibold">{c.id} · {c.project} / {c.part}</h2><p className="mt-2">{c.status}</p>{c.human_reviews.map((r,i)=><p key={i} className="mt-2 opacity-70">{r.observation}</p>)}<p className="mt-2 text-sm opacity-60">原因待验证，尚未自动修改打印配置。照片上传与试打对比后续接入。</p></div>)}</div>}
  {edit&&<div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"><form onSubmit={save} className="bg-white text-slate-900 dark:bg-slate-900 dark:text-white rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-auto"><h2 className="text-xl font-semibold mb-5">编辑采购 {edit.id}</h2><div className="grid md:grid-cols-2 gap-4">{[['item','商品'],['shop','店铺'],['order_no','平台订单号'],['date','购买日期'],['quantity','购买份数'],['paid_cny','实付款（元）'],['due_cny','待付款（元）'],['status','到货状态']].map(([key,label])=><label key={key} className="text-sm">{label}<input name={key} defaultValue={String(edit[key as keyof Order]??'')} type={key==='date'?'date':['quantity','paid_cny','due_cny'].includes(key)?'number':'text'} min={key==='quantity'?1:0} step={key==='quantity'?1:'0.01'} required={['item','shop','status'].includes(key)} className="block w-full border rounded-lg p-2 mt-1 bg-transparent"/></label>)}</div><label className="block text-sm mt-4">备注<textarea name="notes" defaultValue={edit.notes} className="block w-full border rounded-lg p-2 mt-1 bg-transparent" rows={3}/></label><p className="text-xs opacity-60 mt-2">未知金额留空；零元请输入0。每次修改保留历史版本。</p>{error&&<p className="text-red-500 mt-3">{error}</p>}<div className="flex justify-end gap-3 mt-5"><button type="button" onClick={()=>setEdit(null)} disabled={saving}>取消</button><button disabled={saving} className="px-5 py-2 rounded-lg bg-emerald-600 text-white">{saving?'保存中…':'保存'}</button></div></form></div>}
 </div>;
}

export function HomePurchaseSummary(){
 const [ledger,setLedger]=useState<Ledger|null>(null);
 useEffect(()=>{let active=true;void request().then(d=>{if(active)setLedger(d);}).catch(()=>{});return()=>{active=false;};},[]);
 if(!ledger)return null;
 const orders=ledger.data.orders;
 const filamentIds=new Set(ledger.data.filament_units.map(s=>s.purchase_id));
 const paid=orders.reduce((n,o)=>n+(o.paid_cny??0),0);
 const filamentPaid=orders.filter(o=>filamentIds.has(o.id)).reduce((n,o)=>n+(o.paid_cny??0),0);
 return <section className="mb-6 p-5 rounded-xl border border-white/10" aria-label="家庭采购统计">
 <MaterialAccounting compact />
 <h2 className="font-semibold mb-3 mt-6">家庭采购统计 · 全部采购日期</h2>
 <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">{[['采购已付款',money(paid)],['耗材已付款',money(filamentPaid)],['采购记录',orders.length+' 笔'],['已登记耗材',ledger.data.filament_units.length+' 份']].map(([k,v])=><div key={k}><p className="text-sm opacity-60">{k}</p><p className="text-xl font-semibold mt-1">{v}</p></div>)}</div>
 <p className="mt-3 text-sm opacity-60">采购支出不等于已打印成本。首箱按历史建立估算余量，待空卷或称重校准；耗材成本按实际采购单价计算。有云端起止记录的任务采用实际时间，其余时长及用料仍为切片估算。</p>
 <a href="/home-ledger" className="inline-block mt-3 text-emerald-500">查看采购明细与核对依据 →</a>
 </section>;
}
