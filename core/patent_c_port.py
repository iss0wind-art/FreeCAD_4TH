"""
정도전 청구항 Python 이식 (1지국 Ruby → 3지국 Python)

원본: d:/Git/BOQ_2/sketchup_plugins/boq_easyframe/src/boq_easyframe/core/
  - trim_manager.rb (청구항 1·2)
  - geometry_builder.rb (청구항 4 + Healer.weld_vertices)

이식 일자: 2026-05-05
이식자: 이천 (3지국)
근거: JIGUK_ROUND_TABLE_2026-05-05_THREE_PROBLEMS.md 호혜 매트릭스
"""

import math


# ── [청구항 1] 비파괴 선 정사영 (Orthogonal Projection) ────────
def project_points_to_plane(points, plane_pt, plane_normal):
    """
    원본: TrimManager.project_poly_onto_plane (Ruby)
    공식: P' = P - [(P - P0) · n̂] × n̂

    Args:
        points: [(x, y, z), ...] 또는 [(x, y), ...]
        plane_pt: 평면 위 한 점 (x, y, z)
        plane_normal: 평면 단위 법선 (nx, ny, nz)

    Returns:
        정사영된 점들의 리스트
    """
    px, py, pz = plane_pt
    nx, ny, nz = plane_normal
    out = []
    for p in points:
        if len(p) == 2:
            x, y = p; z = 0.0
        else:
            x, y, z = p
        sd = (x - px) * nx + (y - py) * ny + (z - pz) * nz
        out.append((x - sd * nx, y - sd * ny, z - sd * nz))
    return out


# ── [청구항 2] Sutherland-Hodgman 다각형 클리핑 ──────────────
def sh_clip_2d(subject_poly, clip_poly):
    """
    원본: TrimManager.sh_clip (Ruby) — 2D 평면 단순화 버전.

    subject_poly: [(x, y), ...] 자를 다각형
    clip_poly:    [(x, y), ...] 클리핑 경계 (CCW 가정)

    Returns: 클리핑된 다각형 [(x, y), ...] 또는 빈 리스트
    """
    output = list(subject_poly)
    cn = len(clip_poly)

    for i in range(cn):
        if not output:
            return []
        input_poly = output
        output = []
        edge_a = clip_poly[i]
        edge_b = clip_poly[(i + 1) % cn]

        # CCW 기준 내측 법선: edge 회전 90도 시계방향 (CCW면 내부 쪽)
        ex, ey = edge_b[0] - edge_a[0], edge_b[1] - edge_a[1]
        L = math.hypot(ex, ey)
        if L < 1e-10:
            continue
        # 내측 법선 (CCW의 left side)
        en_x, en_y = -ey / L, ex / L

        m = len(input_poly)
        for j in range(m):
            curr = input_poly[j]
            prev = input_poly[(j - 1) % m]

            curr_d = (curr[0] - edge_a[0]) * en_x + (curr[1] - edge_a[1]) * en_y
            prev_d = (prev[0] - edge_a[0]) * en_x + (prev[1] - edge_a[1]) * en_y
            curr_in = curr_d >= -1e-8
            prev_in = prev_d >= -1e-8

            if curr_in:
                if not prev_in:
                    output.append(_seg_line_intersect_2d(prev, curr, edge_a, (en_x, en_y)))
                output.append(curr)
            elif prev_in:
                output.append(_seg_line_intersect_2d(prev, curr, edge_a, (en_x, en_y)))
    return output


def _seg_line_intersect_2d(p1, p2, line_pt, line_normal):
    """선분 (p1, p2) ∩ 직선 (line_pt, normal=line_normal)"""
    nx, ny = line_normal
    px, py = line_pt
    d1 = (p1[0] - px) * nx + (p1[1] - py) * ny
    d2 = (p2[0] - px) * nx + (p2[1] - py) * ny
    denom = d1 - d2
    if abs(denom) < 1e-10:
        return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    t = max(0.0, min(1.0, d1 / denom))
    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))


# ── [geometry_builder 청구항 4] 부동소수점 그리드 정규화 ────────
def normalize_to_grid(points, tolerance=0.001):
    """
    원본: GeometryBuilder.normalize_coplanar_points (Ruby)
    공식: round(value / tol) × tol  (tol = 0.001mm)

    이천 적용: DXF 좌표는 mm 단위 → tolerance를 0.1mm로 완화
    """
    out = []
    for p in points:
        if len(p) == 2:
            out.append((round(p[0] / tolerance) * tolerance,
                       round(p[1] / tolerance) * tolerance))
        else:
            out.append((round(p[0] / tolerance) * tolerance,
                       round(p[1] / tolerance) * tolerance,
                       round(p[2] / tolerance) * tolerance))
    return out


