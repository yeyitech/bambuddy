import { useEffect, useState } from 'react';
import { getAuthToken } from '../api/client';

type Run = {
 run_id:number; archive_id:number; name:string; state:string; reason?:string;
 total_g:number|null; waste_g:number|null; waste_rate:number|null; waste_basis:string;
 breakdown?:{support_g?:number;flush_g?:number;tower_brim_g?:number;unclassified_g?:number;error?:string};
};
type Report = {
 checked_at:string|null; settled_count:number; pending_count:number; total_used_g:number;
 known_waste_g:number; covered_g:number; known_waste_rate:number|null;
 unknown_breakdown_count:number; note:string; runs:Run[];
};
const grams=(n:number|null|undefined)=>n==null?'待核对':n.toFixed(2)+' g';
async function api(path='', method='GET',body?:unknown):Promise<Report>{
 const response=await fetch('/api/v1/home-ledger/material-accounting'+path,{
  method,headers:{Authorization:'Bearer '+getAuthToken(),'Content-Type':'application/json'},
  ...(body===undefined?{}:{body:JSON.stringify(body)})});
 const data=await response.json();
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'读取耗材结算失败');
 return data;
}
export default function MaterialAccounting({compact=false}:{compact?:boolean}){
 const [report,setReport]=useState<Report|null>(null);
 const [error,setError]=useState('');
 const [edit,setEdit]=useState<Run|null>(null);
 const [saving,setSaving]=useState(false);
 useEffect(()=>{
  let active=true;
  const refresh=()=>void api().then(data=>{if(active){setReport(data);setError('');}})
    .catch(e=>{if(active)setError(String(e));});
  refresh();const interval=setInterval(refresh,60000);
  return()=>{active=false;clearInterval(interval);};
 },[]);
 async function save(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();if(!edit)return;
  const form=new FormData(event.currentTarget);setSaving(true);setError('');
  try{
   setReport(await api('/'+edit.run_id+'/waste','PUT',{
    waste_g:Number(form.get('waste_g')),note:String(form.get('note')||'')}));setEdit(null);
  }catch(e){setError(String(e));}finally{setSaving(false);}
 }
 return <section className="rounded-xl border border-black/10 dark:border-white/10 p-5 space-y-4" aria-label="用料结算与损耗">
  <div className="flex flex-wrap justify-between gap-2">
   <h2 className="font-semibold text-lg">用料结算与损耗</h2>
   <span className="text-xs opacity-60">{report?.checked_at?'最近核对 '+new Date(report.checked_at).toLocaleString('zh-CN'):'等待首次核对'}</span>
  </div>
  {error&&<p role="alert" className="text-red-500">{error}</p>}
  {report&&<>
   <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
    {[['累计登记耗料',grams(report.total_used_g)],['已结算／待核对',report.settled_count+' / '+report.pending_count],
     ['已识别损耗',grams(report.known_waste_g)],
     ['已识别损耗率',report.known_waste_rate==null?'待核对':report.known_waste_rate.toFixed(1)+'%']].map(([label,value])=>
      <div key={label}><p className="text-sm opacity-60">{label}</p><p className="text-xl font-semibold mt-1">{value}</p></div>)}
   </div>
   <p className="text-sm opacity-70">库存按每次打印的切片用料估算，称重后可校正。损耗是总耗料的一部分，不会重复扣库存。
    损耗率覆盖 {grams(report.covered_g)} 的任务，另有 {report.unknown_breakdown_count} 次缺少分类数据。</p>
   <p className="text-xs text-amber-600 dark:text-amber-400">{report.note} “已识别损耗率”不等于完整实际损耗率。</p>
   {!compact&&<div className="overflow-x-auto"><table className="w-full text-sm">
    <thead><tr>{['打印任务','结算用料','支撑／塔与裙边','换色排废','未分类','损耗率','记录'].map(h=><th key={h} className="text-left p-3 whitespace-nowrap">{h}</th>)}</tr></thead>
    <tbody>{report.runs.map(r=><tr key={r.run_id} className="border-t border-black/10 dark:border-white/10">
     <td className="p-3 min-w-52 max-w-sm"><a className="text-emerald-600 dark:text-emerald-400 break-all" href="/archives">{r.name}</a>
      <p className="text-xs opacity-60 mt-1">{r.state==='settled'?'已结算 · 估算':'待核对 · '+r.reason}</p></td>
     <td className="p-3 whitespace-nowrap">{grams(r.total_g)}</td>
     <td className="p-3 whitespace-nowrap">{grams(r.breakdown?.support_g)} / {grams(r.breakdown?.tower_brim_g)}</td>
     <td className="p-3 whitespace-nowrap">{grams(r.breakdown?.flush_g)}</td>
     <td className="p-3 whitespace-nowrap">{grams(r.breakdown?.unclassified_g)}</td>
     <td className="p-3 whitespace-nowrap">{r.waste_rate==null?'待核对':r.waste_rate.toFixed(1)+'%'}<p className="text-xs opacity-60">{r.waste_basis}</p></td>
     <td className="p-3">{r.state==='settled'&&<button className="text-emerald-600 whitespace-nowrap" onClick={()=>setEdit(r)}>记录废料称重</button>}</td>
    </tr>)}</tbody></table></div>}
  </>}
  {edit&&<div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
   <form onSubmit={save} className="rounded-xl bg-white dark:bg-slate-900 p-6 max-w-md w-full space-y-4">
    <h3 className="font-semibold">记录本次废料称重</h3><p className="text-sm break-all">{edit.name}</p>
    <p className="text-sm opacity-70">总耗料目前为 {grams(edit.total_g)}（估算）。填写本次收集的全部废料，替换该次损耗统计，不额外扣库存。若废料超过总量，需要先核对用料。</p>
    <label className="block">废料净重（g）<input required type="number" name="waste_g" min="0" max={edit.total_g??0} step="0.01" className="block border rounded p-2 w-full bg-transparent mt-1"/></label>
    <label className="block">说明<textarea required name="note" maxLength={1000} placeholder="例如：支撑＋擦拭塔＋本盘换色废料，不含收集盒" className="block border rounded p-2 w-full bg-transparent mt-1"/></label>
    {error&&<p className="text-red-500">{error}</p>}
    <div className="flex justify-end gap-4"><button type="button" disabled={saving} onClick={()=>setEdit(null)}>取消</button><button disabled={saving} className="bg-emerald-600 text-white rounded px-4 py-2">{saving?'保存中…':'保存记录'}</button></div>
   </form>
  </div>}
 </section>;
}
