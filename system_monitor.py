#!/usr/bin/env python3
"""
실시간 시스템 리소스 모니터링 시스템
CPU, Memory, Disk, Network, Temperature 등을 실시간으로 추적하고 시각화
"""

import psutil
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.gridspec import GridSpec
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
from collections import deque
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import warnings
warnings.filterwarnings('ignore')

class SystemMonitor:
    """시스템 리소스 실시간 모니터링 클래스"""

    def __init__(self, duration_minutes=5, update_interval=1):
        """
        Args:
            duration_minutes: 모니터링 지속 시간 (분)
            update_interval: 업데이트 간격 (초)
        """
        self.duration_minutes = duration_minutes
        self.update_interval = update_interval
        self.max_data_points = int((duration_minutes * 60) / update_interval)

        # 데이터 저장용 deque (최대 크기 제한)
        self.timestamps = deque(maxlen=self.max_data_points)
        self.cpu_percent = deque(maxlen=self.max_data_points)
        self.cpu_per_core = deque(maxlen=self.max_data_points)
        self.memory_percent = deque(maxlen=self.max_data_points)
        self.memory_used_gb = deque(maxlen=self.max_data_points)
        self.disk_percent = deque(maxlen=self.max_data_points)
        self.disk_read_mb = deque(maxlen=self.max_data_points)
        self.disk_write_mb = deque(maxlen=self.max_data_points)
        self.net_sent_mb = deque(maxlen=self.max_data_points)
        self.net_recv_mb = deque(maxlen=self.max_data_points)
        self.cpu_temp = deque(maxlen=self.max_data_points)

        # 이전 네트워크 및 디스크 통계
        self.prev_net_io = psutil.net_io_counters()
        self.prev_disk_io = psutil.disk_io_counters()
        self.prev_time = time.time()

        # 시작 시간
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(minutes=duration_minutes)

        # CPU 코어 수
        self.cpu_count = psutil.cpu_count()

        print(f"시스템 모니터링 시작: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"종료 예정 시간: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"CPU 코어 수: {self.cpu_count}")
        print(f"총 메모리: {psutil.virtual_memory().total / (1024**3):.2f} GB")
        print("-" * 60)

    def get_cpu_temperature(self):
        """CPU 온도 가져오기 (가능한 경우)"""
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                # 'coretemp', 'cpu_thermal', 'k10temp' 등에서 온도 찾기
                for name, entries in temps.items():
                    if name in ['coretemp', 'cpu_thermal', 'k10temp', 'zenpower']:
                        if entries:
                            return entries[0].current
            return None
        except (AttributeError, KeyError):
            return None

    def collect_data(self):
        """현재 시스템 상태 수집"""
        current_time = time.time()
        time_diff = current_time - self.prev_time

        # 타임스탬프
        self.timestamps.append(datetime.now())

        # CPU
        cpu_pct = psutil.cpu_percent(interval=0.1)
        self.cpu_percent.append(cpu_pct)
        self.cpu_per_core.append(psutil.cpu_percent(interval=0.1, percpu=True))

        # 메모리
        mem = psutil.virtual_memory()
        self.memory_percent.append(mem.percent)
        self.memory_used_gb.append(mem.used / (1024**3))

        # 디스크
        disk = psutil.disk_usage('/')
        self.disk_percent.append(disk.percent)

        # 디스크 I/O
        disk_io = psutil.disk_io_counters()
        if disk_io and self.prev_disk_io and time_diff > 0:
            read_bytes = (disk_io.read_bytes - self.prev_disk_io.read_bytes) / time_diff
            write_bytes = (disk_io.write_bytes - self.prev_disk_io.write_bytes) / time_diff
            self.disk_read_mb.append(read_bytes / (1024**2))
            self.disk_write_mb.append(write_bytes / (1024**2))
            self.prev_disk_io = disk_io
        else:
            self.disk_read_mb.append(0)
            self.disk_write_mb.append(0)

        # 네트워크
        net_io = psutil.net_io_counters()
        if time_diff > 0:
            sent_bytes = (net_io.bytes_sent - self.prev_net_io.bytes_sent) / time_diff
            recv_bytes = (net_io.bytes_recv - self.prev_net_io.bytes_recv) / time_diff
            self.net_sent_mb.append(sent_bytes / (1024**2))
            self.net_recv_mb.append(recv_bytes / (1024**2))
            self.prev_net_io = net_io
        else:
            self.net_sent_mb.append(0)
            self.net_recv_mb.append(0)

        # CPU 온도
        temp = self.get_cpu_temperature()
        self.cpu_temp.append(temp if temp else 0)

        self.prev_time = current_time

    def create_figure(self):
        """시각화 Figure 생성"""
        plt.style.use('seaborn-v0_8-darkgrid')
        fig = plt.figure(figsize=(16, 10))
        fig.suptitle('실시간 시스템 리소스 모니터링', fontsize=16, fontweight='bold')

        gs = GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)

        # 서브플롯 생성
        self.ax_cpu = fig.add_subplot(gs[0, 0])
        self.ax_cpu_cores = fig.add_subplot(gs[0, 1])
        self.ax_memory = fig.add_subplot(gs[0, 2])
        self.ax_disk = fig.add_subplot(gs[1, 0])
        self.ax_disk_io = fig.add_subplot(gs[1, 1])
        self.ax_network = fig.add_subplot(gs[1, 2])
        self.ax_temp = fig.add_subplot(gs[2, 0])
        self.ax_summary = fig.add_subplot(gs[2, 1:])

        return fig

    def update_plot(self, frame):
        """플롯 업데이트 (애니메이션 프레임)"""
        # 데이터 수집
        self.collect_data()

        # 남은 시간 계산
        remaining = (self.end_time - datetime.now()).total_seconds()
        if remaining <= 0:
            print("\n모니터링 완료!")
            plt.close('all')
            return

        # 시간 축 (초 단위)
        time_axis = [(t - self.timestamps[0]).total_seconds() for t in self.timestamps]

        # 모든 서브플롯 클리어
        for ax in [self.ax_cpu, self.ax_cpu_cores, self.ax_memory, self.ax_disk,
                   self.ax_disk_io, self.ax_network, self.ax_temp, self.ax_summary]:
            ax.clear()

        # 1. CPU 사용률
        self.ax_cpu.plot(time_axis, self.cpu_percent, 'b-', linewidth=2, label='CPU 전체')
        self.ax_cpu.fill_between(time_axis, self.cpu_percent, alpha=0.3)
        self.ax_cpu.set_ylabel('사용률 (%)', fontweight='bold')
        self.ax_cpu.set_title('CPU 사용률', fontweight='bold')
        self.ax_cpu.set_ylim(0, 100)
        self.ax_cpu.legend(loc='upper right')
        self.ax_cpu.grid(True, alpha=0.3)

        # 2. CPU 코어별 사용률
        if self.cpu_per_core:
            latest_cores = list(self.cpu_per_core)[-1]
            cores_index = np.arange(len(latest_cores))
            bars = self.ax_cpu_cores.bar(cores_index, latest_cores, color='skyblue', edgecolor='navy')

            # 색상 그라데이션 (사용률에 따라)
            for i, (bar, val) in enumerate(zip(bars, latest_cores)):
                if val > 80:
                    bar.set_color('red')
                elif val > 60:
                    bar.set_color('orange')
                else:
                    bar.set_color('green')

            self.ax_cpu_cores.set_ylabel('사용률 (%)', fontweight='bold')
            self.ax_cpu_cores.set_xlabel('코어 번호', fontweight='bold')
            self.ax_cpu_cores.set_title('코어별 CPU 사용률', fontweight='bold')
            self.ax_cpu_cores.set_ylim(0, 100)
            self.ax_cpu_cores.set_xticks(cores_index)

        # 3. 메모리 사용률
        self.ax_memory.plot(time_axis, self.memory_percent, 'r-', linewidth=2, label='메모리 %')
        self.ax_memory.fill_between(time_axis, self.memory_percent, alpha=0.3, color='red')
        self.ax_memory.set_ylabel('사용률 (%)', fontweight='bold')
        self.ax_memory.set_title('메모리 사용률', fontweight='bold')
        self.ax_memory.set_ylim(0, 100)

        # 두 번째 y축 (GB)
        ax_mem2 = self.ax_memory.twinx()
        ax_mem2.plot(time_axis, self.memory_used_gb, 'darkred', linewidth=1,
                     linestyle='--', label='메모리 GB', alpha=0.7)
        ax_mem2.set_ylabel('사용량 (GB)', fontweight='bold')

        self.ax_memory.legend(loc='upper left')
        ax_mem2.legend(loc='upper right')
        self.ax_memory.grid(True, alpha=0.3)

        # 4. 디스크 사용률
        disk_labels = ['사용됨', '여유']
        disk_sizes = [self.disk_percent[-1], 100 - self.disk_percent[-1]]
        colors_disk = ['#ff6b6b', '#51cf66']
        wedges, texts, autotexts = self.ax_disk.pie(disk_sizes, labels=disk_labels, autopct='%1.1f%%',
                                                      colors=colors_disk, startangle=90)
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        self.ax_disk.set_title('디스크 사용률 (/)', fontweight='bold')

        # 5. 디스크 I/O
        self.ax_disk_io.plot(time_axis, self.disk_read_mb, 'g-', linewidth=2, label='읽기')
        self.ax_disk_io.plot(time_axis, self.disk_write_mb, 'orange', linewidth=2, label='쓰기')
        self.ax_disk_io.fill_between(time_axis, self.disk_read_mb, alpha=0.3, color='green')
        self.ax_disk_io.fill_between(time_axis, self.disk_write_mb, alpha=0.3, color='orange')
        self.ax_disk_io.set_ylabel('속도 (MB/s)', fontweight='bold')
        self.ax_disk_io.set_title('디스크 I/O', fontweight='bold')
        self.ax_disk_io.legend(loc='upper right')
        self.ax_disk_io.grid(True, alpha=0.3)

        # 6. 네트워크 트래픽
        self.ax_network.plot(time_axis, self.net_sent_mb, 'purple', linewidth=2, label='송신')
        self.ax_network.plot(time_axis, self.net_recv_mb, 'cyan', linewidth=2, label='수신')
        self.ax_network.fill_between(time_axis, self.net_sent_mb, alpha=0.3, color='purple')
        self.ax_network.fill_between(time_axis, self.net_recv_mb, alpha=0.3, color='cyan')
        self.ax_network.set_ylabel('속도 (MB/s)', fontweight='bold')
        self.ax_network.set_title('네트워크 트래픽', fontweight='bold')
        self.ax_network.legend(loc='upper right')
        self.ax_network.grid(True, alpha=0.3)

        # 7. CPU 온도
        if any(self.cpu_temp) and max(self.cpu_temp) > 0:
            self.ax_temp.plot(time_axis, self.cpu_temp, 'darkred', linewidth=2, label='CPU 온도')
            self.ax_temp.fill_between(time_axis, self.cpu_temp, alpha=0.3, color='red')
            self.ax_temp.set_ylabel('온도 (°C)', fontweight='bold')
            self.ax_temp.set_title('CPU 온도', fontweight='bold')
            self.ax_temp.legend(loc='upper right')
            self.ax_temp.grid(True, alpha=0.3)
        else:
            self.ax_temp.text(0.5, 0.5, 'CPU 온도 센서\n사용 불가',
                            ha='center', va='center', transform=self.ax_temp.transAxes,
                            fontsize=12, fontweight='bold')
            self.ax_temp.set_title('CPU 온도', fontweight='bold')

        # 8. 요약 통계
        self.ax_summary.axis('off')

        # 현재 통계
        current_stats = [
            ['지표', '현재 값', '평균', '최소', '최대'],
            ['CPU (%)', f'{self.cpu_percent[-1]:.1f}',
             f'{np.mean(self.cpu_percent):.1f}',
             f'{np.min(self.cpu_percent):.1f}',
             f'{np.max(self.cpu_percent):.1f}'],
            ['메모리 (%)', f'{self.memory_percent[-1]:.1f}',
             f'{np.mean(self.memory_percent):.1f}',
             f'{np.min(self.memory_percent):.1f}',
             f'{np.max(self.memory_percent):.1f}'],
            ['메모리 (GB)', f'{self.memory_used_gb[-1]:.2f}',
             f'{np.mean(self.memory_used_gb):.2f}',
             f'{np.min(self.memory_used_gb):.2f}',
             f'{np.max(self.memory_used_gb):.2f}'],
            ['디스크 읽기 (MB/s)', f'{self.disk_read_mb[-1]:.2f}',
             f'{np.mean(self.disk_read_mb):.2f}',
             f'{np.min(self.disk_read_mb):.2f}',
             f'{np.max(self.disk_read_mb):.2f}'],
            ['디스크 쓰기 (MB/s)', f'{self.disk_write_mb[-1]:.2f}',
             f'{np.mean(self.disk_write_mb):.2f}',
             f'{np.min(self.disk_write_mb):.2f}',
             f'{np.max(self.disk_write_mb):.2f}'],
            ['네트워크 송신 (MB/s)', f'{self.net_sent_mb[-1]:.2f}',
             f'{np.mean(self.net_sent_mb):.2f}',
             f'{np.min(self.net_sent_mb):.2f}',
             f'{np.max(self.net_sent_mb):.2f}'],
            ['네트워크 수신 (MB/s)', f'{self.net_recv_mb[-1]:.2f}',
             f'{np.mean(self.net_recv_mb):.2f}',
             f'{np.min(self.net_recv_mb):.2f}',
             f'{np.max(self.net_recv_mb):.2f}'],
        ]

        table = self.ax_summary.table(cellText=current_stats, cellLoc='center',
                                       loc='center', bbox=[0, 0, 1, 1])
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)

        # 헤더 스타일
        for i in range(5):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')

        # 데이터 행 스타일 (교대로 색상)
        for i in range(1, len(current_stats)):
            for j in range(5):
                if i % 2 == 0:
                    table[(i, j)].set_facecolor('#f0f0f0')

        self.ax_summary.set_title('통계 요약', fontweight='bold', pad=20)

        # 진행 상황 출력
        elapsed = (datetime.now() - self.start_time).total_seconds()
        progress = (elapsed / (self.duration_minutes * 60)) * 100
        print(f"\r진행: {progress:.1f}% | 경과: {int(elapsed)}초 / {self.duration_minutes * 60}초 | "
              f"CPU: {self.cpu_percent[-1]:.1f}% | 메모리: {self.memory_percent[-1]:.1f}%", end='')

    def run(self):
        """모니터링 실행"""
        fig = self.create_figure()

        # 애니메이션 생성
        ani = animation.FuncAnimation(
            fig,
            self.update_plot,
            interval=self.update_interval * 1000,  # 밀리초
            cache_frame_data=False,
            save_count=self.max_data_points
        )

        try:
            plt.show(block=True)

            # 종료 대기
            while datetime.now() < self.end_time:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n사용자에 의해 중단되었습니다.")
        finally:
            plt.close('all')

    def generate_pdf_report(self, filename='system_monitoring_report.pdf'):
        """PDF 리포트 생성"""
        print(f"\n\nPDF 리포트 생성 중: {filename}")

        # 그래프 이미지 저장
        self.save_charts()

        # PDF 문서 생성
        doc = SimpleDocTemplate(filename, pagesize=landscape(A4),
                               topMargin=0.5*inch, bottomMargin=0.5*inch)

        story = []
        styles = getSampleStyleSheet()

        # 제목 스타일
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        # 부제목 스타일
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#34495E'),
            spaceAfter=12,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )

        # 제목
        story.append(Paragraph("시스템 리소스 모니터링 리포트", title_style))
        story.append(Spacer(1, 12))

        # 기본 정보 테이블
        info_data = [
            ['모니터링 시작', self.start_time.strftime('%Y-%m-%d %H:%M:%S')],
            ['모니터링 종료', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['총 모니터링 시간', f'{self.duration_minutes} 분'],
            ['데이터 수집 포인트', str(len(self.timestamps))],
            ['CPU 코어 수', str(self.cpu_count)],
            ['총 메모리', f'{psutil.virtual_memory().total / (1024**3):.2f} GB'],
        ]

        info_table = Table(info_data, colWidths=[2.5*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (1, 0), (1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
        ]))

        story.append(info_table)
        story.append(Spacer(1, 20))

        # 통계 요약
        story.append(Paragraph("성능 통계 요약", subtitle_style))
        story.append(Spacer(1, 12))

        stats_data = [
            ['지표', '평균', '최소', '최대', '표준편차'],
            ['CPU 사용률 (%)',
             f'{np.mean(self.cpu_percent):.2f}',
             f'{np.min(self.cpu_percent):.2f}',
             f'{np.max(self.cpu_percent):.2f}',
             f'{np.std(self.cpu_percent):.2f}'],
            ['메모리 사용률 (%)',
             f'{np.mean(self.memory_percent):.2f}',
             f'{np.min(self.memory_percent):.2f}',
             f'{np.max(self.memory_percent):.2f}',
             f'{np.std(self.memory_percent):.2f}'],
            ['메모리 사용량 (GB)',
             f'{np.mean(self.memory_used_gb):.2f}',
             f'{np.min(self.memory_used_gb):.2f}',
             f'{np.max(self.memory_used_gb):.2f}',
             f'{np.std(self.memory_used_gb):.2f}'],
            ['디스크 읽기 (MB/s)',
             f'{np.mean(self.disk_read_mb):.2f}',
             f'{np.min(self.disk_read_mb):.2f}',
             f'{np.max(self.disk_read_mb):.2f}',
             f'{np.std(self.disk_read_mb):.2f}'],
            ['디스크 쓰기 (MB/s)',
             f'{np.mean(self.disk_write_mb):.2f}',
             f'{np.min(self.disk_write_mb):.2f}',
             f'{np.max(self.disk_write_mb):.2f}',
             f'{np.std(self.disk_write_mb):.2f}'],
            ['네트워크 송신 (MB/s)',
             f'{np.mean(self.net_sent_mb):.2f}',
             f'{np.min(self.net_sent_mb):.2f}',
             f'{np.max(self.net_sent_mb):.2f}',
             f'{np.std(self.net_sent_mb):.2f}'],
            ['네트워크 수신 (MB/s)',
             f'{np.mean(self.net_recv_mb):.2f}',
             f'{np.min(self.net_recv_mb):.2f}',
             f'{np.max(self.net_recv_mb):.2f}',
             f'{np.std(self.net_recv_mb):.2f}'],
        ]

        stats_table = Table(stats_data, colWidths=[2.5*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ECC71')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
        ]))

        story.append(stats_table)
        story.append(PageBreak())

        # 그래프 페이지
        story.append(Paragraph("시각화 차트", subtitle_style))
        story.append(Spacer(1, 12))

        # 차트 이미지 추가
        if os.path.exists('chart_overview.png'):
            story.append(Image('chart_overview.png', width=10*inch, height=6*inch))

        story.append(PageBreak())

        if os.path.exists('chart_detailed.png'):
            story.append(Paragraph("상세 분석 차트", subtitle_style))
            story.append(Spacer(1, 12))
            story.append(Image('chart_detailed.png', width=10*inch, height=6*inch))

        # PDF 생성
        doc.build(story)
        print(f"PDF 리포트가 생성되었습니다: {filename}")

        # 임시 이미지 파일 삭제
        for img_file in ['chart_overview.png', 'chart_detailed.png']:
            if os.path.exists(img_file):
                os.remove(img_file)

    def save_charts(self):
        """차트를 이미지로 저장"""
        # 개요 차트
        fig1 = plt.figure(figsize=(16, 10))
        gs1 = GridSpec(2, 3, figure=fig1, hspace=0.3, wspace=0.3)

        time_axis = [(t - self.timestamps[0]).total_seconds() / 60 for t in self.timestamps]

        # CPU
        ax1 = fig1.add_subplot(gs1[0, 0])
        ax1.plot(time_axis, self.cpu_percent, 'b-', linewidth=2)
        ax1.fill_between(time_axis, self.cpu_percent, alpha=0.3)
        ax1.set_ylabel('사용률 (%)', fontweight='bold')
        ax1.set_xlabel('시간 (분)', fontweight='bold')
        ax1.set_title('CPU 사용률', fontweight='bold')
        ax1.grid(True, alpha=0.3)

        # 메모리
        ax2 = fig1.add_subplot(gs1[0, 1])
        ax2.plot(time_axis, self.memory_percent, 'r-', linewidth=2)
        ax2.fill_between(time_axis, self.memory_percent, alpha=0.3, color='red')
        ax2.set_ylabel('사용률 (%)', fontweight='bold')
        ax2.set_xlabel('시간 (분)', fontweight='bold')
        ax2.set_title('메모리 사용률', fontweight='bold')
        ax2.grid(True, alpha=0.3)

        # 디스크 I/O
        ax3 = fig1.add_subplot(gs1[0, 2])
        ax3.plot(time_axis, self.disk_read_mb, 'g-', linewidth=2, label='읽기')
        ax3.plot(time_axis, self.disk_write_mb, 'orange', linewidth=2, label='쓰기')
        ax3.set_ylabel('속도 (MB/s)', fontweight='bold')
        ax3.set_xlabel('시간 (분)', fontweight='bold')
        ax3.set_title('디스크 I/O', fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 네트워크
        ax4 = fig1.add_subplot(gs1[1, 0])
        ax4.plot(time_axis, self.net_sent_mb, 'purple', linewidth=2, label='송신')
        ax4.plot(time_axis, self.net_recv_mb, 'cyan', linewidth=2, label='수신')
        ax4.set_ylabel('속도 (MB/s)', fontweight='bold')
        ax4.set_xlabel('시간 (분)', fontweight='bold')
        ax4.set_title('네트워크 트래픽', fontweight='bold')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        # CPU 코어별 평균 사용률
        ax5 = fig1.add_subplot(gs1[1, 1])
        if self.cpu_per_core:
            avg_per_core = np.mean([list(cores) for cores in self.cpu_per_core], axis=0)
            cores_index = np.arange(len(avg_per_core))
            bars = ax5.bar(cores_index, avg_per_core, color='skyblue', edgecolor='navy')
            for i, (bar, val) in enumerate(zip(bars, avg_per_core)):
                if val > 60:
                    bar.set_color('red')
                elif val > 40:
                    bar.set_color('orange')
                else:
                    bar.set_color('green')
            ax5.set_ylabel('평균 사용률 (%)', fontweight='bold')
            ax5.set_xlabel('코어 번호', fontweight='bold')
            ax5.set_title('코어별 평균 CPU 사용률', fontweight='bold')
            ax5.set_xticks(cores_index)

        # 디스크 사용률 파이 차트
        ax6 = fig1.add_subplot(gs1[1, 2])
        disk_labels = ['사용됨', '여유']
        disk_sizes = [np.mean(self.disk_percent), 100 - np.mean(self.disk_percent)]
        colors_disk = ['#ff6b6b', '#51cf66']
        ax6.pie(disk_sizes, labels=disk_labels, autopct='%1.1f%%',
               colors=colors_disk, startangle=90)
        ax6.set_title('평균 디스크 사용률', fontweight='bold')

        fig1.suptitle('시스템 모니터링 개요', fontsize=16, fontweight='bold')
        plt.savefig('chart_overview.png', dpi=150, bbox_inches='tight')
        plt.close(fig1)

        # 상세 차트
        fig2 = plt.figure(figsize=(16, 10))
        gs2 = GridSpec(3, 2, figure=fig2, hspace=0.3, wspace=0.3)

        # CPU + 메모리 복합
        ax1 = fig2.add_subplot(gs2[0, :])
        ax1.plot(time_axis, self.cpu_percent, 'b-', linewidth=2, label='CPU %')
        ax1.set_ylabel('CPU (%)', fontweight='bold', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.set_xlabel('시간 (분)', fontweight='bold')
        ax1.set_title('CPU 및 메모리 사용률 추이', fontweight='bold')
        ax1.grid(True, alpha=0.3)

        ax1_twin = ax1.twinx()
        ax1_twin.plot(time_axis, self.memory_percent, 'r-', linewidth=2, label='메모리 %')
        ax1_twin.set_ylabel('메모리 (%)', fontweight='bold', color='r')
        ax1_twin.tick_params(axis='y', labelcolor='r')

        # 디스크 I/O 상세
        ax2 = fig2.add_subplot(gs2[1, 0])
        ax2.plot(time_axis, self.disk_read_mb, 'g-', linewidth=2, label='읽기')
        ax2.fill_between(time_axis, self.disk_read_mb, alpha=0.3, color='green')
        ax2.set_ylabel('읽기 속도 (MB/s)', fontweight='bold')
        ax2.set_xlabel('시간 (분)', fontweight='bold')
        ax2.set_title('디스크 읽기 I/O', fontweight='bold')
        ax2.grid(True, alpha=0.3)

        ax3 = fig2.add_subplot(gs2[1, 1])
        ax3.plot(time_axis, self.disk_write_mb, 'orange', linewidth=2, label='쓰기')
        ax3.fill_between(time_axis, self.disk_write_mb, alpha=0.3, color='orange')
        ax3.set_ylabel('쓰기 속도 (MB/s)', fontweight='bold')
        ax3.set_xlabel('시간 (분)', fontweight='bold')
        ax3.set_title('디스크 쓰기 I/O', fontweight='bold')
        ax3.grid(True, alpha=0.3)

        # 네트워크 상세
        ax4 = fig2.add_subplot(gs2[2, 0])
        ax4.plot(time_axis, self.net_sent_mb, 'purple', linewidth=2, label='송신')
        ax4.fill_between(time_axis, self.net_sent_mb, alpha=0.3, color='purple')
        ax4.set_ylabel('송신 속도 (MB/s)', fontweight='bold')
        ax4.set_xlabel('시간 (분)', fontweight='bold')
        ax4.set_title('네트워크 송신', fontweight='bold')
        ax4.grid(True, alpha=0.3)

        ax5 = fig2.add_subplot(gs2[2, 1])
        ax5.plot(time_axis, self.net_recv_mb, 'cyan', linewidth=2, label='수신')
        ax5.fill_between(time_axis, self.net_recv_mb, alpha=0.3, color='cyan')
        ax5.set_ylabel('수신 속도 (MB/s)', fontweight='bold')
        ax5.set_xlabel('시간 (분)', fontweight='bold')
        ax5.set_title('네트워크 수신', fontweight='bold')
        ax5.grid(True, alpha=0.3)

        fig2.suptitle('상세 분석 차트', fontsize=16, fontweight='bold')
        plt.savefig('chart_detailed.png', dpi=150, bbox_inches='tight')
        plt.close(fig2)


def main():
    """메인 함수"""
    print("=" * 60)
    print("시스템 리소스 실시간 모니터링 시스템")
    print("=" * 60)

    # 모니터링 설정
    duration_minutes = 5  # 5분
    update_interval = 2    # 2초마다 업데이트

    # 모니터 생성 및 실행
    monitor = SystemMonitor(duration_minutes=duration_minutes, update_interval=update_interval)

    print("\n실시간 모니터링을 시작합니다...")
    print("창을 닫으면 모니터링이 중단됩니다.\n")

    # 모니터링 실행
    monitor.run()

    # PDF 리포트 생성
    monitor.generate_pdf_report('system_monitoring_report.pdf')

    print("\n모니터링이 완료되었습니다!")
    print(f"총 {len(monitor.timestamps)}개의 데이터 포인트가 수집되었습니다.")
    print("PDF 리포트: system_monitoring_report.pdf")


if __name__ == "__main__":
    main()
