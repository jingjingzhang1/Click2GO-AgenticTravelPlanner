# Click2GO — Demo Recording Script

> An all-in-one AI travel companion: it plans a hotel-anchored, day-of itinerary,
> then becomes your live travel journal — photos, notes, and voice memories, all
> saved to your own database and browsable across every trip. Target: **3.5–4.5 min**.

---

## 0 · Pre-flight checklist (before you hit record)

- [ ] **Terminal 1** — start the server from the venv (this avoids the multipart error):
      ```bash
      cd "/Users/jingjingzhang/Desktop/personal_website/independent_projects/click2GO"
      .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
      ```
      Wait for `Application startup complete`.
- [ ] **Terminal 2** — open in the project folder, ready for the DB commands (optional if using DB Browser).
- [ ] **DB Browser for SQLite** — open the app, **Open Database →** `click2go.db`
      (Cmd+Shift+G to paste the path), land on **Browse Data → journal_entries**.
      Leave it open in a window you can switch to.
- [ ] **Browser: Google Chrome** (needed for voice-to-text), at `http://127.0.0.1:8000`,
      hard-refreshed (**Cmd+Shift+R**) so the latest UI (📁 My Trips button) is loaded.
- [ ] A sample **photo** on your machine + a working **microphone**.
- [ ] `.env` has the OpenRouter key. Optionally `rm click2go.db` + restart for a clean journal —
      but if you want to *show existing trips* in "My Trips," keep your current DB.
- [ ] Silence notifications; close noisy tabs.

---

## 1 · Hook (15–20s)

**SAY (punchy hook):**
> "Tired of over-planning a trip until there's no curiosity left? With Click2GO, you just
> book a hotel — it plans everything else. Think blind-box travel: you show up and go. And
> there's no stress on the day itself: you get step-by-step directions between every stop,
> and Click2GO reminds you to book the spots that need a reservation — with the link ready
> to go."

**SAY (alt — calmer, product framing):**
> "Click2GO is an autonomous multi-agent travel planner that doesn't just build an
> itinerary — it comes *with* you on the trip: hotel-anchored routing, day-of directions
> and reservations, and a live journal of photos, notes, and voice memories, all saved to
> your own database and browsable across every trip."

**DO:** Show the landing page.

---

## 2 · Plan a trip (30s)

**DO:** Fill the form:
- Destination: **New York**
- Hotel: **Ace Hotel New York**
- Duration: type **4** · Start date: any
- Travel style: **Photography** + **Chilling**
- Max stops/day: **3** · Click **Generate my itinerary**

**SAY (while it runs):**
> "Three specialized agents coordinate through a LangGraph supervisor — a Knowledge
> Manager curates real places, a Route Optimizer clusters them around my hotel with
> K-Means, and a Design Agent builds the map. Watch the pipeline run live."

---

## 3 · The itinerary — smart routing (35s)

**SAY:**
> "Here's the plan. Every day's route starts from my hotel — see the banner. And the
> routing has real business logic: coffee spots are capped at three a day, food at
> five, so no day is all cafés — each day is a balanced mix, clustered by neighborhood."

**DO:** On a spot, point out the **⭐ score**, **Book ahead** badge, **📅 Reserve /
🌐 Website**, and **🧭 From hotel / Directions** — click Directions to open live Google
Maps transit in a new tab. "No prep — works the day of, right on my phone."

---

## 4 · Interactive map (20s)

**DO:** Toggle **Dark mode**, **Distances** (shows transit time between stops), route lines.
**SAY:** "The map's generated per trip, color-coded by category, restyled instantly — no AI round-trip."

---

## 5 · The travel journal — the star (45s)

**DO:** Click **＋ Memory** on *Devoción* (or Brooklyn Bridge).

**DO + SAY:**
1. Type a note: *"Loved the green wall — best cortado of the trip."*
2. Click **🎙 Record voice note**, speak: *"Come back early, it gets busy by 10."* — watch it
   transcribe live. "Voice transcribes in the browser in real time, and it keeps the audio too."
3. Attach the **photo**.
4. Click **Save memory** → it appears under "Memories here" with the note, transcript, a
   playable audio clip, and the photo.

**SAY:** "Photo, typed note, and a voice memo — all pinned to this exact spot, saved instantly."

---

## 6 · Prove it's really in the database (30s)  ← credibility moment

