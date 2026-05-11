
import sys
import os

sys.path.insert(0, "D:/Git/FreeCAD_4TH")

from core.dxf_parser.pipeline import parse_structural_frame

def test_v10():
    dxf_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    if not os.path.exists(dxf_path):
        print(f"File not found: {dxf_path}")
        return

    # S30-001 영역 (조금 더 넓게)
    CLIP = (100000, 2340000, 180000, 2400000)
    
    print(f"Parsing S30-001 with CLIP {CLIP} for label verification...")
    frame = parse_structural_frame(dxf_path, encoding='cp949', clip=CLIP)
    
    print("-" * 50)
    print(frame.summary())
    
    # Beam Labels
    beams_with_label = [b for b in frame.beams if b.symbol != "NOLABEL"]
    denom_b = len(frame.beams) if len(frame.beams) > 0 else 1
    print(f"\nBeams with labels: {len(beams_with_label)} / {len(frame.beams)} ({len(beams_with_label)/denom_b*100:.1f}%)")
    if beams_with_label:
        print("Sample Beam Labels:", sorted(list(set([b.symbol for b in beams_with_label])))[:10])

    # Slab Labels
    slabs_with_label = [s for s in frame.slab_outlines if s.symbol != "NOSLAB"]
    denom_s = len(frame.slab_outlines) if len(frame.slab_outlines) > 0 else 1
    print(f"\nSlabs with labels: {len(slabs_with_label)} / {len(frame.slab_outlines)} ({len(slabs_with_label)/denom_s*100:.1f}%)")
    for i, s in enumerate(frame.slab_outlines):
        print(f"  Slab {i}: Area {s.area_m2:.1f}m2, Layer '{s.layer}', Symbol '{s.symbol}', BBox {s.bbox()}")
    
    if slabs_with_label:
        print("Sample Slab Labels:", sorted(list(set([s.symbol for s in slabs_with_label])))[:10])

if __name__ == "__main__":
    test_v10()
