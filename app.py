import os
import streamlit as st
import pandas as pd

import ui_theme
from ui_theme import inject_theme, masthead, sidebar_brand, dispatch_card, sentiment_chip_row, copy_button
from api_utils import summarize_long_text, analyze_sentiment_long, DEFAULT_MODEL
from analysis import run_youtube_analysis, run_youtube_analysis_multi
from file_utils import extract_text_from_upload
from history_utils import add_history_entry, get_history, clear_history
from youtube_utils import fetch_replies
import comment_analytics as ca

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Article Analyzer", page_icon="🗞️", layout="wide")
inject_theme()


def get_secret(name):
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name, "")


OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY")
YOUTUBE_API_KEY = get_secret("YOUTUBE_API_KEY")

# ---------------------------------------------------------------------------
# Sidebar — brand + nav
# ---------------------------------------------------------------------------
PAGES = ["📝 Summarize", "💬 Sentiment", "🎥 YouTube Comments", "🕘 History"]

if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = PAGES[0]

with st.sidebar:
    sidebar_brand("Navigate")
    for p in PAGES:
        is_active = st.session_state["nav_page"] == p
        if st.button(p, key=f"nav_btn_{p}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            st.session_state["nav_page"] = p
            st.rerun()

page = st.session_state["nav_page"]

if not OPENROUTER_API_KEY:
    st.error("⚠️ OpenRouter API key not found! Please set OPENROUTER_API_KEY in Streamlit secrets.")
    st.info("""
    ### How to fix this
    1. Create a `.streamlit` folder in your project root (if it doesn't exist)
    2. Create a `secrets.toml` file inside it
    3. Add:
       ```
       OPENROUTER_API_KEY = "your-openrouter-key"
       YOUTUBE_API_KEY = "your-youtube-data-api-key"
       ```
    """)
    st.stop()

# Long-article threshold — text longer than this (characters) is processed in
# real chunks (multiple real API calls) with a real per-chunk progress bar.
LONG_TEXT_CHARS = 6000


def char_count_caption(text):
    chars = len(text) if text else 0
    note = " — will process in chunks with a progress bar" if chars > LONG_TEXT_CHARS else ""
    st.caption(f"📝 {chars:,} characters{note}")


def summarize_with_llm(text, progress_callback=None):
    summary, _key_phrases, error = summarize_long_text(
        OPENROUTER_API_KEY, DEFAULT_MODEL, text,
        chunk_chars=LONG_TEXT_CHARS, progress_callback=progress_callback,
    )
    return error if error else summary


def analyze_sentiment(text, progress_callback=None):
    result, error = analyze_sentiment_long(
        OPENROUTER_API_KEY, DEFAULT_MODEL, text,
        chunk_chars=LONG_TEXT_CHARS, progress_callback=progress_callback,
    )
    return error if error else result


def run_with_progress(fn, text, label):
    progress = st.progress(0.0, text=label)
    result = fn(text, progress_callback=lambda p: progress.progress(p, text=f"{label} {int(p * 100)}%"))
    progress.empty()
    return result


def file_or_pasted_text(uploader_key, textarea_value):
    """
    Returns (effective_text, source_label). If a file is uploaded, its real
    extracted text wins (shown in a preview expander); otherwise falls back
    to whatever was pasted into the text area.
    """
    uploaded = st.file_uploader(
        "Or upload a file (PDF, DOCX, or TXT):", type=["pdf", "docx", "txt"], key=uploader_key,
    )
    if uploaded is not None:
        extracted, error = extract_text_from_upload(uploaded)
        if error:
            st.error(error)
            return textarea_value, "pasted text"
        with st.expander(f"📄 Extracted text from {uploaded.name}", expanded=False):
            st.text(extracted[:3000] + ("…" if len(extracted) > 3000 else ""))
        return extracted, f"file: {uploaded.name}"
    return textarea_value, "pasted text"


# ---------------------------------------------------------------------------
# Shared rendering helpers for YouTube analysis results
# ---------------------------------------------------------------------------
DISPLAY_COLS = ["author", "text", "like_count", "sentiment", "published_at", "author_channel_url"]
RENAME_COLS = {
    "author": "Author",
    "text": "Comment",
    "like_count": "Likes",
    "sentiment": "Sentiment",
    "published_at": "Published",
    "author_channel_url": "Author Link",
}


def render_video_meta(video_meta):
    if not video_meta:
        return
    st.markdown(
        f"<div style='font-family:\"IBM Plex Mono\",monospace; color:{ui_theme.TEXT_MUTED}; font-size:0.85rem; "
        f"margin-bottom:0.5rem;'>ON THE WIRE — <span style='color:{ui_theme.TEXT};'>{video_meta['title']}</span> "
        f"· {video_meta['channel']}</div>",
        unsafe_allow_html=True,
    )
    with st.expander("📺 Video details", expanded=False):
        m1, m2, m3 = st.columns(3)
        m1.metric("Views", f"{video_meta['view_count']:,}")
        m2.metric("Likes", f"{video_meta['like_count']:,}")
        m3.metric("Total comments (on video)", f"{video_meta['comment_count']:,}")


def render_sentiment_breakdown(df):
    counts = df["sentiment"].value_counts().reindex(["Positive", "Negative", "Neutral"]).fillna(0).astype(int)
    sentiment_chip_row({"Positive": int(counts.get("Positive", 0)),
                         "Negative": int(counts.get("Negative", 0)),
                         "Neutral": int(counts.get("Neutral", 0))}, total=len(df))
    st.write("")
    chart_df = counts.rename("Comments").to_frame()
    st.bar_chart(chart_df, color=ui_theme.ACCENT)
    return counts


def render_comment_table(frame):
    if frame.empty:
        st.info("No comments in this category.")
        return
    shown = frame[DISPLAY_COLS].rename(columns=RENAME_COLS).sort_values("Likes", ascending=False)
    st.dataframe(
        shown,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Author Link": st.column_config.LinkColumn("Author Link", display_text="Profile"),
            "Comment": st.column_config.TextColumn("Comment", width="large"),
        },
    )


