"""
Streamlit UI for the Local IPC <-> BNS RAG Pipeline.
"""

import streamlit as st
import time

from production_rag import ProductionRAGPipeline

# Page configuration
st.set_page_config(
    page_title="IPC to BNS Legal Mapper",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def get_pipeline() -> ProductionRAGPipeline:
    """Initialize and index the local RAG pipeline."""
    # This ensures the expensive loading of SentenceTransformers
    # and BM25 indexing only happens once per session/startup.
    pipeline = ProductionRAGPipeline(top_k=7)
    pipeline.index()
    return pipeline


# Application Title and Description
st.title("⚖️ IPC to BNS Mapper")
st.markdown(
    """
    **100% Local RAG Pipeline.** Enter an IPC section or describe an offense, 
    and the system will semantically search the new **Bharatiya Nyaya Sanhita (BNS) 2023** 
    to find the corresponding section.
    """
)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history from session state
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.write(msg["content"])
        else:
            # Reconstruct UI for assistant answers
            result = msg["content"]
            
            if result.get("predicted_bns_section", "NONE") != "NONE":
                st.success(f"**BNS Section {result['predicted_bns_section']}** — {result['bns_section_title']}")
            else:
                st.error("No confident BNS mapping found.")
                
            st.markdown(f"**Reasoning:** {result.get('reasoning', '')}")
            
            changes = result.get("key_changes", "")
            if changes and changes not in ("No significant changes noted.", "See section text for details."):
                st.info(f"**Key Changes:** {changes}")
                
            with st.expander("View Provision Text"):
                st.write(result.get("bns_section_text", "No text available."))

# Suggestion chips for quick start
if not st.session_state.messages:
    SUGGESTIONS = {
        "Murder (IPC 302)": "What is the BNS equivalent of IPC Section 302 Murder?",
        "Cheating (IPC 420)": "What is the BNS section for cheating and dishonestly inducing delivery of property (IPC 420)?",
        "Criminal Conspiracy": "Which section covers criminal conspiracy in the new law?",
    }
    selected = st.pills(
        "Try asking:", list(SUGGESTIONS.keys()), label_visibility="collapsed"
    )
    if selected:
        prompt = SUGGESTIONS[selected]
        st.session_state.chat_input = prompt
    else:
        prompt = None
else:
    prompt = st.chat_input("Ask a legal query or provide an IPC section...")


# Handle new user input
if prompt or getattr(st.session_state, "chat_input", None):
    # If the prompt came from the pills, reset it so we don't infinitely loop
    if not prompt:
        prompt = st.session_state.chat_input
        st.session_state.chat_input = None
        
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        # Show thinking status
        with st.status(":shimmer[Retrieving and Analyzing...]", type="compact") as status:
            pipeline = get_pipeline()
            start_time = time.time()
            result = pipeline.query(prompt)
            elapsed = (time.time() - start_time) * 1000
            
            # Show retrieved docs in the steps
            for i, doc in enumerate(result.get("retrieved_sections", []), 1):
                st.write(f"*Rank {i}:* BNS {doc['section']} ({doc['score']:.4f})")
                
            status.update(label=f"Analysis complete in {elapsed:.0f}ms", state="complete")
        
        # Display Final Answer
        bns = result.get("predicted_bns_section", "NONE")
        title = result.get("bns_section_title", "")
        
        if bns != "NONE":
            st.success(f"**BNS Section {bns}** — {title}")
        else:
            st.error("No confident BNS mapping found.")
            
        st.markdown(f"**Reasoning:** {result.get('reasoning', '')}")
        
        changes = result.get("key_changes", "")
        if changes and changes not in ("No significant changes noted.", "See section text for details."):
            st.info(f"**Key Changes:** {changes}")
            
        with st.expander("View Provision Text"):
            st.write(result.get("bns_section_text", "No text available."))
            
        alts = result.get("alternative_sections", [])
        if alts:
            alt_strs = []
            for a in alts[:3]:
                if isinstance(a, dict):
                    alt_strs.append(f"Sec {a['section']} ({a['title']})")
                else:
                    alt_strs.append(str(a))
            st.caption(f"**Alternatives:** {', '.join(alt_strs)}")

    st.session_state.messages.append({"role": "assistant", "content": result})
