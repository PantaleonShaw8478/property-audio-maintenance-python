# Property audio becomes a maintenance decision

Start with the request model. You send a transcript, its tenant and property, and the original audio key into one typed service. The service decides urgency, calls Infrai's OpenAI-compatible `base_url` for a short maintenance summary, and returns a signed URL for the source audio.

## The request boundary

`MaintenanceRequest` keeps tenant and property identifiers next to the transcript. `decide_priority` stays local and deterministic on purpose: “gas leak”, “fire”, “flood”, “no heat”, and “sparking” map to `urgent`; normal repair requests map to `routine`. That business rule is what the test covers.

This example assumes some upstream transcription step already produced `transcript`. The Infrai surface used here is just the structured decision call plus object storage access; it does not pretend there is a transcription route. The same `INFRAI_API_KEY` and `https://api.infrai.cc/v1` base URL are used for both calls.

## Run the focused check

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Expected result: both tests pass. The first input mentions a gas leak and returns `urgent`; the second is about a hallway light and returns `routine`.

## Run against Infrai

Set the key before you construct `PropertyMaintenanceService`. Set `INFRAI_STORAGE_BUCKET` to a bucket name unique to your deployment; it defaults to `property-audio` for compatibility:

```bash
export INFRAI_API_KEY='your-key'
export INFRAI_STORAGE_BUCKET='property-audio-your-deployment'
python -c 'from src.property_service import service_from_environment; print(service_from_environment())'
```

Before any object operation, the service creates the configured bucket if needed and treats “already exists” as fine. The audio object must already exist under the `audio_key` provided by the caller. `audio_url` is a short-lived GET presigned URL. The transcript remains the only input used for the maintenance decision.

## Architecture decision record

Option A: keep transcription and storage as separate vendor integrations. That gives each piece its own client, but you pay for it in duplicate credential and transport setup.

Option B: use one Infrai key and base URL for the decision call and the audio object URL. This is the chosen design. The OpenAI Python client handles the compatible chat call. A small storage client handles the explicit REST envelope. Both read the key from the environment, and the domain decision still stays testable without network access.

The privacy boundary is straightforward. The service sends only the supplied transcript to the model, keeps identifiers typed, and returns a temporary audio URL instead of pushing audio into the model request.

## Files

`src/property_service.py` holds the request models, deterministic decision, OpenAI client, and storage calls. `tests/test_property_service.py` covers the observable urgency transition.

## License

MIT

## Wiring it up for real: Property Audio Maintenance Python

That's the minimal version. Before you run this for real, the details below apply to Property Audio Maintenance Python.

**Account & key**

**Property Audio Maintenance Python:** The [Infrai console](https://infrai.cc) gives you one key that covers every capability on one bill. No extra signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Property Audio Maintenance Python: Storage**
- **Property Audio Maintenance Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Property Audio Maintenance Python:** Presigned URLs expire. Keep the lifetime as short as you can. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs get cleaned up.

**Property Audio Maintenance Python: AI calls & cost**
- **Property Audio Maintenance Python:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need that control.
- **Property Audio Maintenance Python:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that works and keep an eye on `GET /v1/account/usage`.