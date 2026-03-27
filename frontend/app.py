"""
Streamlit frontend for the Semantic Video Search Engine.

Features:
  - YouTube video ingestion directly from the UI
  - Conversational search with multi-result rendering
  - Timestamp-linked citations with embedded video player
  - Library management sidebar
"""

import streamlit as st
import requests

# ── Page Config ──────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Semantic Video Search Engine",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# IPv4 loopback avoids macOS localhost→IPv6 resolution timeouts
API_BASE = "http://127.0.0.1:8000/api/v1"


def api_call(method: str, path: str, **kwargs) -> dict | None:
    """Centralised API caller with error handling."""
    try:
        resp = getattr(requests, method)(f"{API_BASE}{path}", **kwargs)
        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", resp.text)
            except ValueError:
                err = resp.text
            st.error(f"API Error ({resp.status_code}): {err}")
            return None
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach backend. Is FastAPI running on port 8000?")
        return None
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
        return None


# ── Sidebar: Library Management ──────────────────────────────────────────

with st.sidebar:
    st.header("📚 Video Library")

    # Ingest YouTube video
    st.subheader("Add Video")
    yt_url = st.text_input(
        "YouTube URL or Video ID",
        placeholder="https://youtube.com/watch?v=...",
    )
    if st.button("🔽 Ingest Video", use_container_width=True) and yt_url:
        with st.spinner("Fetching transcript, chunking, embedding..."):
            result = api_call("post", "/ingest/youtube", json={"url": yt_url})
            if result and result.get("success"):
                data = result["data"]
                st.success(
                    f"✅ Ingested **{data['title']}**\n\n"
                    f"`{data['chunks_stored']}` chunks stored"
                )
            elif result:
                st.error(result.get("error", "Ingestion failed"))

    st.divider()

    # List existing clips
    st.subheader("Ingested Videos")
    if st.button("🔄 Refresh Library", use_container_width=True):
        st.session_state.pop("library", None)

    if "library" not in st.session_state:
        lib_resp = api_call("get", "/library")
        if lib_resp and lib_resp.get("success"):
            st.session_state["library"] = lib_resp["data"]["clips"]

    for clip in st.session_state.get("library", []):
        with st.expander(f"🎬 {clip['title'][:50]}"):
            st.caption(f"ID: `{clip['id']}`")
            st.caption(f"Chunks: {clip['chunk_count']}")
            if clip.get("source_url"):
                st.caption(f"[Source]({clip['source_url']})")
            if st.button("🗑️ Delete", key=f"del_{clip['id']}"):
                api_call("delete", f"/library/{clip['id']}")
                st.session_state.pop("library", None)
                st.rerun()


# ── Main Content: Search ─────────────────────────────────────────────────

st.title("🔍 Semantic Video Search Engine")
st.markdown(
    "Ask any question about your video library. The AI agent will search "
    "transcripts, find the best clips, and cite exact timestamped quotes."
)

# Initialize conversation history
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Render conversation history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
query = st.chat_input("Ask a question about your videos...")

if query:
    # Show user message
    st.session_state["messages"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # Show assistant response
    with st.chat_message("assistant"):
        with st.spinner("Agent is reasoning..."):
            result = api_call("post", "/search", json={"query": query})

        if result and result.get("success"):
            data = result.get("data", {})
            results_list = data.get("results", [])

            if not results_list:
                response_text = "No relevant video clips found. Try rephrasing your question."
                st.info(response_text)
            else:
                response_parts = []
                for item in results_list:
                    # Answer
                    answer = item.get("answer", "")
                    clip_id = item.get("clip_id", "")
                    st.markdown(f"**Answer:** {answer}")
                    st.caption(f"Source: `{clip_id}`")
                    response_parts.append(f"**Answer:** {answer}")

                    # Embedded YouTube player (if YouTube clip)
                    if clip_id.startswith("yt-"):
                        video_id = clip_id[3:]
                        first_quote = item.get("relevant_quotes", [{}])[0]
                        start_t = int(first_quote.get("quote_timestamp", 0))
                        st.video(
                            f"https://www.youtube.com/watch?v={video_id}",
                            start_time=start_t,
                        )

                    # Timestamped citations
                    quotes = item.get("relevant_quotes", [])
                    if quotes:
                        st.markdown("**📝 Cited Evidence:**")
                        for q in quotes:
                            ts = q.get("quote_timestamp", 0)
                            minutes = int(ts // 60)
                            seconds = int(ts % 60)
                            desc = q.get("quote_description", "")
                            quote_text = q.get("quote", "")
                            badge = f"`{minutes:02d}:{seconds:02d}`"
                            st.markdown(
                                f"> {badge} *\"{quote_text}\"*"
                                + (f"\n> — {desc}" if desc else "")
                            )

                    # Related questions
                    related = item.get("related_questions", [])
                    if related:
                        st.markdown("**💡 Follow-up questions:**")
                        cols = st.columns(min(len(related), 3))
                        for i, rq in enumerate(related[:3]):
                            with cols[i]:
                                st.button(
                                    rq,
                                    key=f"related_{hash(query)}_{i}",
                                    use_container_width=True,
                                )

                response_text = "\n".join(response_parts) if response_parts else "Search complete."

            st.session_state["messages"].append(
                {"role": "assistant", "content": response_text}
            )
        elif result:
            err_msg = result.get("error", "Unknown error")
            st.error(err_msg)
            st.session_state["messages"].append(
                {"role": "assistant", "content": f"Error: {err_msg}"}
            )
