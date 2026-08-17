"""
Keyword / word-cloud helpers — everything here is computed directly from the
REAL comment text you fetched. No canned word lists, no demo output.
"""
import re
from collections import Counter

from wordcloud import WordCloud, STOPWORDS

# Standard English stopwords, plus a few YouTube-comment-specific filler words
# that would otherwise dominate every cloud regardless of topic.
CUSTOM_STOPWORDS = STOPWORDS.union({
    "video", "videos", "youtube", "channel", "watch", "watching", "watched",
    "will", "just", "really", "one", "also", "im", "ive", "dont", "didnt",
    "thats", "youre", "its", "u", "s", "t", "re", "ve", "d", "ll", "m",
})


def _clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"http\S+|www\.\S+", " ", text)          # strip URLs
    text = re.sub(r"[^a-z\s']", " ", text)                  # strip punctuation/emoji/numbers
    return text


def get_word_frequencies(comments, top_n=20):
    """Real word-frequency count across the given real comments."""
    counter = Counter()
    for c in comments:
        for word in _clean_text(c.get("text", "")).split():
            word = word.strip("'")
            if len(word) < 3 or word in CUSTOM_STOPWORDS:
                continue
            counter[word] += 1
    return counter.most_common(top_n)


def generate_wordcloud_image(comments, width=900, height=380):
    """
    Build a word cloud image from real comment text.
    Returns a PIL Image, or None if there isn't enough real text to render.
    """
    combined_text = " ".join(_clean_text(c.get("text", "")) for c in comments)
    if not combined_text.strip():
        return None

    wc = WordCloud(
        width=width,
        height=height,
        background_color=None,
        mode="RGBA",
        stopwords=CUSTOM_STOPWORDS,
        colormap="viridis",
        collocations=False,
        max_words=100,
    ).generate(combined_text)
    return wc.to_image()