from pathlib import Path

dirs = [
    "backend/app/api", "backend/app/core", "backend/app/models",
    "backend/app/schemas", "backend/app/repositories", "backend/app/services",
    "backend/tests", "engine", "fixtures", "frontend", "docs", "data",
]
for d in dirs:
    Path(d).mkdir(parents=True, exist_ok=True)

for pkg in ["backend", "backend/app", "backend/app/api", "backend/app/core",
            "backend/app/models", "backend/app/schemas",
            "backend/app/repositories", "backend/app/services", "engine"]:
    Path(pkg, "__init__.py").touch()

print("Structure created.")