def render_comment_tabs(df):
    filt_all, filt_pos, filt_neg, filt_neu = st.tabs(["All", "😊 Positive", "😠 Negative", "😐 Neutral"])
    with filt_all:
        render_comment_table(df)
    with filt_pos:
        render_comment_table(df[df["sentiment"] == "Positive"])
    with filt_neg:
        render_comment_table(df[df["sentiment"] == "Negative"])
    with filt_neu:
        render_comment_table(df[df["sentiment"] == "Neutral"])


def render_full_youtube_result(result, key_prefix):
    render_video_meta(result.get("video_meta"))

    st.markdown("### 🧾 Executive Summary")
    if result.get("summary_error"):
        st.error(result["summary_error"])
    elif result.get("summary"):
        with st.expander("Executive summary", expanded=True):
            with dispatch_card():
                st.markdown(result["summary"])
            copy_button(result["summary"], key=f"{key_prefix}_summary_copy")

    comments = result.get("comments") or []
    if not comments:
        st.info("No comments to show.")
        return

    df = pd.DataFrame(comments)

    st.markdown("### 📊 Sentiment Breakdown")
    render_sentiment_breakdown(df)

    st.markdown("### 💬 Comments")
    with st.expander("View all comments", expanded=True):
        render_comment_tabs(df)

    st.download_button(
        "⬇️ Download comments as CSV",
        df[DISPLAY_COLS].rename(columns=RENAME_COLS).to_csv(index=False).encode("utf-8"),
        file_name=f"{key_prefix}_comments_sentiment.csv",
        mime="text/csv",
        key=f"{key_prefix}_download_csv",
    )
    st.download_button(
        "⬇️ Download comments as Excel",
        ca.to_excel_bytes(df[DISPLAY_COLS].rename(columns=RENAME_COLS)),
        file_name=f"{key_prefix}_comments_sentiment.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{key_prefix}_download_xlsx",
    )


