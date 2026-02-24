# Click2GO: Agentic Travel Planning Engine

## 1. Project Overview
Click2GO is an automated, high-precision travel planner that generates personalized itineraries by synthesizing user preferences with real-time social sentiment from **Red Note (Xiaohongshu)**. 

The core innovation is an **Agentic Verification Loop** that prevents outdated or "hallucinated" travel recommendations by deploying autonomous agents to audit live social media data before finalizing any itinerary.

---

## 2. Technical Architecture

### A. The Orchestrator (Main Agent)
* **Role**: Primary controller for the planning lifecycle.
* **Inputs**: Destination, Dates, and User Persona (e.g., "Photography-focused," "Chilling," "Foodie").
* **Action**: Coordinates between the Scraper Tool, the Verification Agents, and the Routing Engine.

### B. Round 1: Discovery (Data Scraper Tool)
* **Process**: Scrapes high-engagement Red Note posts to identify a candidate list of 15–20 Points of Interest (POIs).
* **Metadata**: Captures titles, links, likes, and raw content for initial "Taste" tagging.

### C. Round 2: Agentic Verification (The "Reality Check")
* **Logic**: Each candidate POI is passed to an **Autonomous Verification Agent**.
* **Tools**: Search Tool (fetches the 5 most *recent* posts) + Reasoning Engine.
* **Verification Criteria**:
    * **Status Check**: Detects temporary closures or renovations mentioned in recent posts.
    * **Seasonality**: Validates if the "vibe" (e.g., autumn leaves, golden hour lighting) is active.
    * **Persona Alignment**: Critically analyzes if the current sentiment matches the user's specific "Taste" tags.

### D. MCP (Model Context Protocol) Integration
The following modules are exposed as **MCP Tools** for seamless AI interaction:
* `map_tool`: Wraps Google Maps (Global) & Baidu Maps (China) for geocoding and distance calculation.
* `social_scraper_tool`: Interface for the Red Note scraping logic.
* `itinerary_exporter`: Generates final PDF reports and stylized JPG route maps.

---

## 3. Tech Stack Requirements
* **Language**: Python 3.10+ or TypeScript.
* **Framework**: LangGraph or LangChain (to manage stateful agentic loops).
* **Database**: SQL-based storage for user profiles and cached POI validations.
* **APIs**: Google Maps API, Baidu Maps API, Anthropic/OpenAI API.

---

## 4. Key Features
1.  **Preference-Driven Survey**: Captures traveler style (Photography, Exercise, Chilling) and constraints (Allergies, Budget).
2.  **Agentic Audit**: Real-time validation of every location to ensure it is "open and recommended."
3.  **K-Means Routing**: Clusters validated spots into logical daily zones to minimize commute time.
4.  **Visual Route Mapping**: Generates a stylized, cartoon-style JPG map of the final route.
5.  **Smart Export**: A detailed PDF containing booking links and "Agent Notes" explaining why specific spots were selected.

---

## 5. Development Instructions for Claude Code
1.  **Initial Setup**: Build a FastAPI backend structured to support an MCP server.
2.  **Agent Implementation**: Define the `Verification Agent` with a prompt focus on "Sentiment Analysis" and "Freshness."
3.  **Data Pipeline**: Ensure a strict flow: *User Input -> Scraper -> Agent Verification -> Route Optimizer -> Final Export.*
4.  **Error Handling**: Implement fallbacks for when the scraper fails or if no POIs pass the Agentic Verification.