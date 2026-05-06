"""
core/dxf_parser — DXF 완전 파싱 서브패키지
==========================================
다음 사람, 다음 도면 누가 오더라도 바로 사용.

모듈:
  entity_scanner  — DXF 전수 엔티티 스캔 (INSERT 재귀 포함)
  ev_detector     — E/V 코어 기준점 검출 (F-1 패턴 구현체)
  coord_unifier   — 다중 도면 좌표 통일
  full_extractor  — 기둥·슬라브·벽·보·단차 완전 추출
  level_parser    — SL/EL 표고·단차 파싱
"""
from core.dxf_parser.entity_scanner import scan, iter_all, ScanResult
from core.dxf_parser.ev_detector import TextLabelEVDetector, GridAnchorDetector
from core.dxf_parser.coord_unifier import CoordUnifier, DrawingTransform
from core.dxf_parser.full_extractor import FullExtractor, ExtractResult
from core.dxf_parser.level_parser import parse_dxf as parse_levels, LevelSet, merge_level_sets
from core.dxf_parser.step_zone import parse_step_zones, StepZone, StepZoneMap
from core.dxf_parser.wall_extractor import extract_walls, WallExtractResult
from core.dxf_parser.structural_filter import (
    is_structural, is_structural_block, classify_layers, report_layer_classification
)
from core.dxf_parser.structural_extractor import (
    StructuralExtractor, StructuralData, extract_structural
)

__all__ = [
    'scan', 'iter_all', 'ScanResult',
    'TextLabelEVDetector', 'GridAnchorDetector',
    'CoordUnifier', 'DrawingTransform',
    'FullExtractor', 'ExtractResult',
    'parse_levels', 'LevelSet', 'merge_level_sets',
    'parse_step_zones', 'StepZone', 'StepZoneMap',
    'extract_walls', 'WallExtractResult',
    'is_structural', 'is_structural_block', 'classify_layers',
    'StructuralExtractor', 'StructuralData', 'extract_structural',
]
