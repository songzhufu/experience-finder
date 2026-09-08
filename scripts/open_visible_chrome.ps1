param(
    [int]$Port = 9222,
    [string]$ProfileDir = "$PSScriptRoot\..\data\visible_chrome_profile",
    [string]$Url = "https://www.xiaohongshu.com"
)

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
)

$chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) {
    Write-Error "Could not find Chrome or Playwright Chromium."
    exit 1
}

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null

Write-Host "Opening visible Chrome:"
Write-Host "  $chrome"
Write-Host "Remote debugging:"
Write-Host "  http://127.0.0.1:$Port"
Write-Host "Profile:"
Write-Host "  $ProfileDir"

Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$ProfileDir",
    "--new-window",
    $Url
)
