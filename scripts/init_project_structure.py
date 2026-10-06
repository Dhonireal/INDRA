"""
Initialize the complete project directory structure according to docs/file-structure.md.
"""
import os

directories = [
    "app",
    "app/core",
    "app/ui",
    "app/ui/styles",
    "app/voice",
    "app/voice/providers",
    "app/perception",
    "app/perception/ocr",
    "app/perception/vision",
    "app/agent",
    "app/agent/providers",
    "app/actions",
    "app/safety",
    "app/verification",
    "app/hardware",
    "app/storage",
    "app/services",
    "tests",
    "tests/unit",
    "tests/integration",
    "tests/fixtures",
    "assets",
    "assets/icons",
    "assets/demo",
    "models",
    "packaging",
    "data",
    "logs",
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)
    if directory.startswith("app") or directory.startswith("tests"):
        init_file = os.path.join(directory, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w", encoding="utf-8") as f:
                f.write('"""Package initialization."""\n')

print("VisionPilot directory tree created successfully.")
