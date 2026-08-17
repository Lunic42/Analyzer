import os
import streamlit as st
import pandas as pd

from api_utils import call_openrouter, DEFAULT_MODEL
from analysis import run_youtube_analysis

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Article Analyzer", page_icon="📰", layout="wide")


def get_secret(name):
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name, "")


OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY")
YOUTUBE_API_KEY = get_secret("YOUTUBE_API_KEY")

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

# Title
st.title("📰 Article Analyzer")
st.markdown("Paste any article — or a real YouTube video/channel link — to get AI-powered sentiment analysis and summarization.")


def summarize_with_llm(text):
    system_prompt = (
        "You are a helpful assistant. Summarize the following text concisely:\n"
        "- Keep it to 2-3 sentences\n- Capture the main points\n- Be clear and direct"
    )
    result, error = call_openrouter(OPENROUTER_API_KEY, DEFAULT_MODEL, system_prompt, text, max_tokens=500)
    return error if error else result


def analyze_sentiment(text):
    system_prompt = (
        "You are a sentiment analysis expert. Analyze the sentiment of the following text and respond with:\n"
        "- Sentiment: Positive/Negative/Neutral/Mixed\n- Confidence: XX%\n"
        "- Brief explanation of your decision\nKeep it brief and well-formatted."
    )
    result, error = call_openrouter(OPENROUTER_API_KEY, DEFAULT_MODEL, system_prompt, text, max_tokens=500)
    return error if error else result


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
    st.markdown(f"**{video_meta['title']}** — {video_meta['channel']}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Views", f"{video_meta['view_count']:,}")
    m2.metric("Likes", f"{video_meta['like_count']:,}")
    m3.metric("Total comments (on video)", f"{video_meta['comment_count']:,}")


def render_sentiment_breakdown(df):
    counts = df["sentiment"].value_counts().reindex(["Positive", "Negative", "Neutral"]).fillna(0).astype(int)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Comments analyzed", len(df))
    c2.metric("Positive", int(counts.get("Positive", 0)))
    c3.metric("Negative", int(counts.get("Negative", 0)))
    c4.metric("Neutral", int(counts.get("Neutral", 0)))
    st.bar_chart(counts)
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
    """Render video meta, executive summary, sentiment breakdown, and comment tables for one analyzed video."""
    render_video_meta(result.get("video_meta"))

    st.markdown("### 🧾 Executive Summary")
    if result.get("summary_error"):
        st.error(result["summary_error"])
    elif result.get("summary"):
        st.markdown(result["summary"])

    comments = result.get("comments") or []
    if not comments:
        st.info("No comments to show.")
        return

    df = pd.DataFrame(comments)

    st.markdown("### 📊 Sentiment Breakdown")
    render_sentiment_breakdown(df)

    st.markdown("### 💬 Comments")
    render_comment_tabs(df)

    st.download_button(
        "⬇️ Download comments as CSV",
        df[DISPLAY_COLS].rename(columns=RENAME_COLS).to_csv(index=False).encode("utf-8"),
        file_name=f"{key_prefix}_comments_sentiment.csv",
        mime="text/csv",
        key=f"{key_prefix}_download",
    )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📝 Summarize", "💬 Sentiment", "🔍 Full Analysis", "🎥 YouTube Comments"]
)

with tab1:
    st.subheader("Summarize Article")
    text1 = st.text_area("Paste your article here:", height=200, key="summary",
                          placeholder="Enter or paste your article text here...")
    if st.button("📝 Summarize", key="sum_btn"):
        if text1 and text1.strip():
            with st.spinner("Summarizing..."):
                st.markdown("### Summary")
                st.write(summarize_with_llm(text1))
        else:
            st.warning("Please enter some text to summarize.")

with tab2:
    st.subheader("Sentiment Analysis")
    text2 = st.text_area("Paste your article here:", height=200, key="sentiment",
                          placeholder="Enter or paste your article text here...")
    if st.button("💬 Analyze Sentiment", key="sent_btn"):
        if text2 and text2.strip():
            with st.spinner("Analyzing sentiment..."):
                st.markdown("### Sentiment Result")
                st.write(analyze_sentiment(text2))
        else:
            st.warning("Please enter some text to analyze.")

with tab3:
    st.subheader("Full Analysis")
    text3 = st.text_area("Paste your article here:", height=200, key="full",
                          placeholder="Enter or paste your article text here...")
    if st.button("🔍 Run Full Analysis", key="full_btn"):
        if text3 and text3.strip():
            with st.spinner("Performing full analysis..."):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📊 Sentiment")
                    st.write(analyze_sentiment(text3))
                with col2:
                    st.markdown("### 📝 Summary")
                    st.write(summarize_with_llm(text3))
        else:
            st.warning("Please enter some text to analyze.")

# ---------------------------------------------------------------------------
# Tab 4: single YouTube video/channel — real data only
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("YouTube Comment Analyzer")
    st.markdown("Pull real comments from a video (or a whole channel), classify sentiment, and get an executive summary.")

    if not YOUTUBE_API_KEY:
        st.error("⚠️ YOUTUBE_API_KEY not found in secrets. Add it to `.streamlit/secrets.toml` to use this tab.")
        st.info(
            "Get a key from the Google Cloud Console → enable **YouTube Data API v3** → "
            "Credentials → API key. Then add:\n\n```\nYOUTUBE_API_KEY = \"your-key\"\n```"
        )
    else:
        col_a, col_b = st.columns([3, 1])
        with col_a:
            yt_url = st.text_input(
                "Paste a YouTube video or channel URL:",
                placeholder="https://www.youtube.com/watch?v=... or https://www.youtube.com/@somechannel",
                key="yt_url",
            )
        with col_b:
            max_comments = st.number_input("Max comments", min_value=20, max_value=1000, value=200, step=20)

        if st.button("🔎 Fetch & Analyze Comments", key="yt_fetch_btn"):
            if not yt_url or not yt_url.strip():
                st.warning("Please paste a YouTube video or channel URL.")
            else:
                progress = st.progress(0.0, text="Fetching and analyzing...")
                with st.spinner(f"Fetching up to {max_comments} real comments and classifying sentiment..."):
                    result = run_youtube_analysis(
                        yt_url, max_comments, YOUTUBE_API_KEY, OPENROUTER_API_KEY,
                        progress_callback=lambda p: progress.progress(p, text=f"Classifying sentiment... {int(p * 100)}%"),
                    )
                progress.empty()

                if result["resolve_error"]:
                    st.error(result["resolve_error"])
                else:
                    if result["fetch_error"]:
                        st.warning(result["fetch_error"])
                    if result["batch_errors"]:
                        with st.expander(f"⚠️ {len(result['batch_errors'])} batch(es) had issues"):
                            for e in result["batch_errors"]:
                                st.write(e)
                    st.session_state["yt_result"] = result

        if "yt_result" in st.session_state and st.session_state["yt_result"].get("comments"):
            st.divider()
            render_full_youtube_result(st.session_state["yt_result"], key_prefix="yt")