# -*- coding: utf-8 -*-
"""
Window sill height extractor from A50 + A30 DXF files.

규칙:
- 도어(SD, PD, FSD, WD, HD, AD): sill=0mm (도어 규칙)
- 발코니/전면창(AG): A30 도면에서 추출 (FL.+120 → 1200mm)
- 방 창(PW): 관례 fallback (900mm)
"""

import ezdxf
from pathlib import Path
import json
import re
from typing import Dict, Optional, Tuple
from collections import defaultdict


def extract_windows_from_schedule(dxf_path: Path) -> Dict:
    """Extract window symbols and classify by sill rule."""

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    # Find window symbol block
    block_counts = {}
    for entity in msp:
        if entity.dxftype() == 'INSERT':
            block_counts[entity.dxf.name] = block_counts.get(entity.dxf.name, 0) + 1

    target_block = max(block_counts, key=block_counts.get)
    if block_counts[target_block] < 100:
        raise ValueError(f"Window block has only {block_counts[target_block]} instances")

    # Extract all windows
    windows_raw = []
    for entity in msp:
        if entity.dxftype() == 'INSERT' and entity.dxf.name == target_block:
            pos = entity.dxf.insert
            windows_raw.append({'x': pos[0], 'y': pos[1]})

    # For each window, find nearby TEXT
    windows_annotated = []
    for win_idx, window in enumerate(windows_raw):
        wx, wy = window['x'], window['y']

        window_info = {
            'idx': win_idx,
            'x': wx,
            'y': wy,
            'type': None,
            'num': None,
            'size': None,
            'size_h_m': None,
        }

        for text_entity in msp:
            if text_entity.dxftype() == 'TEXT':
                tx, ty = text_entity.dxf.insert[0], text_entity.dxf.insert[1]
                dist = ((tx - wx)**2 + (ty - wy)**2)**0.5

                if dist < 1000:
                    text = text_entity.dxf.text

                    if text in ['PW', 'SD', 'PD', 'AD', 'FSD', 'WD', 'HD', 'AG']:
                        window_info['type'] = text
                    elif text.isdigit() and len(text) <= 2:
                        window_info['num'] = text
                    elif '×' in text or 'x' in text.lower():
                        window_info['size'] = text
                        import re
                        match = re.search(r'([\d.]+)\s*×\s*([\d.]+)', text)
                        if match:
                            window_info['size_h_m'] = float(match.group(2))

        if window_info['type'] and window_info['num']:
            windows_annotated.append(window_info)

    return {
        'block': target_block,
        'windows_raw': windows_raw,
        'windows': windows_annotated,
    }


def extract_sill_from_a30_balcony(a30_dxf_path: Path) -> Dict[str, int]:
    """Extract sill values from A30 발코니 단면도."""

    try:
        doc = ezdxf.readfile(str(a30_dxf_path))
        msp = doc.modelspace()
    except Exception as e:
        print(f"Warning: Cannot read A30 file: {e}")
        return {}

    # Find window block in A30
    block_counts = {}
    for entity in msp:
        if entity.dxftype() == 'INSERT':
            block_counts[entity.dxf.name] = block_counts.get(entity.dxf.name, 0) + 1

    if not block_counts:
        return {}

    window_block = max(block_counts, key=block_counts.get)

    # Extract sill values from TEXT (FL.+XXX, SL.XXX patterns)
    sill_distribution = defaultdict(int)

    for entity in msp:
        if entity.dxftype() == 'INSERT' and entity.dxf.name == window_block:
            wx, wy = entity.dxf.insert[0], entity.dxf.insert[1]

            for text_entity in msp:
                if text_entity.dxftype() == 'TEXT':
                    tx, ty = text_entity.dxf.insert[0], text_entity.dxf.insert[1]
                    dist = ((tx - wx)**2 + (ty - wy)**2)**0.5

                    if dist < 1500:
                        text = text_entity.dxf.text
                        if 'FL' in text or 'SL' in text:
                            match = re.search(r'[SFL]{1,2}\.?[\+\-]?(\d+)', text)
                            if match:
                                value = int(match.group(1))
                                if 'SL.-' in text or 'SL-' in text:
                                    value = -value
                                sill_distribution[value] += 1
                                break

    # Most common sill value is the balcony standard
    if sill_distribution:
        most_common = max(sill_distribution, key=sill_distribution.get)
        # Convert doc units to mm (doc value × 10)
        actual_sill = most_common * 10
        return {'balcony_sill': actual_sill, 'distribution': dict(sill_distribution)}

    return {}


