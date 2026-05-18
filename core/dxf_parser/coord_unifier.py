"""
coord_unifier.py — 다중 DXF 도면 좌표 통일
============================================
여러 도면 파일을 하나의 절대 좌표계로 통일.

[왜 필요한가]
한국 건설 도면은 동별·층별·용도별로 파일이 분리된다.
101동 도면과 지하주차장 도면은 서로 다른 좌표계를 사용한다.
FreeCAD에서 합치면 왼쪽·오른쪽으로 분리돼 보인다 (v3 문제 4).

[해결 원리]
공통 물리 기준점 → 두 도면의 동일 점 → 오프셋 계산 → 전체 이동

[전략 우선순위]
  1. E/V 코어 SW 모서리 (F-1 패턴) — 권장, 건물 전층 불변
  2. 격자선 교점 (X1·Y1 교점) — E/V 없을 때
  3. 특정 TEXT 검색 ('101', '기준점' 등) — 상황별
  4. 수동 앵커 지정 — 최후 수단

[사용법]
    unifier = CoordUnifier()
    unifier.add('dong101', dong101_dxf_path, dong='101')
    unifier.add('basement', basement_dxf_path, dong='B2F',
                dong_clip=(247250, -1390677, 877250, -945177))
    transforms = unifier.unify(reference='dong101')

    # 지하주차장 좌표 → 통일 좌표
    ux, uy = unifier.apply('basement', raw_x, raw_y)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import ezdxf

from core.dxf_parser.ev_detector import (
    AnchorPoint, TextLabelEVDetector, GridAnchorDetector,
    _entity_bbox,
)
from core.dxf_parser.entity_scanner import iter_all


# ─────────────────────────────────────────────────────────────
# 변환 결과
# ─────────────────────────────────────────────────────────────

@dataclass
class DrawingTransform:
    """도면 raw 좌표 → 통일 좌표계 변환."""
    drawing_id: str
    tx: float = 0.0
    ty: float = 0.0
    rotation_deg: float = 0.0  # 현재 평행이동만 — 회전은 Phase 2
    scale: float = 1.0
    strategy: str = ""
    anchor_label: str = ""
    confidence: float = 1.0

    def apply(self, x: float, y: float) -> Tuple[float, float]:
        """raw (x, y) → 통일 좌표."""
        if self.rotation_deg != 0:
            rad = math.radians(self.rotation_deg)
            xr = x * math.cos(rad) - y * math.sin(rad)
            yr = x * math.sin(rad) + y * math.cos(rad)
            x, y = xr, yr
        return (x * self.scale + self.tx, y * self.scale + self.ty)

    def apply_pts(self, pts: List[Tuple[float,float]]) -> List[Tuple[float,float]]:
        return [self.apply(x, y) for x, y in pts]

    def summary(self) -> str:
        return (f'{self.drawing_id}: tx={self.tx:.0f} ty={self.ty:.0f} '
                f'strategy={self.strategy} conf={self.confidence:.2f}')


# ─────────────────────────────────────────────────────────────
# 좌표 통일기
# ─────────────────────────────────────────────────────────────

class CoordUnifier:
    """여러 DXF 도면을 단일 좌표계로 통일.

    add() → unify() → apply() 순서로 사용.

    Examples:
        unifier = CoordUnifier()
        unifier.add('dong101', DONG_DXF, dong='101')
        unifier.add('b2f', BSMNT_DXF, dong='지하주차장',
                    dong_clip=(247250, -1390677, 877250, -945177))
        transforms = unifier.unify(reference='dong101')
        for did, tr in transforms.items():
            print(tr.summary())
        ux, uy = unifier.apply('b2f', raw_x, raw_y)
    """

    def __init__(self):
        self._entries: Dict[str, dict] = {}
        self._transforms: Dict[str, DrawingTransform] = {}

    def add(self, drawing_id: str, dxf_path: str,
            dong: str = '', floor: object = 0, sheet_id: str = '',
            dong_clip: Optional[Tuple[float,float,float,float]] = None,
            encoding: str = 'auto',
            manual_anchor: Optional[Tuple[float,float]] = None) -> 'CoordUnifier':
        """도면 등록.

        Args:
            drawing_id: 식별자 (예: 'dong101', 'b2f')
            dxf_path: DXF 파일 경로
            dong: 동 이름 (예: '101', '지하주차장')
            dong_clip: 해당 동 영역 제한 (xmin,ymin,xmax,ymax)
            encoding: 'auto'(utf-8/cp949 자동) | 'cp949' | 'utf-8'
            manual_anchor: (x, y) 수동 앵커 — 자동 검출 실패 시 사용
        """
        if encoding == 'auto':
            from core.dxf_parser.safe_reader import safe_readfile
            doc = safe_readfile(dxf_path)
        else:
            doc = ezdxf.readfile(dxf_path, encoding=encoding)
        # manual_anchor가 있으면 최우선 적용
        if manual_anchor is not None:
            anchor = AnchorPoint(
                x=manual_anchor[0], y=manual_anchor[1],
                label='manual', strategy='manual', confidence=1.0,
            )
        else:
            anchor = self._auto_detect(doc, dong, floor, sheet_id, dong_clip)

        self._entries[drawing_id] = {
            'path': dxf_path,
            'doc': doc,
            'anchor': anchor,
            'dong': dong,
        }

        strat = anchor.strategy if anchor else 'none'
        conf = f'{anchor.confidence:.2f}' if anchor else '-'
        print(f'[CoordUnifier] {drawing_id}: strategy={strat} conf={conf} '
              + (f'({anchor.x:.0f},{anchor.y:.0f})' if anchor else '(no anchor)'))
        return self

    def add_text_anchor(self, drawing_id: str, search_text: str,
                        encoding: str = 'auto') -> 'CoordUnifier':
        """특정 TEXT 검색으로 앵커 설정 (예: '101', '기준점').

        v3에서 지하주차장 도면의 "101" TEXT를 101동 위치 기준점으로 사용한 방식.
        """
        entry = self._entries.get(drawing_id)
        if entry is None:
            raise KeyError(f'{drawing_id!r} 미등록. add() 먼저 호출.')

        doc = entry['doc']
        msp = doc.modelspace()
        hits = []
        import re
        pat = re.compile(re.escape(search_text), re.IGNORECASE)

        for e in iter_all(msp):
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            try:
                txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
                if pat.search(txt):
                    pos = e.dxf.insert
                    hits.append((pos.x, pos.y))
            except Exception:
                pass

        if not hits:
            print(f'[WARN] {drawing_id}: TEXT "{search_text}" 미발견')
            return self

        cx = sum(x for x, y in hits) / len(hits)
        cy = sum(y for x, y in hits) / len(hits)
        entry['anchor'] = AnchorPoint(
            x=cx, y=cy,
            label=f'text_{search_text}',
            strategy='text_search',
            confidence=0.9 if len(hits) == 1 else 0.7,
        )
        print(f'[CoordUnifier] {drawing_id}: TEXT "{search_text}" '
              f'{len(hits)}건 → ({cx:.0f},{cy:.0f})')
        return self

    def unify(self, reference: str) -> Dict[str, DrawingTransform]:
        """기준 도면 기준으로 모든 변환 계산.

        기준 도면: 항등 변환 (tx=ty=0).
        나머지: anchor가 기준 anchor와 일치하도록 이동.

        Returns:
            {drawing_id: DrawingTransform}
        """
        if reference not in self._entries:
            raise KeyError(f'기준 도면 {reference!r} 미등록')

        ref_anchor = self._entries[reference]['anchor']
        if ref_anchor is None:
            raise ValueError(f'기준 도면 {reference!r} anchor 없음. '
                             f'add() 시 manual_anchor 또는 add_text_anchor() 사용.')

        ref_x, ref_y = ref_anchor.x, ref_anchor.y
        self._transforms = {}

        for did, info in self._entries.items():
            anchor = info['anchor']
            if anchor is None:
                print(f'[WARN] {did}: anchor 없음 → 항등 변환')
                tr = DrawingTransform(drawing_id=did, strategy='none', confidence=0.0)
            elif did == reference:
                tr = DrawingTransform(
                    drawing_id=did, tx=0.0, ty=0.0,
                    strategy='reference', confidence=1.0,
                    anchor_label=reference,
                )
            else:
                tr = DrawingTransform(
                    drawing_id=did,
                    tx=ref_x - anchor.x,
                    ty=ref_y - anchor.y,
                    strategy=anchor.strategy,
                    confidence=anchor.confidence,
                    anchor_label=anchor.label,
                )

            self._transforms[did] = tr
            print(f'[CoordUnifier.unify] {tr.summary()}')

        return dict(self._transforms)

    def apply(self, drawing_id: str, x: float, y: float) -> Tuple[float, float]:
        """도면 raw 좌표 → 통일 좌표."""
        tr = self._get_transform(drawing_id)
        return tr.apply(x, y)

    def apply_pts(self, drawing_id: str,
                  pts: List[Tuple[float,float]]) -> List[Tuple[float,float]]:
        tr = self._get_transform(drawing_id)
        return tr.apply_pts(pts)

    def get_doc(self, drawing_id: str):
        """등록된 도면 doc 반환."""
        return self._entries[drawing_id]['doc']

    def get_anchor(self, drawing_id: str) -> Optional[AnchorPoint]:
        return self._entries[drawing_id]['anchor']

    def report(self) -> str:
        lines = ['[CoordUnifier 변환 보고]']
        for did, tr in self._transforms.items():
            lines.append(f'  {tr.summary()}')
        return '\n'.join(lines)

    # ─────────────────────────────────────────────────────────
    # 검증 — 두 도면 공통 기둥이 통일 후 겹치는지
    # ─────────────────────────────────────────────────────────

    def verify_overlap(self, did_a: str, did_b: str,
                       columns_a: List[Tuple[float,float]],
                       columns_b: List[Tuple[float,float]],
                       tol_mm: float = 500.0) -> dict:
        """두 도면 기둥 좌표를 통일 후 겹치는 비율 검증.
        
        Returns:
            {'matched': int, 'total_a': int, 'total_b': int, 'rate': float, 'avg_dist': float}
        """
        ua = self.apply_pts(did_a, columns_a)
        ub = self.apply_pts(did_b, columns_b)

        matched = 0
        distances = []
        for ax, ay in ua:
            best_d = 1e9
            for bx, by in ub:
                d = math.hypot(ax-bx, ay-by)
                if d < best_d: best_d = d
            
            if best_d < tol_mm:
                matched += 1
                distances.append(best_d)

        total_a = len(ua)
        rate = matched / total_a if total_a else 0.0
        avg_dist = sum(distances) / len(distances) if distances else 0.0
        
        return {
            'matched': matched,
            'total_a': total_a,
            'total_b': len(ub),
            'rate': round(rate, 3),
            'avg_dist': round(avg_dist, 1),
            'distances': sorted(distances)[:10] # 상위 10개 오차
        }

    # ─────────────────────────────────────────────────────────
    # 내부
    # ─────────────────────────────────────────────────────────

    def _auto_detect(self, doc, dong, floor, sheet_id,
                     clip) -> Optional[AnchorPoint]:
        """자동 앵커 검출 — E/V → 격자 순 폴백."""
        # 전략 1: E/V 코어
        detector = TextLabelEVDetector(dong_clip=clip)
        try:
            ev = detector.detect(doc, dong, floor, sheet_id)
            if ev is not None and ev.confidence >= 0.5:
                return AnchorPoint(
                    x=ev.sw_corner[0], y=ev.sw_corner[1],
                    label=f'ev_sw_{dong}',
                    strategy='ev_core',
                    confidence=ev.confidence,
                )
        except Exception as err:
            print(f'[WARN] EV 검출 오류: {err}')

        # 전략 2: 격자 교점
        grid_det = GridAnchorDetector(dong_clip=clip)
        anchor = grid_det.detect(doc, dong, floor, sheet_id)
        return anchor

    def _get_transform(self, drawing_id: str) -> DrawingTransform:
        if not self._transforms:
            raise RuntimeError('unify() 먼저 호출.')
        tr = self._transforms.get(drawing_id)
        if tr is None:
            raise KeyError(f'{drawing_id!r} 미등록.')
        return tr
