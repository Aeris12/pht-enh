# Photo Enhancer — Render prototype

Minimal single-button photo enhancer. API keys are read server-side from `GEMINI_API_KEY`.

## Deploy to Render
- Create a public GitHub repository and upload these files.
- In Render, create a Web Service from that repository.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Add `GEMINI_API_KEY` under Environment only when ready to test.
- `GEMINI_MODEL` defaults to `gemini-3.1-flash-image-preview`; verify model availability in your Google AI Studio account before spending credits.

## Notes
This is a prototype, not production-ready: no user accounts, daily quotas, durable image storage, billing, or abuse controls yet. Add those before opening publicly. The model may alter details despite the preservation prompt.
