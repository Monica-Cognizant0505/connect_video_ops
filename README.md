# Connected IT and Operations Intelligence

A single-page Streamlit demo of an end-to-end tire / service-center operation:
digital work, physical (video) operations, ERP and IoT evidence are correlated
into one operational context, and Neuro SAN agents turn it into decisions for
**Day-of Execution**, **Forecasting & Planning** and **CapEx / Budgeting**.

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app runs fully in **Demo Mode** with no backend, Soroco, CV model, ERP or IoT
connection. All demo content is labelled in the UI.

## Page flow (one operation, top to bottom)

1. Header and executive KPI strip
2. End-to-end business journey (9 clickable stages); the selected stage drives the evidence below
3. Operational evidence: Digital Work, Physical/Video, Enterprise Systems, IoT
4. Physical operations observation: extracted video frames and **Analyze Physical Operation**
5. Digital work observation: Soroco-style task evidence
6. Digital + physical correlation: unified swim-lane timeline and cross-channel insights
7. Neuro SAN intelligence: **Run Neuro SAN Analysis**, with six specialist agents
8. Neuro SAN decision intelligence (four questions)
9. Decision horizons, then the STUDY → … → ACT story footer

## Structure

```
app.py                         page composition only
components/                    one module per page section (+ theme.py)
services/
  config.py                    st.secrets / env lookup, DEMO vs CONNECTED
  digital_evidence_provider.py get_digital_evidence()   (Soroco / task mining)
  enterprise_evidence_provider.py  ERP, IoT, physical providers
  video_analyzer.py            analyze_video_frame(image)  (CV plug-in point)
  correlation_engine.py        unified timeline + OperationalContext
  neuro_san_client.py          run_neuro_san(context) -> NeuroSANResult
  http_events.py               shared HTTP helper for live sources
  workbook_evidence.py         reads the synthetic task-mining + video workbook per scenario
  video_assessment.py          video segment classification / assessment CSVs
  azure_openai.py              Azure OpenAI client (GPT-4o vision)
models/                        Pydantic: EvidenceEvent, OperationalContext, AgentResult, NeuroSANResult
data/demo_data.py              ALL demo values (KPIs, events, frame observations, sample assessment)
data/*.xlsx                    Synthetic_Soroco_TaskMining_Video_Integration_Demo workbook
data/video_assessment/         process-mining event log + KPI summary CSVs
assets/video_frames/           put extracted frames here
registries/                    Neuro SAN manifest + phygital_operations_intelligence.hocon
phygital_coded_tools/          AGENT_TOOL_PATH root for Neuro SAN (no coded tools yet)
scripts/                       check_neuro_san.py, repair_neuro_san_logging.py
setup.ps1, run_app.ps1         Windows: create venv + install, then run Streamlit
run_nsflow.ps1                 Windows: run the agent network in nsflow
```

## Configuration files

- `.streamlit/secrets.toml.example` → copy to `.streamlit/secrets.toml`
- `.env.example` → copy to `.env` (Azure OpenAI fallback)

Both real files are git-ignored.


## Video frames

Drop JPG/PNG files into `assets/video_frames/`. They are processed in filename
order (`frame_01.jpg`, `frame_02.jpg`, …). The N-th frame receives the N-th entry
of `FRAME_OBSERVATIONS` in `data/demo_data.py`, labelled **Demo observation**,
until a real model is connected via `VIDEO_AI_API_URL` or by editing
`analyze_video_frame()` in `services/video_analyzer.py`.

## Azure OpenAI (live mode)

Set these in `.streamlit/secrets.toml`, as environment variables, or in
Streamlit Cloud secrets. The `AZURE_OPENAI_*` / `OPENAI_API_VERSION` names in a
local `.env` also work as a fallback.

```toml
AZURE_API_KEY = "..."
AZURE_ENDPOINT = "https://techmod-azureopenai.openai.azure.com/"
DEPLOYMENT_NAME = "gpt-4o"
API_VERSION = "2024-12-01-preview"
```

With Azure configured, Demo Mode starts OFF (override with `DEMO_MODE = "true"`):

- **Video AI**: each frame goes to GPT-4o vision (`services/video_analyzer.py`
  → `_analyze_with_azure`). The previous observation and elapsed time are
  included so the model can flag extended service. Results are labelled
  "Azure gpt-4o vision" with the model-reported confidence.
- **Neuro SAN**: runs `registries/phygital_operations_intelligence.hocon`
  in-process on Azure (`NEURO_SAN_MODE=direct`). This needs the `neuro-san`
  package (`requirements-neuro-san.txt`), so on Streamlit Cloud use
  `NEURO_SAN_MODE=neuro_san` with `NEURO_SAN_API_URL` pointing at a hosted
  neuro-san server instead.

Digital, ERP and IoT remain demo data until their own endpoints are configured.
Their day-of-service timestamps in `data/demo_data.py` are aligned to the
supplied video frames (13:38–14:28).

## Connecting real systems

Set values in `.streamlit/secrets.toml` (see `secrets.toml.example`), as
environment variables, or in Streamlit Cloud → App settings → Secrets. Then
switch **Demo Mode** off in the sidebar. A source is shown as CONNECTED only
when Demo Mode is off and its URL is set. A failing live source falls back to
demo data with a visible warning.

| Source | Settings |
|---|---|
| Neuro SAN | `NEURO_SAN_MODE`, `NEURO_SAN_API_URL`, `NEURO_SAN_AGENT_NAME`, `NEURO_SAN_API_KEY` |
| Soroco / Digital | `DIGITAL_WORK_API_URL`, `DIGITAL_WORK_API_KEY` |
| Video AI | `VIDEO_AI_API_URL`, `VIDEO_AI_API_KEY` |
| ERP | `ERP_API_URL`, `ERP_API_KEY` |
| IoT | `IOT_API_URL`, `IOT_API_KEY` |

### Neuro SAN

The UI calls exactly one function, `services.neuro_san_client.run_neuro_san(context)`.
Search `neuro_san_client.py` for `TODO(NEURO SAN)`.

- `NEURO_SAN_MODE=neuro_san` posts to a neuro-san server at
  `{NEURO_SAN_API_URL}/api/v1/{NEURO_SAN_AGENT_NAME}/streaming_chat`. The prompt
  is `context.to_prompt_text()` plus the response contract, and the full
  OperationalContext is passed as `sly_data`.
- `NEURO_SAN_MODE=json` posts `{"operational_context": ...}` to your own endpoint,
  which returns NeuroSANResult JSON.
- `NEURO_SAN_MODE=direct` runs an in-process `SimpleOneShot` session. It needs
  `requirements-neuro-san.txt` and is not suitable for Streamlit Cloud.

The agent network must answer with the JSON described in `RESPONSE_CONTRACT`.
`AGENT_TOOL_ALIASES` maps your network's tool names to the six UI agents so
their cards light up as progress streams in.
