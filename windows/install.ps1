# Installs (or repairs) Typing Trainer for the current Windows user, no
# admin needed. Install-TypingTrainer.cmd downloads and runs this. Layout:
# see launcher/update.py. Re-running it reinstalls the newest version and
# keeps data\ (progress) untouched.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is far faster without the bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = 'ntriplett/typing-trainer'
$UvVersion = '0.12.15'
$Python = '3.12'
$Root = Join-Path $env:LOCALAPPDATA 'TypingTrainer'

function Step($text) { Write-Host "  $text" -ForegroundColor Cyan }

New-Item -ItemType Directory -Force -Path "$Root\bin", "$Root\versions", "$Root\data" | Out-Null
$tmp = Join-Path $env:TEMP ("typing-trainer-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
    # 1. uv: one exe that fetches Python and the app's packages.
    if (-not (Test-Path "$Root\bin\uv.exe")) {
        Step "Getting uv $UvVersion..."
        $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'aarch64' } else { 'x86_64' }
        $uvZip = "$tmp\uv.zip"
        Invoke-WebRequest -UseBasicParsing "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-$arch-pc-windows-msvc.zip" -OutFile $uvZip
        Expand-Archive $uvZip "$tmp\uv"
        Copy-Item (Get-ChildItem "$tmp\uv" -Recurse -Filter uv.exe | Select-Object -First 1).FullName "$Root\bin\uv.exe"
    }

    # 2. The newest release.
    Step "Finding the newest version..."
    $release = Invoke-RestMethod -UseBasicParsing "https://api.github.com/repos/$Repo/releases/latest"
    $tag = $release.tag_name
    $asset = $release.assets | Where-Object { $_.name -like 'typing-trainer-*.zip' } | Select-Object -First 1
    if (-not $asset) { throw "Release $tag has no typing-trainer zip." }
    Step "Downloading Typing Trainer $tag..."
    $appZip = "$tmp\app.zip"
    Invoke-WebRequest -UseBasicParsing $asset.browser_download_url -OutFile $appZip
    Expand-Archive $appZip "$tmp\app"
    $versionDir = "$Root\versions\$tag"
    if (Test-Path $versionDir) { Remove-Item -Recurse -Force $versionDir }
    Move-Item "$tmp\app\typing-trainer" $versionDir

    # 3. Python and packages, all kept inside $Root.
    Step "Installing Python and packages (first time takes a minute)..."
    $env:UV_PYTHON_INSTALL_DIR = "$Root\python"
    $env:UV_PROJECT_ENVIRONMENT = "$Root\venv"
    $env:UV_CACHE_DIR = "$Root\cache"
    $env:UV_MANAGED_PYTHON = '1'
    & "$Root\bin\uv.exe" sync --frozen --no-install-project --python $Python --project $versionDir
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed." }

    Copy-Item "$versionDir\windows\launch.pyw" "$Root\launch.pyw" -Force
    Copy-Item "$versionDir\windows\TypingTrainer.ico" "$Root\TypingTrainer.ico" -Force
    Set-Content -Path "$Root\current.txt" -Value $tag -NoNewline -Encoding ascii

    # 4. Shortcuts: desktop and Start menu.
    Step "Adding shortcuts..."
    $shell = New-Object -ComObject WScript.Shell
    $places = @(
        [Environment]::GetFolderPath('Desktop'),
        [Environment]::GetFolderPath('Programs')
    )
    foreach ($place in $places) {
        $lnk = $shell.CreateShortcut((Join-Path $place 'Typing Trainer.lnk'))
        $lnk.TargetPath = "$Root\venv\Scripts\pythonw.exe"
        $lnk.Arguments = "`"$Root\launch.pyw`""
        $lnk.WorkingDirectory = $Root
        $lnk.IconLocation = "$Root\TypingTrainer.ico"
        $lnk.Description = 'Typing Trainer'
        $lnk.Save()
    }

    # Drop older versions (the updater keeps one to roll back to).
    Get-ChildItem "$Root\versions" -Directory | Where-Object { $_.Name -ne $tag } |
        Sort-Object LastWriteTime -Descending | Select-Object -Skip 1 |
        Remove-Item -Recurse -Force

    Write-Host ""
    Write-Host "  Typing Trainer $tag is installed. Starting it now..." -ForegroundColor Green
    Start-Process "$Root\venv\Scripts\pythonw.exe" -ArgumentList "`"$Root\launch.pyw`"" -WorkingDirectory $Root
}
finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
