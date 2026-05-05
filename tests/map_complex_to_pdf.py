"""
GLB 동 좌표 ↔ PDF 라벨 좌표 자력 매핑
======================================

이순신(2지국) → 이천 친서 청 2 응답.

[입력]
  - GLB: D:/Git/FreeCAD_4TH/output/complex_master.glb (16개 동, D{dong}_{B1|B2})
  - PDF 라벨: D:/Git/H2OWIND_2/public/drawings/_tmp/v2_label_positions.json (16점)

[방법]
  1) GLB 노드 mesh accessor min/max → 동별 (cx, cy)
  2) underground_floors로 두 집합 9/7 분할 (이천 자료 + 이순신 PDF 분류 일치)
  3) 두 좌표계 정규화 (0~1)
  4) 8 가지 변환(4 회전 × 2 반전) × 9/7 분할 안에서 그리디 최소 거리 매칭
  5) 평균 거리 가장 작은 변환 채택

[출력]
  - output/complex_to_pdf_label_mapping.json
"""
import os, sys, json, struct, re, math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

GLB_PATH = r"D:/Git/FreeCAD_4TH/output/complex_master.glb"
MASTER_JSON = r"D:/Git/FreeCAD_4TH/output/complex_master.json"
PDF_LABELS = r"D:/Git/H2OWIND_2/public/drawings/_tmp/v2_label_positions.json"
OUT = r"D:/Git/FreeCAD_4TH/output/complex_to_pdf_label_mapping.json"


def load_glb_centers():
    """GLB 노드 D{dong}_B1 메시 BB 중심 (cx, cy) 채굴.
    B1·B2 둘 있으면 같은 위치이므로 B1 우선 사용."""
    with open(GLB_PATH, 'rb') as f:
        f.read(12)
        json_len = struct.unpack('<I', f.read(4))[0]
        f.read(4)
        j = json.loads(f.read(json_len))

    nodes = j['nodes']
    meshes = j['meshes']
    accessors = j['accessors']
    pat = re.compile(r'^D(\d+)_(B[12])$')

    by_dong = {}
    for node in nodes:
        m = pat.match(node.get('name', ''))
        if not m:
            continue
        dong = int(m.group(1))
        layer = m.group(2)
        if dong in by_dong and layer == 'B2':
            continue  # B1 우선
        mesh_idx = node.get('mesh')
        if mesh_idx is None:
            continue
        mesh = meshes[mesh_idx]
        prim = mesh['primitives'][0]
        pos_idx = prim['attributes']['POSITION']
        acc = accessors[pos_idx]
        mn, mx = acc.get('min'), acc.get('max')
        if not (mn and mx):
            continue
        by_dong[dong] = {
            'cx': (mn[0] + mx[0]) / 2,
            'cy': (mn[1] + mx[1]) / 2,
            'layer_present': layer,
        }
    return by_dong


def load_underground_floors():
    """complex_master.json → dong → underground_floors."""
    with open(MASTER_JSON, encoding='utf-8') as f:
        d = json.load(f)
    return {b['dong']: b['underground_floors'] for b in d['buildings']}


def load_pdf_labels():
    with open(PDF_LABELS, encoding='utf-8') as f:
        d = json.load(f)
    page_w, page_h = d['page_w'], d['page_h']
    labels = []
    for i, lab in enumerate(d['labels']):
        cx, cy = lab['center']
        labels.append({
            'idx': i,
            'px': cx, 'py': cy,
            'glyphs': lab['glyphs'],
        })
    return labels, page_w, page_h


