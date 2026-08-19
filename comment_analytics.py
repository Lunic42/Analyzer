"""
Analytics computed directly from real fetched YouTube comments — no external
calls, no fabricated numbers. Everything here is pandas aggregation over the
comment list your app already pulled from the YouTube Data API.

Note on "most disliked": YouTube hid public dislike counts in Dec 2021 — the
Data API does not expose them, and no real dislike count can be fetched.
`most_liked_negative_comments()` is the honest substitute this module offers:
real like counts, filtered to comments the sentiment classifier scored as
Negative — a defensible proxy, not a real dislike figure.
"""
import re
from collections import Counter

import pandas as pd

# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
def filter_comments(df, min_likes=0, start_date=None, end_date=None):
    """Filter a comments DataFrame by minimum real like count and/or real published date range."""
    out = df.copy()
    if min_likes:
        out = out[out["like_count"] >= min_likes]
    if start_date is not None or end_date is not None:
        published = pd.to_datetime(out["published_at"], errors="coerce", utc=True)
        if start_date is not None:
            out = out[published >= pd.Timestamp(start_date, tz="UTC")]
            published = pd.to_datetime(out["published_at"], errors="coerce", utc=True)
        if end_date is not None:
            end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)
            out = out[published < end_ts]
    return out


# ---------------------------------------------------------------------------
# Sentiment trend over time
# ---------------------------------------------------------------------------
def sentiment_trend(df, freq="D"):
    """
    Real sentiment counts bucketed by real comment publish date.
    freq: 'D' (day), 'W' (week), 'M' (month) — pandas offset alias.
    Returns a DataFrame indexed by date bucket, columns Positive/Negative/Neutral.
    """
    if df.empty:
        return pd.DataFrame(columns=["Positive", "Negative", "Neutral"])
    work = df.copy()
    work["published_dt"] = pd.to_datetime(work["published_at"], errors="coerce", utc=True)
    work = work.dropna(subset=["published_dt"])
    if work.empty:
        return pd.DataFrame(columns=["Positive", "Negative", "Neutral"])
    grouped = (
        work.groupby([pd.Grouper(key="published_dt", freq=freq), "sentiment"])
        .size()
        .unstack(fill_value=0)
    )
    for col in ["Positive", "Negative", "Neutral"]:
        if col not in grouped.columns:
            grouped[col] = 0
    return grouped[["Positive", "Negative", "Neutral"]]


# ---------------------------------------------------------------------------
# Most liked / most-liked-negative ("closest real proxy to most disliked")
# ---------------------------------------------------------------------------
def most_liked_comments(df, n=10):
    return df.sort_values("like_count", ascending=False).head(n)


def most_liked_negative_comments(df, n=10):
    negative = df[df["sentiment"] == "Negative"]
    return negative.sort_values("like_count", ascending=False).head(n)


def most_replied_comments(df, n=10):
    if "reply_count" not in df.columns:
        return df.head(0)
    return df.sort_values("reply_count", ascending=False).head(n)


# ---------------------------------------------------------------------------
# Commenter analytics
# ---------------------------------------------------------------------------
def commenter_stats(df, n=15):
    """Real per-author aggregation: comment count, total likes received, sentiment mix."""
    if df.empty:
        return pd.DataFrame(columns=["Author", "Comments", "Total Likes", "Positive", "Negative", "Neutral"])
    grouped = df.groupby("author").agg(
        Comments=("text", "count"),
        **{"Total Likes": ("like_count", "sum")},
    )
    sentiment_pivot = df.pivot_table(index="author", columns="sentiment", aggfunc="size", fill_value=0)
    for col in ["Positive", "Negative", "Neutral"]:
        if col not in sentiment_pivot.columns:
            sentiment_pivot[col] = 0
    merged = grouped.join(sentiment_pivot[["Positive", "Negative", "Neutral"]])
    merged = merged.sort_values("Comments", ascending=False).head(n)
    merged.index.name = "Author"
    return merged.reset_index()


# ---------------------------------------------------------------------------
# Spam heuristics — deterministic, rule-based, no model call
# ---------------------------------------------------------------------------
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_PROMO_PHRASES = [
    "subscribe to my", "check out my channel", "check out my page", "follow me on",
    "click the link", "click here", "free money", "make money fast", "work from home",
    "dm me", "whatsapp me", "telegram me", "投资", "earn $", "guaranteed profit",
    "crypto giveaway", "bitcoin giveaway", "sign up now", "link in bio",
]
_REPEATED_CHARS_RE = re.compile(r"(.)\1{4,}")  # same char 5+ times in a row


def _spam_reasons(text, duplicate_count):
    text_lower = (text or "").lower()
    reasons = []
    if _URL_RE.search(text_lower):
        reasons.append("contains a link")
    matched_phrase = next((p for p in _PROMO_PHRASES if p in text_lower), None)
    if matched_phrase:
        reasons.append(f"promotional phrase (\"{matched_phrase}\")")
    if _REPEATED_CHARS_RE.search(text):
        reasons.append("repeated characters")
    if text and text.isupper() and len(text) > 15:
        reasons.append("all caps")
    if duplicate_count and duplicate_count > 2:
        reasons.append(f"identical text posted {duplicate_count}x by different accounts")
    return reasons


def detect_possible_spam(df):
    """
    Deterministic, rule-based spam flagging over real comment text — no model
    call, no fabricated confidence score. Flags: links, promotional phrases,
    repeated characters, all-caps shouting, and identical text repeated by
    multiple different authors (a classic real spam-wave signal).
    Returns a DataFrame of only the flagged rows, with a 'spam_reasons' column.
    """
    if df.empty:
        return df.assign(spam_reasons=[])

    text_counts = Counter(df["text"].str.strip().str.lower())
    flagged_rows = []
    for _, row in df.iterrows():
        dup_count = text_counts.get(str(row["text"]).strip().lower(), 0)
        reasons = _spam_reasons(row["text"], dup_count)
        if reasons:
            flagged_rows.append({**row.to_dict(), "spam_reasons": "; ".join(reasons)})

    return pd.DataFrame(flagged_rows)


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------
def to_excel_bytes(df):
    """Real .xlsx bytes for a download_button — no external service, built locally."""
    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Comments")
    return buffer.getvalue()


def try_to_excel_bytes(df):
    """
    Same as to_excel_bytes(), but never raises — returns (bytes, error).
    Use this from the UI so a missing/broken openpyxl install degrades to a
    warning instead of crashing the whole Streamlit script (Streamlit halts
    the entire page render on any uncaught exception).
    """
    try:
        return to_excel_bytes(df), None
    except ImportError:
        return None, "Excel export needs the 'openpyxl' package — add it to requirements.txt and redeploy."
    except Exception as e:
        return None, f"Couldn't build the Excel file: {e}"