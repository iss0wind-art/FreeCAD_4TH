"""
claude_track_section_compare.py — 정규식 확장 전후 비교

PKG 도면 직독 데이터로 기존 vs 확장 정규식의 SECTION 매칭률 비교.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ezdxf
from core.dxf_parser.safe_reader import safe_readfile

DXF_PKG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'

# 기존 패턴
PAT_OLD = re.compile(r"^(C|TC|RG|G|B|TB|FB|W|F)\d+[A-Z]?$", re.IGNORECASE)

# 확장 패턴 1: 알려진 prefix 추가
PAT_EXT_NAMED = re.compile(
    r"^[\-]?\d?(C|TC|EC|AC|G|TG|TB|FB|B|W|S|F|RG|REG|RWG|RPG|EG|PG|WG)\d+[A-Z]?$",
    re.IGNORECASE,
)

# 확장 패턴 2: 일반화 (1~4자 알파벳 + 숫자)
PAT_EXT_GENERIC = re.compile(r"^[\-]?\d?[A-Z]{1,4}\d{1,3}[A-Z]?$", re.IGNORECASE)

# 격자 패턴 (false positive 차단)
PAT_GRID_X = re.compile(r"^X\d+[a-z]?$", re.IGNORECASE)
PAT_GRID_Y = re.compile(r"^Y\d+[a-z]?$", re.IGNORECASE)


def main():
    print('PKG 로드...', flush=True)
    doc = safe_readfile(DXF_PKG)
    msp = doc.modelspace()

    texts = []
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if txt and len(txt) <= 8:
                texts.append(txt)
        except Exception:
            pass

    print(f'\n총 짧은 텍스트: {len(texts)}건')

    old_match = [t for t in texts if PAT_OLD.match(t)]
    ext_named_match = [t for t in texts
                       if PAT_EXT_NAMED.match(t)
                       and not (PAT_GRID_X.match(t) or PAT_GRID_Y.match(t))]
    ext_generic_match = [t for t in texts
                         if PAT_EXT_GENERIC.match(t)
                         and not (PAT_GRID_X.match(t) or PAT_GRID_Y.match(t))]

    print(f'\n[기존] PAT_OLD 매칭: {len(old_match)}건 ({len(set(old_match))} unique)')
    print(f'  TOP 10: {sorted(set(old_match))[:10]}')

    print(f'\n[확장1] PAT_EXT_NAMED 매칭: {len(ext_named_match)}건 ({len(set(ext_named_match))} unique)')
    print(f'  추가: {sorted(set(ext_named_match) - set(old_match))[:20]}')

    print(f'\n[확장2] PAT_EXT_GENERIC 매칭: {len(ext_generic_match)}건 ({len(set(ext_generic_match))} unique)')
    print(f'  추가: {sorted(set(ext_generic_match) - set(old_match))[:20]}')

    # false positive 검증
    fp_named = set(ext_named_match) - set(ext_generic_match)
    fp_generic = set(ext_generic_match) - set(ext_named_match)
    print(f'\n[차이] named만 잡음: {sorted(fp_named)[:10]}')
    print(f'[차이] generic만 잡음: {sorted(fp_generic)[:10]}')

    # 회수율
    print(f'\n=== 회수 효과 ===')
    print(f'기존  → 확장1(named):   {len(old_match)} → {len(ext_named_match)} '
          f'({(len(ext_named_match)/max(1,len(old_match))-1)*100:+.1f}%)')
    print(f'기존  → 확장2(generic): {len(old_match)} → {len(ext_generic_match)} '
          f'({(len(ext_generic_match)/max(1,len(old_match))-1)*100:+.1f}%)')


if __name__ == '__main__':
    main()
