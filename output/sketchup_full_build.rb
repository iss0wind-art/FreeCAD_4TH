# sketchup_full_build.rb — 101동 전층(16층 타워) 골조 재빌드
#   load 'D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output/sketchup_full_build.rb'
# 기존 삭제 → 솔리드(기준층 3F~15F 반복) → 덧그림 태그 → 저장
# start_operation 미사용 (undo스택 오염 대비 안전 모드)
require 'json'

MM = 25.4
BASE = 'D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output'

module GoljoBuild
  module_function

  def ring(coords, z)
    pts = coords.map { |x, y| Geom::Point3d.new(x/MM, y/MM, z/MM) }
    pts.pop if pts.length > 1 && pts.first.distance(pts.last) < 0.01
    pts
  end

  # [확인요망] 계단 간이 생성 — 실측(단높이157.22/디딤270/9단2런), 런방향=개구 장변 가정
  def build_stairs(ents, opening, z, m_stair)
    xs = opening.map { |p| p[0] }; ys = opening.map { |p| p[1] }
    x0, x1 = xs.min, xs.max; y0, y1 = ys.min, ys.max
    w, h = x1 - x0, y1 - y0
    along_x = w >= h
    run_len = 8 * 270.0
    riser = 157.22
    half = (along_x ? h : w) / 2.0
    8.times do |i|
      zt = z + riser * (i + 1)
      if along_x
        tx0 = x0 + i * 270.0; tx1 = tx0 + 270.0
        f1 = ents.add_face([tx0/MM, y0/MM, zt/MM], [tx1/MM, y0/MM, zt/MM],
                           [tx1/MM, (y0+half)/MM, zt/MM], [tx0/MM, (y0+half)/MM, zt/MM]) rescue nil
      else
        ty0 = y0 + i * 270.0; ty1 = ty0 + 270.0
        f1 = ents.add_face([x0/MM, ty0/MM, zt/MM], [(x0+half)/MM, ty0/MM, zt/MM],
                           [(x0+half)/MM, ty1/MM, zt/MM], [x0/MM, ty1/MM, zt/MM]) rescue nil
      end
      if f1 && f1.valid?
        f1.material = m_stair
        f1.pushpull(f1.normal.z > 0 ? -170.0/MM : 170.0/MM) rescue nil
      end
      # 2런째 (반대편 절반, 반대 방향, 상부 구간)
      zt2 = z + 1415.0 + riser * (i + 1)
      if along_x
        tx0 = x1 - i * 270.0; tx1 = tx0 - 270.0
        f2 = ents.add_face([tx1/MM, (y0+half)/MM, zt2/MM], [tx0/MM, (y0+half)/MM, zt2/MM],
                           [tx0/MM, y1/MM, zt2/MM], [tx1/MM, y1/MM, zt2/MM]) rescue nil
      else
        ty0 = y1 - i * 270.0; ty1 = ty0 - 270.0
        f2 = ents.add_face([(x0+half)/MM, ty1/MM, zt2/MM], [(x0+half)/MM, ty0/MM, zt2/MM],
                           [x1/MM, ty0/MM, zt2/MM], [x1/MM, ty1/MM, zt2/MM]) rescue nil
      end
      if f2 && f2.valid?
        f2.material = m_stair
        f2.pushpull(f2.normal.z > 0 ? -170.0/MM : 170.0/MM) rescue nil
      end
    end
    # 중간참 (런 끝단)
    zl = z + 1415.0
    if along_x
      lf = ents.add_face([(x0+run_len)/MM, y0/MM, zl/MM], [x1/MM, y0/MM, zl/MM],
                         [x1/MM, y1/MM, zl/MM], [(x0+run_len)/MM, y1/MM, zl/MM]) rescue nil
    else
      lf = ents.add_face([x0/MM, (y0+run_len)/MM, zl/MM], [x1/MM, (y0+run_len)/MM, zl/MM],
                         [x1/MM, y1/MM, zl/MM], [x0/MM, y1/MM, zl/MM]) rescue nil
    end
    if lf && lf.valid?
      lf.material = m_stair
      lf.pushpull(lf.normal.z > 0 ? -170.0/MM : 170.0/MM) rescue nil
    end
  end

  def build_floor(model, name, f, z, wz0, wz1, mats)
    m_slab, m_wall, m_col, m_fnd = mats
    thk = f['slab_thk'].to_f
    g = model.entities.add_group
    g.name = name
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
    # 1F 기립벽 (해당층 골조선) — "1층 비었음" 수정
    sw = f['standing_walls']
    if sw
      swh = sw['z1'].to_f - sw['z0'].to_f
      sw['faces'].each do |w|
        begin
          face = ents.add_face(ring(w, sw['z0'].to_f))
          next unless face && face.valid?
          face.material = m_wall
          face.pushpull(face.normal.z > 0 ? swh/MM : -swh/MM)
        rescue StandardError
        end
      end
    end
    # 계단 [확인요망]
    st = f['stairs']
    if st
      m_stair = ents.model.materials['계단'] ||
                ents.model.materials.add('계단')
      m_stair.color = [120, 180, 120]
      st['openings'].each do |op|
        begin
          build_stairs(ents, op, z, m_stair)
        rescue StandardError
        end
      end
    end
  end
