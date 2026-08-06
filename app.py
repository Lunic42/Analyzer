import os
import streamlit as st
from openrouter import OpenRouter

# Page config
st.set_page_config(page_title="Article Analyzer", page_icon="📰", layout="wide")

# Get API key from secrets or environment
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Title
st.title("📰 Article Analyzer")
st.markdown("Paste any article to get AI-powered sentiment analysis and summarization.")

# Sidebar for API key
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("OpenRouter API Key", type="password", value=OPENROUTER_API_KEY)
    if api_key:
        st.success("✅ API Key provided")
    else:
        st.warning("⚠️ Please enter your OpenRouter API Key")
        st.markdown("Get your free key at [OpenRouter](https://openrouter.ai/keys)")

def analyze_sentiment(text, api_key):
    """Analyze sentiment using OpenRouter API."""
    if not text.strip():
        return "Please enter some text to analyze."
    if not api_key:
        return "Error: API key required"
    
    with OpenRouter(api_key=api_key) as client:
        response = client.chat.send(
            model="openrouter/free",
            messages=[
                {
                    "role": "system",
                    "content": "You are a sentiment analysis expert. Analyze the sentiment of the following text and respond with: 'Sentiment: Positive/Negative/Neutral' and 'Confidence: XX%'. Keep it brief."
                },
                {"role": "user", "content": text}
            ],
            stream=False,
        )
    return response.choices[0].message.content

def summarize_with_llm(text, api_key):
    """Summarize text using OpenRouter free LLM."""
    if not text.strip():
        return "Please enter some text to summarize."
    if not api_key:
        return "Error: API key required"
    
    with OpenRouter(api_key=api_key) as client:
        response = client.chat.send(
            model="openrouter/free",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Summarize the following text concisely in 2-3 sentences."
                },
                {"role": "user", "content": text}
            ],
            stream=False,
        )
    return response.choices[0].message.content

# Tabs
tab1, tab2, tab3 = st.tabs(["📝 Summarize", "💬 Sentiment", "🔍 Full Analysis"])

with tab1:
    st.subheader("Summarize Article")
    text1 = st.text_area("Paste your article here:", height=200, key="summary")
    if st.button("Summarize", key="sum_btn"):
        if text1:
            with st.spinner("Summarizing..."):
                result = summarize_with_llm(text1, api_key)
                st.markdown("### Summary")
                st.write(result)
        else:
            st.warning("Please enter some text.")

with tab2:
    st.subheader("Sentiment Analysis")
    text2 = st.text_area("Paste your article here:", height=200, key="sentiment")
    if st.button("Analyze Sentiment", key="sent_btn"):
        if text2:
            with st.spinner("Analyzing..."):
                result = analyze_sentiment(text2, api_key)
                st.markdown("### Sentiment Result")
                st.write(result)
        else:
            st.warning("Please enter some text.")

with tab3:
    st.subheader("Full Analysis")
    text3 = st.text_area("Paste your article here:", height=200, key="full")
    if st.button("Run Full Analysis", key="full_btn"):
        if text3:
            with st.spinner("Analyzing..."):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📊 Sentiment")
                    st.write(analyze_sentiment(text3, api_key))
                with col2:
                    st.markdown("### 📝 Summary")
                    st.write(summarize_with_llm(text3, api_key))
        else:
            st.warning("Please enter some text.")