# sketchup_overlay_build.rb — 덧그림+오류표시 층별 태그 빌드
# 사용: SketchUp Ruby 콘솔에서
#   load 'D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output/sketchup_overlay_build.rb'
# 전제: 솔리드(101동_B2F/B1F/1F 그룹)는 이미 빌드됨. 이 스크립트는 덧그림만 추가.
require 'json'
model = Sketchup.active_model
ovl = JSON.parse(File.read('D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output/sketchup_overlay_101동.json'))
MM = 25.4
CROSS = 300.0 / MM
ZMAP = {'B2F' => -9050.0, 'B1F' => -5600.0, '1F' => 370.0}
layers = model.layers
mat = model.materials
m_err = mat['오류붉은표시'] || mat.add('오류붉은표시')
m_err.color = [255, 0, 0]

def _tag(layers, n)
  layers[n] || layers.add(n)
end

ovl['floors'].each do |fl, f|
  zi = ZMAP[fl] / MM + 2.0 / MM
  model.start_operation("덧그림_#{fl}", true)
  old = model.entities.grep(Sketchup::Group).find { |g| g.name == "덧그림_#{fl}" }
  old.erase! if old
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
    pts = rg.map { |x, y| Geom::Point3d.new(x/MM, y/MM, zi + 1.0/MM) }
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
        circ = ents.add_circle([x, y, zi+2.0/MM], Geom::Vector3d.new(0, 0, 1), CROSS*1.2, 12)
        cf = begin; ents.add_face(circ); rescue StandardError; nil; end
        if cf && cf.valid?
          cf.material = m_err; cf.back_material = m_err; cf.layer = layer_e
          cf.edges.each { |e| e.layer = layer_e }
        end
      end
    rescue StandardError
    end
  end
  model.commit_operation
  puts "덧그림_#{fl} 완료"
end
puts '덧그림 전층 완료'
