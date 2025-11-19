
import os
import fileinput

files = [
    r"D:\Code\pc-control\pc-agent\src\api\main.py",
    r"D:\Code\pc-control\pc-agent\src\api\middleware.py",
    r"D:\Code\pc-control\pc-agent\src\api\rest_endpoints.py",
    r"D:\Code\pc-control\pc-agent\src\api\endpoints\pairing.py",
    r"D:\Code\pc-control\pc-agent\src\mcp_tools\tools.py",
    r"D:\Code\pc-control\pc-agent\src\services\audit_log_service.py",
    r"D:\Code\pc-control\pc-agent\src\services\certificate_service.py",
    r"D:\Code\pc-control\pc-agent\src\services\pairing_service.py",
    r"D:\Code\pc-control\pc-agent\src\services\pairing_validator.py",
    r"D:\Code\pc-control\pc-agent\src\services\system_control.py"
]

for file_path in files:
    try:
        with fileinput.FileInput(file_path, inplace=True) as file:
            for line in file:
                print(line.replace("from src.", "from ").replace("import src.", "import "), end='')
        print(f"Fixed {file_path}")
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