# ── [Healer Patent C] 정점 병합 (Vertex Welder) ────────────────
def weld_vertices(points, tolerance=0.5):
    """
    원본: Healer.weld_vertices (Ruby)
    근거리 정점들을 하나의 대표 점으로 병합.

    이천 적용: DXF 페어링 전 LINE 끝점들에 적용 → 같은 노드 자동 통합.
    """
    welded = []
    out = []
    for p in points:
        match = None
        for w in welded:
            if len(p) == 2:
                d = math.hypot(p[0] - w[0], p[1] - w[1])
            else:
                d = math.sqrt((p[0]-w[0])**2 + (p[1]-w[1])**2 + (p[2]-w[2])**2)
            if d < tolerance:
                match = w; break
        if match is None:
            welded.append(p); out.append(p)
        else:
            out.append(match)
    return out


# ── [확장] LINE 사전 통합: 동일 직선상 인접 LINE을 하나로 ───────
def merge_collinear_lines(lines, angle_tol_deg=1.0, gap_tol=50.0):
    """
    이천 추가 — 정도전 청구항 직접 대응 안 되나, 정밀도 ③ 부재 분해 해결책.

    동일 방향 + 끝점 인접 LINE들을 하나의 긴 LINE으로 통합.

    Args:
        lines: [((x1,y1),(x2,y2)), ...]
        angle_tol_deg: 평행 판정 각도 허용
        gap_tol: 끝점-시작점 거리 허용 (mm)

    Returns:
        통합된 LINE 리스트
    """
    cos_tol = math.cos(math.radians(angle_tol_deg))
    used = [False] * len(lines)
    merged = []

    def line_dir(seg):
        (x1, y1), (x2, y2) = seg
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        return (dx/L, dy/L) if L > 1e-6 else None

    for i, seg in enumerate(lines):
        if used[i]:
            continue
        d_i = line_dir(seg)
        if d_i is None:
            used[i] = True; continue

        # 양 끝에서 확장 시도
        chain = list(seg)  # [start, end]
        used[i] = True
        changed = True
        while changed:
            changed = False
            for j, sj in enumerate(lines):
                if used[j]:
                    continue
                d_j = line_dir(sj)
                if d_j is None:
                    continue
                # 평행 검사 (방향 또는 역방향)
                cos_ij = abs(d_i[0]*d_j[0] + d_i[1]*d_j[1])
                if cos_ij < cos_tol:
                    continue
                # 끝점 인접 검사 (chain의 양 끝과 sj 양 끝)
                a, b = chain[0], chain[-1]
                c, d = sj
                d_bc = math.hypot(b[0]-c[0], b[1]-c[1])
                d_bd = math.hypot(b[0]-d[0], b[1]-d[1])
                d_ac = math.hypot(a[0]-c[0], a[1]-c[1])
                d_ad = math.hypot(a[0]-d[0], a[1]-d[1])

                if d_bc < gap_tol:
                    chain.append(d); used[j] = True; changed = True; break
                if d_bd < gap_tol:
                    chain.append(c); used[j] = True; changed = True; break
                if d_ac < gap_tol:
                    chain.insert(0, d); used[j] = True; changed = True; break
                if d_ad < gap_tol:
                    chain.insert(0, c); used[j] = True; changed = True; break

        # chain의 시작/끝만 남김 (중간점은 통합)
        merged.append((chain[0], chain[-1]))

    return merged


# ── [확장] 평행 라인 페어 직각 정렬 (정밀도 ① 해결) ────────────
def align_pair_to_rectangle(s1, s2):
    """
    이천 추가 — 청구항 1 (정사영) 응용.

    두 평행 라인을 입력받아 정확한 직사각형 4점 반환.
    s1을 기준으로 s2를 정사영하여 평행사변형을 사각형화.

    Args:
        s1, s2: ((x1,y1), (x2,y2)) 평행한 두 선분

    Returns:
        [p1, p2, p3, p4] 직사각형 4점 (CCW)
    """
    p1, p2 = s1
    p3, p4 = s2

    # s1 방향 단위벡터
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return [p1, p2, p4, p3]
    ux, uy = dx / L, dy / L
    # s1에 수직인 단위벡터 (90도 CCW 회전)
    vx, vy = -uy, ux

    # s2의 두 점을 s1 방향으로 투영하여 정렬된 좌표 계산
    # s2의 기준 거리 (s1으로부터 수직 거리)
    dist = (p3[0] - p1[0]) * vx + (p3[1] - p1[1]) * vy
    # s1의 시작/끝점에 수직 방향으로 dist만큼 이동 → s2의 정렬된 끝점
    p3_aligned = (p1[0] + dist * vx, p1[1] + dist * vy)
    p4_aligned = (p2[0] + dist * vx, p2[1] + dist * vy)

    # CCW 4점 (직사각형)
    return [p1, p2, p4_aligned, p3_aligned]
