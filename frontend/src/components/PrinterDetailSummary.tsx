import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Box, History, Info } from 'lucide-react';
import { api, withMediaToken, type Printer } from '../api/client';
import { EmbeddedCameraViewer } from './EmbeddedCameraViewer';
import { PrinterAccessories } from './PrinterAccessories';
import { useAuth } from '../contexts/AuthContext';

export function PrinterDetailSummary({ printer }: { printer: Printer }) {
  const { hasPermission } = useAuth();
  const canReadHistory = hasPermission('archives:read_all') || hasPermission('archives:read_own');
  const { data: status } = useQuery({
    queryKey: ['printerStatus', printer.id],
    queryFn: () => api.getPrinterStatus(printer.id),
    refetchInterval: 30000,
  });
  const { data: archives, isPending, isError } = useQuery({
    queryKey: ['printer-detail-history', printer.id],
    queryFn: () => api.getArchives(printer.id, undefined, 6),
    enabled: canReadHistory,
    refetchInterval: 60000,
  });
  const rows = [
    ['设备型号', printer.model ?? '—'],
    ['位置', printer.location || '未设置'],
    ['固件版本', status?.firmware_version ?? '—'],
    ['连接方式', !status?.connected ? '离线' : status.wired_network ? '有线网络' : status.wifi_signal != null ? 'Wi-Fi · ' + status.wifi_signal + ' dBm' : '已连接'],
    ['开发者模式', status?.developer_mode == null ? '—' : status.developer_mode ? '已开启' : '未开启'],
  ];
  return <>
    <div className="min-w-0 space-y-4" aria-label="实时画面与设备资料">
    {hasPermission('camera:view') && <div id="printer-live-camera"><EmbeddedCameraViewer printerId={printer.id} printerName={printer.name} inline onClose={() => {}} /></div>}
    <section className="min-w-0 rounded-xl border border-bambu-dark-tertiary bg-bambu-dark-secondary p-5">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white"><Info className="h-4 w-4 text-bambu-green" />设备资料</h2>
      <dl className="grid grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-3">{rows.map(([label,value]) => <div key={label} className="min-w-0 text-sm"><dt className="mb-1 text-xs text-bambu-gray">{label}</dt><dd className="break-words text-white">{value}</dd></div>)}</dl>
    </section>
    </div>
    <div className="grid min-w-0 grid-cols-1 items-start gap-4 xl:col-span-2 xl:grid-cols-2" aria-label="配件与打印记录">
    <PrinterAccessories units={status?.ams} connected={status?.connected ?? false} />
    {canReadHistory && <section className="min-w-0 rounded-xl border border-bambu-dark-tertiary bg-bambu-dark-secondary p-5">
      <div className="mb-4 flex items-center justify-between gap-2"><h2 className="flex items-center gap-2 font-semibold text-white"><History className="h-4 w-4 text-bambu-green" />近期打印</h2><Link to="/archives" className="text-xs text-bambu-green">全部归档 →</Link></div>
      {isPending ? <p className="text-sm text-bambu-gray">正在读取打印记录…</p> : isError ? <p role="status" className="text-sm text-bambu-gray">暂时无法读取打印记录，请稍后重试。</p> : !archives?.length ? <p className="text-sm text-bambu-gray">暂无打印记录</p> : <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">{archives.map(a => <li key={a.id} className="flex min-w-0 items-center gap-3 rounded-lg border border-bambu-dark-tertiary bg-bambu-dark/40 p-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-bambu-dark overflow-hidden">
          {a.thumbnail_path ? <img src={withMediaToken('/api/v1/archives/' + a.id + '/thumbnail')} alt="" className="h-full w-full object-contain" loading="lazy" /> : <Box className="h-6 w-6 text-bambu-gray" />}
        </div>
        <div className="min-w-0"><p className="truncate text-sm text-white" title={a.print_name || a.filename}>{a.print_name || a.filename}</p>
          <p className="mt-1 text-xs text-bambu-gray">{({completed:'已完成',printing:'打印中',failed:'失败',cancelled:'已取消'} as Record<string,string>)[a.status] ?? a.status}{a.filament_used_grams != null ? ' · 预计用料 ' + Math.round(a.filament_used_grams) + 'g' : ''}</p>
          {a.started_at && <p className="mt-1 text-xs text-bambu-gray">{new Date(/[Zz]|[+-]\d\d:\d\d$/.test(a.started_at) ? a.started_at : a.started_at + 'Z').toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}</p>}
        </div>
      </li>)}</ul>}
    </section>}
    </div>
  </>;
}

