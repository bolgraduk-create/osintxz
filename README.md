# OSINTXZ Desktop

The authoritative Qt Quick desktop interface for OSINTXZ.

## What is included

- frameless dark desktop shell;
- segmented triangular OSINTXZ logo;
- sidebar with animated hover/selection states;
- top intelligence search bar and profile area;
- four metric cards;
- backend-backed investigation graph;
- Recent Intelligence and Recent Cases panels;
- responsive proportions down to 1280×720;
- subtle motion only — no neon/glow styling;
- Ctrl+K command-search overlay.

The interface is connected to the existing ServiceContainer, controllers and
application services. Empty installations show empty states; reference-design
records are not used as application data.

## Run on Windows

From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python main.py
```

## Reference geometry

The UI is tuned around a 1648×928 reference window and scales down to 1280×720.
# osintxz
