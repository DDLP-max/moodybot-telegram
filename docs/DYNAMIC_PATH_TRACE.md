# Dynamic Mode production path trace

## Verdict

Live **Dynamic Mode** is **not** the Telegram Render worker in `moodybot-telegram`.

It is the Node web app:

- Repo: `DDLP-max/moodybot-app`
- Frontend: `client/src/pages/dynamic.tsx`
- API: `POST /api/chat/messages`
- Generator: `server/moodybot.ts` → `generateChatResponse()`
- Post-process: `utils/moodybotPostProcess.ts`

`recognition_landing.py` in this Telegram repo was never on that path. That is why the broken closer survived after the Python landing work shipped.

## Exact call chain (web Dynamic Mode)

1. `client/src/pages/dynamic.tsx` — `fetch("/api/chat/messages", { mode: "dynamic" })`
2. `server/routes.ts` — `app.post("/api/chat/messages", ...)`
3. `server/moodybot.ts` — `generateChatResponse(message, "dynamic", ...)`
4. OpenRouter chat completion (`MODEL_DYNAMIC`)
5. `postProcessMoodyResponse(aiRaw, userMessage, { mode: "dynamic" })`
6. `applyRecognitionLanding()` in `utils/recognitionLanding.ts` (**authoritative closer gate**)
7. `finalSurfaceRender()` — typography only
8. `appendSignature()` — brand line only (no random CTA in Dynamic)
9. HTTP JSON `{ aiMessage.content, landing_engine_version, diagnostics }`

## Telegram path (separate runtime)

1. Telegram update → `moodybot.py` `handle_message`
2. OpenRouter
3. polish helpers
4. `finalize_response()` → epistemic → `apply_landing()` (`recognition_landing.py`) → `final_surface_render()`
5. `send_message(..., allow_cta=False)`

Render Background Worker deploys **this** repo. Web Dynamic Mode deploys **moodybot-app**.

## Deployment fingerprint

Every Dynamic response must log:

- `DYNAMIC_TRACE_START` … `DYNAMIC_TRACE_END`
- `landing_engine_version=recognition-landing-v1`

If that version string is missing from host logs, production is stale / wrong service.

## Banned closer

Any landing matching:

- `What about … looks different…`
- `…now that you've seen it named?`
- `What about … hate …`

must be `REJECTED` by `validateLanding()` / `validate_landing()` and must not appear in the HTTP body.
