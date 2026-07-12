"""
core/dxf_parser/encoding_helper.py — 한국형 도면 인코딩 및 바이너리 스트림 평탄화 헬퍼
========================================================================
국내 CAD 도면 특유의 CP949/UTF-8 기형적 혼재 및 인코딩 깨짐 현상을 방지하기 위해
ezdxf 진입점 바이너리 스트림을 가로채어 안전하게 디코딩합니다.
"""
from __future__ import annotations

import ezdxf

def safe_read_dxf(dxf_path: str, default_encoding: str = 'cp949') -> ezdxf.document.Drawing:
    """
    ezdxf.readfile을 가로채어 바이너리 바이트 스트림을 직접 평탄화(Flatting)합니다.
    CP949 디코딩 실패 시 UTF-8 폴백을 시도하며, 최종 실패 시 에러 문자열을 대체하여 로드 실패를 원천 방지합니다.
    """
    with open(dxf_path, 'rb') as f:
        binary_data = f.read()

    # 1. 기본 인코딩(CP949) 디코딩 시도
    try:
        text = binary_data.decode(default_encoding)
    except UnicodeDecodeError:
        # 2. UTF-8 디코딩 폴백 시도
        try:
            text = binary_data.decode('utf-8')
        except UnicodeDecodeError:
            # 3. 하이브리드 스트림 강제 평탄화 (에러 문자열 대체하여 데이터 유실 최소화)
            text = binary_data.decode(default_encoding, errors='replace')

    # ezdxf 문자열 파서로 복원
    return ezdxf.readstring(text)
