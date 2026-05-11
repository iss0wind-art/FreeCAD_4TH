"""
pipeline.py — 골조 파싱 완전 파이프라인
==========================================
다음 사람이 호출할 단일 진입점.
DXF 파일 경로 → 골조 데이터 (기둥·보·슬라브·전단벽·격자·표고)

[사용법]
    from core.dxf_parser.pipeline import parse_structural_frame, FrameData

    # 1. 도면 파싱
    frame = parse_structural_frame(
        dxf_path="path/to/drawing.dxf",
        clip=(xmin, ymin, xmax, ymax),  # 관심 영역 (선택)
    )

    # 2. 결과 확인
    print(frame.summary())

    # 3. 데이터 활용
    frame.columns   → 기둥 목록
    frame.beams     → 보 목록
    frame.shear_walls → 전단벽 목록
    frame.slab_outlines → 슬라브 외곽
    frame.level_set → 층고·SL
    frame.grid      → 격자선
    frame.to_json() → JSON 직렬화

[원칙]
  도면에 있으면 도면에서 읽는다. 추정 없음.
  조적·마감·창호·설비·가구 = 무시.
  골조(기둥·보·슬라브·전단벽·코어)만.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import ezdxf

from core.dxf_parser.structural_extractor import (
    StructuralExtractor, StructuralData, ColumnPrim, BeamLine,
)
from core.dxf_parser.full_extractor import SlabOutline
from core.dxf_parser.level_parser import parse_dxf as parse_levels, LevelSet
from core.dxf_parser.grid_extractor import extract_grid, StructuralGrid
from core.dxf_parser.step_zone import parse_step_zones, StepZoneMap
from core.line_pairing import WallPair


# ─────────────────────────────────────────────────────────────
# 파이프라인 출력 자료구조
# ─────────────────────────────────────────────────────────────

@dataclass
class FrameData:
    """골조 파싱 완전 결과."""
    source_dxf: str = ''
    clip: Optional[Tuple] = None

    # 구조 부재
    columns: List[ColumnPrim] = field(default_factory=list)
    beams: List[BeamLine] = field(default_factory=list)
    slab_outlines: List[SlabOutline] = field(default_factory=list)
    shear_walls: List[WallPair] = field(default_factory=list)

    # 수직 정보
    level_set: Optional[LevelSet] = None
    step_zones: Optional[StepZoneMap] = None

    # 기준점
    grid: Optional[StructuralGrid] = None

    def summary(self) -> str:
        total_beam_vol = sum(b.volume_m3 for b in self.beams)
        lines = [
            f'[FrameData] {self.source_dxf[:60]}',
            f'  기둥 {len(self.columns)}개 | 보 {len(self.beams)}개 ({total_beam_vol:.1f}m3) | '
            f'슬라브외곽 {len(self.slab_outlines)}개 | 전단벽 {len(self.shear_walls)}개',
        ]
        if self.level_set:
            lines.append(f'  층 SL: {self.level_set.floor_sl}')
        if self.grid:
            lines.append(f'  {self.grid.summary()}')
        if self.slab_outlines:
            best = self.slab_outlines[0]
            lines.append(f'  최대 슬라브 외곽: {best.area_m2:.0f}m² ({len(best.pts)}점)')
        return '\n'.join(lines)

    def to_json(self, indent: int = 2) -> str:
        """JSON 직렬화 (build_3d에 주입 가능한 형식)."""
        def col_dict(c: ColumnPrim) -> dict:
            return {'cx': c.cx, 'cy': c.cy, 'w': abs(c.w), 'h': abs(c.h),
                    'source': c.source, 'layer': c.layer}

        def beam_dict(b: BeamLine) -> dict:
            return {'symbol': b.symbol, 'x0': b.x0, 'y0': b.y0, 'x1': b.x1, 'y1': b.y1,
                    'length': round(b.length), 'width': b.width, 'height': b.height}

        def slab_dict(s: SlabOutline) -> dict:
            return {'symbol': s.symbol, 'area_m2': round(s.area_m2, 1), 'pts_count': len(s.pts),
                    'pts': [[round(x), round(y)] for x, y in s.pts],
                    'layer': s.layer}

        def wall_dict(w: WallPair) -> dict:
            return {'p1': list(w.centerline_p1), 'p2': list(w.centerline_p2),
                    'thickness': round(w.thickness), 'length': round(w.overlap_length)}

        data: Dict[str, Any] = {
            'source': self.source_dxf,
            'clip': list(self.clip) if self.clip else None,
            'columns': [col_dict(c) for c in self.columns],
            'beams': [beam_dict(b) for b in self.beams],
            'slab_outlines': [slab_dict(s) for s in self.slab_outlines[:5]],
            'shear_walls': [wall_dict(w) for w in self.shear_walls],
        }
        if self.level_set:
            data['level_set'] = {
                'floor_sl': self.level_set.floor_sl,
                'step_count': len(self.level_set.steps),
            }
        if self.grid:
            data['grid'] = {
                'x_coords': self.grid.x_coords[:20],
                'y_coords': self.grid.y_coords[:20],
                'rotation_deg': self.grid.rotation_deg,
                'spans_x': sorted(set(round(s) for s in self.grid.spans_x))[:10],
                'spans_y': sorted(set(round(s) for s in self.grid.spans_y))[:10],
            }
        return json.dumps(data, ensure_ascii=False, indent=indent)


# ─────────────────────────────────────────────────────────────
# 파이프라인 메인 함수
# ─────────────────────────────────────────────────────────────

def parse_structural_frame(
    dxf_path: str,
    clip: Optional[Tuple[float,float,float,float]] = None,
    encoding: str = 'auto',
    extract_levels: bool = True,
    extract_grid: bool = True,
    extract_steps: bool = True,
    min_slab_area_m2: float = 100.0,
    shear_max_thickness: float = 500.0,
) -> FrameData:
    """골조 파싱 완전 파이프라인.

    Args:
        dxf_path: DXF 파일 경로
        clip: (xmin,ymin,xmax,ymax) 관심 영역 (None=전체)
        encoding: 'auto'(utf-8/cp949 자동, 기본) | 'cp949' | 'utf-8'
        extract_levels: 층고·SL 파싱 여부
        extract_grid: 격자선 추출 여부
        extract_steps: 단차 구역 추출 여부
        min_slab_area_m2: 슬라브 최소 면적 (m²)
        shear_max_thickness: 전단벽 최대 두께 (mm)

    Returns:
        FrameData — 골조 데이터 전체
    """
    # 1. DXF 로드
    if encoding == 'auto':
        from core.dxf_parser.safe_reader import safe_readfile
        doc = safe_readfile(dxf_path)
    else:
        doc = ezdxf.readfile(dxf_path, encoding=encoding)

    # ── [개선] 1차 목표(80%) 달성을 위한 좌표 통일 기반 마련 ──
    # 격자 탐지 영역은 클립보다 조금 더 넓게 설정하여 외곽 라벨까지 포착
    anchor_clip = None
    if clip:
        xmin, ymin, xmax, ymax = clip
        anchor_clip = (xmin-50000, ymin-50000, xmax+50000, ymax+50000)
    
    # ── [개선] 1차 목표(80%) 달성을 위한 다중 좌표계 지원 ──
    from core.dxf_parser.ev_detector import GridAnchorDetector
    anchor_det = GridAnchorDetector(dong_clip=clip)
    
    # 현재 시트 기준점 탐지
    anchor = anchor_det.detect(doc)
    # 도면 전체 기준점 리스트 확보
    all_anchors = anchor_det.detect_all(doc)
    
    if anchor:
        print(f"  [Anchor Found] Current: {anchor.strategy} ({anchor.x:.0f}, {anchor.y:.0f})")
    print(f"  [Global Context] Total Anchors found in drawing: {len(all_anchors)}")
    # ─────────────────────────────────────────────────────────

    # 2. 격자선 추출 (부재 매칭에 필요할 수 있음)
    grid = None
    if extract_grid:
        from core.dxf_parser.grid_extractor import extract_grid as _extract_grid
        grid = _extract_grid(doc, clip=clip)

    # 3. 골조 부재 추출
    extractor = StructuralExtractor(
        min_slab_area_m2=min_slab_area_m2,
        shear_max_thickness=shear_max_thickness,
    )
    structural = extractor.extract(doc, clip=clip, grid=grid, anchor=anchor, all_anchors=all_anchors)

    frame = FrameData(
        source_dxf=dxf_path,
        clip=clip,
        columns=structural.columns,
        beams=structural.beams,
        slab_outlines=structural.slab_outlines,
        shear_walls=structural.shear_walls,
        grid=grid,
    )

    # 4. 층고·SL 파싱
    if extract_levels:
        from core.dxf_parser.level_parser import parse_msp
        frame.level_set = parse_msp(doc.modelspace(), clip=clip)

    # 5. 단차 구역
    if extract_steps:
        from core.dxf_parser.step_zone import parse_step_zones
        frame.step_zones = parse_step_zones(
            dxf_path, encoding=encoding, clip=clip,
            base_sl=frame.level_set.floor_sl if frame.level_set else None,
        )

    return frame


def parse_multi_drawing(drawings: List[dict]) -> List[FrameData]:
    """여러 도면 일괄 파싱.

    Args:
        drawings: [{'path': str, 'clip': tuple, 'encoding': str}, ...]
            encoding default = 'auto' (utf-8/cp949 자동 판별)
    """
    return [
        parse_structural_frame(
            dxf_path=d['path'],
            clip=d.get('clip'),
            encoding=d.get('encoding', 'auto'),
        )
        for d in drawings
    ]
