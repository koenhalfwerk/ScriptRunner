param(
    [string]$displayName,
    [int]$maxResults,
     [ValidateSet('Writer', 'Reader', 'Admin')]
    [string[]]$roles,
     [ValidateSet('1year', '2years', '180days')]
    [string]$SecretExpiry,
    [bool]$isMultiTenant
)

Write-Output "Creating Entra App..."
Write-Output "Name: $displayName"

# Simulatie
Start-Sleep -Seconds 2

Write-Output "Done"