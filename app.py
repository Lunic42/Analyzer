import os
import streamlit as st
import requests
import json

# Page config
st.set_page_config(page_title="Article Analyzer", page_icon="📰", layout="wide")

# Get API key from Streamlit secrets
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
except:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    if not OPENROUTER_API_KEY:
        st.error("⚠️ API key not found! Please set OPENROUTER_API_KEY in Streamlit secrets.")
        st.info("""
        ### How to fix this:
        1. Create a `.streamlit` folder in your project root
        2. Create a `secrets.toml` file inside it
        3. Add: `OPENROUTER_API_KEY = "your-api-key-here"`
        4. Or use terminal: `echo 'OPENROUTER_API_KEY = "your-key"' > .streamlit/secrets.toml`
        """)
        st.stop()

# Title
st.title("📰 Article Analyzer")
st.markdown("Paste any article to get AI-powered sentiment analysis and summarization.")

def call_openrouter_api(text, system_prompt):
    """Make API call to OpenRouter using the free model."""
    if not OPENROUTER_API_KEY:
        return "Error: API key not configured"
    if not text or not text.strip():
        return "Please enter some text to analyze."
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://your-app-name.streamlit.app",  # Replace with your app URL
                "X-Title": "Article Analyzer",
            },
            json={
                "model": "openrouter/free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            # Try specific free models as fallback
            fallback_models = [
                "meta-llama/llama-3.2-3b-instruct:free",
                "google/gemini-2.0-flash-lite-preview-02-05:free",
                "microsoft/phi-3-mini-128k-instruct:free"
            ]
            
            for fallback_model in fallback_models:
                try:
                    fallback_response = requests.post(
                        url="https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": fallback_model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": text}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 500
                        },
                        timeout=30
                    )
                    if fallback_response.status_code == 200:
                        result = fallback_response.json()
                        return result['choices'][0]['message']['content'] + f"\n\n*(Note: Used fallback model: {fallback_model})*"
                except:
                    continue
            
            # If all models fail, return error
            error_detail = response.json() if response.text else response.text
            return f"Error: {response.status_code} - {str(error_detail)[:200]}"
            
    except requests.exceptions.Timeout:
        return "Error: Request timed out. Please try again."
    except requests.exceptions.ConnectionError:
        return "Error: Connection error. Please check your internet."
    except Exception as e:
        return f"Error: {str(e)}"

def analyze_sentiment(text):
    """Analyze sentiment using OpenRouter API."""
    system_prompt = """You are a sentiment analysis expert. Analyze the sentiment of the following text and respond with:
    - Sentiment: Positive/Negative/Neutral/Mixed
    - Confidence: XX%
    - Brief explanation of your decision
    Keep it brief and well-formatted."""
    return call_openrouter_api(text, system_prompt)

def summarize_with_llm(text):
    """Summarize text using OpenRouter free LLM."""
    system_prompt = """You are a helpful assistant. Summarize the following text concisely:
    - Keep it to 2-3 sentences
    - Capture the main points
    - Be clear and direct"""
    return call_openrouter_api(text, system_prompt)

# Tabs
tab1, tab2, tab3 = st.tabs(["📝 Summarize", "💬 Sentiment", "🔍 Full Analysis"])

with tab1:
    st.subheader("Summarize Article")
    st.markdown("Enter or paste your article text below to get a concise summary.")
    text1 = st.text_area("Paste your article here:", height=200, key="summary", 
                         placeholder="Enter or paste your article text here...")
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("📝 Summarize", key="sum_btn", use_container_width=True):
            if text1 and text1.strip():
                with st.spinner("Summarizing... This may take a few seconds."):
                    result = summarize_with_llm(text1)
                    st.markdown("### Summary")
                    st.write(result)
            else:
                st.warning("Please enter some text to summarize.")

with tab2:
    st.subheader("Sentiment Analysis")
    st.markdown("Analyze the emotional tone and sentiment of your article.")
    text2 = st.text_area("Paste your article here:", height=200, key="sentiment",
                         placeholder="Enter or paste your article text here...")
    
    if st.button("💬 Analyze Sentiment", key="sent_btn"):
        if text2 and text2.strip():
            with st.spinner("Analyzing sentiment... This may take a few seconds."):
                result = analyze_sentiment(text2)
                st.markdown("### Sentiment Result")
                st.write(result)
        else:
            st.warning("Please enter some text to analyze.")

with tab3:
    st.subheader("Full Analysis")
    st.markdown("Get both sentiment analysis and summarization in one go.")
    text3 = st.text_area("Paste your article here:", height=200, key="full",
                         placeholder="Enter or paste your article text here...")
    
    if st.button("🔍 Run Full Analysis", key="full_btn"):
        if text3 and text3.strip():
            with st.spinner("Performing full analysis... This may take a few seconds."):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📊 Sentiment")
                    sentiment_result = analyze_sentiment(text3)
                    st.write(sentiment_result)
                with col2:
                    st.markdown("### 📝 Summary")
                    summary_result = summarize_with_llm(text3)
                    st.write(summary_result)
        else:
            st.warning("Please enter some text to analyze.")
