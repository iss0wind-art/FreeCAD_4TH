
import ezdxf
import sys
import os

sys.path.insert(0, "D:/Git/FreeCAD_4TH")

from core.dxf_parser.ev_detector import TextLabelEVDetector

def scan_pkg():
    dxf_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/EDB24-PKG-101.dxf"
    if not os.path.exists(dxf_path):
        print(f"File not found: {dxf_path}")
        return

    doc = ezdxf.readfile(dxf_path, encoding='cp949')
    msp = doc.modelspace()
    
    # 1. Detect E/V cores
    detector = TextLabelEVDetector()
    ev_anchors = detector.detect(msp)
    
    print(f"Found {len(ev_anchors)} E/V anchors:")
    for i, anchor in enumerate(ev_anchors):
        print(f"  [{i}] x={anchor[0]:.0f}, y={anchor[1]:.0f}")

    # 2. Detect Grid Bubbles (TEXT near long lines)
    # Just a simple bounding box check for entities to see where clusters are.
    entities = list(msp)
    if not entities:
        return
    
    # Simple clustering by X coordinate to find sheets
    xs = []
    for e in entities:
        try:
            if e.dxftype() == 'LINE':
                xs.append(e.dxf.start.x)
            elif e.dxftype() == 'INSERT':
                xs.append(e.dxf.insert.x)
        except:
            continue
            
    if not xs:
        return
        
    xs.sort()
    clusters = []
    if xs:
        curr = [xs[0]]
        for x in xs[1:]:
            if x - curr[-1] > 500000: # 500m gap
                clusters.append(curr)
                curr = [x]
            else:
                curr.append(x)
        clusters.append(curr)
        
    print(f"\nDetected {len(clusters)} sheet clusters by X coordinate:")
    for i, c in enumerate(clusters):
        xmin, xmax = min(c), max(c)
        print(f"  Cluster {i}: x={xmin:.0f} ~ {xmax:.0f} (width={(xmax-xmin)/1000:.1f}m)")

if __name__ == "__main__":
    scan_pkg()
