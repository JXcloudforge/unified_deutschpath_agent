param(
    [ValidateSet("127.0.0.1")]
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvConfig = Join-Path $ProjectRoot ".venv\pyvenv.cfg"

function Stop-WithMessage([string]$Message) {
    [Console]::Error.WriteLine("Deutschpath frontend: $Message")
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
    & $Python $RuntimeCheck frontend
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "Python 版本不符合 pyproject.toml，或 Streamlit/API 客户端依赖不可导入。"
    }

    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env.example") -PathType Leaf)) {
        Stop-WithMessage "找不到 .env.example；请检查项目配置文件。"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "ui\streamlit_app.py") -PathType Leaf)) {
        Stop-WithMessage "找不到 ui/streamlit_app.py。"
    }

    $ApiBaseUrl = $env:DEUTSCHPATH_API_BASE_URL
    if (-not $ApiBaseUrl) {
        $EnvFile = Join-Path $ProjectRoot ".env"
        if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
            $EnvLine = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match '^\s*DEUTSCHPATH_API_BASE_URL\s*=' } | Select-Object -First 1
            if ($EnvLine) {
                $ApiBaseUrl = ($EnvLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
            }
        }
    }
    if (-not $ApiBaseUrl) {
        $ApiBaseUrl = "http://127.0.0.1:8765"
    }
    $env:DEUTSCHPATH_API_BASE_URL = $ApiBaseUrl
    # Credential management is disabled in the isolated demo environment.
    if ($env:DEUTSCHPATH_DEMO_MODE -eq "1") {
        $env:DEUTSCHPATH_LOCAL_SETTINGS_ENABLED = "0"
    }
    else {
        $env:DEUTSCHPATH_LOCAL_SETTINGS_ENABLED = "1"
    }
    $ApiUri = $null
    if (-not [uri]::TryCreate($ApiBaseUrl, [UriKind]::Absolute, [ref]$ApiUri) -or $ApiUri.Scheme -notin @("http", "https")) {
        Stop-WithMessage "DEUTSCHPATH_API_BASE_URL 必须是有效的 HTTP 或 HTTPS 地址。"
    }

    Write-Host "启动 Deutschpath Streamlit：http://${HostAddress}:$Port"
    Write-Host "后端 API 地址：$($ApiUri.GetLeftPart([UriPartial]::Authority))"
    & $Python -m streamlit run ui/streamlit_app.py --server.address $HostAddress --server.port $Port --server.headless true
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "Streamlit 以退出码 $LASTEXITCODE 结束。"
    }
}
finally {
    Pop-Location
}