**SAY:**
> "And this isn't just UI state — it's persisted to a real database."

**Option A — DB Browser (visual, recommended for video):**
**DO:** Switch to **DB Browser for SQLite**. Click the **↻ (Revert Changes / Refresh)** button
in the toolbar → **Browse Data → journal_entries**. Point at the new row — `spot_name`, `note`,
`transcript`. Switch the Table dropdown to **journal_media** → show the `file_path` rows for the
photo and audio.
**SAY:**
> "There's my note and the voice transcript in `journal_entries`, and the photo and audio
> files in `journal_media`. Managed with SQLAlchemy and Alembic migrations — SQLite by default,
> Postgres in production, so anyone who forks this hosts their own trip database."

**Option B — terminal (fastest, no refresh dance):**
**DO:** In Terminal 2:
```bash
sqlite3 click2go.db "SELECT spot_name, note, transcript FROM journal_entries;"
sqlite3 click2go.db "SELECT media_type, file_path FROM journal_media;"
ls media/
```
*(Reminder: DB Browser caches — always hit ↻ Refresh after saving, or it looks empty.)*

---

## 7 · Travel Log (15s)

**DO:** Back in the browser, click **📔 My Travel Log**.
**SAY:** "Everything rolls up into a personal travel log — a count of memories, photos, and voice
notes, with every entry, image, and recording in one place."

---

## 8 · My Trips — persistence across trips (30s)  ← NEW

**SAY:**
> "And it's not tied to one browser session. Every trip I've planned is saved."

**DO:** Close the log, click **📁 My Trips** (top-right of the planning form). Show the list —
each trip with its destination, dates, hotel, and **memory count**.
**SAY:**
> "Here's every trip, with how many memories each one holds. I can jump back into any past trip —"

**DO:** Click the **New York** trip → its itinerary and map reload → open **📔 My Travel Log** again
→ the Devoción memory is right there.
**SAY:**
> "— and all its photos, notes, and voice memos come right back. Plan a new trip, come back
> weeks later, everything's still here. This is the whole point: one platform for the entire trip."

---

## 9 · The AI poster (15s, optional)

**DO:** Click **🎨 Generate Poster.**
**SAY:** "A finishing touch — a custom hand-drawn travel-journal poster of the trip, generated
via an image model routed through OpenRouter."
*(If it shows `Provider: pollinations`, that's the keyless fallback — fine; mention OpenRouter/Gemini is primary.)*

---

## 10 · Under the hood — talking points (20s, voiceover)

**SAY:**
> "Under the hood: a clean layered backend — thin FastAPI routers over a service layer, a
> repository/DAO layer, and mappers. A real Model Context Protocol server exposes the database
> read-only to agents, plus structured logging with a `/metrics` endpoint, Docker Compose, and CI.
> Built to look like production, not a toy."

**DO:** Optionally flash the repo tree / `/docs` Swagger / `/metrics`.

---

## 11 · Close (10s)

**SAY:** "Click2GO — plan perfectly, arrive curious, and keep every memory in one place. Thanks for watching."

---

### Quick shot list
1. Landing → 2. Fill form (hotel + personas) → 3. Pipeline runs →
4. Itinerary (hotel banner, caps, Reserve, Directions) → 5. Map toggles →
6. ＋Memory (note + voice→text + photo, Save) → 7. **DB Browser: refresh → journal_entries / journal_media** →
8. Travel Log → 9. **📁 My Trips → reopen NY trip → Travel Log again** → 10. Poster → 11. README/Swagger/metrics → close.

### One-liners
- "Coffee's capped at 3 a day, food at 5 — the routing enforces a realistic mix."
- "Directions are live Google Maps transit links — no prep, works the day of."
- "Voice notes transcribe in the browser and save the audio."
- "It's all in a real SQLite/Postgres database with Alembic migrations — here it is in the DB."
- "Every trip is saved and browsable — jump back into any past trip's journal anytime."
- "Layered architecture, an MCP server, metrics, Docker, and CI — production-shaped."

### Recording gotchas
- Run the server with `.venv/bin/uvicorn …` so you never hit the `python-multipart` error.
- Use **Chrome** (voice-to-text) and open **`http://127.0.0.1:8000`** (not `localhost` if it's flaky).
- **DB Browser doesn't auto-refresh** — hit ↻ after saving or it looks empty.