def render_reply_chains(df, key_prefix):
    """Real reply threads — top comments by real reply_count, replies fetched
    on demand (lazy) via the real YouTube comments.list endpoint."""
    top_replied = ca.most_replied_comments(df, n=10)
    top_replied = top_replied[top_replied["reply_count"] > 0]
    if top_replied.empty:
        st.info("No comments with replies in this set.")
        return

    if "loaded_replies" not in st.session_state:
        st.session_state["loaded_replies"] = {}

    for _, row in top_replied.iterrows():
        cid = row["comment_id"]
        with st.container(border=True):
            video_note = f" · *{row['video_title']}*" if "video_title" in row and pd.notna(row.get("video_title")) else ""
            st.markdown(f"**{row['author']}** — {row['like_count']} likes · {row['reply_count']} replies{video_note}")
            st.write(row["text"])
            if cid in st.session_state["loaded_replies"]:
                replies, error = st.session_state["loaded_replies"][cid]
                if error:
                    st.error(error)
                for r in replies:
                    st.markdown(f"↳ **{r['author']}**: {r['text']} · {r['like_count']} likes")
            else:
                if st.button(f"💬 Load {row['reply_count']} replies", key=f"{key_prefix}_load_{cid}"):
                    replies, error = fetch_replies(YOUTUBE_API_KEY, cid, max_results=50)
                    st.session_state["loaded_replies"][cid] = (replies, error)
                    st.rerun()


def render_cross_video_analytics(all_comments, key_prefix):
    """
    Filters, trends, rankings, spam flags, and commenter stats computed over
    the real merged comment set (one video, or several if multiple URLs were
    fetched at once).
    """
    df = pd.DataFrame(all_comments)
    if df.empty:
        return

    st.markdown("### 🔬 Cross-Video Analytics")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        min_likes = st.number_input("Minimum likes", min_value=0, value=0, step=1, key=f"{key_prefix}_min_likes")
    with col_f2:
        start_date = st.date_input("From date", value=None, key=f"{key_prefix}_start_date")
    with col_f3:
        end_date = st.date_input("To date", value=None, key=f"{key_prefix}_end_date")

    filtered = ca.filter_comments(df, min_likes=min_likes, start_date=start_date, end_date=end_date)
    st.caption(f"Showing {len(filtered):,} of {len(df):,} fetched comments after filters.")

    if filtered.empty:
        st.info("No comments match these filters.")
        return

    st.markdown("#### 📈 Sentiment Trend Over Time")
    freq_label = st.radio("Bucket by", ["Day", "Week", "Month"], horizontal=True, key=f"{key_prefix}_trend_freq")
    freq_map = {"Day": "D", "Week": "W", "Month": "M"}
    trend = ca.sentiment_trend(filtered, freq=freq_map[freq_label])
    if trend.empty:
        st.info("Not enough dated comments to chart a trend.")
    else:
        st.line_chart(trend)

    st.markdown("#### 🔥 Most Liked Comments")
    st.dataframe(
        ca.most_liked_comments(filtered, n=10)[["author", "text", "like_count", "sentiment"]]
        .rename(columns={"author": "Author", "text": "Comment", "like_count": "Likes", "sentiment": "Sentiment"}),
        use_container_width=True, hide_index=True,
    )

    st.markdown("#### 👎 Most-Liked Negative Comments")
    st.caption(
        "YouTube hid public dislike counts in 2021, so a real dislike count can't be fetched. "
        "This is the closest honest proxy: real like counts on comments the sentiment model scored as Negative."
    )
    most_liked_neg = ca.most_liked_negative_comments(filtered, n=10)
    if most_liked_neg.empty:
        st.info("No negative comments with likes in this set.")
    else:
        st.dataframe(
            most_liked_neg[["author", "text", "like_count"]]
            .rename(columns={"author": "Author", "text": "Comment", "like_count": "Likes"}),
            use_container_width=True, hide_index=True,
        )

    st.markdown("#### 🧵 Reply Chains")
    st.caption("Top comments by real reply count — click to load the actual replies.")
    render_reply_chains(filtered, key_prefix=key_prefix)

    st.markdown("#### 🚩 Possible Spam")
    st.caption("Rule-based flags on real comment text — links, promo phrases, repeated chars, duplicate spam waves. Not a model judgment.")
    spam_df = ca.detect_possible_spam(filtered)
    if spam_df.empty:
        st.success("No comments matched the spam heuristics.")
    else:
        st.dataframe(
            spam_df[["author", "text", "like_count", "spam_reasons"]]
            .rename(columns={"author": "Author", "text": "Comment", "like_count": "Likes", "spam_reasons": "Flagged for"}),
            use_container_width=True, hide_index=True,
        )

    st.markdown("#### 👤 Commenter Analytics")
    st.caption("Most active commenters in this fetched set (by real comment count).")
    st.dataframe(ca.commenter_stats(filtered, n=15), use_container_width=True, hide_index=True)

    st.markdown("#### ⬇️ Export Filtered Comments")
    export_cols = [c for c in ["video_title", "author", "text", "like_count", "sentiment",
                                "published_at", "reply_count", "author_channel_url"] if c in filtered.columns]
    export_df = filtered[export_cols]
    ec1, ec2 = st.columns(2)
    with ec1:
        st.download_button(
            "⬇️ CSV", export_df.to_csv(index=False).encode("utf-8"),
            file_name="filtered_comments.csv", mime="text/csv", key=f"{key_prefix}_export_csv",
        )
    with ec2:
        st.download_button(
            "⬇️ Excel", ca.to_excel_bytes(export_df),
            file_name="filtered_comments.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_export_xlsx",
        )


