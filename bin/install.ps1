# Downloads and verifies the Windows build of the Redmine MCP server, called by redmine-mcp.cmd.
param([Parameter(Mandatory)][string]$Version, [Parameter(Mandatory)][string]$Data)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$platform = 'windows-x64'
$asset = "redmine-mcp-$Version-$platform.zip"
$releaseUrl = if ($env:REDMINE_MCP_RELEASE_URL) { $env:REDMINE_MCP_RELEASE_URL } else { 'https://github.com/expertZentrale/claude-redmine-mcp/releases/download' }
$target = Join-Path $Data "$Version\$platform"

function Say($message) { [Console]::Error.WriteLine("redmine-mcp launcher: $message") }

$line = Get-Content (Join-Path $PSScriptRoot 'SHA256SUMS') | Where-Object { ($_ -split '\s+')[1] -eq $asset }
if (-not $line) { Say "no checksum for $asset in SHA256SUMS, version $Version has no build for $platform"; exit 1 }
$expected = ($line -split '\s+')[0]

New-Item -ItemType Directory -Force -Path (Join-Path $Data $Version) | Out-Null
$tmp = Join-Path $Data "$Version\.download.$PID"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
    Say "downloading $asset"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri "$releaseUrl/v$Version/$asset" -OutFile (Join-Path $tmp $asset)

    $actual = (Get-FileHash -Algorithm SHA256 (Join-Path $tmp $asset)).Hash.ToLower()
    if ($actual -ne $expected.ToLower()) { Say "checksum mismatch for $asset (expected $expected, got $actual), not running it"; exit 1 }

    Expand-Archive -Path (Join-Path $tmp $asset) -DestinationPath (Join-Path $tmp 'out')
    # Another session may have finished first, its copy is just as good
    if (-not (Test-Path (Join-Path $target 'redmine-mcp\redmine-mcp.exe'))) { Move-Item (Join-Path $tmp 'out') $target }

    # Builds of older plugin versions are not needed anymore
    Get-ChildItem $Data -Directory | Where-Object { $_.Name -ne $Version } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Say "installed $Version for $platform"
}
finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
