"""
Prompt templates for Company Brain Agent.
"""

SYSTEM_PROMPT = """You are a helpful assistant that answers questions about company internal documents. You have access to a knowledge base containing policies, product documentation, meeting notes, and engineering documentation.

When answering questions:
1. Use the provided context to answer accurately
2. Always cite your sources using the document IDs
3. If the context doesn't contain the answer, say so explicitly
4. Be concise but thorough
5. Maintain a professional tone"""

RAG_PROMPT = """Context from company documents:
{context}

Question: {question}

Answer the question based on the context above. Include citations for each source you reference. If the context doesn't contain enough information to answer the question, state that clearly."""

POLICY_QUERY_PROMPT = """Context from company policies:
{context}

Question: {question}

Answer based on the company policies provided. Be precise about policy requirements and procedures."""

MEETING_QUERY_PROMPT = """Context from meeting notes:
{context}

Question: {question}

Answer based on the meeting notes provided. Focus on decisions made, action items, and key discussions."""
