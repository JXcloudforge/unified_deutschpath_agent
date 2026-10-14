param(
    [ValidateSet("127.0.0.1")]
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8765,
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 8501,
    [switch]$CheckOnly,
    [switch]$DemoMode
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackendScript = Join-Path $PSScriptRoot "start_backend.ps1"
$FrontendScript = Join-Path $PSScriptRoot "start_frontend.ps1"
$ApiBaseUrl = "http://${HostAddress}:$BackendPort"
$UiUrl = "http://${HostAddress}:$FrontendPort"

if ($DemoMode) {
    if (-not $PSBoundParameters.ContainsKey("BackendPort")) { $BackendPort = 18765 }
    if (-not $PSBoundParameters.ContainsKey("FrontendPort")) { $FrontendPort = 18501 }
    $ApiBaseUrl = "http://${HostAddress}:$BackendPort"
    $UiUrl = "http://${HostAddress}:$FrontendPort"
    if ($HostAddress -ne "127.0.0.1") { Stop-WithMessage "DemoMode 仅允许绑定 127.0.0.1。" }
    $DemoDataRoot = Join-Path $env:LOCALAPPDATA "DeutschpathUnifiedAgent\demo-v0.2.1"
    $DemoDataRoot = [System.IO.Path]::GetFullPath($DemoDataRoot)
    New-Item -ItemType Directory -Path $DemoDataRoot -Force | Out-Null
    $script:PriorEnvironment = @{}
    foreach ($name in @("DEUTSCHPATH_DEMO_MODE", "DEUTSCHPATH_API_BASE_URL", "STAGE2_DATA_PATH", "APP_ENV", "M08_LOCAL_ENABLED", "STAGE3_ROUTER", "STAGE2_EMBEDDING_PROVIDER", "DEEPSEEK_API_KEY", "TAVILY_API_KEY", "DEUTSCHPATH_LOCAL_SETTINGS_ENABLED")) {
        $script:PriorEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    }
    $env:DEUTSCHPATH_DEMO_MODE = "1"
    $env:STAGE2_DATA_PATH = $DemoDataRoot
    $env:APP_ENV = "development"
    $env:M08_LOCAL_ENABLED = "true"
    $env:STAGE3_ROUTER = "rules"
    $env:STAGE2_EMBEDDING_PROVIDER = "deterministic"
    $env:DEEPSEEK_API_KEY = ""
    $env:TAVILY_API_KEY = ""
    $env:DEUTSCHPATH_LOCAL_SETTINGS_ENABLED = "0"
    Write-Host "隔离演示数据目录：$DemoDataRoot"
}

function Stop-WithMessage([string]$Message) {
    [Console]::Error.WriteLine("Deutschpath launcher: $Message")
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "app\api\main.py") -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $ProjectRoot "ui\streamlit_app.py") -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $ProjectRoot "pyproject.toml") -PathType Leaf)) {
    Stop-WithMessage "当前目录不是 Deutschpath 主工程根目录。请从包含 app、ui 和 pyproject.toml 的目录启动。"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Stop-WithMessage "找不到项目 Python：$Python。请先按 README 创建并安装 .venv。"
}
foreach ($script in @($BackendScript, $FrontendScript)) {
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) {
        Stop-WithMessage "缺少启动脚本：$script"
    }
}

