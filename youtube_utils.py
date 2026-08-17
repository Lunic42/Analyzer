"""
YouTube Data API v3 helpers.

Everything here hits the real YouTube Data API — there is no mock/demo data.
You need a YOUTUBE_API_KEY (from Google Cloud Console, with "YouTube Data API v3"
enabled) added to .streamlit/secrets.toml.
"""
import re
import requests

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def extract_video_id(url: str):
    """Pull an 11-char YouTube video ID out of watch/shorts/embed/youtu.be URLs."""
    url = url.strip()
    patterns = [
        r"(?:v=|/videos/|embed/|youtu\.be/|/shorts/)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
        return url
    return None


def extract_channel_id(url: str):
    """Pull a channel ID out of a /channel/UC... URL. Returns None for @handle URLs."""
    match = re.search(r"channel/(UC[0-9A-Za-z_-]{22})", url)
    return match.group(1) if match else None


def resolve_channel_id(url_or_handle: str, api_key: str):
    """Resolve an @handle (or custom /c/ /user/ URL fragment) to a channel ID."""
    handle_match = re.search(r"@([\w.-]+)", url_or_handle)
    handle = handle_match.group(1) if handle_match else url_or_handle.strip().lstrip("@/")
    try:
        resp = requests.get(
            f"{YOUTUBE_API_BASE}/channels",
            params={"part": "id", "forHandle": handle, "key": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return items[0]["id"] if items else None
    except requests.exceptions.RequestException:
        return None


def fetch_video_metadata(video_id: str, api_key: str):
    """Real video title/channel/view/like/comment counts."""
    resp = requests.get(
        f"{YOUTUBE_API_BASE}/videos",
        params={"part": "snippet,statistics", "id": video_id, "key": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None
    item = items[0]
    stats = item.get("statistics", {})
    return {
        "title": item["snippet"]["title"],
        "channel": item["snippet"]["channelTitle"],
        "view_count": int(stats.get("viewCount", 0)),
        "like_count": int(stats.get("likeCount", 0)),
        "comment_count": int(stats.get("commentCount", 0)),
    }


def fetch_comments(api_key, video_id=None, channel_id=None, max_results=200, order="relevance"):
    """
    Fetch real top-level comments for a single video, or across a whole channel.

    Returns (comments, error_message). error_message is None on success (partial
    results are still returned if an error interrupts a later page).
    """
    if not video_id and not channel_id:
        return [], "No video or channel ID provided."

    comments = []
    page_token = None
    params_base = {
        "part": "snippet",
        "key": api_key,
        "maxResults": 100,
        "order": order,
        "textFormat": "plainText",
    }
    if video_id:
        params_base["videoId"] = video_id
    else:
        params_base["allThreadsRelatedToChannelId"] = channel_id

    try:
        while len(comments) < max_results:
            params = dict(params_base)
            if page_token:
                params["pageToken"] = page_token

            resp = requests.get(f"{YOUTUBE_API_BASE}/commentThreads", params=params, timeout=15)

            if resp.status_code == 403:
                reason = ""
                try:
                    reason = resp.json().get("error", {}).get("errors", [{}])[0].get("reason", "")
                except Exception:
                    pass
                if reason == "commentsDisabled":
                    return comments, "Comments are disabled for this video."
                if reason == "quotaExceeded":
                    return comments, "YouTube API daily quota exceeded. Try again later or use a different key."
                return comments, f"YouTube API 403 error: {reason or resp.text[:200]}"

            if resp.status_code != 200:
                return comments, f"YouTube API error {resp.status_code}: {resp.text[:200]}"

            data = resp.json()
            for item in data.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "comment_id": item["snippet"]["topLevelComment"]["id"],
                    "author": top.get("authorDisplayName", "Unknown"),
                    "author_channel_url": top.get("authorChannelUrl", ""),
                    "author_profile_image": top.get("authorProfileImageUrl", ""),
                    "text": top.get("textDisplay", ""),
                    "like_count": int(top.get("likeCount", 0)),
                    "published_at": top.get("publishedAt", ""),
                    "reply_count": item["snippet"].get("totalReplyCount", 0),
                    "video_id": item["snippet"].get("videoId", video_id or ""),
                })
                if len(comments) >= max_results:
                    break

            page_token = data.get("nextPageToken")
            if not page_token:
                break
    except requests.exceptions.Timeout:
        return comments, "Request to YouTube timed out."
    except requests.exceptions.RequestException as e:
        return comments, f"Network error while fetching comments: {e}"

    return comments, None
