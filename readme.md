
## Intro

ScriptRunner is nothing more than a flask server that translates json configured parameters to a powershell script call.
Its best served by Waittress

### Adding a new script

You can add new PowerShell scripts and automatically generate a UI by creating a JSON config.

---

#### Files

Place your script in the `scripts/` folder:
Place a json file with the same name in `configs/`

#### Config

Types
| JSON type | UI | PowerShell |
|----------|----|-----------|
| text | input | `[string]` |
| number | input type=number | `[int]` |
| checkbox | checkbox | `[bool]` |
| select | dropdown | `[string]` |
| checkbox-list | checkbox-list | `[string[]]` |

Optional
| Field | Description |
|------|------------|
| `label` | Display name in UI |
| `required` | Marks field as required (UI hint) |
| `default` | Default value |
| `options` | Values for select dropdown |

Simpele config
```json
{
  "name": "My Script",
  "script": "MyScript.ps1",
  "parameters": [
    {
      "name": "DisplayName",
      "label": "Display Name",
      "type": "text",
      "required": true,
      "default": "MyApp"
    },
    {
      "name": "maxResults",
      "label": "Max Results",
      "type": "number",
      "default": 10
    },
    {
      "name": "roles",
      "label": "Roles",
      "type": "checkbox-list",
      "options": ["Reader", "Writer", "Admin"],
      "default": ["Reader", "Writer"]
    }
  ]
}
```

Config met parameter set
```json
{
  "name": "My Script",
  "script": "MyScript.ps1",
  "parameterSets": [
    {
      "name": "DisplayName",
      "label": "Lookup by Display Name",
      "parameters": [
        {
          "name": "DisplayName",
          "label": "Display Name",
          "type": "text",
          "required": true,
          "default": "MyApp"
        },
        {
          "name": "SecretExpiry",
          "label": "SecretExpiry",
          "type": "select",
          "options": [
            "1year",
            "2year",
            "3year"
          ],
          "default": "1year"
        },
      ]
    },
    {
      "name": "ApplicationID",
      "label": "Lookup by Application ID",
      "parameters": [
        {
          "name": "ApplicationID",
          "label": "Application ID",
          "type": "text",
          "required": true
        },
        {
          "name": "force",
          "label": "Force execution",
          "type": "checkbox",
          "default": true
        }
      ]
    }
  ]
}
```

Notes:
- Checkbox translates to a boolean, dont use switches
- Only parameters with values are passed to PowerShell



## setup
### Install Python

1. Download Python from https://www.python.org/downloads/
2. Run the installer
3. Make sure to check "Add Python to PATH"
4. Verify installation:

   ```powershell
   python --version

### Run setup.ps1

### Run Start.ps1 on every use