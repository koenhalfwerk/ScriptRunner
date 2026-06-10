<#
.SYNOPSIS
    Adds a new secret to an existing Azure Entra ID application registration.

.DESCRIPTION
    Looks up an existing Azure Entra ID application by DisplayName.
    The script only continues when exactly one application is found.
    It then appends the supplied ticket number or notes to the existing Notes field
    and adds a new client secret to the application.

.EXAMPLE
    Single app
    .\StandaardChanges\Renew-MCPAASappSecret.ps1 -DisplayName "HOS-SP-AZUREDEVOPS-KOA-VERWIJSADMINISTRATIE-001" -CreateSecret -SecretExpiry "1year" -Ticketnumber "RFC-445415"

.EXAMPLE
    Multiple apps
    "HOS-SP-AZUREDEVOPS-KOA-VERWIJSADMINISTRATIE-001","HOS-SP-MCPAAS-KOA-VERWIJSADMINISTRATIE-001" | % { .\StandaardChanges\Renew-MCPAASappSecret.ps1 -DisplayName $_ -CreateSecret -SecretExpiry "1year" -Ticketnumber "RFC-445739" }
#>

param (
    [Parameter(Mandatory = $true, ParameterSetName = 'DisplayName')]
    [string]$DisplayName,

    [Parameter(Mandatory = $true, ParameterSetName = 'ApplicationID')]
    [string]$ApplicationID,

    [bool]$CreateSecret=$false,

    [ValidateSet('1year', '2years', '180days')]
    [string]$SecretExpiry = '1year',

    [Parameter(Mandatory = $true)]
    [string]$Ticketnumber,

    [Parameter(Mandatory = $false)]
    [string]$Notes
)

# Install Microsoft Graph PowerShell SDK if not already installed
if (-not (Get-Module -Name Microsoft.Graph -ListAvailable)) {
    Install-Module Microsoft.Graph -Scope CurrentUser -Force
}

# Check if already connected to Microsoft Graph; if not, connect
if (-not (Get-MgContext -ErrorAction SilentlyContinue)) {
    Connect-MgGraph -Scopes 'Application.ReadWrite.All', 'Directory.ReadWrite.All' -NoWelcome -ErrorAction Stop
}

try {
    if ($DisplayName) {
        # Find the existing application by display name and make sure there is exactly one hit
        $escapedDisplayName = $DisplayName.Replace("'", "''")
        $apps = @(Get-MgApplication -Filter "displayName eq '$escapedDisplayName'" -All -Property Id, AppId, DisplayName, Notes)

        if ($apps.Count -eq 0) {
            throw "No application found with DisplayName '$DisplayName'."
        }

        if ($apps.Count -gt 1) {
            throw "Multiple applications found with DisplayName '$DisplayName'. Please use a unique DisplayName."
        }

        $app = $apps[0]
        # $app | Format-Table DisplayName, AppId, Id -AutoSize
    }
    else {
        $app = Get-MgApplication -Filter "AppId eq '$ApplicationID'"
    }
}
catch {}
try {
    # Append to the notes instead of overwriting them
    $noteToAppend = if ([string]::IsNullOrWhiteSpace($Notes)) { $Ticketnumber } else { $Notes }

    if (-not [string]::IsNullOrWhiteSpace($noteToAppend)) {
        $existingNotes = $app.Notes
        $updatedNotes = if ([string]::IsNullOrWhiteSpace($existingNotes)) {
            $noteToAppend
        }
        else {
            "$existingNotes`r`n$noteToAppend"
        }

        Update-MgApplication -ApplicationId $app.Id -Notes $updatedNotes
    }

    # Create a client secret if requested
    $secret = $null
    if ($CreateSecret) {
        $endDate = switch ($SecretExpiry) {
            '1year' { (Get-Date).AddYears(1) }
            '2years' { (Get-Date).AddYears(2) }
            '180days' { (Get-Date).AddDays(180) }
            default { (Get-Date).AddYears(1) }
        }

        if ($Ticketnumber) {
            $SecretName = $Ticketnumber
        }
        else {
            $SecretName = 'Generated Secret'
        }

        $passwordCredential = @{
            displayName = $SecretName
            endDateTime = $endDate
        }

        $secret = Add-MgApplicationPassword -ApplicationId $app.Id -PasswordCredential $passwordCredential
    }

    # Output the results
    [PSCustomObject]@{
        Request     = if ($Ticketnumber) { $Ticketnumber } else { $null }
        DisplayName = $app.DisplayName
        AppId       = $app.AppId
        Expires     = if ($secret) { $secret.EndDateTime.ToString('yyyyMMdd') } else { $null }
        SecretId    = if ($secret) { $secret.KeyId } else { $null }
        Secret      = if ($secret) { $secret.SecretText } else { $null }
    }
    '=================================================' 
    ''
}
catch {
    Write-Error "An error occurred: $_"
}