param(
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvConfig = Join-Path $ProjectRoot ".venv\pyvenv.cfg"

function Stop-WithMessage([string]$Message) {
    [Console]::Error.WriteLine("Deutschpath backend: $Message")
    exit 1
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Stop-WithMessage "找不到项目虚拟环境的 Python：$Python。请先按 README 环境步骤创建并安装项目依赖。"
}
if (-not (Test-Path -LiteralPath $VenvConfig -PathType Leaf)) {
    Stop-WithMessage "找不到 .venv/pyvenv.cfg，无法验证虚拟环境基准解释器。"
}

$ConfigText = Get-Content -LiteralPath $VenvConfig -Raw
$HomeMatch = [regex]::Match($ConfigText, '(?m)^home\s*=\s*(.+?)\s*$')
if (-not $HomeMatch.Success) {
    Stop-WithMessage ".venv/pyvenv.cfg 缺少 home 路径。"
}
$BasePython = Join-Path $HomeMatch.Groups[1].Value.Trim() "python.exe"
if (-not (Test-Path -LiteralPath $BasePython -PathType Leaf)) {
    Stop-WithMessage "虚拟环境基准解释器不存在：$BasePython。保留现有 .venv；请先建立隔离环境。"
}

Push-Location $ProjectRoot
try {
    $RuntimeCheck = Join-Path $PSScriptRoot "check_runtime.py"
    & $Python $RuntimeCheck backend
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "Python 版本不符合 pyproject.toml，或 FastAPI/Uvicorn/Chroma 依赖不可导入。"
    }

    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env.example") -PathType Leaf)) {
        Stop-WithMessage "找不到 .env.example；请检查项目配置文件。"
    }

    $PortProbe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Parse($HostAddress), $Port)
    try {
        $PortProbe.Start()
    }
    catch [System.Net.Sockets.SocketException] {
        Stop-WithMessage "端口 ${HostAddress}:$Port 已被占用。Deutschpath 不会连接或关闭现有服务；请释放该端口后重试。"
    }
    finally {
        $PortProbe.Stop()
    }

    Write-Host "启动 Deutschpath FastAPI：http://${HostAddress}:$Port"
    Write-Host "数据目录使用 STAGE2_DATA_PATH（未设置时为项目 data/）。不会显示 API 凭据。"
    & $Python -m uvicorn app.api.main:app --host $HostAddress --port $Port --log-level info
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "Uvicorn 以退出码 $LASTEXITCODE 结束。"
    }
}
finally {
    Pop-Location
}