def normalize(points, key_x, key_y):
    xs = [p[key_x] for p in points]
    ys = [p[key_y] for p in points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    rx = maxx - minx if maxx > minx else 1.0
    ry = maxy - miny if maxy > miny else 1.0
    return [
        {**p, 'nx': (p[key_x] - minx) / rx, 'ny': (p[key_y] - miny) / ry}
        for p in points
    ]


def transform(pt_nx, pt_ny, rot, flip_x):
    """8가지 변환 (4 회전 × 2 좌우반전)."""
    x, y = pt_nx, pt_ny
    if flip_x:
        x = 1 - x
    if rot == 0:
        return x, y
    elif rot == 90:
        return y, 1 - x
    elif rot == 180:
        return 1 - x, 1 - y
    elif rot == 270:
        return 1 - y, x


def greedy_match(group_a, group_b, key_a_xy=('tx', 'ty'), key_b_xy=('nx', 'ny')):
    """그리디 매칭: 가장 가까운 쌍부터 차례로 짝 짓기."""
    pairs = []
    used_b = set()
    a_sorted = list(range(len(group_a)))
    while a_sorted:
        best = None
        for i in a_sorted:
            ax, ay = group_a[i][key_a_xy[0]], group_a[i][key_a_xy[1]]
            for j in range(len(group_b)):
                if j in used_b:
                    continue
                bx, by = group_b[j][key_b_xy[0]], group_b[j][key_b_xy[1]]
                d = math.hypot(ax - bx, ay - by)
                if best is None or d < best[0]:
                    best = (d, i, j)
        if best is None:
            break
        d, i, j = best
        pairs.append((i, j, d))
        used_b.add(j)
        a_sorted.remove(i)
    return pairs


def total_cost(pairs):
    return sum(d for _, _, d in pairs)


def main():
    glb_centers = load_glb_centers()
    floors = load_underground_floors()
    pdf_labels, pw, ph = load_pdf_labels()

    print(f'[GLB] {len(glb_centers)} 동')
    print(f'[PDF] {len(pdf_labels)} 라벨, page={pw}×{ph}')

    # 동 16개 -> 분류 (B2 있는 9 / B1만 7)
    glb_b2 = []
    glb_b1_only = []
    for dong, info in glb_centers.items():
        rec = {'dong': dong, 'cx': info['cx'], 'cy': info['cy']}
        if floors[dong] == 2:
            glb_b2.append(rec)
        else:
            glb_b1_only.append(rec)

    # PDF 16개 -> 분류 (glyphs ≥ 21 → B1F+B2F 긴 라벨, < 21 → B1F만)
    pdf_b2 = [l for l in pdf_labels if l['glyphs'] >= 21]
    pdf_b1_only = [l for l in pdf_labels if l['glyphs'] < 21]

    print(f'[B1+B2 9] GLB={len(glb_b2)}, PDF={len(pdf_b2)}')
    print(f'[B1만 7]  GLB={len(glb_b1_only)}, PDF={len(pdf_b1_only)}')
    assert len(glb_b2) == 9 and len(pdf_b2) == 9
    assert len(glb_b1_only) == 7 and len(pdf_b1_only) == 7

    # 정규화
    glb_b2_n = normalize(glb_b2, 'cx', 'cy')
    glb_b1_n = normalize(glb_b1_only, 'cx', 'cy')
    pdf_b2_n = normalize(pdf_b2, 'px', 'py')
    pdf_b1_n = normalize(pdf_b1_only, 'px', 'py')

    # 8 변환 시도 — GLB를 PDF 좌표계로 변환 후 매칭
    best_overall = None
    for rot in (0, 90, 180, 270):
        for flip in (False, True):
            # 변환 적용
            glb_b2_t = [
                {**p, 'tx': transform(p['nx'], p['ny'], rot, flip)[0],
                       'ty': transform(p['nx'], p['ny'], rot, flip)[1]}
                for p in glb_b2_n
            ]
            glb_b1_t = [
                {**p, 'tx': transform(p['nx'], p['ny'], rot, flip)[0],
                       'ty': transform(p['nx'], p['ny'], rot, flip)[1]}
                for p in glb_b1_n
            ]
            pairs_b2 = greedy_match(glb_b2_t, pdf_b2_n)
            pairs_b1 = greedy_match(glb_b1_t, pdf_b1_n)
            cost = total_cost(pairs_b2) + total_cost(pairs_b1)
            if best_overall is None or cost < best_overall['cost']:
                best_overall = {
                    'rot': rot, 'flip': flip, 'cost': cost,
                    'pairs_b2': pairs_b2, 'pairs_b1': pairs_b1,
                    'glb_b2_t': glb_b2_t, 'glb_b1_t': glb_b1_t,
                }
            print(f'  rot={rot:>3} flip={flip}  cost={cost:.4f}')

    print(f'\n[최적] rot={best_overall["rot"]}, flip={best_overall["flip"]}, '
          f'cost={best_overall["cost"]:.4f}')
    print(f'  평균 거리: {best_overall["cost"]/16:.4f} (정규화 단위)')

    # 매핑 결과 박제
    final_mapping = []
    for i, j, d in best_overall['pairs_b2']:
        glb = best_overall['glb_b2_t'][i]
        pdf = pdf_b2_n[j]
        final_mapping.append({
            'pdf_label_idx': pdf['idx'],
            'pdf_center_xy': [pdf['px'], pdf['py']],
            'pdf_glyphs': pdf['glyphs'],
            'pdf_class': 'B1F+B2F',
            'dong': glb['dong'],
            'glb_center_xy': [glb['cx'], glb['cy']],
            'distance_normalized': round(d, 4),
        })
    for i, j, d in best_overall['pairs_b1']:
        glb = best_overall['glb_b1_t'][i]
        pdf = pdf_b1_only[j]
        final_mapping.append({
            'pdf_label_idx': pdf['idx'],
            'pdf_center_xy': [pdf['px'], pdf['py']],
            'pdf_glyphs': pdf['glyphs'],
            'pdf_class': 'B1F-only',
            'dong': glb['dong'],
            'glb_center_xy': [glb['cx'], glb['cy']],
            'distance_normalized': round(d, 4),
        })
    final_mapping.sort(key=lambda x: x['pdf_label_idx'])

    print(f'\n[매핑 결과 — 라벨 idx 0~15]')
    print(f'{"idx":>3} {"동":>4} {"PDF center":>16} {"GLB cx,cy":>14} {"분류":<10} {"거리":>6}')
    for m in final_mapping:
        px, py = m['pdf_center_xy']
        cx, cy = m['glb_center_xy']
        print(f'{m["pdf_label_idx"]:>3} {m["dong"]:>4} '
              f'({px:>6.1f},{py:>7.1f}) ({cx:>5.0f},{cy:>5.0f}) '
              f'{m["pdf_class"]:<10} {m["distance_normalized"]:>6.4f}')

    # 박제
    out = {
        'source_glb': GLB_PATH,
        'source_pdf_labels': PDF_LABELS,
        'method': 'normalized affine + greedy 8-transform search',
        'best_transform': {
            'rotation_deg': best_overall['rot'],
            'flip_x': best_overall['flip'],
            'total_cost': round(best_overall['cost'], 4),
            'avg_distance_normalized': round(best_overall['cost'] / 16, 4),
        },
        'mappings': final_mapping,
        'glb_node_naming_pattern': 'D{dong}_{B1|B2}  (예: D101_B2, D101_B1)',
        'note': '동별 평균 거리(정규화)가 0.05 이하면 매핑 매우 신뢰. 0.10 이하면 신뢰. 그 이상이면 변환 가설 점검 필요.',
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[박제] {OUT}')


if __name__ == '__main__':
    main()
