"""
층고·슬라브 두께 도면에서 자력 채굴
======================================
추정값(4400·200) 폐기. 도면에서 실제값 읽기.

[채굴 대상]
1. 층고 — 101동 구조평면도 SL(설계 레벨) TEXT 두 층 차이
2. 층고 — 지하주차장 구조평면도 SL TEXT
3. 슬라브 두께 — S40-121~124 지하주차장 슬라브 리스트.dxf
4. 보 높이 — output/codex_beams_basement.json (이미 채굴 완료)
"""
import sys, re, json, time
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import ezdxf

DONG_DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
BSMNT_DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
SLAB_DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S40-121~124 지하주차장 슬라브 리스트.dxf"
BEAM_CODEX = r"output/codex_beams_basement.json"


def iter_all(c, d=0, m=6):
    if d > m: return
    for e in c:
        if e.dxftype() == 'INSERT':
            try: yield from iter_all(list(e.virtual_entities()), d+1, m)
            except: pass
        else: yield e


def extract_sl_texts(dxf_path, label):
    """SL(설계 레벨) 텍스트 추출 — 층 표고 정보."""
    print(f'\n[{label}] SL 표기 채굴...')
    t0 = time.time()
    doc = ezdxf.readfile(dxf_path, encoding='cp949')
    msp = doc.modelspace()
    print(f'  로드 {time.time()-t0:.1f}s')

    # SL 표기 패턴: "B2F SL -8800", "SL-4400", "B1F SL +1600" 등
    sl_pat = re.compile(
        r'(B[123]F|B\d|PIT|1F|2F|RF|지하\s*\d층)?'
        r'.*?SL'
        r'[^\d\-\+]*'
        r'([+\-]?\d[\d,\.]*)',
        re.IGNORECASE
    )
    # 절대 표고 직접 패턴
    elev_pat = re.compile(r'(B[123]F|PIT|1F|지하\s*\d층).*?([+\-]\s*\d[\d\.]+)', re.IGNORECASE)

    results = []
    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip()
            if not txt or len(txt) > 60:
                continue
            if 'SL' not in txt.upper() and '표고' not in txt and 'EL' not in txt.upper():
                continue
            pos = e.dxf.insert
            results.append((txt, pos.x, pos.y))
        except: pass

    # 정렬 + 출력
    seen = set()
    print(f'  SL 텍스트 {len(results)}건:')
    for txt, px, py in sorted(results, key=lambda x: -x[2]):
        key = txt[:30]
        if key in seen: continue
        seen.add(key)
        print(f'    "{txt}"  ({px:.0f}, {py:.0f})')
        if len(seen) >= 30: break
    return results


def parse_slab_list(dxf_path):
    """슬라브 리스트 DXF에서 두께 채굴."""
    print(f'\n[슬라브 리스트] 두께 채굴...')
    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
        msp = doc.modelspace()
    except Exception as e:
        print(f'  로드 실패: {e}')
        return []

    # 두께 패턴: "T=200", "두께 180", "200mm" 등
    thick_pat = re.compile(r'(?:T=|두께|t=|THK)?\s*(\d{2,3})\s*(?:mm)?', re.IGNORECASE)
    slab_codes = re.compile(r'^S\d|^SL\d|^슬|^SLAB', re.IGNORECASE)

    texts = []
    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip()
            if txt: texts.append(txt)
        except: pass

    print(f'  전체 텍스트 {len(texts)}건')
    # 두께로 보이는 숫자들
    thickness_candidates = defaultdict(int)
    for t in texts:
        for m in thick_pat.finditer(t):
            v = int(m.group(1))
            if 100 <= v <= 400:  # 슬라브 두께 범위
                thickness_candidates[v] += 1

    print('  두께 후보 (100~400mm):')
    for v, cnt in sorted(thickness_candidates.items(), key=lambda x: -x[1])[:15]:
        print(f'    {v}mm — {cnt}건')
    return dict(thickness_candidates)


def parse_beam_codex(path):
    """보 높이 — 이미 채굴된 codex에서 읽기."""
    print(f'\n[보 codex] 이미 채굴된 실제값 읽기...')
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    heights = defaultdict(int)
    for b in d.get('부재_법전', []):
        h = b.get('height')
        if h: heights[h] += 1
    print('  보 높이 분포:')
    for h, cnt in sorted(heights.items()):
        print(f'    {h}mm — {cnt}건')
    return dict(heights)


if __name__ == '__main__':
    # 1. 101동 도면 층 표고
    extract_sl_texts(DONG_DXF, '101동 구조평면도')

    # 2. 지하주차장 도면 층 표고
    extract_sl_texts(BSMNT_DXF, '지하주차장 구조평면도')

    # 3. 슬라브 리스트 두께
    parse_slab_list(SLAB_DXF)

    # 4. 보 높이 (이미 있음)
    parse_beam_codex(BEAM_CODEX)

    print('\n[종결] 실제값 채굴 완료.')
