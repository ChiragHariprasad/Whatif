# Band Tom & Jerry

This standalone pair was provisioned with Band's official registration helper. It follows Band's LangGraph examples, adapted only so the provided Groq key can be used through its OpenAI-compatible endpoint.

`agent_config.yaml` contains the two generated Band agent credentials and is ignored by git. Copy `.env.example` to `.env`, enter `GROQ_API_KEY`, then run:

```powershell
uv sync
uv run python tom_agent.py
# in a second terminal
uv run python jerry_agent.py
```

Open `https://app.band.ai`, start a chat, add **Tom** only, then send `@Tom catch jerry`. Tom locates and invites Jerry.

The credentials created for these agents are separate from the Band user API key and no user key is saved in this folder.
