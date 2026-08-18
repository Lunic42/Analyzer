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
EMOTION_LABELS = ["Joy", "Sadness", "Anger", "Fear", "Surprise", "Disgust"]


def _deduplicate_bullet_lines(text: str) -> str:
    """Remove consecutive duplicate bullet lines (e.g., '- Confidence: ...' repeated)."""
    lines = text.splitlines()
    cleaned = []
    last_clean = None
    for line in lines:
        # Strip leading bullet markers (*, -, •) and whitespace for comparison
        stripped = line.lstrip("*•- ").strip()
        if stripped == last_clean:
            continue   # skip duplicate
        cleaned.append(line)
        last_clean = stripped
    return "\n".join(cleaned)


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


# ---------------------------------------------------------------------------
# Structured text analysis — summaries, detailed sentiment, emotions
# ---------------------------------------------------------------------------
_LENGTH_INSTRUCTIONS = {
    "short": "1-2 sentences total",
    "medium": "3-4 sentences total",
    "long": "2-3 short paragraphs",
}


def summarize_text(api_key, model, text, length="medium", bullet_points=False):
    """
    Real structured summarization: returns (summary, key_phrases, error).
    key_phrases is a list of short strings pulled from the real input text.
    """
    length_instruction = _LENGTH_INSTRUCTIONS.get(length, _LENGTH_INSTRUCTIONS["medium"])
    format_instruction = (
        'Format "summary" as a markdown bulleted list (use "- " per line).'
        if bullet_points else
        'Write "summary" as flowing prose (no bullets).'
    )
    system_prompt = (
        "You are a precise summarization assistant. Read the user's text and respond "
        'ONLY with a JSON object: {"summary": "...", "key_phrases": ["...", "..."]}. '
        f"Summary length: {length_instruction}. {format_instruction} "
        '"key_phrases" must be 5-8 short noun phrases (2-4 words each) capturing the '
        "core topics of the text — no duplicates, no full sentences."
    )
    content, error = call_openrouter(api_key, model, system_prompt, text, max_tokens=900, temperature=0.4)
    if error:
        return None, [], error

    try:
        parsed = json.loads(_clean_json_block(content))
        summary = str(parsed.get("summary", "")).strip()
        key_phrases = [str(p).strip() for p in parsed.get("key_phrases", []) if str(p).strip()]
        if not summary:
            return content, [], None
        return summary, key_phrases, None
    except json.JSONDecodeError:
        # Model didn't follow the JSON format — fall back to using the raw text as
        # the summary rather than losing the result entirely.
        return content, [], None


def _split_into_chunks(text, chunk_chars=6000):
    """Split real article text into paragraph-respecting chunks near chunk_chars each."""
    paragraphs = text.split("\n")
    chunks, current = [], ""
    for p in paragraphs:
        if current and len(current) + len(p) > chunk_chars:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n{p}" if current else p
    if current:
        chunks.append(current)
    return chunks


def summarize_long_text(api_key, model, text, length="medium", bullet_points=False,
                         chunk_chars=6000, progress_callback=None):
    """
    Map-reduce summarization for long articles: summarize each chunk, then summarize
    the combined chunk-summaries into the final result. Reports real progress across
    chunks via progress_callback(fraction_complete).
    Returns (summary, key_phrases, error).
    """
    if len(text) <= chunk_chars:
        summary, key_phrases, error = summarize_text(api_key, model, text, length, bullet_points)
        if progress_callback:
            progress_callback(1.0)
        return summary, key_phrases, error

    chunks = _split_into_chunks(text, chunk_chars)
    partial_summaries = []
    for i, chunk in enumerate(chunks):
        chunk_summary, _, error = summarize_text(api_key, model, chunk, length="medium", bullet_points=False)
        if not error and chunk_summary:
            partial_summaries.append(chunk_summary)
        if progress_callback:
            progress_callback((i + 1) / (len(chunks) + 1))

    if not partial_summaries:
        if progress_callback:
            progress_callback(1.0)
        return None, [], "Could not summarize any part of this article."

    combined = "\n\n".join(partial_summaries)
    final_summary, key_phrases, error = summarize_text(api_key, model, combined, length, bullet_points)
    if progress_callback:
        progress_callback(1.0)
    return final_summary, key_phrases, error


