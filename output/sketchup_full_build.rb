# sketchup_full_build.rb — 101동 골조 전체 재빌드 (스케치업 재시작 후 1회 실행)
#   load 'D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output/sketchup_full_build.rb'
# 내용: 기존 삭제 → 솔리드(벽 수직구간 수정판) → 덧그림 태그 → 저장
require 'json'
model = Sketchup.active_model
model.entities.clear!

MM = 25.4
BASE = 'D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output'
build = JSON.parse(File.read("#{BASE}/sketchup_build_101동.json"))
ovl = JSON.parse(File.read("#{BASE}/sketchup_overlay_101동.json"))

mat = model.materials
m_slab = mat['슬라브'] || mat.add('슬라브'); m_slab.color = [200, 200, 205]
m_wall = mat['벽체'] || mat.add('벽체'); m_wall.color = [180, 150, 120]
m_col  = mat['기둥'] || mat.add('기둥'); m_col.color = [140, 140, 160]
m_fnd  = mat['기초_미확정'] || mat.add('기초_미확정'); m_fnd.color = [255, 80, 80]
layers = model.layers

def _tag(l, n); l[n] || l.add(n); end

def ring(coords, z)
  pts = coords.map { |x, y| Geom::Point3d.new(x/25.4, y/25.4, z/25.4) }
  pts.pop if pts.length > 1 && pts.first.distance(pts.last) < 0.01
  pts
end

# ── 솔리드 ──
build['floors'].each do |fl, f|
  z = f['z_sl'].to_f
  thk = f['slab_thk'].to_f
  wz0 = f['wall_z0']
  wz1 = f['wall_z1'].to_f
  g = model.entities.add_group
  g.name = "101동_#{fl}"
  ents = g.entities

  f['slabs'].each do |p|
    begin
      outer = ents.add_face(ring(p['exterior'], z))
      p['holes'].each do |h|
        begin; hf = ents.add_face(ring(h, z)); hf.erase! if hf && hf.valid?; rescue StandardError; end
      end
      if outer && outer.valid?
        outer.material = m_slab
        outer.pushpull(outer.normal.z > 0 ? -thk/MM : thk/MM)
      end
    rescue StandardError
    end
  end

  # 벽·기둥: 아래층 부재 — SL(N-1)~SL(N). 기초(wz0=nil)는 발자국 face만(붉은색).
  wall_h = wz0 ? (wz1 - wz0.to_f) : 0
  wall_base = wz0 ? wz0.to_f : wz1
  f['wall_faces'].each do |w|
    begin
      face = ents.add_face(ring(w, wall_base))
      next unless face && face.valid?
      if wall_h > 0
        face.material = m_wall
        face.pushpull(face.normal.z > 0 ? wall_h/MM : -wall_h/MM)
      else
        face.material = m_fnd; face.back_material = m_fnd
      end
    rescue StandardError
    end
  end
  f['columns'].each do |c|
    begin
      x0 = (c['cx']-c['w']/2.0)/MM; y0 = (c['cy']-c['h']/2.0)/MM
      x1 = (c['cx']+c['w']/2.0)/MM; y1 = (c['cy']+c['h']/2.0)/MM
      zb = wall_base/MM
      face = ents.add_face([x0,y0,zb],[x1,y0,zb],[x1,y1,zb],[x0,y1,zb])
      next unless face && face.valid?
      if wall_h > 0
        face.material = m_col
        face.pushpull(face.normal.z > 0 ? wall_h/MM : -wall_h/MM)
      else
        face.material = m_fnd; face.back_material = m_fnd
      end
    rescue StandardError
    end
  end
  puts "솔리드 #{fl} 완료 (벽구간 #{wz0.inspect}~#{wz1})"
end

# ── 덧그림 + 오류표시 ──
CROSS = 300.0/MM
ZMAP = {'B2F' => -9050.0, 'B1F' => -5600.0, '1F' => 370.0}
m_err = mat['오류붉은표시'] || mat.add('오류붉은표시'); m_err.color = [255, 0, 0]
ovl['floors'].each do |fl, f|
  zi = ZMAP[fl]/MM + 2.0/MM
  g = model.entities.add_group
  g.name = "덧그림_#{fl}"
  ents = g.entities
  { 'trace_wall' => '벽체', 'trace_beam' => '보',
    'trace_bridge' => '연결보정선', 'trace_slab_end' => '슬라브단부선' }.each do |key, nm|
    layer = _tag(layers, "덧그림_#{fl}_#{nm}")
    (f[key] || []).each do |(a, b)|
      begin
        e = ents.add_line([a[0]/MM, a[1]/MM, zi], [b[0]/MM, b[1]/MM, zi])
        e.layer = layer if e
      rescue StandardError
      end
    end
  end
  layer_s = _tag(layers, "덧그림_#{fl}_슬라브경계")
  f['trace_slab'].each do |rg|
    pts = rg.map { |x, y| Geom::Point3d.new(x/MM, y/MM, zi+1.0/MM) }
    pts.pop if pts.length > 1 && pts.first.distance(pts.last) < 0.01
    begin
      ed = ents.add_edges(pts + [pts.first])
      ed.each { |e| e.layer = layer_s } if ed
    rescue StandardError
    end
  end
  layer_e = _tag(layers, "오류_#{fl}_붉은표시")
  f['errors'].each do |err|
    begin
      x = err['x']/MM; y = err['y']/MM
      if err['kind'] == 'unpaired_wall' && err['x1']
        e = ents.add_line([err['x1']/MM, err['y1']/MM, zi+2.0/MM],
                          [err['x2']/MM, err['y2']/MM, zi+2.0/MM])
        e.layer = layer_e if e
      else
        e1 = ents.add_line([x-CROSS, y-CROSS, zi+2.0/MM], [x+CROSS, y+CROSS, zi+2.0/MM])
        e2 = ents.add_line([x-CROSS, y+CROSS, zi+2.0/MM], [x+CROSS, y-CROSS, zi+2.0/MM])
        [e1, e2].each { |e| e.layer = layer_e if e }
      end
    rescue StandardError
    end
  end
  puts "덧그림 #{fl} 완료 (오류 #{f['errors'].length}건)"
end

model.active_view.zoom_extents
ok = model.save('D:/Git/FreeCAD_4TH/output/101동_골조_파이프라인_2026-07-02.skp')
puts "저장: #{ok}"
