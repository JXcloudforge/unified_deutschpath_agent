param(
    [switch]$KeepFailedArtifacts,
    [string[]]$PytestArgs = @()
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "项目 Python 不存在：$Python。请先按 README 安装项目环境。"
}

$TempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$OwnedParent = [System.IO.Path]::GetFullPath((Join-Path $TempBase 'Deutschpath-test-runs'))
if (-not $OwnedParent.StartsWith($TempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw '测试临时目录未通过系统临时目录边界检查。'
}
New-Item -ItemType Directory -Path $OwnedParent -Force | Out-Null

$RunPath = Join-Path $OwnedParent ([guid]::NewGuid().ToString('N'))
$RunPath = [System.IO.Path]::GetFullPath($RunPath)
if ([System.IO.Path]::GetDirectoryName($RunPath) -ne $OwnedParent) {
    throw '测试临时目录不是专用临时目录的直接子目录。'
}
New-Item -ItemType Directory -Path $RunPath | Out-Null

$ExitCode = 1
Push-Location $ProjectRoot
try {
    Write-Host "运行 pytest；临时文件位于系统临时目录。"
    $PytestCommandArgs = @('-m', 'pytest', '-q', '--ignore=tests/integration/test_api_smoke.py', '-p', 'no:cacheprovider', '--basetemp', $RunPath) + $PytestArgs
    & $Python @PytestCommandArgs
    $ExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
    $Keep = $KeepFailedArtifacts.IsPresent -and $ExitCode -ne 0
    if ($Keep) {
        Write-Warning "测试失败现场已按显式请求保留：$RunPath"
    }
    else {
        $ResolvedRunPath = [System.IO.Path]::GetFullPath($RunPath)
        if ([System.IO.Path]::GetDirectoryName($ResolvedRunPath) -eq $OwnedParent -and
            $ResolvedRunPath.StartsWith($OwnedParent + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $ResolvedRunPath -Recurse -Force
            Write-Host '本次测试临时数据已清理。'
        }
        else {
            Write-Warning '临时目录边界校验失败，未执行清理。'
        }
    }
}

exit $ExitCode
