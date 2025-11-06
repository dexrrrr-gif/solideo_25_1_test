#!/usr/bin/env python3
"""
실시간 시스템 리소스 모니터링 시스템 (Headless 버전)
GUI 없이 백그라운드에서 실행되며 콘솔에 진행상황을 출력하고 PDF 리포트를 생성합니다.
"""

import psutil
import matplotlib
matplotlib.use('Agg')  # GUI 없는 백엔드
import matplotlib.pyplot as plt
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
    """시스템 리소스 실시간 모니터링 클래스 (Headless)"""

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

        print("=" * 80)
        print("시스템 리소스 실시간 모니터링 시스템 (Headless Mode)".center(80))
        print("=" * 80)
        print(f"\n시작 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"종료 예정: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"모니터링 시간: {self.duration_minutes}분")
        print(f"업데이트 간격: {self.update_interval}초")
        print(f"\n시스템 정보:")
        print(f"  - CPU 코어 수: {self.cpu_count}")
        print(f"  - 총 메모리: {psutil.virtual_memory().total / (1024**3):.2f} GB")
        print(f"  - 디스크 용량: {psutil.disk_usage('/').total / (1024**3):.2f} GB")
        print("\n" + "-" * 80)

    def get_cpu_temperature(self):
        """CPU 온도 가져오기 (가능한 경우)"""
        try:
            temps = psutil.sensors_temperatures()
            if temps:
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

    def print_status(self):
        """현재 상태를 콘솔에 출력"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        remaining = (self.end_time - datetime.now()).total_seconds()
        progress = (elapsed / (self.duration_minutes * 60)) * 100

        # 진행 바
        bar_length = 50
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)

        # 통계
        cpu_current = self.cpu_percent[-1] if self.cpu_percent else 0
        mem_current = self.memory_percent[-1] if self.memory_percent else 0
        disk_read = self.disk_read_mb[-1] if self.disk_read_mb else 0
        disk_write = self.disk_write_mb[-1] if self.disk_write_mb else 0
        net_sent = self.net_sent_mb[-1] if self.net_sent_mb else 0
        net_recv = self.net_recv_mb[-1] if self.net_recv_mb else 0

        print(f"\r진행: [{bar}] {progress:.1f}%", end='')
        print(f" | 경과: {int(elapsed)}s / {self.duration_minutes * 60}s", end='')
        print(f" | CPU: {cpu_current:.1f}% | 메모리: {mem_current:.1f}%", end='')
        print(f" | 디스크 I/O: ↑{disk_write:.2f} ↓{disk_read:.2f} MB/s", end='')
        print(f" | 네트워크: ↑{net_sent:.2f} ↓{net_recv:.2f} MB/s", end='', flush=True)

    def run(self):
        """모니터링 실행 (Headless)"""
        print("데이터 수집 시작...\n")

        iteration = 0
        try:
            while datetime.now() < self.end_time:
                # 데이터 수집
                self.collect_data()

                # 상태 출력
                self.print_status()

                # 주기적으로 자세한 통계 출력
                iteration += 1
                if iteration % 30 == 0:  # 30번마다 (보통 1분마다)
                    print("\n" + "-" * 80)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 통계 스냅샷:")
                    print(f"  CPU: 평균 {np.mean(self.cpu_percent):.1f}% (최대 {np.max(self.cpu_percent):.1f}%)")
                    print(f"  메모리: 평균 {np.mean(self.memory_percent):.1f}% ({np.mean(self.memory_used_gb):.2f} GB)")
                    print(f"  디스크 I/O: 평균 읽기 {np.mean(self.disk_read_mb):.2f} MB/s, 쓰기 {np.mean(self.disk_write_mb):.2f} MB/s")
                    print(f"  네트워크: 평균 송신 {np.mean(self.net_sent_mb):.2f} MB/s, 수신 {np.mean(self.net_recv_mb):.2f} MB/s")
                    print("-" * 80)

                # 대기
                time.sleep(self.update_interval)

            print("\n\n" + "=" * 80)
            print("데이터 수집 완료!".center(80))
            print("=" * 80)

        except KeyboardInterrupt:
            print("\n\n사용자에 의해 중단되었습니다.")

    def generate_pdf_report(self, filename='system_monitoring_report.pdf'):
        """PDF 리포트 생성"""
        print(f"\nPDF 리포트 생성 중: {filename}")

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
            ['업데이트 간격', f'{self.update_interval} 초'],
            ['CPU 코어 수', str(self.cpu_count)],
            ['총 메모리', f'{psutil.virtual_memory().total / (1024**3):.2f} GB'],
            ['총 디스크 용량', f'{psutil.disk_usage("/").total / (1024**3):.2f} GB'],
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
        print(f"✓ PDF 리포트가 생성되었습니다: {filename}")

        # 임시 이미지 파일 삭제
        for img_file in ['chart_overview.png', 'chart_detailed.png']:
            if os.path.exists(img_file):
                os.remove(img_file)

    def save_charts(self):
        """차트를 이미지로 저장"""
        print("  - 차트 생성 중...")

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
        ax1.set_title('CPU 사용률', fontweight='bold', fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, 100)

        # 메모리
        ax2 = fig1.add_subplot(gs1[0, 1])
        ax2.plot(time_axis, self.memory_percent, 'r-', linewidth=2)
        ax2.fill_between(time_axis, self.memory_percent, alpha=0.3, color='red')
        ax2.set_ylabel('사용률 (%)', fontweight='bold')
        ax2.set_xlabel('시간 (분)', fontweight='bold')
        ax2.set_title('메모리 사용률', fontweight='bold', fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 100)

        # 디스크 I/O
        ax3 = fig1.add_subplot(gs1[0, 2])
        ax3.plot(time_axis, self.disk_read_mb, 'g-', linewidth=2, label='읽기')
        ax3.plot(time_axis, self.disk_write_mb, 'orange', linewidth=2, label='쓰기')
        ax3.set_ylabel('속도 (MB/s)', fontweight='bold')
        ax3.set_xlabel('시간 (분)', fontweight='bold')
        ax3.set_title('디스크 I/O', fontweight='bold', fontsize=12)
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 네트워크
        ax4 = fig1.add_subplot(gs1[1, 0])
        ax4.plot(time_axis, self.net_sent_mb, 'purple', linewidth=2, label='송신')
        ax4.plot(time_axis, self.net_recv_mb, 'cyan', linewidth=2, label='수신')
        ax4.set_ylabel('속도 (MB/s)', fontweight='bold')
        ax4.set_xlabel('시간 (분)', fontweight='bold')
        ax4.set_title('네트워크 트래픽', fontweight='bold', fontsize=12)
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
            ax5.set_title('코어별 평균 CPU 사용률', fontweight='bold', fontsize=12)
            ax5.set_xticks(cores_index)
            ax5.set_ylim(0, 100)

        # 디스크 사용률 파이 차트
        ax6 = fig1.add_subplot(gs1[1, 2])
        disk_labels = ['사용됨', '여유']
        disk_sizes = [np.mean(self.disk_percent), 100 - np.mean(self.disk_percent)]
        colors_disk = ['#ff6b6b', '#51cf66']
        wedges, texts, autotexts = ax6.pie(disk_sizes, labels=disk_labels, autopct='%1.1f%%',
               colors=colors_disk, startangle=90)
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        ax6.set_title('평균 디스크 사용률', fontweight='bold', fontsize=12)

        fig1.suptitle('시스템 모니터링 개요', fontsize=16, fontweight='bold')
        plt.savefig('chart_overview.png', dpi=150, bbox_inches='tight')
        plt.close(fig1)
        print("    ✓ 개요 차트 저장 완료")

        # 상세 차트
        fig2 = plt.figure(figsize=(16, 10))
        gs2 = GridSpec(3, 2, figure=fig2, hspace=0.3, wspace=0.3)

        # CPU + 메모리 복합
        ax1 = fig2.add_subplot(gs2[0, :])
        ax1.plot(time_axis, self.cpu_percent, 'b-', linewidth=2, label='CPU %')
        ax1.set_ylabel('CPU (%)', fontweight='bold', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.set_xlabel('시간 (분)', fontweight='bold')
        ax1.set_title('CPU 및 메모리 사용률 추이', fontweight='bold', fontsize=14)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, 100)

        ax1_twin = ax1.twinx()
        ax1_twin.plot(time_axis, self.memory_percent, 'r-', linewidth=2, label='메모리 %')
        ax1_twin.set_ylabel('메모리 (%)', fontweight='bold', color='r')
        ax1_twin.tick_params(axis='y', labelcolor='r')
        ax1_twin.set_ylim(0, 100)

        # 디스크 I/O 상세
        ax2 = fig2.add_subplot(gs2[1, 0])
        ax2.plot(time_axis, self.disk_read_mb, 'g-', linewidth=2, label='읽기')
        ax2.fill_between(time_axis, self.disk_read_mb, alpha=0.3, color='green')
        ax2.set_ylabel('읽기 속도 (MB/s)', fontweight='bold')
        ax2.set_xlabel('시간 (분)', fontweight='bold')
        ax2.set_title('디스크 읽기 I/O', fontweight='bold', fontsize=12)
        ax2.grid(True, alpha=0.3)

        ax3 = fig2.add_subplot(gs2[1, 1])
        ax3.plot(time_axis, self.disk_write_mb, 'orange', linewidth=2, label='쓰기')
        ax3.fill_between(time_axis, self.disk_write_mb, alpha=0.3, color='orange')
        ax3.set_ylabel('쓰기 속도 (MB/s)', fontweight='bold')
        ax3.set_xlabel('시간 (분)', fontweight='bold')
        ax3.set_title('디스크 쓰기 I/O', fontweight='bold', fontsize=12)
        ax3.grid(True, alpha=0.3)

        # 네트워크 상세
        ax4 = fig2.add_subplot(gs2[2, 0])
        ax4.plot(time_axis, self.net_sent_mb, 'purple', linewidth=2, label='송신')
        ax4.fill_between(time_axis, self.net_sent_mb, alpha=0.3, color='purple')
        ax4.set_ylabel('송신 속도 (MB/s)', fontweight='bold')
        ax4.set_xlabel('시간 (분)', fontweight='bold')
        ax4.set_title('네트워크 송신', fontweight='bold', fontsize=12)
        ax4.grid(True, alpha=0.3)

        ax5 = fig2.add_subplot(gs2[2, 1])
        ax5.plot(time_axis, self.net_recv_mb, 'cyan', linewidth=2, label='수신')
        ax5.fill_between(time_axis, self.net_recv_mb, alpha=0.3, color='cyan')
        ax5.set_ylabel('수신 속도 (MB/s)', fontweight='bold')
        ax5.set_xlabel('시간 (분)', fontweight='bold')
        ax5.set_title('네트워크 수신', fontweight='bold', fontsize=12)
        ax5.grid(True, alpha=0.3)

        fig2.suptitle('상세 분석 차트', fontsize=16, fontweight='bold')
        plt.savefig('chart_detailed.png', dpi=150, bbox_inches='tight')
        plt.close(fig2)
        print("    ✓ 상세 차트 저장 완료")

    def print_final_summary(self):
        """최종 요약 출력"""
        print("\n" + "=" * 80)
        print("최종 통계 요약".center(80))
        print("=" * 80)

        print(f"\n총 수집 데이터: {len(self.timestamps)}개")
        print(f"실제 모니터링 시간: {(self.timestamps[-1] - self.timestamps[0]).total_seconds():.1f}초")

        print("\n[ CPU ]")
        print(f"  평균: {np.mean(self.cpu_percent):.2f}%")
        print(f"  최소: {np.min(self.cpu_percent):.2f}%")
        print(f"  최대: {np.max(self.cpu_percent):.2f}%")

        print("\n[ 메모리 ]")
        print(f"  평균 사용률: {np.mean(self.memory_percent):.2f}%")
        print(f"  평균 사용량: {np.mean(self.memory_used_gb):.2f} GB")
        print(f"  최대 사용량: {np.max(self.memory_used_gb):.2f} GB")

        print("\n[ 디스크 I/O ]")
        print(f"  평균 읽기: {np.mean(self.disk_read_mb):.2f} MB/s")
        print(f"  평균 쓰기: {np.mean(self.disk_write_mb):.2f} MB/s")
        print(f"  최대 읽기: {np.max(self.disk_read_mb):.2f} MB/s")
        print(f"  최대 쓰기: {np.max(self.disk_write_mb):.2f} MB/s")

        print("\n[ 네트워크 ]")
        print(f"  평균 송신: {np.mean(self.net_sent_mb):.2f} MB/s")
        print(f"  평균 수신: {np.mean(self.net_recv_mb):.2f} MB/s")
        print(f"  최대 송신: {np.max(self.net_sent_mb):.2f} MB/s")
        print(f"  최대 수신: {np.max(self.net_recv_mb):.2f} MB/s")

        print("\n" + "=" * 80)


def main():
    """메인 함수"""
    # 모니터링 설정
    duration_minutes = 5  # 5분
    update_interval = 2    # 2초마다 업데이트

    # 모니터 생성
    monitor = SystemMonitor(duration_minutes=duration_minutes, update_interval=update_interval)

    # 모니터링 실행
    monitor.run()

    # 최종 요약
    monitor.print_final_summary()

    # PDF 리포트 생성
    monitor.generate_pdf_report('system_monitoring_report.pdf')

    print("\n✓ 모니터링이 완료되었습니다!")
    print(f"✓ 총 {len(monitor.timestamps)}개의 데이터 포인트가 수집되었습니다.")
    print(f"✓ PDF 리포트: system_monitoring_report.pdf")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