Push-Location $ProjectRoot
try {
    & $Python (Join-Path $PSScriptRoot "check_runtime.py") backend
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Python 或后端依赖检查失败。" }
    & $Python (Join-Path $PSScriptRoot "check_runtime.py") frontend
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Python 或前端依赖检查失败。" }
    $Version = (& $Python -c "from app.version import VERSION; print(VERSION)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Version) { Stop-WithMessage "无法读取 pyproject.toml 中的项目版本。" }
} finally {
    Pop-Location
}

if ($BackendPort -eq $FrontendPort) { Stop-WithMessage "后端和前端不能使用同一端口。" }

function Get-PortListeners([int]$Port) {
    @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

function Get-ProcessInfo([int]$ProcessId) {
    Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
}

function Get-ProcessTree([int]$RootProcessId) {
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $seen = [System.Collections.Generic.HashSet[int]]::new()
    $pending.Enqueue($RootProcessId)
    while ($pending.Count -gt 0) {
        $currentId = $pending.Dequeue()
        if (-not $seen.Add($currentId)) { continue }
        $current = Get-ProcessInfo $currentId
        if (-not $current) { continue }
        $current
        foreach ($child in Get-CimInstance Win32_Process -Filter "ParentProcessId=$currentId" -ErrorAction SilentlyContinue) {
            $pending.Enqueue([int]$child.ProcessId)
        }
    }
}

function Get-CommandLineNormalized($ProcessInfo) {
    if (-not $ProcessInfo -or -not $ProcessInfo.CommandLine) { return "" }
    return $ProcessInfo.CommandLine.Replace('/', '\').ToLowerInvariant()
}

function Test-BackendIdentity([int]$ProcessId) {
    $rootNeedle = $ProjectRoot.Replace('/', '\').ToLowerInvariant()
    $expected = (Join-Path $ProjectRoot ".venv\Scripts\python.exe").Replace('/', '\').ToLowerInvariant()
    $backendProcess = @(Get-ProcessTree $ProcessId | Where-Object {
        $commandLine = Get-CommandLineNormalized $_
        $commandLine.Contains($rootNeedle) -and $commandLine.Contains($expected) -and
        $commandLine.Contains("uvicorn") -and $commandLine.Contains("app.api.main:app")
    }) | Select-Object -First 1
    if (-not $backendProcess) { return $false }
    try {
        $health = Invoke-RestMethod -Uri "$ApiBaseUrl/health" -TimeoutSec 3
        $openapi = Invoke-RestMethod -Uri "$ApiBaseUrl/openapi.json" -TimeoutSec 3
        $valid = ($health.status -eq "ok" -and $health.router_initialized -eq $true -and
                $health.web_provider_initialized -eq $true -and
                $openapi.info.title -eq "Deutschpath Unified Agent" -and
                $openapi.info.version -eq $Version)
        if ($DemoMode) {
            $valid = $valid -and $health.app_environment -eq "development" -and
                $health.m08_local_orchestration -eq $true -and $health.router_configured_mode -eq "rules" -and
                $health.llm_provider -eq "FakeLLM" -and $health.deepseek_api_key_configured -eq $false -and
                $health.tavily_api_key_configured -eq $false
        }
        return $valid
    } catch { return $false }
}

function Test-FrontendIdentity([int]$ProcessId) {
    $rootNeedle = $ProjectRoot.Replace('/', '\').ToLowerInvariant()
    $expected = (Join-Path $ProjectRoot ".venv\Scripts\python.exe").Replace('/', '\').ToLowerInvariant()
    $frontendProcess = @(Get-ProcessTree $ProcessId | Where-Object {
        $commandLine = Get-CommandLineNormalized $_
        $commandLine.Contains($rootNeedle) -and $commandLine.Contains($expected) -and
        $commandLine.Contains("streamlit") -and $commandLine.Contains("ui\streamlit_app.py")
    }) | Select-Object -First 1
    if (-not $frontendProcess) { return $false }
    try {
        $response = Invoke-WebRequest -Uri "$UiUrl/_stcore/health" -TimeoutSec 3 -UseBasicParsing
        return $response.StatusCode -eq 200
    } catch { return $false }
}

function Start-ServiceWindow([string]$ScriptPath, [int]$Port) {
    $powershellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    if (-not (Test-Path -LiteralPath $powershellExe -PathType Leaf)) {
        $powershellExe = (Get-Process -Id $PID).Path
    }
    $arguments = "-NoProfile -NoExit -File `"$ScriptPath`" -HostAddress $HostAddress -Port $Port"
    return Start-Process -FilePath $powershellExe -ArgumentList $arguments -WorkingDirectory $ProjectRoot -PassThru
}

$backendListeners = Get-PortListeners $BackendPort
$frontendListeners = Get-PortListeners $FrontendPort
$useBackend = $false
$useFrontend = $false

if ($backendListeners.Count -gt 0) {
    if ($backendListeners.Count -ne 1 -or -not (Test-BackendIdentity $backendListeners[0])) {
        $owner = $backendListeners -join ", "
        Stop-WithMessage "端口 ${HostAddress}:$BackendPort 已被 PID $owner 占用，且不能确认它是本版本 Deutschpath FastAPI。不会复用或停止该服务。"
    }
    $useBackend = $true
    Write-Host "已确认现有 Deutschpath FastAPI：$ApiBaseUrl（版本 $Version）。"
} else {
    Write-Host "FastAPI 端口 ${HostAddress}:$BackendPort 可用。"
}

if ($frontendListeners.Count -gt 0) {
    if ($DemoMode -or $frontendListeners.Count -ne 1 -or -not (Test-FrontendIdentity $frontendListeners[0])) {
        $owner = $frontendListeners -join ", "
        if ($DemoMode) { Stop-WithMessage "DemoMode 不复用已运行的 Streamlit（PID $owner）；请使用空闲演示端口，且不会停止现有进程。" }
        Stop-WithMessage "端口 ${HostAddress}:$FrontendPort 已被 PID $owner 占用，且不能确认它是本项目 Streamlit。不会复用或停止该服务。"
    }
    $useFrontend = $true
    Write-Host "已确认现有 Deutschpath Streamlit：$UiUrl。"
} else {
    Write-Host "Streamlit 端口 ${HostAddress}:$FrontendPort 可用。"
}

if ($CheckOnly) {
    Write-Host "启动前检查 PASS；未启动或停止任何服务。"
    exit 0
}

if (-not $useBackend) {
    $backendProcess = Start-ServiceWindow $BackendScript $BackendPort
    Write-Host "已打开 FastAPI 窗口（PID $($backendProcess.Id)），等待 /health 和 OpenAPI..."
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 500
        if (Test-BackendIdentity $backendProcess.Id) { $ready = $true; break }
        if ($backendProcess.HasExited) { break }
    }
    if (-not $ready) { Stop-WithMessage "FastAPI 未在 60 秒内通过项目版本、/health 与 OpenAPI 检查。查看新开的后端窗口。" }
}

if (-not $useFrontend) {
    $env:DEUTSCHPATH_API_BASE_URL = $ApiBaseUrl
    $frontendProcess = Start-ServiceWindow $FrontendScript $FrontendPort
    Write-Host "已打开 Streamlit 窗口（PID $($frontendProcess.Id)），等待 /_stcore/health..."
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 500
        if (Test-FrontendIdentity $frontendProcess.Id) { $ready = $true; break }
        if ($frontendProcess.HasExited) { break }
    }
    if (-not $ready) { Stop-WithMessage "Streamlit 未在 45 秒内通过进程身份与 /_stcore/health 检查。查看新开的前端窗口。" }
}

if ($DemoMode) {
    foreach ($name in $script:PriorEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $script:PriorEnvironment[$name], "Process")
    }
}

Write-Host "FastAPI 已验证：$ApiBaseUrl/health；Streamlit 已验证：$UiUrl/_stcore/health。"
Write-Host "正在打开浏览器：$UiUrl"
Start-Process $UiUrl
Write-Host "关闭时请在各服务窗口分别按 Ctrl+C；先停止 Streamlit，再停止 FastAPI。"
