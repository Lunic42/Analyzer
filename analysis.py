"""
Shared YouTube analysis pipeline — resolve a URL, pull real comments, classify
real sentiment, and generate a real executive summary. Used by both the single
-video tab and the compare-two-videos tab so the logic only lives in one place.
"""
from api_utils import classify_all_comments, generate_executive_summary, DEFAULT_MODEL
from youtube_utils import (
    extract_video_id,
    extract_channel_id,
    resolve_channel_id,
    fetch_video_metadata,
    fetch_comments,
)


def run_youtube_analysis(url, max_comments, youtube_api_key, openrouter_api_key,
                          progress_callback=None, model=DEFAULT_MODEL):
    """
    Runs the full real pipeline for one URL:
      resolve video/channel -> fetch real comments -> classify sentiment -> summarize.

    Returns a dict:
      {
        "video_meta": dict | None,
        "comments": list[dict] (each with a 'sentiment' key) | [],
        "summary": str | None,
        "summary_error": str | None,
        "fetch_error": str | None,   # non-fatal if comments is non-empty
        "batch_errors": list[str],
        "resolve_error": str | None, # fatal — could not identify a video/channel
      }
    """
    result = {
        "video_meta": None,
        "comments": [],
        "summary": None,
        "summary_error": None,
        "fetch_error": None,
        "batch_errors": [],
        "resolve_error": None,
    }

    if not url or not url.strip():
        result["resolve_error"] = "No URL provided."
        return result

    video_id = extract_video_id(url)
    channel_id = None if video_id else extract_channel_id(url)
    if not video_id and not channel_id:
        channel_id = resolve_channel_id(url, youtube_api_key)

    if not video_id and not channel_id:
        result["resolve_error"] = "Couldn't recognize that as a YouTube video or channel URL."
        return result

    if video_id:
        try:
            result["video_meta"] = fetch_video_metadata(video_id, youtube_api_key)
        except Exception as e:
            result["fetch_error"] = f"Couldn't fetch video metadata: {e}"

    comments, fetch_error = fetch_comments(
        youtube_api_key, video_id=video_id, channel_id=channel_id, max_results=max_comments,
    )
    if fetch_error:
        result["fetch_error"] = fetch_error
    if not comments:
        result["comments"] = []
        return result

    comments, batch_errors = classify_all_comments(
        openrouter_api_key, model, comments, batch_size=25, progress_callback=progress_callback,
    )
    result["batch_errors"] = batch_errors
    result["comments"] = comments

    video_title = result["video_meta"]["title"] if result["video_meta"] else None
    summary, summary_error = generate_executive_summary(
        openrouter_api_key, model, comments, video_title=video_title,
    )
    result["summary"] = summary
    result["summary_error"] = summary_error

    return result


def run_youtube_analysis_multi(urls, max_comments_per_video, youtube_api_key, openrouter_api_key,
                                progress_callback=None, model=DEFAULT_MODEL):
    """
    Run the real single-video pipeline across several URLs. Each result is
    the same shape as run_youtube_analysis(), plus every comment dict gets a
    'video_title' tag so results can be merged into one cross-video view.

    progress_callback(fraction_complete) reports overall progress across all
    videos (not per-video), so the caller only needs one progress bar.
    """
    urls = [u.strip() for u in urls if u and u.strip()]
    results = []
    total = max(1, len(urls))

    for i, url in enumerate(urls):
        def per_video_progress(p, i=i):
            if progress_callback:
                progress_callback((i + p) / total)

        result = run_youtube_analysis(
            url, max_comments_per_video, youtube_api_key, openrouter_api_key,
            progress_callback=per_video_progress, model=model,
        )
        video_title = result["video_meta"]["title"] if result.get("video_meta") else url
        for c in result.get("comments", []):
            c["video_title"] = video_title
        results.append(result)

        if progress_callback:
            progress_callback((i + 1) / total)

    return results