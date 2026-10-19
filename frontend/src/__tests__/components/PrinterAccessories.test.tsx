import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PrinterAccessories } from '../../components/PrinterAccessories';
import type { AMSUnit } from '../../api/client';
const ams = {
 id:0, module_type:'n3f', is_ams_ht:false, humidity:41, temp:30.5, sw_ver:'05.00.22.19',
 dry_status:0, dry_time:0, tray:[{id:0,tray_type:'PLA',tray_color:'FFF144FF',exists:true}],
} as AMSUnit;

describe('PrinterAccessories', () => {
 it('identifies an AMS 2 Pro from reported module type, including its image and telemetry', () => {
  render(<PrinterAccessories units={[ams]} connected />);
  expect(screen.getByRole('img',{name:'AMS 2 Pro'})).toHaveAttribute('src','/img/accessories/ams-2-pro.jpg');
  expect(screen.getByText(/温度 30.5°C · 湿度 41%/)).toBeInTheDocument();
  expect(screen.getByText('干燥待机')).toBeInTheDocument();
 });
 it('does not guess a Pro model from slot count or an unrecognized module', () => {
  render(<PrinterAccessories units={[{...ams,module_type:'future'}]} connected />);
  expect(screen.getByText('AMS · 型号待识别')).toBeInTheDocument();
  expect(screen.queryByRole('img',{name:'AMS 2 Pro'})).toBeNull();
 });
 it('marks cached data offline and updates when accessory reports change', () => {
  const {rerender} = render(<PrinterAccessories units={[ams]} connected={false} />);
  expect(screen.getByText(/打印机离线/)).toBeInTheDocument();
  expect(screen.queryByText(/温度 30.5/)).toBeNull();
  rerender(<PrinterAccessories units={[{...ams,module_type:'n3s',id:128,is_ams_ht:true}]} connected />);
  expect(screen.getByRole('img',{name:'AMS HT'})).toBeInTheDocument();
  expect(screen.queryByRole('img',{name:'AMS 2 Pro'})).toBeNull();
 });
 it('does not claim purchased accessories are connected when none are reported', () => {
  render(<PrinterAccessories units={[]} connected />);
  expect(screen.getByText('当前没有设备上报的 AMS 配件')).toBeInTheDocument();
 });
});

