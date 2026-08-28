"""
test_safe_reader.py — safe_readfile() 인코딩 자동 판별 검증

[방부장 원칙: 추측 배제. 데이터로 입증]
- PKG: $DWGCODEPAGE = ANSI_949, 실제 cp949 → utf-8 시도 시 fallback
- DONG: $DWGCODEPAGE = ANSI_949 (거짓), 실제 utf-8 → utf-8 우선이 정답
"""
import pytest

from core.dxf_parser.safe_reader import (
    safe_readfile, has_surrogate, is_layers_broken, detect_encoding,
)

DXF_PKG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'


def test_has_surrogate():
    assert not has_surrogate('A-WALL-RC')
    assert not has_surrogate('한글레이어')
    # surrogate 문자 직접 생성
    surrogate = chr(0xDC80)
    assert has_surrogate(f'broken{surrogate}layer')


def test_pkg_loads_clean():
    """PKG는 cp949 정합. utf-8 시도 후 cp949 fallback으로 정상 로드."""
    doc = safe_readfile(DXF_PKG)
    assert doc is not None
    assert not is_layers_broken(doc), 'PKG 레이어가 깨짐 — fallback 실패'


def test_dong_loads_clean():
    """DONG는 헤더 거짓말. utf-8 우선 전략이 정답."""
    doc = safe_readfile(DXF_DONG)
    assert doc is not None
    assert not is_layers_broken(doc), 'DONG 레이어가 깨짐 — utf-8 우선 실패'

    # 한국어 레이어가 정상 디코딩되었는지 검증
    korean_layers = [
        l.dxf.name for l in doc.layers
        if any(0xAC00 <= ord(c) <= 0xD7AF for c in l.dxf.name)
    ]
    assert len(korean_layers) > 10, f'한국어 레이어 적음: {len(korean_layers)}'


def test_detect_encoding_pkg():
    enc = detect_encoding(DXF_PKG)
    assert enc in ('utf-8', 'cp949')


def test_detect_encoding_dong():
    enc = detect_encoding(DXF_DONG)
    # DONG은 utf-8이 정답이어야 함
    assert enc == 'utf-8', f'DONG 인코딩 판별 실패: {enc}'