def analyze_sentiment_detailed(api_key, model, text):
    """
    Real structured sentiment scoring. Returns (dict, error) where dict is
    {"positive": float, "negative": float, "neutral": float, "explanation": str}.
    """
    system_prompt = (
        "You are a sentiment analysis expert. Analyze the user's text and respond ONLY "
        'with JSON: {"positive": <0-100>, "negative": <0-100>, "neutral": <0-100>, '
        '"explanation": "one or two sentences"}. The three numbers should sum to '
        "approximately 100 and reflect how strongly each sentiment is present."
    )
    content, error = call_openrouter(api_key, model, system_prompt, text, max_tokens=400, temperature=0.2)
    if error:
        return None, error
    try:
        parsed = json.loads(_clean_json_block(content))
        scores = {k: float(parsed.get(k, 0)) for k in ("positive", "negative", "neutral")}
        scores["explanation"] = str(parsed.get("explanation", "")).strip()
        return scores, None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, f"Could not parse sentiment scores: {content[:200]}"


def _sentiment_unit_prompt():
    return (
        "You are a sentiment analysis expert. Analyze the sentiment of this excerpt and "
        "respond with:\n- Sentiment: Positive/Negative/Neutral/Mixed\n- Confidence: XX%\n"
        "- Brief explanation of your decision\nKeep it brief and well-formatted."
    )


def _sentiment_combine_prompt():
    return (
        "You are given sentiment assessments of consecutive excerpts from one long "
        "document. Synthesize ONE overall verdict for the whole document, in the same "
        "format:\n- Sentiment: Positive/Negative/Neutral/Mixed\n- Confidence: XX%\n"
        "- Brief explanation referencing what drove the verdict"
    )


def analyze_sentiment_long(api_key, model, text, chunk_chars=6000, progress_callback=None):
    """
    Map-reduce sentiment analysis for long articles: analyze each chunk, then
    synthesize one overall verdict. Reports real progress across chunks via
    progress_callback(fraction_complete). Returns (result_text, error).
    """
    if len(text) <= chunk_chars:
        content, error = call_openrouter(
            api_key, model, _sentiment_unit_prompt(), text, max_tokens=500, temperature=0.3,
        )
        if progress_callback:
            progress_callback(1.0)
        if content:
            content = _deduplicate_bullet_lines(content)
        return content, error

    chunks = _split_into_chunks(text, chunk_chars)
    partials = []
    for i, chunk in enumerate(chunks):
        content, error = call_openrouter(
            api_key, model, _sentiment_unit_prompt(), chunk, max_tokens=300, temperature=0.3,
        )
        if not error and content:
            # Also dedupe each chunk's output (optional, but harmless)
            content = _deduplicate_bullet_lines(content)
            partials.append(f"Excerpt {i + 1}: {content}")
        if progress_callback:
            progress_callback((i + 1) / (len(chunks) + 1))

    if not partials:
        if progress_callback:
            progress_callback(1.0)
        return None, "Could not analyze sentiment for any part of this text."

    combined = "\n\n".join(partials)
    final_content, error = call_openrouter(
        api_key, model, _sentiment_combine_prompt(), combined, max_tokens=500, temperature=0.3,
    )
    if progress_callback:
        progress_callback(1.0)
    if final_content:
        final_content = _deduplicate_bullet_lines(final_content)
    return final_content, error


def analyze_emotions(api_key, model, text):
    """
    Real emotion classification. Returns (dict {emotion: score 0-100}, error).
    Scores are independent (not required to sum to 100) since multiple emotions
    can coexist.
    """
    system_prompt = (
        "You are an emotion classification expert. Score how strongly each of these "
        f"emotions is expressed in the user's text: {', '.join(EMOTION_LABELS)}. "
        "Respond ONLY with a JSON object mapping each exact label to an integer 0-100, "
        f'e.g. {{"Joy": 10, "Sadness": 0, ...}} using exactly these keys: {EMOTION_LABELS}.'
    )
    content, error = call_openrouter(api_key, model, system_prompt, text, max_tokens=300, temperature=0.2)
    if error:
        return None, error
    try:
        parsed = json.loads(_clean_json_block(content))
        scores = {label: float(parsed.get(label, 0)) for label in EMOTION_LABELS}
        return scores, None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, f"Could not parse emotion scores: {content[:200]}"