end

model = Sketchup.active_model
model.entities.clear!

build = JSON.parse(File.read("#{BASE}/sketchup_build_101동.json"))
ovl = JSON.parse(File.read("#{BASE}/sketchup_overlay_101동.json"))

mat = model.materials
m_slab = mat['슬라브'] || mat.add('슬라브'); m_slab.color = [200, 200, 205]
m_wall = mat['벽체'] || mat.add('벽체'); m_wall.color = [180, 150, 120]
m_col  = mat['기둥'] || mat.add('기둥'); m_col.color = [140, 140, 160]
m_fnd  = mat['기초_미확정'] || mat.add('기초_미확정'); m_fnd.color = [255, 80, 80]
m_err  = mat['오류붉은표시'] || mat.add('오류붉은표시'); m_err.color = [255, 0, 0]
mats = [m_slab, m_wall, m_col, m_fnd]
layers = model.layers

build['floors'].each do |fl, f|
  if f['repeat']
    f['repeat'].each do |rp|
      GoljoBuild.build_floor(model, "101동_#{rp['floor']}", f,
                             rp['z_sl'].to_f, rp['wall_z0'], rp['wall_z1'].to_f, mats)
    end
    puts "솔리드 #{fl} 반복 #{f['repeat'].length}개층 완료"
  else
    GoljoBuild.build_floor(model, "101동_#{fl}", f,
                           f['z_sl'].to_f, f['wall_z0'],
                           (f['wall_z1'] || f['z_sl']).to_f, mats)
    puts "솔리드 #{fl} 완료"
  end
end

# ── 덧그림 + 오류표시 (파싱 시트 3개층 기준) ──
CROSS = 300.0/MM
ZMAP = {'B2F' => -9050.0, 'B1F' => -5600.0, '1F' => 370.0,
        '2F' => 3300.0, 'TYP' => 6130.0, '16F' => 43020.0}

def _tag(l, n); l[n] || l.add(n); end

ovl['floors'].each do |fl, f|
  next unless ZMAP[fl]
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
  (f['trace_slab'] || []).each do |rg|
    pts = rg.map { |x, y| Geom::Point3d.new(x/MM, y/MM, zi+1.0/MM) }
    pts.pop if pts.length > 1 && pts.first.distance(pts.last) < 0.01
    begin
      ed = ents.add_edges(pts + [pts.first])
      ed.each { |e| e.layer = layer_s } if ed
    rescue StandardError
    end
  end
  layer_e = _tag(layers, "오류_#{fl}_붉은표시")
  (f['errors'] || []).each do |err|
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
  puts "덧그림_#{fl} 완료"
end

model.active_view.zoom_extents
ok = model.save('D:/Git/FreeCAD_4TH/output/101동_골조_파이프라인_2026-07-02.skp')
puts "저장: #{ok}"
