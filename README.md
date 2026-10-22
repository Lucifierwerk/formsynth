# FormSynth — Synthetic Google Forms Response Generator

Educational tool for generating synthetic survey responses.  
Designed for marketing students to practice data analysis on realistic (but artificial) datasets.

---

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API will be available at http://localhost:8000  
Swagger docs at http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Usage

1. **Parse** — Paste any public Google Form URL and click Parse.  
   The form questions and answer options are extracted automatically.

2. **Configure** — In the Config tab:
   - Enable/disable individual answer options per question
   - Adjust weight sliders to bias answer probabilities  
     (weight=10 means ~10× more likely than weight=1)
   - For checkbox questions: set min/max selected count
   - For text questions: add a custom phrase pool
   - Choose respondent profiles (Premium, Young Female, etc.)

3. **Settings** — Right sidebar:
   - Set total number of responses to generate
   - Adjust concurrency (parallel requests)
   - Configure delays between submissions
   - Set batch size and pause between batches

4. **Start** — Click Start. Watch progress and realtime logs.  
   Use Pause / Resume / Stop at any time.

5. **Analytics** — Switch to the Analytics tab to see estimated answer distributions.

6. **Export / Import** — Save your full configuration as JSON and reload it later.

---

## Supported Question Types

| Google Forms | FormSynth Type | Behaviour |
|---|---|---|
| Multiple Choice (radio) | `single` | Picks one option by weight |
| Dropdown | `single` | Picks one option by weight |
| Checkboxes | `multi` | Picks min–max options by weight |
| Short Answer | `text` | Picks from phrase pool |
| Paragraph | `textarea` | Picks from longer phrase pool |

---

## Respondent Profiles

Profiles bias answer weights for certain question categories:

| Profile | Effect |
|---|---|
| `young_male` | Younger age ranges, male gender options |
| `young_female` | Younger age ranges, female gender options |
| `premium_customer` | Higher budget options |
| `budget_buyer` | Lower budget options |
| `event_customer` | Event-related purpose options |

Multiple profiles can be active simultaneously.

---

## API Reference

| Method | Path | Description |
|---|---|---|
| POST | `/api/forms/parse` | Parse a Google Form URL |
| POST | `/api/jobs/start` | Start a job |
| GET | `/api/jobs/{id}` | Get job status |
| POST | `/api/jobs/{id}/pause` | Pause |
| POST | `/api/jobs/{id}/resume` | Resume |
| POST | `/api/jobs/{id}/stop` | Cancel |
| GET | `/api/jobs/{id}/logs` | Get logs |
| WS | `/ws/jobs/{id}/logs` | Realtime log stream |

---

## Notes

- The parser requires the form to be **publicly accessible** (Anyone with the link).
- No Selenium or browser automation is used — pure HTTP requests.
- All data stays local; nothing is sent anywhere except to your own Google Forms.
- Works with Russian and English forms.

---

## File Structure

```
formsynth/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── api/routes.py        # REST + WebSocket endpoints
│   │   ├── models/schemas.py    # Pydantic models
│   │   ├── parser/form_parser.py     # Google Forms parser
│   │   ├── generator/response_generator.py  # Weighted random engine
│   │   ├── sender/form_sender.py    # Async HTTP submission
│   │   ├── jobs/job_manager.py      # Job lifecycle management
│   │   └── websocket/ws_manager.py  # WebSocket broadcast
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   │   ├── Toolbar.tsx       # URL input + job controls
    │   │   ├── JobStatusBar.tsx  # Progress strip
    │   │   ├── QuestionPanel.tsx # Per-question weight editor
    │   │   ├── SettingsPanel.tsx # Global settings + profiles
    │   │   ├── LogsPanel.tsx     # Realtime log viewer
    │   │   └── AnalyticsPanel.tsx # Charts
    │   ├── store/index.ts        # Zustand state
    │   ├── api/index.ts          # API client
    │   └── types/index.ts        # TypeScript types
    └── package.json
```
