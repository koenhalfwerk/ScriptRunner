<#
.SYNOPSIS
    Creates an Azure AD (Entra ID) application with OAuth/OIDC support and adds owners. Created for requests from the A&T team
.EXAMPLE
    "OKL_BIA","OKL_BIA Acc","OKL_BIA Tst" | % {. .\New-AnTApp.ps1 -AppType OIDC -DisplayName $_ -owners 'rga025@uwv.nl','tfa014@uwv.nl','dbr105@uwv.nl' -Notes "RFC: RFC-443340"}
#>

param (
    [Parameter(Mandatory = $true)]
    [ValidateSet('OAuth', 'OIDC', 'SAML')]
    [string]$AppType,

    [Parameter(Mandatory = $true)]
    [string]$DisplayName,

    [string[]]$Owners = @(),

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

$graphEndpoint = (Get-MgEnvironment -Name (Get-MgContext).Environment).GraphEndpoint

function Wait-GraphObject {
    param (
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$ObjectName
    )
    $maxWaitSeconds = 60
    $elapsedSeconds = 0
    $delaySeconds = 1
    while ($elapsedSeconds -lt $maxWaitSeconds) {
        try {
            return & $Command
        }
        catch {
            if ($_.Exception.Message -notmatch '404|NotFound|Resource.*does not exist') {
                throw
            }
            $sleepSeconds = [Math]::Min($delaySeconds, $maxWaitSeconds - $elapsedSeconds)
            Start-Sleep -Seconds $sleepSeconds
            $elapsedSeconds = $elapsedSeconds + $sleepSeconds
            if ($delaySeconds -lt 8) {
                $delaySeconds = $delaySeconds * 2
            }
        }
    }
    throw "$ObjectName was not available in Graph after $maxWaitSeconds seconds."
}

# Check if the applicationname already exist. No Duplicates
$filterDisplayName = $DisplayName.Replace("'", "''")
$existingApp = @(Get-MgApplication -Filter "displayName eq '$filterDisplayName'" -Top 1)
$existingSpn = @(Get-MgServicePrincipal -Filter "displayName eq '$filterDisplayName'" -Top 1)
if ($existingApp -or $existingSpn) {
    if ($existingApp) {
        Write-Warning "Application registration with display name '$DisplayName' already exists."
    }
    if ($existingSpn) {
        Write-Warning "Enterprise application with display name '$DisplayName' already exists."
    }
    throw "Display name '$DisplayName' is already in use. Script stopped."
}

try {
    # Create the application
    if ($AppType -in 'OAuth', 'OIDC') {
        $app = New-MgApplication -DisplayName $DisplayName -SignInAudience 'AzureADMyOrg' # -Web @{ RedirectUris = $RedirectUris }
        $app | Format-Table -AutoSize
        $spn = New-MgServicePrincipal -AppId $app.AppId 
    }
    if ($AppType -eq 'SAML') {
        $res = Invoke-MgInstantiateApplicationTemplate -ApplicationTemplateId '8adf8e6e-67b2-4cf2-a259-e3dc5476c621' -DisplayName $DisplayName
        $app = $res.Application
        $spn = $res.ServicePrincipal
        $app | Format-Table -AutoSize

        # SAML template is not always directly available.
        $appcheckId = $app.Id
        $app = Wait-GraphObject -ObjectName "Application '$DisplayName'" -Command {
            Get-MgApplication -ApplicationId $appcheckId -ErrorAction Stop
        }

        $spncheckId = $spn.Id
        $spn = Wait-GraphObject -ObjectName "Enterprise application '$DisplayName'" -Command {
            Get-MgServicePrincipal -ServicePrincipalId $spncheckId -ErrorAction Stop
        }
    }

    if ($Notes) {
        if ($app) {
            Update-MgApplication -ApplicationId $app.Id -Notes $Notes
        }
        if ($spn) {
            Update-MgServicePrincipal -ServicePrincipalId $spn.Id -Notes $Notes
        }
    }

    # set the Enterprise app to hidden
    if ($spn) {
        $tags = @($spn.Tags)
        if ($tags -notcontains 'HideApp') {
            $tags = $tags + 'HideApp'
            Update-MgServicePrincipal -ServicePrincipalId $spn.Id -Tags $tags 
        }
    }

    # Add owners if specified
    if ($Owners) {
        foreach ($owner in $Owners) {
            $user = Get-MgUser -UserId $owner -ErrorAction SilentlyContinue
            if ($user) {
                $currentUserOdataId = "$graphEndpoint/v1.0/users/{$($user.Id)}"

                New-MgApplicationOwnerByRef -ApplicationId $app.Id -OdataId $currentUserOdataId
                if ($spn) {
                    New-MgServicePrincipalOwnerByRef -ServicePrincipalId $spn.Id -OdataId $currentUserOdataId
                }
            }
            else {
                Write-Warning "User $owner not found. Skipping."
            }
        }
    }
}
catch {
    Write-Error "An error occurred: $_"
}
finally {
}