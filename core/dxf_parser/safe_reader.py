"""
safe_reader.py — DXF 인코딩 자동 판별 reader

[발견 — 2026-05-08, 끌로드 트랙 직독]
DONG 도면은 $DWGCODEPAGE = ANSI_949로 선언하지만 실제로는 utf-8로 저장.
ezdxf 기본 동작(헤더 신뢰)으로 cp949 디코딩하면 240/316 레이어가 surrogate로 깨짐.
→ 헤더 무시, utf-8 우선 + cp949 fallback.

증거: scripts/claude_track_probe3.py 실행 결과
  cp949: 깨짐 240 (75.9%)
  utf-8: 깨짐 0
"""
from __future__ import annotations

from typing import Optional
import ezdxf


def has_surrogate(s: str) -> bool:
    """utf-8 잘못 디코딩된 surrogate 문자 존재 여부."""
    return any(0xD800 <= ord(c) <= 0xDFFF for c in s)


def is_layers_broken(doc, sample_size: int = 20) -> bool:
    """레이어명 샘플로 깨짐 판단. 샘플 중 하나라도 surrogate면 True."""
    count = 0
    for layer in doc.layers:
        if has_surrogate(layer.dxf.name):
            return True
        count += 1
        if count >= sample_size:
            break
    return False


def safe_readfile(path: str, prefer: str = 'utf-8') -> ezdxf.document.Drawing:
    """DXF 파일을 인코딩 자동 판별로 읽는다.

    Args:
        path: DXF 파일 경로
        prefer: 우선 시도 인코딩 ('utf-8' or 'cp949')

    Returns:
        ezdxf.Drawing 객체. 깨짐 적은 인코딩으로 로드된 것.

    Raises:
        IOError: 둘 다 실패 시
    """
    fallback = 'cp949' if prefer == 'utf-8' else 'utf-8'

    # 1차: 우선 인코딩
    try:
        doc = ezdxf.readfile(path, encoding=prefer)
        if not is_layers_broken(doc):
            return doc
    except UnicodeDecodeError:
        pass
    except Exception as e:
        # ezdxf 내부 오류는 그대로 전파
        if 'encoding' not in str(e).lower():
            raise

    # 2차: fallback
    try:
        return ezdxf.readfile(path, encoding=fallback)
    except Exception as e:
        raise IOError(f'safe_readfile FAIL ({prefer},{fallback}): {path}: {e}')


def detect_encoding(path: str) -> str:
    """경량 인코딩 판별. 'utf-8' 또는 'cp949' 반환."""
    for enc in ['utf-8', 'cp949']:
        try:
            doc = ezdxf.readfile(path, encoding=enc)
            if not is_layers_broken(doc):
                return enc
        except Exception:
            pass
    return 'cp949'  # 둘 다 실패 시 default
