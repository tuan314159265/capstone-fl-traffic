"""Render measured pilot results into Obsidian with standalone scientific plots."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

COLORS={'persistence':'#a7b0a0','local':'#d0a65c','centralized':'#5b8dba','fedavg':'#36836b','fedprox':'#a3759a'}


def node_label(ids):
    return ids[0].split(':')[0].upper().replace('BEN_THANH_','BT').replace('TRAFFIC_','TT').replace('BT_','BT')+(' +'+str(len(ids)-1) if len(ids)>1 else '')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--vault-root',type=Path,required=True)
    parser.add_argument('--study-path',default='Project/Scl/DACN/Thực nghiệm')
    args=parser.parse_args();data=json.loads(args.report.read_text());q=data['quality'];b=data['benchmark']
    report_dir=args.vault_root/args.study_path/'Báo cáo';assets=report_dir/'assets'/b['run_id'];assets.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'axes.titleweight':'medium','figure.facecolor':'white','savefig.facecolor':'white'})
    def save(figure,name):
        for extension in ['svg','png','pdf']:figure.savefig(assets/(name+'.'+extension),bbox_inches='tight',dpi=180)
        plt.close(figure)
    nodes=q['nodes'];labels=[node_label(n['point_ids']) for n in nodes]
    figure,axes=plt.subplots(1,2,figsize=(12,8),sharey=True)
    y=np.arange(len(nodes))
    axes[0].barh(y,[(n['coverage_24h'] or 0)*100 for n in nodes],color=['#36836b' if n['eligible'] else '#c2cfb8' for n in nodes])
    axes[0].axvline(90,color='#b89755',linestyle='--',label='Proposed 90% target')
    axes[0].set(yticks=y,yticklabels=labels,xlim=(0,105),xlabel='Coverage (%)',title='Coverage over observed part of last 24 h');axes[0].invert_yaxis();axes[0].legend(fontsize=8,loc='lower right')
    axes[1].barh(y,[n['longest_run'] for n in nodes],color='#7799b3')
    axes[1].axvline(9,color='#36836b',linestyle='--',label='One 8 → +15 min window')
    axes[1].set(xlabel='Consecutive 15-minute slots',title='Longest uninterrupted run');axes[1].legend(fontsize=8)
    figure.suptitle('TomTom snapshot quality — coverage is not API uptime',y=1.01);figure.tight_layout();save(figure,'01_data_quality')
    methods=b['methods'];x=np.arange(len(methods))
    figure,axis=plt.subplots(figsize=(8,4.8));axis.bar(x,[m['metrics']['macro_mae_kmh']['mean'] for m in methods],
        yerr=[m['metrics']['macro_mae_kmh']['std'] for m in methods],capsize=5,color=[COLORS[m['id']] for m in methods])
    axis.set(xticks=x,xticklabels=[m['name'] for m in methods],ylabel='Macro MAE (km/h)',title='Pilot: test MAE, mean ± sample SD over 3 seeds')
    axis.text(.01,-.2,f"Same snapshot, {b['clients']} clients, {b['sizes']['test']} test windows. Not a research conclusion.",transform=axis.transAxes,fontsize=9,color='#777777');save(figure,'02_method_comparison')
    matrix=np.array([[n['methods'][m['id']]['mean'] for m in methods] for n in b['per_node']])
    figure,axis=plt.subplots(figsize=(9,5));image=axis.imshow(matrix,cmap='YlOrBr',aspect='auto')
    axis.set(xticks=np.arange(len(methods)),xticklabels=[m['name'] for m in methods],
        yticks=np.arange(len(b['per_node'])),yticklabels=[node_label(n['point_ids']) for n in b['per_node']],title='Per-node test MAE (seed mean)')
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):axis.text(column,row,f'{matrix[row,column]:.2f}',ha='center',va='center',color='white' if matrix[row,column]>matrix.max()*.65 else '#3b3b3b')
    figure.colorbar(image,ax=axis,label='MAE (km/h)');save(figure,'03_per_node')
    figure,axis=plt.subplots(figsize=(8,4.8))
    for curve in b['curves']:
        if not curve['points']:continue
        rounds=np.array([v['round'] for v in curve['points']]);mean=np.array([v['mean'] for v in curve['points']]);std=np.array([v['std'] for v in curve['points']])
        axis.plot(rounds,mean,color=COLORS[curve['method']],marker='.',label=curve['method'])
        axis.fill_between(rounds,np.maximum(0,mean-std),mean+std,color=COLORS[curve['method']],alpha=.09)
    axis.set(xlabel='Round',ylabel='Validation macro MAE (km/h)',title='Convergence on validation; test is not used to choose rounds')
    axis.legend();save(figure,'04_convergence')
    figure,axis=plt.subplots(figsize=(8,4.8))
    axis.bar(x,[m['train_upload_bytes']/1024 for m in methods],label='Train upload',color='#36836b')
    axis.bar(x,[m['train_download_bytes']/1024 for m in methods],bottom=[m['train_upload_bytes']/1024 for m in methods],label='Train download',color='#92b49b')
    axis.bar(x,[m['validation_download_bytes']/1024 for m in methods],bottom=[(m['train_upload_bytes']+m['train_download_bytes'])/1024 for m in methods],label='Validation download',color='#d4dfcb')
    axis.set(xticks=x,xticklabels=[m['name'] for m in methods],ylabel='Logical tensor payload (KiB / seed run)',title='Model communication only — not network traffic')
    axis.legend(fontsize=8);axis.text(.01,-.18,'Zero excludes centralized raw-data upload and all protocol/TLS overhead.',transform=axis.transAxes,fontsize=9,color='#777777');save(figure,'05_communication')
    figure,axis=plt.subplots(figsize=(8,4.8))
    for node in b['per_node']:
        if node['train_js_divergence'] is None:continue
        axis.scatter(node['train_js_divergence'],node['fedavg_minus_local_kmh'],color='#36836b',s=45)
        axis.annotate(node_label(node['point_ids']),(node['train_js_divergence'],node['fedavg_minus_local_kmh']),xytext=(5,5),textcoords='offset points',fontsize=8)
    axis.axhline(0,color='#aaaaaa',linestyle='--');axis.set(xlabel='Train-only JS divergence to pooled distribution',ylabel='FedAvg MAE − Local MAE (km/h)',title='Exploratory heterogeneity vs. negative transfer (no causal claim)');save(figure,'06_heterogeneity')
    with (assets/'method_summary.csv').open('w') as handle:
        fields=['method','seeds','macro_mae_mean','macro_mae_std','micro_mae_mean','rmse_mean','worst_node_mean','worst_decile_mean','node_mae_std_mean','logical_model_bytes']
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for m in methods:writer.writerow({'method':m['id'],'seeds':m['seeds'],'macro_mae_mean':m['metrics']['macro_mae_kmh']['mean'],
            'macro_mae_std':m['metrics']['macro_mae_kmh']['std'],'micro_mae_mean':m['metrics']['micro_mae_kmh']['mean'],
            'rmse_mean':m['metrics']['rmse_kmh']['mean'],'worst_node_mean':m['metrics']['worst_node_mae_kmh']['mean'],
            'worst_decile_mean':m['metrics']['worst_decile_mae_kmh']['mean'],'node_mae_std_mean':m['metrics']['node_mae_std_kmh']['mean'],
            'logical_model_bytes':m['logical_model_bytes']['mean']})
    shutil.copyfile(args.report,assets/'reports.json')
    cutoff=datetime.fromisoformat(b['generated_at']).astimezone(ZoneInfo('Asia/Ho_Chi_Minh'))
    note=report_dir/f'{cutoff:%Y-%m-%d} - Pilot TomTom.md'
    if note.exists() and b['run_id'] not in note.read_text():note=report_dir/f'{cutoff:%Y-%m-%d} - {b["run_id"]}.md'
    prefix=str(assets.relative_to(args.vault_root));table='\n'.join(f"| {m['name']} | {m['metrics']['macro_mae_kmh']['mean']:.3f} ± {m['metrics']['macro_mae_kmh']['std']:.3f} | {m['metrics']['rmse_kmh']['mean']:.3f} | {m['metrics']['worst_node_mae_kmh']['mean']:.3f} | {m['logical_model_bytes']['mean']/1024:.1f} |" for m in methods)
    content=f'''---
date: {cutoff:%Y-%m-%d}
type: measured-pilot
run_id: {b['run_id']}
research_result: false
tags: [DACN, FL, TomTom, pilot]
---
# Pilot TomTom — {cutoff:%d/%m/%Y}

Liên kết: [[Project/Scl/DACN/Thực nghiệm/00 - Tổng quan|Tổng quan thực nghiệm]] · [[Project/Scl/DACN/Thực nghiệm/01 - Protocol và kịch bản|Protocol và kịch bản]]

> [!warning] Chỉ là pilot
> {q['raw_rows']} bản ghi → {q['distinct_segment_slots']} mốc đoạn hợp lệ; {b['clients']}/{q['segments']} đoạn đủ mẫu, train/validation/test={b['sizes']['train']}/{b['sizes']['validation']}/{b['sizes']['test']}. Chưa dùng để kết luận phương pháp nào tốt hơn hoặc đưa vào dự báo vận hành.

## Nguồn và tính tái lập

- Dữ liệu thật từ PostgreSQL/PostGIS AWS, các điểm đang hoạt động; khử trùng đoạn/mốc.
- Snapshot SHA-256: `{b['snapshot_sha256']}`.
- Source SHA-256: `{b['source_sha256']}`.
- Run: `{b['run_id']}`. Thời điểm xuất kết quả: {cutoff:%d/%m/%Y %H:%M} UTC+7.
- Seed: {', '.join(map(str,b['seeds']))}; cùng kiến trúc GRU, khởi tạo theo seed và cửa sổ đầu vào8mốc, đầu ra+15phút.
- 10vòng × 2epoch; Adam reset mỗi vòng; FedProxμ={b['proximal_mu']}. Chọn vòng bằng validation, không tune theo test.
- Train targets trước `{b['train_targets_before']}`; test targets từ `{b['test_targets_from']}`. Lịch sử đầu vào có thể nằm ở tập trước; nhãn không chồng tập.
- Runtime mô phỏng tuần tự trên một EC2, không phải nhiều máy phân tán thật.

## 1. Chất lượng dữ liệu

- Dòng lệch lưới/tương lai: {q['rejected'].get('off_grid_or_future',0)}; tốc độ/confidence không đạt: {q['rejected'].get('invalid_speed_or_confidence',0)}.
- {q['duplicate_segment_slots']} dòng được gộp vì nhiều điểm cùng đoạn, cùng mốc; không mặc định là lỗi ghi DB.
- Độ phủ tính từ quan sát hợp lệ đầu tiên đến thời điểm audit, tối đa24h cho biểu đồ; không đại diện uptime API từ lúc triển khai.
- Freshness đang là tuổi thu thập; chưa đo tuổi cập nhật mô hình hoặc độ mới dữ liệu gốc của nhà cung cấp.

![[{prefix}/01_data_quality.svg]]

## 2. So sánh cùng snapshot

| Phương pháp | Macro MAE ± SD seed (km/h) | RMSE mean (km/h) | Worst-node mean (km/h) | Tensor/run (KiB) |
| --- | ---: | ---: | ---: | ---: |
{table}

![[{prefix}/02_method_comparison.svg]]

Persistence hiện tốt hơn các mô hình học trên snapshot này. Đây là một khoảng test rất ngắn với ít thay đổi tốc độ; không diễn giải rằng FL không phù hợp với bài toán giao thông.

## 3. Hiệu năng từng node và hội tụ

![[{prefix}/03_per_node.svg]]

![[{prefix}/04_convergence.svg]]

SD giữa3seed phản ánh bất ổn tối ưu trên snapshot này, không phải độ bất định theo ngày giao thông. Không dựng CI tổng quát từ3seed này. Worst-decile lấy ceil(10% × K), hiện K={b['clients']} nên chỉ1node.

## 4. Chi phí trao đổi và heterogeneity

![[{prefix}/05_communication.svg]]

Đếm tensor model train xuống/lên và validation xuống; chưa đo network/TLS/serialization. Centralized có số0 ở cột tensor FL, nhưng chi phí truyền dữ liệu thô chưa được tính.

![[{prefix}/06_heterogeneity.svg]]

JS chỉ tính trên quan sát trước cutoff train. Δdương nghĩa là FedAvg kém local trên node đó. Ít node và test ít mẫu chưa cho phép kết luận quan hệ nhân quả giữa JS và negative transfer.

## 5. Những việc chưa hoàn thành

- Chưa chạy kịch bản non-IID có kiểm soát, delay/dropout/drift, cold-start hoặc ablation.
- SCAFFOLD, Ditto/FedRep, adaptive aggregation/personalization còn phải triển khai theo đề bài.
- Chưa chốt tập test cuối kỳ; các snapshot tuần có thể chồng test. Giữ riêng protocol nghiên cứu trước khi chạy bộ test cuối.
- Chưa triển khai dự báo trực tiếp bằng checkpoint pilot.

## Tệp đi kèm

- [[{prefix}/method_summary.csv|Bảng số liệu CSV]].
- [[{prefix}/reports.json|JSON toàn bộ báo cáo]].
- Mỗi biểu đồ có SVG/PNG/PDF trong cùng thư mục assets; có thể đưa vào báo cáo hoặc slide.
'''
    note.write_text(content)
    print(json.dumps({'note':str(note),'assets':str(assets),'figures':6},ensure_ascii=False))


if __name__=='__main__':main()
