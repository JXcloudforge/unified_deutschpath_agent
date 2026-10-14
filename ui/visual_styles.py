"""Small centralized typography and reading-width adjustments for Streamlit."""


def render_visual_styles(st) -> None:
    """Improve readability without setting colors, so Streamlit themes remain intact."""
    st.markdown("""
<style>
html, body, [class*="st-"], button, input, textarea { font-size: 16px; }
html, body, [class*="st-"], p, li { line-height: 1.65; }
section[data-testid="stMain"] > div { max-width: 78rem; padding-left: clamp(1rem, 3vw, 2.5rem); padding-right: clamp(1rem, 3vw, 2.5rem); }
section[data-testid="stSidebar"] { min-width: 20rem; }
div[data-testid="stChatMessage"] { padding: 1rem 1.1rem; }
div[data-testid="stChatInput"] { max-width: 72rem; }
div[data-testid="stMarkdown"] { overflow-wrap: anywhere; }
pre, table { max-width: 100%; overflow-x: auto; }
@media (max-width: 700px) {
  section[data-testid="stSidebar"] { min-width: min(20rem, 85vw); }
  section[data-testid="stMain"] > div { padding-left: 0.75rem; padding-right: 0.75rem; }
}
</style>
""", unsafe_allow_html=True)
