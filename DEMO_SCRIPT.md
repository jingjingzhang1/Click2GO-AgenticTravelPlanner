# Click2GO — Voiceover Script

> Read the text under each scene. The **[bracketed labels]** are just sync cues for
> the footage — don't read them. ~2.5–3.5 minutes at a natural pace.

---

**[Opening]**

Tired of over-planning a trip until there's no curiosity left? With Click2GO, you
just book a hotel — and it plans everything else. Think of it like blind-box travel:
you show up, and you go. And there's no stress on the day itself, because you get
step-by-step directions between every stop, and Click2GO reminds you to book the
places that need a reservation, with the link ready to go.

---

**[Planning a trip]**

Let's plan a trip to New York. I just tell it where I'm staying, how many days, and
what kind of traveler I am — here, photography and chilling. Behind the scenes, three
specialized agents coordinate through a LangGraph supervisor: a Knowledge Manager
curates real places, a Route Optimizer clusters them around my hotel, and a Design
Agent builds the map.

---

**[The itinerary]**

And here's the plan. Every day starts from my hotel. The routing has real logic built
in — coffee spots are capped at three a day, food at five — so no day is all cafés;
each one is a balanced mix, grouped by neighborhood to keep travel short. Every stop
comes with a rating, a reservation or website link, and one-tap directions — live
Google Maps transit, from my hotel or the previous stop. No prep. It just works on
the day.

---

**[The map]**

The route map is generated for each trip, color-coded by category, and I can restyle
it instantly — dark mode, transit times between stops, route lines — with no AI
round-trip.

---

**[The travel journal]**

Now the part that makes this a companion, not just a planner. On any stop, I add a
memory. I can type a note, record a voice note that transcribes to text right in the
browser while keeping the audio, and attach a photo. I hit save, and it's pinned to
that exact spot.

---

**[Proving it's saved in the database]**

And this isn't just something on the screen — it's saved to a real database. Here's
my note and the voice transcript in the journal entries table, and the photo and
audio files right alongside them. It's managed with SQLAlchemy and Alembic migrations
— SQLite by default, or Postgres in production — so anyone who forks this hosts their
own trip database.

---

**[Travel Log]**

Everything rolls up into a personal travel log — a count of my memories, photos, and
voice notes, with every entry, image, and recording in one place.

---

**[My Trips]**

And it's not tied to one session. Every trip I've planned is saved. I can see them all
here, with how many memories each one holds — jump back into any past trip to get its
itinerary and journal back, or delete the ones I don't need.

---

**[Under the hood]**

Under the hood, it's built like production software: a clean layered backend — thin
FastAPI routers over a service layer, a repository layer, and mappers — a real Model
Context Protocol server, structured logging with a metrics endpoint, Docker, and
continuous integration.

---

**[Close]**

Click2GO. Plan perfectly, arrive curious, and keep every memory in one place.
