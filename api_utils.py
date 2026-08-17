"""
OpenRouter helpers shared by the article-text tabs and the YouTube comments tab.

No demo/mock output anywhere — every function here makes a real HTTP call to
OpenRouter and returns whatever the model actually produced (or a real error).
"""
import json
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Free OpenRouter model — same as your original app.py. No paid credits needed.
DEFAULT_MODEL = "openrouter/free"

# If the default free router model fails/is rate-limited, fall back through
# these free-tier models, same idea as your original app.py's fallback list.
FREE_FALLBACK_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemini-2.0-flash-lite-preview-02-05:free",
    "microsoft/phi-3-mini-128k-instruct:free",
]

# Shown in the YouTube tab's model picker — all free, no credits required.
MODEL_OPTIONS = {
    "OpenRouter Free (auto)": DEFAULT_MODEL,
    "Llama 3.2 3B Instruct (free)": "meta-llama/llama-3.2-3b-instruct:free",
    "Gemini 2.0 Flash Lite (free)": "google/gemini-2.0-flash-lite-preview-02-05:free",
    "Phi-3 Mini 128k (free)": "microsoft/phi-3-mini-128k-instruct:free",
}

VALID_LABELS = ("Positive", "Negative", "Neutral")


def _post_openrouter(api_key, model, system_prompt, user_prompt, max_tokens, temperature, json_mode):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-app-name.streamlit.app",
        "X-Title": "Article Analyzer",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)


def call_openrouter(api_key, model, system_prompt, user_prompt,
                     max_tokens=1500, temperature=0.3, json_mode=False):
    """
    Real call to OpenRouter's chat completions endpoint, using free models only.
    If `model` fails (rate-limited, unavailable, etc.), automatically retries
    through FREE_FALLBACK_MODELS before giving up — same behavior as the
    original app.py.
    """
    if not api_key:
        return None, "OpenRouter API key not configured."

    models_to_try = [model] + [m for m in FREE_FALLBACK_MODELS if m != model]
    last_error = None

    for attempt_model in models_to_try:
        try:
            resp = _post_openrouter(api_key, attempt_model, system_prompt, user_prompt,
                                     max_tokens, temperature, json_mode)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                if attempt_model != model:
                    content += f"\n\n*(Note: used fallback model {attempt_model})*"
                return content, None
            last_error = f"OpenRouter error {resp.status_code} on {attempt_model}: {resp.text[:200]}"
        except requests.exceptions.Timeout:
            last_error = f"Request to OpenRouter timed out on {attempt_model}."
        except requests.exceptions.RequestException as e:
            last_error = f"Network error on {attempt_model}: {e}"
        except (KeyError, IndexError) as e:
            last_error = f"Unexpected response format from {attempt_model}: {e}"

    return None, last_error or "All free models failed."


def _clean_json_block(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned.split("\n", 1)[-1]
    cleaned = cleaned.strip()
    # Free models sometimes chat around the JSON ("Sure! Here's the result: {...}").
    # Fall back to grabbing the first {...} block if the whole string doesn't parse.
    if not (cleaned.startswith("{") and cleaned.endswith("}")):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]
    return cleaned


def classify_comments_batch(api_key, model, comments_batch):
    """
    Classify a batch of REAL comments in one call.
    comments_batch: list of dicts with 'comment_id' and 'text'.
    Returns (dict {comment_id: sentiment}, error_message).
    """
    numbered = "\n".join(f"{i}. {c['text'][:500]}" for i, c in enumerate(comments_batch))
    system_prompt = (
        "You are a precise sentiment classification engine. You will be given a numbered "
        "list of real user comments. Classify EACH one as exactly one of: Positive, "
        "Negative, Neutral. Respond ONLY with a JSON object mapping the number (as a "
        'string) to the label, e.g. {"0": "Positive", "1": "Negative"}. No other text, '
        "no markdown fences."
    )
    content, error = call_openrouter(
        api_key, model, system_prompt, numbered,
        max_tokens=2000, temperature=0, json_mode=False,
    )
    if error:
        return None, error

    try:
        parsed = json.loads(_clean_json_block(content))
    except json.JSONDecodeError:
        return None, f"Could not parse sentiment response as JSON: {content[:200]}"

    result = {}
    for i, c in enumerate(comments_batch):
        label = parsed.get(str(i), "Neutral")
        result[c["comment_id"]] = label if label in VALID_LABELS else "Neutral"
    return result, None


def classify_all_comments(api_key, model, comments, batch_size=25, progress_callback=None):
    """
    Classify every real comment in `comments` (mutates each dict with a 'sentiment' key).
    Returns (comments, list_of_batch_errors).
    """
    results = {}
    errors = []
    total_batches = max(1, (len(comments) + batch_size - 1) // batch_size)

    for b in range(total_batches):
        batch = comments[b * batch_size:(b + 1) * batch_size]
        if not batch:
            continue
        classified, error = classify_comments_batch(api_key, model, batch)
        if error:
            errors.append(f"Batch {b + 1}/{total_batches}: {error}")
            for c in batch:
                results[c["comment_id"]] = "Neutral"
        else:
            results.update(classified)
        if progress_callback:
            progress_callback((b + 1) / total_batches)

    for c in comments:
        c["sentiment"] = results.get(c["comment_id"], "Neutral")
    return comments, errors


def generate_executive_summary(api_key, model, comments, video_title=None):
    """
    Build an executive summary strictly from the REAL fetched comments (most-liked
    sample if the set is large, so the prompt stays a reasonable size).
    """
    sample = sorted(comments, key=lambda c: c.get("like_count", 0), reverse=True)[:150]
    lines = [
        f"- [{c.get('sentiment', '?')}] ({c['like_count']} likes) {c['author']}: {c['text'][:300]}"
        for c in sample
    ]
    comments_blob = "\n".join(lines)

    title_line = f'Video: "{video_title}"\n' if video_title else ""
    system_prompt = (
        "You are an analyst producing an executive summary of audience feedback from "
        "real YouTube comments. Base your summary strictly on the comments provided — "
        "do not invent details or comments that aren't there. Structure your response "
        "in markdown with exactly these sections:\n"
        "## Key Takeaways\n"
        "## Main Praise\n"
        "## Major Complaints / Pain Points\n"
        "Keep each section to 3-5 concise bullet points."
    )
    user_prompt = f"{title_line}Here are {len(sample)} real audience comments (most-liked first):\n\n{comments_blob}"

    return call_openrouter(api_key, model, system_prompt, user_prompt, max_tokens=900, temperature=0.4)