# Check if the 'npwd' directory exists
if  (!(Test-Path -Path npwd)) {
    # If not, create it
    New-Item -ItemType Directory -Force -Path npwd
}

# Navigate to the 'npwd' directory
Set-Location npwd

# Default parameter values
$defaultParams  = @{
    Source = "src"
    WithProgress = $true
    IdleTimeout = 900
}

# Create a new HashTable for parameters
$params  = @{}

# Fill the HashTable with passed arguments
for  ($i = 0; $i -lt $Args.Count; $i += 2) {
    # Remove leading dashes from parameter names and convert to camelCase
    $name = $Args[$i].TrimStart('-').Replace('-', '')
    # Add argument to the HashTable, or use default value if not provided
    if  ($Args.Length -gt $i + 1) {
        $params.Add($name, $Args[$i + 1])
    } elseif (-not $defaultParams.ContainsKey($name)) {
        # If the parameter is not in the default list, add it with a null value
        $params.Add($name, $null)
    } else {
        $params.Add($name, $defaultParams[$name])
    }
}

# Execute Python script with parameters passed from ps
python -m npwd run --source $params['Source'] --withProgress $params['WithProgress'] `
--idleTask (if ($null -ne $params['IdleTask']) { "--idleTask" }) `
--idleTimeout $params['IdleTimeout']