def assign_sill(window_info: Dict, a30_data: Dict = None) -> Tuple[Optional[int], str]:
    """Assign sill based on type rule and A30 data."""

    window_type = window_info['type']

    if window_type in ['SD', 'PD', 'FSD', 'WD', 'HD', 'AD']:
        return (0, 'door_rule')
    elif window_type == 'AG':
        # Aluminum Glass = 발코니 window
        if a30_data and 'balcony_sill' in a30_data:
            return (a30_data['balcony_sill'], 'dim')
        else:
            return (None, 'na')
    elif window_type == 'PW':
        # Power Window = 방 window (허리창)
        # Convention: sill = 900mm
        return (900, 'convention')
    else:
        return (None, 'unknown_type')


def extract_window_sills(a50_dxf_path: Path, a30_dxf_path: Path = None) -> Dict:
    """Main function: extract window sills from A50 + A30."""

    # Extract A50 schedule
    result = extract_windows_from_schedule(a50_dxf_path)
    windows = result['windows']

    # Extract A30 balcony sill
    a30_data = {}
    if a30_dxf_path and a30_dxf_path.exists():
        a30_data = extract_sill_from_a30_balcony(a30_dxf_path)

    sills_dict = {}
    seen_ids = set()
    method_counts = defaultdict(int)

    for win in windows:
        if win['type'] and win['num']:
            window_id = f"{win['type']}{win['num']}"

            if window_id not in seen_ids:
                sill_mm, method = assign_sill(win, a30_data)
                sills_dict[window_id] = {
                    'sill_mm': sill_mm,
                    'method': method,
                    'type': win['type'],
                    'h_m': win['size_h_m'],
                }
                seen_ids.add(window_id)
                method_counts[method] += 1

    resolved_count = sum(1 for v in sills_dict.values() if v['sill_mm'] is not None)
    from_drawing = method_counts['dim'] + method_counts['door_rule']
    from_convention = method_counts['convention']

    return {
        'file_a50': str(a50_dxf_path.name),
        'file_a30': str(a30_dxf_path.name) if a30_dxf_path else None,
        'n': len(sills_dict),
        'n_resolved': resolved_count,
        'n_from_drawing': from_drawing,
        'n_convention': from_convention,
        'a30_data': a30_data,
        'sills': sills_dict,
    }


if __name__ == '__main__':
    import sys

    a50_path = Path('input_drawings/A50-001~018 단위세대 창호일람표.dxf')
    a30_path = Path('input_drawings/A30-101~118 단위세대 발코니 평,입,단면도.dxf')

    if not a50_path.exists():
        print(f"Error: {a50_path} not found")
        sys.exit(1)

    result = extract_window_sills(a50_path, a30_path if a30_path.exists() else None)

    print(f"## Window Sill Extraction Result")
    print(f"- File A50: {result['file_a50']}")
    if result['file_a30']:
        print(f"- File A30: {result['file_a30']}")
    print(f"- Total windows (unique): {result['n']}")
    print(f"- Resolved (sill confirmed): {result['n_resolved']}")
    print(f"  - From drawing: {result['n_from_drawing']}")
    print(f"  - From convention: {result['n_convention']}")

    if result['a30_data'] and 'balcony_sill' in result['a30_data']:
        print(f"\n## A30 Balcony Analysis")
        print(f"- Balcony standard sill: {result['a30_data']['balcony_sill']}mm")
        print(f"- Distribution (doc units): {result['a30_data']['distribution']}")

    types = {}
    for window_id, info in result['sills'].items():
        wtype = info['type']
        if wtype not in types:
            types[wtype] = {'total': 0, 'dim': 0, 'conv': 0}
        types[wtype]['total'] += 1
        if info['method'] == 'dim' or info['method'] == 'door_rule':
            types[wtype]['dim'] += 1
        elif info['method'] == 'convention':
            types[wtype]['conv'] += 1

    print(f"\n## By Type:")
    for wtype in sorted(types.keys()):
        counts = types[wtype]
        print(f"- {wtype}: {counts['dim']} from drawing, {counts['conv']} convention (total {counts['total']})")

    print(f"\n## Samples (all window types):")
    for wid in sorted(result['sills'].keys()):
        info = result['sills'][wid]
        method_str = f"[{info['method']}]"
        sill_str = f"{info['sill_mm']}mm" if info['sill_mm'] is not None else "NA"
        print(f"  {wid}: {sill_str} {method_str}, h={info['h_m']}m")

    output_file = Path('output/window_sills.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {output_file}")
