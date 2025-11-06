#!/usr/bin/env python3
"""1분 테스트용 모니터링"""

import sys
sys.path.insert(0, '/home/user/solideo_25_1_test')

from system_monitor_headless import SystemMonitor

# 1분간 모니터링
monitor = SystemMonitor(duration_minutes=1, update_interval=2)
monitor.run()
monitor.generate_pdf_report('test_korean_report.pdf')
print("\n테스트 완료! test_korean_report.pdf 확인하세요.")
