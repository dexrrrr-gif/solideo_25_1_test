# 시스템 모니터링 코드 보안 및 품질 리뷰

**리뷰 날짜**: 2025-11-06
**리뷰 대상**: system_monitor.py, system_monitor_headless.py
**심각도 범례**: 🔴 높음 | 🟡 중간 | 🟢 낮음

---

## 목차
1. [보안 취약점](#1-보안-취약점)
2. [코드 품질 문제](#2-코드-품질-문제)
3. [기능적 문제](#3-기능적-문제)
4. [성능 문제](#4-성능-문제)
5. [유지보수성 문제](#5-유지보수성-문제)
6. [권장사항 요약](#6-권장사항-요약)

---

## 1. 보안 취약점

### 🔴 1.1 경고 메시지 전역 비활성화 (심각)
**위치**:
- `system_monitor.py:24`
- `system_monitor_headless.py:25`

**문제**:
```python
warnings.filterwarnings('ignore')
```

**보안 영향**:
- 모든 경고를 무시하여 중요한 보안 경고나 deprecated 함수 사용 경고를 놓칠 수 있음
- 라이브러리의 보안 패치나 업데이트 필요성을 인지하지 못할 수 있음
- 디버깅 시 문제의 근본 원인을 파악하기 어려움

**권장사항**:
- 특정 경고만 선택적으로 무시하거나 제거
- matplotlib 관련 특정 경고만 필터링

---

### 🔴 1.2 파일 경로 검증 부족 (심각)
**위치**:
- `system_monitor.py:354` - `generate_pdf_report()`
- `system_monitor.py:481, 486` - 이미지 파일 존재 확인
- `system_monitor_headless.py:202` - `generate_pdf_report()`

**문제**:
```python
def generate_pdf_report(self, filename='system_monitoring_report.pdf'):
    # filename 매개변수에 대한 검증 없음
    doc = SimpleDocTemplate(filename, ...)
```

**보안 영향**:
- **디렉토리 순회 공격** 가능: `../../../etc/passwd` 같은 경로 주입
- 임의의 시스템 파일 덮어쓰기 가능
- 민감한 디렉토리에 파일 생성 가능

**공격 시나리오**:
```python
monitor.generate_pdf_report('../../../../etc/cron.d/malicious')
```

**권장사항**:
- 파일명에서 경로 구분자(`/`, `\`, `..`) 검증
- 파일명을 basename으로 정규화
- 허용된 디렉토리 내에서만 파일 생성
- 파일명 화이트리스트 사용

---

### 🟡 1.3 임시 파일 보안 (중간)
**위치**:
- `system_monitor.py:496-498` - 임시 이미지 파일 삭제
- `system_monitor_headless.py:346-348`

**문제**:
```python
plt.savefig('chart_overview.png', dpi=150, bbox_inches='tight')
# ...
os.remove(img_file)
```

**보안 영향**:
- 현재 작업 디렉토리에 예측 가능한 이름의 임시 파일 생성
- **심볼릭 링크 공격** 가능: 악의적 사용자가 미리 심볼릭 링크 생성
- 멀티유저 환경에서 다른 사용자가 파일 읽기 가능
- 경쟁 조건(Race Condition): 파일 생성과 삭제 사이 시간 간격

**권장사항**:
- `tempfile.NamedTemporaryFile()` 사용
- 안전한 권한(0600)으로 파일 생성
- `with` 문을 사용한 자동 정리

---

### 🟡 1.4 하드코딩된 디스크 경로 (중간)
**위치**:
- `system_monitor.py:103` - `disk = psutil.disk_usage('/')`
- `system_monitor_headless.py:110`

**문제**:
```python
disk = psutil.disk_usage('/')  # 하드코딩된 루트 경로
```

**보안 영향**:
- Windows 환경에서 오류 발생 또는 잘못된 디스크 정보 수집
- 사용자가 모니터링하려는 디스크를 선택할 수 없음
- 특정 시스템 구성에서 권한 오류 발생 가능

**권장사항**:
- OS별로 적절한 경로 사용 (`os.path.expanduser('~')` 등)
- 설정 가능한 매개변수로 변경
- 여러 디스크 파티션 지원

---

### 🟡 1.5 입력 검증 부족 (중간)
**위치**:
- `system_monitor.py:29-37` - `__init__()` 매개변수
- `system_monitor_headless.py:30-38`

**문제**:
```python
def __init__(self, duration_minutes=5, update_interval=1):
    self.duration_minutes = duration_minutes  # 검증 없음
    self.update_interval = update_interval    # 검증 없음
```

**보안 영향**:
- **리소스 소진 공격**:
  - `duration_minutes=999999` → 메모리 초과 사용
  - `update_interval=0.001` → CPU 100% 사용
- 음수 값 입력 시 예상치 못한 동작
- `max_data_points` 계산 시 매우 큰 값 또는 0으로 나누기 오류

**공격 시나리오**:
```python
# 메모리 고갈 공격
monitor = SystemMonitor(duration_minutes=10000, update_interval=0.1)
# 약 600만 개의 데이터 포인트 생성 시도
```

**권장사항**:
- 매개변수 범위 검증 (최소/최대값)
- 타입 검증
- 계산된 `max_data_points`에 상한선 설정

---

### 🟢 1.6 권한 관련 문제 (낮음)
**위치**:
- `system_monitor.py:70-82` - `get_cpu_temperature()`
- psutil 함수 전반

**문제**:
```python
def get_cpu_temperature(self):
    temps = psutil.sensors_temperatures()  # root 권한 필요할 수 있음
```

**보안 영향**:
- 일부 시스템에서 센서 접근에 root 권한 필요
- 권한 부족 시 예외 발생 또는 None 반환
- README에 sudo 실행 권장하나 보안상 위험

**권장사항**:
- 최소 권한 원칙 적용
- 권한 오류 시 적절한 안내 메시지
- 센서 접근 실패해도 다른 기능은 계속 동작

---

### 🟢 1.7 정보 노출 (낮음)
**위치**:
- PDF 리포트 생성 전반
- 콘솔 출력

**문제**:
- 시스템 상세 정보(CPU 코어 수, 메모리 용량 등)가 PDF에 기록
- 네트워크 트래픽 패턴 노출

**보안 영향**:
- 시스템 핑거프린팅에 사용 가능
- PDF가 유출될 경우 공격자에게 유용한 정보 제공

**권장사항**:
- PDF 파일 암호화 옵션
- 민감 정보 포함 여부를 사용자가 선택 가능하도록

---

## 2. 코드 품질 문제

### 🔴 2.1 예외 처리 부족 (심각)
**위치**: 전체 코드

**문제**:
```python
# system_monitor.py:107
disk_io = psutil.disk_io_counters()  # 실패 시 예외 처리 없음

# system_monitor.py:54
self.prev_disk_io = psutil.disk_io_counters()  # None일 수 있음
```

**영향**:
- psutil 함수 실패 시 프로그램 크래시
- `disk_io_counters()`가 None 반환 시 이후 연산 오류
- 네트워크/디스크 접근 불가 시스템에서 즉시 종료

**발생 가능한 예외**:
- `PermissionError`: 권한 부족
- `FileNotFoundError`: 센서 파일 없음
- `psutil.AccessDenied`: 특정 정보 접근 거부

**권장사항**:
- 모든 psutil 호출을 try-except로 감싸기
- 실패 시 기본값 반환 또는 해당 메트릭 건너뛰기
- 로깅 추가

---

### 🟡 2.2 빈 컬렉션 처리 부족 (중간)
**위치**:
- `system_monitor.py:274-301` - 통계 계산
- `system_monitor_headless.py:275-309`

**문제**:
```python
# deque가 비어있을 때 IndexError 또는 ValueError 발생 가능
current_stats = [
    ['CPU (%)', f'{self.cpu_percent[-1]:.1f}',  # IndexError if empty
     f'{np.mean(self.cpu_percent):.1f}',        # RuntimeWarning if empty
     f'{np.min(self.cpu_percent):.1f}',         # ValueError if empty
     f'{np.max(self.cpu_percent):.1f}'],
]
```

**영향**:
- 데이터 수집 전 또는 실패 시 크래시
- `np.mean([])` → RuntimeWarning 발생
- `np.min([])` / `np.max([])` → ValueError 발생

**권장사항**:
- 통계 계산 전 길이 확인
- 빈 컬렉션에 대한 기본값 반환
- `if len(self.cpu_percent) > 0:` 체크 추가

---

### 🟡 2.3 리소스 정리 불완전 (중간)
**위치**:
- `system_monitor.py:342-352` - `run()` 메서드
- matplotlib figures

**문제**:
```python
def run(self):
    fig = self.create_figure()
    ani = animation.FuncAnimation(...)
    try:
        plt.show(block=True)
        while datetime.now() < self.end_time:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
    finally:
        plt.close('all')
```

**영향**:
- `ani` 변수가 사용되지 않아 가비지 컬렉션 대상이 될 수 있음
- 예외 발생 시 일부 리소스가 정리되지 않을 수 있음
- PDF 생성 중 오류 발생 시 임시 파일이 남을 수 있음

**권장사항**:
- Context manager 사용
- 명시적 리소스 정리
- `ani` 변수를 인스턴스 변수로 저장

---

### 🟡 2.4 에러 메시지 부족 (중간)
**위치**: 전체 코드

**문제**:
- 대부분의 오류 상황에서 조용히 실패 (Silent Failure)
- 사용자에게 오류 원인 알림 없음

**예시**:
```python
# system_monitor.py:70-82
def get_cpu_temperature(self):
    try:
        temps = psutil.sensors_temperatures()
        # ...
        return None  # 왜 None인지 사용자가 알 수 없음
    except (AttributeError, KeyError):
        return None  # 예외 발생 시 로그 없음
```

**권장사항**:
- 로깅 모듈 사용
- 중요한 오류는 사용자에게 알림
- 디버그 모드 옵션 추가

---

### 🟡 2.5 매직 넘버 사용 (중간)
**위치**: 전체 코드

**문제**:
```python
# system_monitor.py:193-198
if val > 80:
    bar.set_color('red')
elif val > 60:
    bar.set_color('orange')

# system_monitor.py:93
cpu_pct = psutil.cpu_percent(interval=0.1)

# system_monitor_headless.py:183
if iteration % 30 == 0:
```

**영향**:
- 코드 가독성 저하
- 값의 의미 불명확
- 변경 시 여러 곳 수정 필요

**권장사항**:
- 상수로 정의
```python
CPU_CRITICAL_THRESHOLD = 80
CPU_WARNING_THRESHOLD = 60
CPU_SAMPLE_INTERVAL = 0.1
STATS_DISPLAY_INTERVAL = 30
```

---

## 3. 기능적 문제

### 🔴 3.1 크로스 플랫폼 호환성 부족 (심각)
**위치**:
- `system_monitor.py:103` - 디스크 경로
- `system_monitor_headless.py:110`

**문제**:
```python
disk = psutil.disk_usage('/')  # Windows에서 오류
```

**영향**:
- Windows에서 실행 시 오류 발생 또는 잘못된 정보
- macOS에서는 작동하나 사용자가 원하는 디스크가 아닐 수 있음

**권장사항**:
```python
import platform
if platform.system() == 'Windows':
    disk_path = 'C:\\'
else:
    disk_path = '/'
```

---

### 🟡 3.2 시간 동기화 문제 (중간)
**위치**:
- `system_monitor.py:86-134` - `collect_data()`

**문제**:
```python
current_time = time.time()
time_diff = current_time - self.prev_time
# ...
self.timestamps.append(datetime.now())  # datetime.now()와 time.time() 혼용
```

**영향**:
- 시간 계산 불일치 가능
- 시스템 시간 변경 시 문제 발생

**권장사항**:
- 일관된 시간 함수 사용
- `time.monotonic()` 사용 권장 (시스템 시간 변경 영향 안받음)

---

### 🟡 3.3 데이터 정확성 문제 (중간)
**위치**:
- `system_monitor.py:93-95` - CPU 측정

**문제**:
```python
cpu_pct = psutil.cpu_percent(interval=0.1)
self.cpu_percent.append(cpu_pct)
self.cpu_per_core.append(psutil.cpu_percent(interval=0.1, percpu=True))
```

**영향**:
- CPU 측정을 두 번 수행 (0.1초씩 총 0.2초)
- 각 측정이 다른 시간 구간의 데이터
- 전체 CPU와 코어별 CPU가 일치하지 않을 수 있음
- `update_interval`이 짧을 때 대부분의 시간을 CPU 측정에 사용

**권장사항**:
- 한 번의 호출로 전체 및 코어별 데이터 수집
- interval을 0으로 설정하여 이전 호출 이후 누적값 사용

---

### 🟡 3.4 GUI 버전의 종료 로직 문제 (중간)
**위치**:
- `system_monitor.py:342-352` - `run()`

**문제**:
```python
try:
    plt.show(block=True)

    # 종료 대기
    while datetime.now() < self.end_time:
        time.sleep(1)
```

**영향**:
- `plt.show(block=True)` 이후 코드는 창이 닫힐 때까지 실행되지 않음
- `while` 루프가 의미 없음 (이미 5분이 지났거나 창이 닫힘)
- 사용자가 창을 닫으면 PDF 생성 전에 종료

**권장사항**:
- 타이머 기반 종료 로직 개선
- 애니메이션 종료 후 자동으로 PDF 생성

---

### 🟢 3.5 deque maxlen 제한 (낮음)
**위치**:
- `system_monitor.py:40-50` - deque 선언

**문제**:
```python
self.timestamps = deque(maxlen=self.max_data_points)
```

**영향**:
- 모니터링 시간이 길어지면 초기 데이터 손실
- 사용자가 예상치 못한 데이터 손실

**권장사항**:
- maxlen을 더 크게 설정하거나 제거
- 또는 명시적으로 사용자에게 알림

---

## 4. 성능 문제

### 🟡 4.1 불필요한 반복 작업 (중간)
**위치**:
- `system_monitor.py:156-328` - `update_plot()`

**문제**:
```python
def update_plot(self, frame):
    # 모든 서브플롯 클리어
    for ax in [self.ax_cpu, self.ax_cpu_cores, ...]:
        ax.clear()

    # 매번 전체 재렌더링
```

**영향**:
- 매 업데이트마다 전체 플롯을 다시 그림
- CPU 사용률 증가
- 대용량 데이터에서 성능 저하

**권장사항**:
- 블리팅(blitting) 사용하여 변경된 부분만 업데이트
- 데이터만 업데이트하고 축/레이블은 재사용

---

### 🟡 4.2 중복 계산 (중간)
**위치**:
- 통계 계산 부분

**문제**:
```python
# 같은 계산을 여러 번 수행
np.mean(self.cpu_percent)  # 여러 곳에서 반복
np.max(self.cpu_percent)
```

**권장사항**:
- 계산 결과를 캐싱
- 또는 한 번만 계산하여 변수에 저장

---

### 🟢 4.3 메모리 사용 (낮음)
**위치**:
- deque 저장

**문제**:
- 각 deque에 최대 수천~수만 개의 데이터 포인트 저장
- 10개의 deque × 수만 포인트 = 상당한 메모리

**영향**:
- 장시간 실행 시 메모리 사용량 증가
- 저사양 시스템에서 문제 가능

**권장사항**:
- 데이터 다운샘플링 고려
- 디스크에 주기적으로 저장하고 메모리 정리

---

## 5. 유지보수성 문제

### 🔴 5.1 코드 중복 (심각)
**위치**:
- `system_monitor.py`와 `system_monitor_headless.py`

**문제**:
- 두 파일이 95% 이상 동일한 코드
- 총 1100줄 중 약 1000줄이 중복

**영향**:
- 버그 수정 시 두 파일 모두 수정 필요
- 유지보수 비용 2배
- 불일치 발생 가능

**권장사항**:
- 공통 로직을 기본 클래스로 추출
- GUI/Headless를 상속으로 구현
- 또는 플래그로 모드 선택

---

### 🟡 5.2 하드코딩된 설정값 (중간)
**위치**:
- `main()` 함수들

**문제**:
```python
def main():
    duration_minutes = 5  # 하드코딩
    update_interval = 2   # 하드코딩
```

**영향**:
- 사용자가 값을 변경하려면 코드 수정 필요
- 명령줄 인자 없음

**권장사항**:
- argparse를 사용한 CLI 인터페이스
- 설정 파일 지원

---

### 🟡 5.3 문서화 부족 (중간)
**위치**: 전체 코드

**문제**:
- Docstring이 일부 함수에만 존재
- 복잡한 로직에 대한 주석 부족
- 타입 힌트 없음

**권장사항**:
- 모든 public 메서드에 docstring 추가
- 타입 힌트 추가
- 복잡한 계산에 주석 추가

---

### 🟡 5.4 테스트 코드 부재 (중간)
**문제**:
- 단위 테스트 없음
- 통합 테스트 없음

**영향**:
- 리팩토링 시 기능 검증 어려움
- 회귀 버그 발견 어려움

**권장사항**:
- pytest를 사용한 단위 테스트
- mock을 사용한 psutil 함수 테스트

---

## 6. 권장사항 요약

### 즉시 수정 필요 (우선순위: 높음)
1. ✅ **경고 필터링 제거 또는 선택적 적용**
2. ✅ **파일명 검증 추가** (디렉토리 순회 방지)
3. ✅ **입력 매개변수 검증** (DoS 방지)
4. ✅ **예외 처리 추가** (크래시 방지)
5. ✅ **빈 컬렉션 처리** (IndexError/ValueError 방지)
6. ✅ **코드 중복 제거** (리팩토링)

### 중기 개선 사항 (우선순위: 중간)
1. 🔄 **임시 파일 보안 강화** (tempfile 사용)
2. 🔄 **크로스 플랫폼 지원** (Windows 호환)
3. 🔄 **로깅 시스템 구축**
4. 🔄 **설정 파일 및 CLI 인자 지원**
5. 🔄 **타입 힌트 및 문서화 개선**

### 장기 개선 사항 (우선순위: 낮음)
1. 📋 **성능 최적화** (블리팅, 캐싱)
2. 📋 **테스트 코드 작성**
3. 📋 **데이터 다운샘플링**
4. 📋 **PDF 암호화 옵션**
5. 📋 **다국어 지원**

---

## 보안 체크리스트

- [ ] 사용자 입력 검증 (파일명, 경로, 매개변수)
- [ ] 경로 순회 공격 방지
- [ ] 임시 파일 안전하게 생성/삭제
- [ ] 리소스 소진 공격 방지
- [ ] 예외 처리 및 에러 메시지
- [ ] 최소 권한 원칙 적용
- [ ] 민감 정보 보호
- [ ] 로깅 및 모니터링
- [ ] 의존성 버전 고정 및 보안 패치
- [ ] 코드 정적 분석 도구 사용

---

## 추가 권장 도구

### 보안 스캐닝
```bash
# 취약점 스캔
bandit -r system_monitor.py system_monitor_headless.py

# 의존성 취약점 확인
safety check -r requirements.txt

# 정적 분석
pylint system_monitor.py
flake8 system_monitor.py
```

### 코드 품질
```bash
# 타입 체크
mypy system_monitor.py

# 복잡도 측정
radon cc system_monitor.py -a

# 중복 코드 검출
pylint --disable=all --enable=duplicate-code system_monitor.py system_monitor_headless.py
```

---

## 결론

이 코드는 **기능적으로는 동작하지만 보안 및 품질 측면에서 여러 개선이 필요**합니다.

### 주요 보안 위험:
1. 파일 경로 검증 부족으로 인한 **디렉토리 순회 공격** 가능성
2. 입력 검증 부족으로 인한 **리소스 소진 공격** 가능성
3. 예외 처리 부족으로 인한 **서비스 거부** 가능성

### 주요 품질 문제:
1. 95% 이상의 **코드 중복**
2. **예외 처리 부재**로 인한 불안정성
3. **크로스 플랫폼 호환성** 부족

### 권장 조치:
프로덕션 환경에 배포하기 전에 **최소한 우선순위 높음 항목들을 모두 수정**해야 합니다. 특히 파일 경로 검증과 입력 검증은 보안에 직접적인 영향을 미치므로 즉시 수정이 필요합니다.

---

**리뷰어**: Claude Code Assistant
**리뷰 버전**: v1.0
**다음 리뷰 예정**: 코드 수정 후
