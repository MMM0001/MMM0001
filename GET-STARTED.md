# Getting started (non-technical guide)

This runs the dashboard on **your own computer**. It's free and private. You
only do the setup once; after that it's a double-click.

## Step 1 — Download the code from GitHub

1. Go to your repository on GitHub: **github.com/mmm0001/mmm0001**
2. Near the top-left there's a branch dropdown (it probably says `main`). Click
   it and choose the branch **`claude/hyperliquid-polymarket-arb-ceonb3`**.
3. Click the green **`< > Code`** button, then **Download ZIP**.
4. Find the downloaded ZIP in your Downloads folder and **unzip it**
   (double-click it on Mac; right-click → "Extract All" on Windows).
   You now have a folder with all the files in it — that's the "project folder."

## Step 2 — Start the dashboard

Open the unzipped folder and double-click the launcher for your computer:

- **Mac:** `Start-Dashboard-Mac.command`
- **Windows:** `Start-Dashboard-Windows.bat`

The first time, it spends a minute setting itself up. Then your web browser
opens automatically to the dashboard. A small black "terminal" window also
opens — **just leave it open**; it's what keeps the dashboard running. To stop
the dashboard later, close that window (or press `Ctrl+C` in it).

> **If it says Python isn't installed:** the launcher will tell you. Install it
> from <https://www.python.org/downloads/> (the big yellow "Download" button).
> On Windows, tick **"Add Python to PATH"** on the installer's first screen.
> Then double-click the launcher again.

> **Mac "unidentified developer" warning:** if double-clicking is blocked,
> right-click the `.command` file → **Open** → **Open** once to allow it.

## Step 3 — Use it

The dashboard opens at **http://localhost:8000**. `localhost` just means "this
computer," so the page only works while that terminal window is running.

- The shipped example event will show an **error** badge — that's expected,
  because it uses placeholder ids. Replace it with a real one (next step).
- Use **Add an event pair** to enter a market you want to watch. You'll need
  four ids — see below.

### What the four ids are

For each market you watch, the dashboard needs:

- **Hyperliquid YES id** and **NO id** — the `#` codes for the outcome on
  Hyperliquid.
- **Polymarket YES token id** and **NO token id** — long number strings from
  the Polymarket market.

Finding these by hand is the only fiddly part. If you'd like, I can add a
**"search markets" box** to the dashboard that looks them up and fills them in
for you — just ask.

---

**Reminder:** this tool only *detects and displays* opportunities. It never
places a trade. And always confirm a market means the *exact same thing* on
both venues before acting on any edge it shows.
