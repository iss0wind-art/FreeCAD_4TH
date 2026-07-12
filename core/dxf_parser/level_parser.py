"""
level_parser.py — SL·EL 표고·단차 완전 파싱
=============================================
도면의 모든 수직 정보를 추출한다.

[추출 대상]
  - SL (설계 레벨): "B2F SL -9050", "SL+370" 등
  - EL (표고): "EL-8800" 등
  - 단차 (Level Difference): "단차 +50", "SL±0"
  - 피트 (PIT): "PIT -200", 엘리베이터 피트
  - 경사로 (RAMP): 진입 경사로 변화 구간

[출력]
  LevelSet — 층별 SL 값 + 단차 위치 목록
  이를 build_3d에 주입 → 균일 층고 탈피, 국부 단차 반영

[다음 사람에게]
  parse_dxf(path, clip)만 호출하면 된다.
  반환된 LevelSet.floor_sl['B2F'] = -9050 (mm)
  LevelSet.steps = [(x,y,'B2F SL -1800'), ...] — 단차 위치
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import ezdxf

from core.dxf_parser.entity_scanner import iter_all


# ─────────────────────────────────────────────────────────────
# 패턴
# ─────────────────────────────────────────────────────────────

_SL_PAT = re.compile(
    r'(?:(B[123]?F|PIT|[12]F|RF|지하\s*\d층)\s+)?'
    r'(?:SL|EL|표고|설계레벨)\s*'
    r'([+\-]?\s*\d[\d,\.]*)',
    re.IGNORECASE,
)
# "SL = GL. -9.05" 형식 — GL 기준 절대 표고 (m 단위, 인코딩 무관)
# %%P0 = ±0 (DXF 특수문자), 인코딩 깨져도 GL 숫자만 찾음
_GL_PAT = re.compile(
    r'SL\s*[^\n]{0,30}?=\s*GL\s*\.?\s*([+\-]?\d[\d\.]+)',
    re.IGNORECASE,
)
# "지하 2층 SL = GL. -9.05" 또는 한국어 레이블 포함 형식
_FLOOR_GL_PAT = re.compile(
    r'(지하\s*\d층|B[123]F)\s+SL[^\n]*?GL\s*\.?\s*([+\-]?\d[\d\.]+)',
    re.IGNORECASE,
)
# 층 레이블 없는 단순 GL: "= GL. -9.05" (SL 행에 있음)
_GL_SIMPLE_PAT = re.compile(
    r'=\s*GL\s*\.?\s*([+\-]\d[\d\.]+)',
    re.IGNORECASE,
)
_STEP_PAT = re.compile(r'단차|STEP\s*UP|STEP\s*DN|레벨\s*차|경사로|RAMP|PIT\s*하부',
                       re.IGNORECASE)
_PIT_PAT = re.compile(r'PIT|피트|E/?V\s*PIT', re.IGNORECASE)
_FLOOR_PAT = re.compile(r'B[123]F|PIT|[12]F|RF|지하\s*\d층', re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# 자료구조
# ─────────────────────────────────────────────────────────────

@dataclass
class LevelMark:
    """단일 표고 표기."""
    text: str
    x: float
    y: float
    value_mm: Optional[float] = None   # 파싱된 수치 (mm)
    floor_label: str = ''              # 'B2F', 'B1F', '1F' 등
    kind: str = 'SL'                   # 'SL' | 'STEP' | 'PIT' | 'RAMP'


@dataclass
class LevelSet:
    """도면에서 추출된 수직 정보 전체."""
    floor_sl: Dict[str, float] = field(default_factory=dict)
    # 예: {'B2F': -9050.0, 'B1F': -5600.0, '1F': 370.0}

    steps: List[LevelMark] = field(default_factory=list)
    # 국부 단차 — 위치와 값

    pits: List[LevelMark] = field(default_factory=list)
    # 피트 (엘리베이터 피트 등)

    all_marks: List[LevelMark] = field(default_factory=list)
    # 모든 표기 원본

    def summary(self) -> str:
        lines = ['[LevelSet]']
        lines.append(f'  층 SL: {self.floor_sl}')
        lines.append(f'  단차 {len(self.steps)}건, 피트 {len(self.pits)}건')
        lines.append(f'  전체 표기 {len(self.all_marks)}건')
        return '\n'.join(lines)

    def sl(self, floor: str) -> Optional[float]:
        """층 SL 반환. 없으면 None."""
        return self.floor_sl.get(floor)

    def floor_height(self, lower: str, upper: str) -> Optional[float]:
        """두 층 간 층고 = upper_SL - lower_SL."""
        lo = self.floor_sl.get(lower)
        hi = self.floor_sl.get(upper)
        if lo is None or hi is None:
            return None
        return hi - lo


# ─────────────────────────────────────────────────────────────
# 파싱 함수
# ─────────────────────────────────────────────────────────────

def parse_dxf(dxf_path: str, encoding: str = 'cp949',
              clip: Optional[Tuple[float,float,float,float]] = None) -> LevelSet:
    """DXF에서 모든 표고·단차 정보 추출.

    Args:
        dxf_path: DXF 파일 경로
        encoding: 인코딩 (한국 = cp949)
        clip: (xmin,ymin,xmax,ymax) 영역 제한

    Returns:
        LevelSet — 층 SL 딕셔너리 + 단차 목록
    """
    from core.dxf_parser.encoding_helper import safe_read_dxf
    doc = safe_read_dxf(dxf_path, default_encoding=encoding)
    msp = doc.modelspace()
    return parse_msp(msp, clip)


def parse_msp(msp, clip: Optional[Tuple[float,float,float,float]] = None) -> LevelSet:
    """modelspace에서 직접 파싱 (doc 재사용 시)."""
    result = LevelSet()
    floor_candidates: Dict[str, List[float]] = {}

    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if not txt or len(txt) > 100:
                continue

            pos = e.dxf.insert
            if clip and not (clip[0] <= pos.x <= clip[2] and
                             clip[1] <= pos.y <= clip[3]):
                continue

            # GL 기준 절대 표고 파싱 우선 — "지하 2층 SL = GL. -9.05"
            gl_match = _FLOOR_GL_PAT.search(txt) or _GL_PAT.search(txt)
            if gl_match and 'GL' in txt.upper():
                # group 인덱스 분기: FLOOR_GL_PAT는 그룹2, GL_PAT는 그룹1
                if _FLOOR_GL_PAT.search(txt):
                    m_fgl = _FLOOR_GL_PAT.search(txt)
                    floor_raw = (m_fgl.group(1) or '').strip()
                    gl_val_str = m_fgl.group(2).replace(',', '').replace(' ', '')
                else:
                    floor_raw = ''
                    gl_val_str = gl_match.group(1).replace(',', '').replace(' ', '')
                floor_label = _normalize_floor_label(floor_raw)
                try:
                    val_m = float(gl_val_str)
                    val_mm = val_m * 1000  # m → mm
                except ValueError:
                    val_mm = None
                mark = LevelMark(
                    text=txt, x=pos.x, y=pos.y,
                    value_mm=val_mm,
                    floor_label=floor_label,
                    kind='SL',
                )
                result.all_marks.append(mark)
                if val_mm is not None and floor_label:
                    floor_candidates.setdefault(floor_label, []).append(val_mm)
                elif val_mm is not None:
                    # 층 레이블 없는 GL값 → 별도 리스트 (나중에 층 추론)
                    floor_candidates.setdefault('_GL_UNLABELED', []).append(val_mm)
                continue  # GL 형식 처리 완료 → 아래 SL_PAT 중복 방지

            # SL/EL 파싱 (mm 단위 직접 표기)
            m_sl = _SL_PAT.search(txt)
            if m_sl:
                floor_label = _normalize_floor_label(m_sl.group(1) or '')
                raw_val = m_sl.group(2).replace(',', '').replace(' ', '')
                try:
                    val_raw = float(raw_val)
                    # 소수점 있고 절댓값 < 100 → m 단위 (예: -9.05 → -9050)
                    val_mm = val_raw * 1000 if (abs(val_raw) < 100 and '.' in raw_val) else val_raw
                except ValueError:
                    val_mm = None

                kind = 'SL'
                if _STEP_PAT.search(txt):
                    kind = 'STEP'
                elif _PIT_PAT.search(txt):
                    kind = 'PIT'

                mark = LevelMark(
                    text=txt, x=pos.x, y=pos.y,
                    value_mm=val_mm,
                    floor_label=floor_label,
                    kind=kind,
                )
                result.all_marks.append(mark)

                if val_mm is not None and floor_label:
                    floor_candidates.setdefault(floor_label, []).append(val_mm)

                if kind == 'STEP':
                    result.steps.append(mark)
                elif kind == 'PIT':
                    result.pits.append(mark)

            # 단차 전용 패턴 (SL 없이 단차만 표기된 경우)
            elif _STEP_PAT.search(txt):
                mark = LevelMark(
                    text=txt, x=pos.x, y=pos.y,
                    kind='STEP',
                )
                result.all_marks.append(mark)
                result.steps.append(mark)

        except Exception:
            pass

    # 층 SL 확정 — 가장 많이 나온 값 또는 중간값
    from collections import Counter
    for floor_label, vals in floor_candidates.items():
        if not vals or floor_label == '_GL_UNLABELED':
            continue
        cnt = Counter(round(v) for v in vals)
        result.floor_sl[floor_label] = float(cnt.most_common(1)[0][0])

    # 단차값이 floor_sl에 잘못 들어간 경우 먼저 제거 (GL 추론 전)
    # "B2F SL +1600" = 단차 표기 — 절댓값 아닌 상대값이므로 제거
    to_remove = [fl for fl, sl in list(result.floor_sl.items())
                 if ('B2F' in fl or 'B1F' in fl) and 0 < sl < 5000]
    for fl in to_remove:
        del result.floor_sl[fl]

    # GL 미레이블 값 → 크기 기준 자동 매핑 (단차 제거 후 실행)
    # 한국 아파트: B3F < B2F < B1F < 0 < 1F < 2F ...
    if '_GL_UNLABELED' in floor_candidates:
        unlabeled = floor_candidates['_GL_UNLABELED']
        _infer_floor_labels(unlabeled, result.floor_sl)

    return result


def _infer_floor_labels(values: list, existing_sl: dict) -> None:
    """GL 미레이블 값들을 크기 순서로 층에 매핑.

    가정: 지하 2층 → 지하 1층 → 1층 → 상위 층 순으로 증가.
    이미 floor_sl에 있는 값과 겹치면 스킵.
    """
    known_values = set(round(v) for v in existing_sl.values())
    unique = sorted(set(round(v) for v in values))
    basement_candidates = [v for v in unique if v < -4000]
    ground_pos = [v for v in unique if v >= 0]

    label_map = [
        (lambda v: v < -7000, 'B2F'),
        (lambda v: -7000 <= v < -1000, 'B1F'),
        (lambda v: -500 <= v < 1000, '1F'),
    ]
    for val in basement_candidates + ground_pos:
        if round(val) in known_values:
            continue
        for pred, label in label_map:
            if pred(val) and label not in existing_sl:
                existing_sl[label] = float(val)
                break


def _normalize_floor_label(raw: str) -> str:
    """'지하 2층' → 'B2F', '지하 1층' → 'B1F', '1F' → '1F' 등 정규화."""
    raw = raw.strip().upper()
    if not raw:
        return ''
    import re as _re
    m = _re.search(r'지하\s*(\d)층?', raw, _re.IGNORECASE)
    if m:
        return f'B{m.group(1)}F'
    for label in ('B2F', 'B1F', 'B3F', '1F', '2F', 'RF', 'PIT'):
        if label in raw:
            return label
    return raw


def merge_level_sets(*sets: LevelSet) -> LevelSet:
    """여러 도면의 LevelSet 병합 (층 SL은 값이 같아야 함)."""
    merged = LevelSet()
    for ls in sets:
        merged.all_marks.extend(ls.all_marks)
        merged.steps.extend(ls.steps)
        merged.pits.extend(ls.pits)
        for floor, sl in ls.floor_sl.items():
            if floor in merged.floor_sl:
                existing = merged.floor_sl[floor]
                if abs(existing - sl) > 10:
                    print(f'[WARN] {floor} SL 충돌: {existing} vs {sl} — 기존값 유지')
            else:
                merged.floor_sl[floor] = sl
    return merged
