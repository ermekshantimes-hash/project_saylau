<#
fix_psql_path.ps1
Скрипт для поиска psql.exe в типичных каталогах установки PostgreSQL и (опционально)
добавления каталога bin в системную переменную PATH.

Запускать от имени администратора для сохранения PATH в системе.
#>

param(
    [switch]$AddToMachinePath
)

function Find-PSQL {
    $searchRoots = @(
        'C:\Program Files\PostgreSQL',
        'C:\Program Files (x86)\PostgreSQL',
        'C:\Program Files\EnterpriseDB',
        'C:\Program Files (x86)\EnterpriseDB'
    )

    foreach ($root in $searchRoots) {
        if (Test-Path $root) {
            try {
                $res = Get-ChildItem -Path $root -Filter psql.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($res) { return $res }
            } catch {
                # ignore
            }
        }
    }

    # Fallback: быстрый поиск в корне C:\ (будет медленнее)
    try {
        $res = Get-ChildItem -Path C:\ -Filter psql.exe -Recurse -ErrorAction SilentlyContinue -Force | Select-Object -First 1
        if ($res) { return $res }
    } catch {
        # ignore
    }
    return $null
}

Write-Host "Ищем psql.exe в типичных местах..." -ForegroundColor Cyan
$psql = Find-PSQL

if (-not $psql) {
    Write-Host "psql.exe не найден. Возможно PostgreSQL не установлен на этом компьютере." -ForegroundColor Yellow
    Write-Host "Если хотите, установите PostgreSQL (EnterpriseDB) или используйте Docker."
    exit 2
}

$binDir = $psql.DirectoryName
Write-Host "Найден psql: $($psql.FullName)" -ForegroundColor Green
Write-Host "Каталог bin: $binDir" -ForegroundColor Green

# Тест текущего PATH (в сессии)
if ($env:Path -like "*${binDir}*") {
    Write-Host "Каталог уже присутствует в PATH (сессии). Вы можете использовать psql прямо сейчас." -ForegroundColor Green
    Write-Host "Чтобы начать новую сессию PowerShell с обновлённым PATH, закройте и откройте окно терминала." -ForegroundColor Cyan
    exit 0
}

if (-not $AddToMachinePath) {
    Write-Host "Каталог не найден в PATH текущей сессии." -ForegroundColor Yellow
    Write-Host "Вы можете временно добавить bin в PATH для текущей сессии (без прав):" -ForegroundColor Cyan
    Write-Host "  $env:PSCommandPath" -ForegroundColor DarkCyan
    Write-Host "Команда для текущей сессии:\n    $env:Path += \";$binDir\"\n" -ForegroundColor Cyan
    Write-Host "Если хотите добавить его в системный PATH (потребуются права администратора), перезапустите скрипт с флагом -AddToMachinePath" -ForegroundColor Yellow
    exit 0
}

# Если пользователь попросил добавить в Machine PATH
# Проверка на права администратора
$isElevated = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isElevated) {
    Write-Host "Добавление в системный PATH требует прав администратора. Перезапустите PowerShell как Administrator." -ForegroundColor Red
    exit 3
}

$machinePath = [Environment]::GetEnvironmentVariable('Path', [EnvironmentVariableTarget]::Machine)
if ($machinePath -notlike "*${binDir}*") {
    $newPath = $machinePath + ";" + $binDir
    [Environment]::SetEnvironmentVariable('Path', $newPath, [EnvironmentVariableTarget]::Machine)
    Write-Host "Добавлено в системный PATH: $binDir" -ForegroundColor Green
    Write-Host "Перезапустите терминал, чтобы изменения вступили в силу." -ForegroundColor Cyan
} else {
    Write-Host "Каталог уже присутствует в системном PATH." -ForegroundColor Green
}

exit 0
