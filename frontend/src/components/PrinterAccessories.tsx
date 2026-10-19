import { Boxes, Box } from 'lucide-react';
import type { AMSUnit } from '../api/client';

export function identifyAccessory(unit: AMSUnit) {
  switch (unit.module_type) {
    case 'n3f': return { name: 'AMS 2 Pro', image: '/img/accessories/ams-2-pro.jpg', known: true };
    case 'n3s': return { name: 'AMS HT', image: '/icons/ams-ht.png', known: true };
    case 'ams': return { name: 'AMS', image: '/icons/ams.png', known: true };
    default: return { name: 'AMS · 型号待识别', image: null, known: false };
  }
}

function dryingLabel(unit: AMSUnit) {
  if (unit.module_type !== 'n3f' && unit.module_type !== 'n3s') return null;
  if (unit.dry_countdown_stalled) return '干燥尚未启动／已暂停';
  return ({0:'干燥待机',1:'干燥检查中',2:'正在干燥',3:'冷却中',4:'正在停止干燥',5:'干燥异常'} as Record<number,string>)[unit.dry_status] ?? '干燥状态待确认';
}

export function PrinterAccessories({ units, connected, compact = false }: { units?: AMSUnit[]; connected: boolean; compact?: boolean }) {
  if (compact && !units?.length) return null;
  return <section aria-label={compact ? '配件概览' : '已识别配件'} className={compact ? 'mt-3 space-y-2' : 'rounded-xl border border-bambu-dark-tertiary bg-bambu-dark-secondary p-5'}>
    {!compact && <><h2 className="mb-1 flex items-center gap-2 font-semibold text-white"><Boxes className="h-4 w-4 text-bambu-green" />已识别配件<span className="text-xs font-normal text-bambu-gray">{units?.length ?? 0} 台</span></h2><p className="mb-4 text-xs text-bambu-gray">{connected ? '根据设备上报自动识别' : '打印机离线 · 显示上次识别信息'}</p></>}
    {!units?.length ? <p className="text-sm text-bambu-gray">{connected ? '当前没有设备上报的 AMS 配件' : '连接后读取配件信息'}</p> :
      <div className={compact ? 'space-y-2' : 'space-y-4'}>{units.map(unit => {
        const model = identifyAccessory(unit);
        const dry = dryingLabel(unit);
        return <div key={unit.id} className={compact ? 'flex items-center gap-3 rounded-lg border border-bambu-dark-tertiary bg-bambu-dark/40 p-2' : 'rounded-lg bg-bambu-dark p-3'}>
          <div className={compact ? 'contents' : 'flex items-center gap-4'}>
            <div className={compact ? 'h-12 w-16 shrink-0 overflow-hidden rounded-md bg-white/5 flex items-center justify-center' : 'h-24 w-28 shrink-0 overflow-hidden rounded-lg bg-white/5 flex items-center justify-center'}>
              {model.image ? <img src={model.image} alt={model.name} className="h-full w-full object-contain" /> : <Box className="h-8 w-8 text-bambu-gray" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-white">{model.name}</p>
              <p className="mt-1 text-xs text-bambu-gray">{unit.is_ams_ht ? 'HT-' + (unit.id - 127) : 'AMS-' + String.fromCharCode(65 + unit.id)} · {unit.tray.length} 个料槽{!connected ? ' · 离线' : ''}</p>
              {connected && <p className="mt-1 text-xs text-bambu-gray">温度 {unit.temp == null ? '—' : unit.temp + '°C'} · 湿度 {unit.humidity == null ? '—' : unit.humidity + '%'}</p>}
            </div>
          </div>
          {!compact && <>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-bambu-gray"><span>固件 {unit.sw_ver || '待读取'}</span>{dry && <span>{connected ? dry : '当前状态待重连'}</span>}{connected && unit.dry_status === 2 && unit.dry_time > 0 && !unit.dry_countdown_stalled && <span>剩余 {unit.dry_time} 分钟</span>}</div>
            <div className="mt-3 grid grid-cols-4 gap-2">{unit.tray.map(tray => {
              const hex = tray.tray_color?.slice(0,6);
              return <div key={tray.id} className="rounded-md border border-bambu-dark-tertiary p-2 text-center text-xs">
                <span className="mx-auto mb-1 block h-3 w-3 rounded-full border border-white/20" style={{backgroundColor: tray.exists !== false && hex && /^[0-9a-f]{6}$/i.test(hex) ? '#' + hex : '#64748b'}} />
                <p className="text-white">{tray.id + 1} · {tray.exists === false ? '空' : tray.tray_type || '未知'}</p>
              </div>;
            })}</div>
            <p className="mt-2 text-[11px] text-bambu-gray">料槽颜色与材料为设备上报值</p>
          </>}
        </div>;
      })}</div>}
  </section>;
}

