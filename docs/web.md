# Booth Blaster — Web / GitHub Pages

Play in a browser (including iPhone Safari) via [pygbag](https://pygame-web.github.io/wiki/pygbag/).

## Play URL

After the GitHub Actions workflow succeeds and Pages is enabled:

`https://lmccreationsllc8-cpu.github.io/DobbyCatRomGame/`

## Enable GitHub Pages (one-time)

1. Repo → **Settings** → **Pages**
2. **Build and deployment** → Source: **Deploy from a branch**
3. Branch: **gh-pages** / folder: **/ (root)** → Save

Pushing to `master` (or `main`) runs `.github/workflows/deploy-pages.yml`, which builds the WASM package and updates `gh-pages`.

## Local web test

```bash
python -m pip install pygbag
# From repo root — stages only game files then serves:
rm -rf web_src
mkdir -p web_src && cp -r main.py config.py core games assets web_src/
# Prefer OGG in the staged tree for browser audio:
# (OGG files already live under assets/audio/)
python -m pygbag --ume_block 0 web_src
```

Open http://localhost:8000 — tap/click once to start audio on mobile.

## Controls (phone)

- Drag to move Dobby
- Tap / hold to fire
- Mute chip and audio panel work as on Android

Scores and mute settings store in the browser (`localStorage`).
