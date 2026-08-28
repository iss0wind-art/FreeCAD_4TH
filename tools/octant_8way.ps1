# 8분할 tmux — 4 모델 × 2 인스턴스
# 각 pane이 독립 PTY로 single-shot CLI 호출
# 사용: powershell -ExecutionPolicy Bypass -File tools\octant_8way.ps1 [prompt]

param(
    [string]$Prompt = "Say only your model name in one line"
)

# shim 우회: scoop app 디렉토리에서 psmux/pmux/tmux 바이너리 동적 탐색
$psmuxRoot = "$env:USERPROFILE\scoop\apps\psmux"
$candidates = @()
if (Test-Path $psmuxRoot) {
    $dirs = @("$psmuxRoot\current")
    $dirs += Get-ChildItem $psmuxRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "current" } |
        Sort-Object Name -Descending |
        ForEach-Object { $_.FullName }
    foreach ($d in $dirs) {
        foreach ($n in @("pmux.exe", "psmux.exe", "tmux.exe")) {
            $candidates += "$d\$n"
        }
    }
}
$candidates += "$env:USERPROFILE\scoop\shims\tmux.exe"
$candidates += "$env:USERPROFILE\scoop\shims\psmux.exe"

$TMUX = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $TMUX) {
    Write-Host "tmux/psmux binary not found. Tried:" -ForegroundColor Red
    $candidates | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host "[octant] tmux binary: $TMUX" -ForegroundColor DarkGray

Write-Host "[octant] killing any existing tmux server..." -ForegroundColor DarkGray
& $TMUX kill-server 2>$null

Write-Host "[octant] creating 8-pane session..." -ForegroundColor Cyan
& $TMUX new-session -d -s octant -x 280 -y 70

# 4×2 grid: 7 splits then tiled
& $TMUX split-window -h -t octant
& $TMUX split-window -h -t "octant:0.0"
& $TMUX split-window -h -t "octant:0.2"
& $TMUX split-window -v -t "octant:0.0"
& $TMUX split-window -v -t "octant:0.2"
& $TMUX split-window -v -t "octant:0.4"
& $TMUX split-window -v -t "octant:0.6"
& $TMUX select-layout -t octant tiled

# 사관 정의: (pane index, label, cmd template)
# {0} = prompt (single-quoted in pane PowerShell)
$panes = @(
    @{ Idx=0; Label="claude-1";   Cmd="claude -p '{0}'" }
    @{ Idx=1; Label="claude-2";   Cmd="claude -p '{0}'" }
    @{ Idx=2; Label="gemini-1";   Cmd="gemini '{0}'" }
    @{ Idx=3; Label="gemini-2";   Cmd="gemini '{0}'" }
    @{ Idx=4; Label="deepseek-1"; Cmd="deepseek -p '{0}'" }
    @{ Idx=5; Label="deepseek-2"; Cmd="deepseek -p '{0}'" }
    @{ Idx=6; Label="qwen-1";     Cmd="qwen '{0}'" }
    @{ Idx=7; Label="qwen-2";     Cmd="qwen '{0}'" }
)

Write-Host "[octant] dispatching commands to 8 panes..." -ForegroundColor Cyan
foreach ($p in $panes) {
    $cmd = $p.Cmd -f $Prompt
    $banner = "Write-Host '=== Pane $($p.Idx): $($p.Label) ===' -ForegroundColor Yellow"
    $full = "$banner; $cmd"
    & $TMUX send-keys -t "octant:0.$($p.Idx)" $full Enter
}

# attach script 생성 후 새 PowerShell 창에서 attach
# 매 실행마다 새 파일 (이전 파일이 user-mapped section으로 잠겨있을 수 있음)
$stamp = Get-Date -Format "yyyyMMddHHmmss"
$attachScript = "$env:TEMP\tmux_attach_octant_$stamp.ps1"
@"
`$Host.UI.RawUI.WindowTitle = '이천 8사관 tmux'
& '$TMUX' attach -t octant
"@ | Set-Content $attachScript -Encoding UTF8

Write-Host "[octant] launching attach window..." -ForegroundColor Cyan
cmd /c start "이천 8사관 tmux" powershell.exe -NoExit -ExecutionPolicy Bypass -File $attachScript

Write-Host ""
Write-Host "[octant] DONE. attach window opened." -ForegroundColor Green
Write-Host "  - session name : octant"
Write-Host "  - prompt       : $Prompt"
Write-Host "  - re-attach    : tmux attach -t octant"
Write-Host "  - kill         : tmux kill-session -t octant"