# ---------------------------------------------------------------------------
# Masthead (main content area)
# ---------------------------------------------------------------------------
masthead(
    eyebrow="Live Wire · Sentiment Desk",
    title="The Article Analyzer",
    subtitle="Filed from real articles and real YouTube comment threads — sentiment, summary, and the numbers behind them.",
)

# ---------------------------------------------------------------------------
# Page: Summarize
# ---------------------------------------------------------------------------
if page == PAGES[0]:
    st.markdown("##### Summarize Article")
    effective_text, source = file_or_pasted_text("upload_summary", st.session_state.get("summary_text", ""))
    text1 = st.text_area("Paste your article here:", height=200, key="summary_text",
                          placeholder="Enter or paste your article text here...")
    if source == "pasted text":
        effective_text = text1
    char_count_caption(effective_text)

    if st.button("📝 Summarize", key="sum_btn"):
        if effective_text and effective_text.strip():
            result = run_with_progress(summarize_with_llm, effective_text, "Summarizing...")
            st.markdown("### Summary")
            with st.expander("Full summary", expanded=True):
                with dispatch_card():
                    st.write(result)
                copy_button(result, key="summary_result_copy")
            add_history_entry("Summarize", effective_text, result)
        else:
            st.warning("Please enter some text or upload a file to summarize.")

# ---------------------------------------------------------------------------
# Page: Sentiment
# ---------------------------------------------------------------------------
elif page == PAGES[1]:
    st.markdown("##### Sentiment Analysis")
    effective_text, source = file_or_pasted_text("upload_sentiment", st.session_state.get("sentiment_text", ""))
    text2 = st.text_area("Paste your article here:", height=200, key="sentiment_text",
                          placeholder="Enter or paste your article text here...")
    if source == "pasted text":
        effective_text = text2
    char_count_caption(effective_text)

    if st.button("💬 Analyze Sentiment", key="sent_btn"):
        if effective_text and effective_text.strip():
            result = run_with_progress(analyze_sentiment, effective_text, "Analyzing sentiment...")
            st.markdown("### Sentiment Result")
            with st.expander("Full sentiment result", expanded=True):
                with dispatch_card():
                    st.write(result)
                copy_button(result, key="sentiment_result_copy")
            add_history_entry("Sentiment", effective_text, result)
        else:
            st.warning("Please enter some text or upload a file to analyze.")

