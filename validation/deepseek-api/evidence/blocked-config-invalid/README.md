# Evidence: the single real verification attempt stopped on missing configuration

`validation/deepseek-api/runs/<stamp>/` is the timestamped run directory (git-ignored).
This folder keeps a copy of the small files that document the outcome.

| File | Meaning |
| --- | --- |
| `prompt-0.txt` | the exact planner prompt the stage built (LF-normalised; sha256 equals `frozen/prompt-0.txt`) |
| `model-request.json` | the `deepseek_api` audit record: `status=config_invalid`, `request_sent=false` |
| `model-error.json` | the classified error: `model_config_invalid` |

Result: `DEEPSEEK_API_KEY` was not configured, so the backend refused to send
anything. **Zero requests were made**, no model name was guessed and the attempt was
not repeated. The same outcome is summarised in `../result.json`.

To complete the live check, put `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` in a local,
git-ignored `.env` (see `.env.example`) and run:

```sh
python validation/deepseek-api/verify_planner.py run --timeout 600
```
