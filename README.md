# Composio App Research Pipeline

## What it does
Researches the 100 assigned apps for:
- Authentication
- Developer access / gating
- API surface
- MCP availability
- Buildability

## Setup

### Prerequisites
- Python 3.10+
- Git
- Required API/model credentials

### Install

git clone <repo-url>
cd composio-app-research

python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

## Configuration

Configure the credentials/environment variables required by
`src/researcher.py`.

Do not commit `.env` or API keys.

## Run the research

python src/run_all.py

The runner:
1. Loads apps from `data/apps.json`
2. Searches documentation for authentication, API, access and MCP
3. Fetches and cleans selected sources
4. Extracts structured evidence
5. Generates the research record
6. Saves results under `results/`
7. Skips completed apps when rerun

## Run analysis

python src/analyze.py

Outputs:
- results/analysis.json
- results/analysis_summary.md

## Output

results/
├── individual app results
├── results.json
├── analysis.json
└── analysis_summary.md

## Case Study

Open:
case-study/index.html

## Verification

A sample of the generated results was checked against
the cited documentation. Recurring errors were identified,
the extraction logic was improved, and affected research
was rerun.

## Important

The pipeline researches public documentation and does not
claim to directly call the production APIs of all 100 apps.
Unknown information is preserved rather than guessed.
# Project Workflow

The complete workflow is:

```text
                    data/apps.json
                         |
                         v
                +-------------------+
                |   Research Runner |
                |   run_all.py      |
                +-------------------+
                         |
                         v
              Research each application
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
   Authentication       API          Access
          |              |              |
          +--------------+--------------+
                         |
                         v
                        MCP
                         |
                         v
              Source Discovery / Fetch
                         |
                         v
               Evidence Extraction
                         |
                         v
               Structured JSON Result
                         |
                         v
                  results/*.json
                         |
                         v
                results/results.json
                         |
                         v
                  analyze.py
                         |
                         v
             Pattern & Cluster Analysis
                         |
             +-----------+-----------+
             |                       |
             v                       v
      analysis.json          analysis_summary.md
             |
             v
        Case Study HTML