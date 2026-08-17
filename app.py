import os
import streamlit as st
import pandas as pd

from api_utils import call_openrouter, classify_all_comments, generate_executive_summary, MODEL_OPTIONS, DEFAULT_MODEL
from youtube_utils import (
    extract_video_id,
    extract_channel_id,
    resolve_channel_id,
    fetch_video_metadata,
    fetch_comments,
)

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
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📝 Summarize", "💬 Sentiment", "🔍 Full Analysis", "🎥 YouTube Comments"])

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
# Tab 4: YouTube comments — real data only (YouTube Data API + OpenRouter)
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

        '''model_label = st.selectbox("Sentiment model (via OpenRouter)", list(MODEL_OPTIONS.keys()), index=0)
        sentiment_model = MODEL_OPTIONS[model_label]'''

        fetch_clicked = st.button("🔎 Fetch & Analyze Comments", key="yt_fetch_btn")

        if fetch_clicked:
            if not yt_url or not yt_url.strip():
                st.warning("Please paste a YouTube video or channel URL.")
            else:
                video_id = extract_video_id(yt_url)
                channel_id = None if video_id else extract_channel_id(yt_url)
                if not video_id and not channel_id:
                    with st.spinner("Resolving channel handle..."):
                        channel_id = resolve_channel_id(yt_url, YOUTUBE_API_KEY)

                if not video_id and not channel_id:
                    st.error("Couldn't recognize that as a YouTube video or channel URL.")
                else:
                    video_meta = None
                    if video_id:
                        with st.spinner("Fetching video info..."):
                            try:
                                video_meta = fetch_video_metadata(video_id, YOUTUBE_API_KEY)
                            except Exception as e:
                                st.warning(f"Couldn't fetch video metadata: {e}")

                    with st.spinner(f"Fetching up to {max_comments} real comments..."):
                        comments, fetch_error = fetch_comments(
                            YOUTUBE_API_KEY, video_id=video_id, channel_id=channel_id,
                            max_results=max_comments,
                        )

                    if fetch_error and not comments:
                        st.error(fetch_error)
                    else:
                        if fetch_error:
                            st.warning(f"Fetched {len(comments)} comments before hitting an issue: {fetch_error}")

                        if not comments:
                            st.info("No comments found.")
                        else:
                            progress = st.progress(0.0, text="Classifying sentiment...")
                            comments, batch_errors = classify_all_comments(
                                OPENROUTER_API_KEY, sentiment_model, comments,
                                batch_size=25,
                                progress_callback=lambda p: progress.progress(p, text=f"Classifying sentiment... {int(p * 100)}%"),
                            )
                            progress.empty()
                            if batch_errors:
                                with st.expander(f"⚠️ {len(batch_errors)} batch(es) had issues"):
                                    for e in batch_errors:
                                        st.write(e)

                            with st.spinner("Generating executive summary..."):
                                summary, summary_error = generate_executive_summary(
                                    OPENROUTER_API_KEY, sentiment_model, comments,
                                    video_title=video_meta["title"] if video_meta else None,
                                )

                            st.session_state["yt_comments"] = comments
                            st.session_state["yt_video_meta"] = video_meta
                            st.session_state["yt_summary"] = summary
                            st.session_state["yt_summary_error"] = summary_error

        # Render results if we have them (persists across reruns/filter changes)
        if "yt_comments" in st.session_state and st.session_state["yt_comments"]:
            comments = st.session_state["yt_comments"]
            video_meta = st.session_state.get("yt_video_meta")
            summary = st.session_state.get("yt_summary")
            summary_error = st.session_state.get("yt_summary_error")

            st.divider()

            if video_meta:
                st.markdown(f"**{video_meta['title']}** — {video_meta['channel']}")
                m1, m2, m3 = st.columns(3)
                m1.metric("Views", f"{video_meta['view_count']:,}")
                m2.metric("Likes", f"{video_meta['like_count']:,}")
                m3.metric("Total comments (on video)", f"{video_meta['comment_count']:,}")

            st.markdown("### 🧾 Executive Summary")
            if summary_error:
                st.error(summary_error)
            else:
                st.markdown(summary)

            st.markdown("### 📊 Sentiment Breakdown")
            df = pd.DataFrame(comments)
            counts = df["sentiment"].value_counts().reindex(["Positive", "Negative", "Neutral"]).fillna(0).astype(int)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Comments analyzed", len(df))
            c2.metric("Positive", int(counts.get("Positive", 0)))
            c3.metric("Negative", int(counts.get("Negative", 0)))
            c4.metric("Neutral", int(counts.get("Neutral", 0)))

            st.bar_chart(counts)

            st.markdown("### 💬 Comments")
            filt_all, filt_pos, filt_neg, filt_neu = st.tabs(["All", "😊 Positive", "😠 Negative", "😐 Neutral"])

            display_cols = ["author", "text", "like_count", "sentiment", "published_at", "author_channel_url"]
            rename = {
                "author": "Author",
                "text": "Comment",
                "like_count": "Likes",
                "sentiment": "Sentiment",
                "published_at": "Published",
                "author_channel_url": "Author Link",
            }

            def show_table(frame):
                if frame.empty:
                    st.info("No comments in this category.")
                    return
                shown = frame[display_cols].rename(columns=rename).sort_values("Likes", ascending=False)
                st.dataframe(
                    shown,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Author Link": st.column_config.LinkColumn("Author Link", display_text="Profile"),
                        "Comment": st.column_config.TextColumn("Comment", width="large"),
                    },
                )

            with filt_all:
                show_table(df)
            with filt_pos:
                show_table(df[df["sentiment"] == "Positive"])
            with filt_neg:
                show_table(df[df["sentiment"] == "Negative"])
            with filt_neu:
                show_table(df[df["sentiment"] == "Neutral"])

            st.download_button(
                "⬇️ Download comments as CSV",
                df[display_cols].rename(columns=rename).to_csv(index=False).encode("utf-8"),
                file_name="youtube_comments_sentiment.csv",
                mime="text/csv",
            )