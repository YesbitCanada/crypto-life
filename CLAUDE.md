# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**币圈浮生记** (Crypto Life Simulator) is a single-file HTML5 browser game. The player owes $3,000 at 10% daily compound interest and has $1,000 to trade crypto assets over 20 days.

- `index.html` — the primary game file (pixel art style, current version)
- `crypto-cex.html` — legacy dark HUD version (backup/reference)
- `help.html` — rendered help page served alongside the game

## Deployment

Push to `main` triggers GitHub Actions (`.github/workflows/deploy.yml`), which uploads `index.html` and `help.html` to Tencent COS bucket `degen-1256918364` (region: ap-hongkong). Secrets needed: `TCB_SECRET_ID`, `TCB_SECRET_KEY`.

There is no build step — files are deployed as-is.

## Architecture

The entire game logic lives inside `index.html` as a single self-contained file:

- **CSS** — pixel art theme using CSS variables (`--panel`, `--screen`, `--screenText`, etc.) with `Courier New` monospace font. Panels use 4px borders + inset shadows for the pixel effect.
- **Game state** — a flat JS object (`state`) holding `cash`, `debt`, `savings`, `hp` (morale), `day`, `positions` (per-asset holdings), and `plusRugged` flag.
- **Assets** — defined in a `GOODS` array: BTC, ETH, DOGE, GPU, MINER, NFT, LP, PLUS — each with price range, color, and display name.
- **Daily loop** — `doMove()`: advances day, applies 10% debt compound interest, 1% AAVE savings interest, randomizes prices, checks liquidations (`checkLiquidations()`), then 65% chance triggers a random event.
- **Events** — defined in the `EVENTS` array (source of truth is `event.md`). Four types: `price` (multiply asset price by `rate`), `goods` (free airdrop of N units), `cash` (multiply cash by `rate`, adjust morale), `debt` (add fixed debt amount).
- **Special flags**: `plusRugged` — once PLUS rug-pull event fires, price locks to $0.01–$0.10 permanently. LP hack event allows price to go below floor but recovers next day.
- **Modals** — inline HTML modals for: events, liquidations, AAVE deposit/withdraw, repay debt, psychological help, Etherscan log, game over.
- **Persistence** — `localStorage` for save/load between sessions.

## Updating Events

`event.md` is the human-readable source of truth for all game events, mood mappings, ticker pool, and insider tips. After editing `event.md`, manually sync the changes into the `EVENTS` array, `TICKER_POOL`, and `INSIDER_TIPS` in `index.html`.

## Repository Conventions

- Version notes should be tracked in `CHANGELOG.md`. Keep entries aligned with the real shipped state of `index.html`, and do not open a new version section when the change clearly belongs to the current unreleased/recent version block.
- When Codex updates `CHANGELOG.md`, add a clear `Codex AI` note only for the items Codex actually changed or summarized. Do not attribute unrelated work to Codex.
- When Codex creates git commits for this repository, use `Codex AI` as the author note by default, preferably via single-commit `--author` instead of changing the user's global git identity.
- Keep `event.md` and `index.html` synchronized. If an event description, rate, icon, ticker hint, or insider tip changes in one place, update the corresponding source in the other file within the same task when possible.