# ---------------------------------------------------------------------------
# Page: YouTube Comments — real data only
# ---------------------------------------------------------------------------
elif page == PAGES[2]:
    st.markdown("##### YouTube Comment Analyzer")
    st.caption("Pull real comments from one or more videos (or a whole channel), classify sentiment, and get an executive summary.")

    if not YOUTUBE_API_KEY:
        st.error("⚠️ YOUTUBE_API_KEY not found in secrets. Add it to `.streamlit/secrets.toml` to use this tab.")
        st.info(
            "Get a key from the Google Cloud Console → enable **YouTube Data API v3** → "
            "Credentials → API key. Then add:\n\n```\nYOUTUBE_API_KEY = \"your-key\"\n```"
        )
    else:
        col_a, col_b = st.columns([3, 1])
        with col_a:
            yt_urls_raw = st.text_area(
                "Paste one or more YouTube video/channel URLs (one per line):",
                height=90,
                placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...\nhttps://www.youtube.com/@somechannel",
                key="yt_urls",
            )
        with col_b:
            max_comments = st.number_input("Max comments / video", min_value=20, max_value=1000, value=200, step=20)

        if st.button("🔎 Fetch & Analyze Comments", key="yt_fetch_btn"):
            urls = [u.strip() for u in (yt_urls_raw or "").splitlines() if u.strip()]
            if not urls:
                st.warning("Please paste at least one YouTube video or channel URL.")
            else:
                st.session_state["loaded_replies"] = {}  # reset lazy-loaded replies for a fresh fetch
                progress = st.progress(0.0, text=f"Fetching {len(urls)} video(s)...")
                results = run_youtube_analysis_multi(
                    urls, max_comments, YOUTUBE_API_KEY, OPENROUTER_API_KEY,
                    progress_callback=lambda p: progress.progress(p, text=f"Fetching & analyzing... {int(p * 100)}%"),
                )
                progress.empty()
                st.session_state["yt_results"] = results

                for result in results:
                    if result["resolve_error"]:
                        continue
                    if result.get("comments"):
                        title = result["video_meta"]["title"] if result.get("video_meta") else "video"
                        add_history_entry(
                            "YouTube", title,
                            result.get("summary") or "(no summary)",
                            extra={"comment_count": len(result["comments"])},
                        )

        if "yt_results" in st.session_state and st.session_state["yt_results"]:
            results = st.session_state["yt_results"]
            st.divider()

            all_comments = []
            for i, result in enumerate(results):
                if result["resolve_error"]:
                    st.error(f"Video {i + 1}: {result['resolve_error']}")
                    continue
                title = result["video_meta"]["title"] if result.get("video_meta") else f"Video {i + 1}"
                with st.expander(f"🎬 {title}", expanded=(len(results) == 1)):
                    if result.get("fetch_error"):
                        st.warning(result["fetch_error"])
                    if result.get("batch_errors"):
                        with st.expander(f"⚠️ {len(result['batch_errors'])} batch(es) had issues", expanded=False):
                            for e in result["batch_errors"]:
                                st.write(e)
                    render_full_youtube_result(result, key_prefix=f"yt_{i}")
                all_comments.extend(result.get("comments") or [])

            if all_comments:
                st.divider()
                render_cross_video_analytics(all_comments, key_prefix="yt_cross")

# ---------------------------------------------------------------------------
# Page: History
# ---------------------------------------------------------------------------
elif page == PAGES[3]:
    st.markdown("##### Session History")
    st.caption("Everything you've run this session — resets when the browser tab closes.")

    entries = get_history()
    if not entries:
        st.info("No history yet — results from Summarize, Sentiment, and YouTube will show up here.")
    else:
        if st.button("🗑️ Clear history", key="clear_history_btn"):
            clear_history()
            st.rerun()

        for i, entry in enumerate(entries):
            title = f"{entry['kind']} · {entry['time']}"
            with st.expander(title, expanded=(i == 0)):
                st.caption("Input")
                st.write(entry["input_preview"])
                st.caption("Result")
                with dispatch_card():
                    st.write(entry["result_preview"])
                copy_button(entry["result_preview"], key=f"history_copy_{i}")