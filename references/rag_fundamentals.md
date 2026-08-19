# Introduction to RAG (Retrieval-Augmented Generation)

## What is RAG?

RAG stands for **Retrieval-Augmented Generation**. It is a technique that helps AI systems give better, more accurate answers by first searching for relevant information before generating a response.

Think of RAG like an open-book exam. Instead of answering from memory alone, the AI looks up information first, then uses that information to write its answer.

## The Problem RAG Solves

Large Language Models (LLMs) like GPT or Gemini are trained on data up to a certain date. After that, they do not know about new information. Also, they can sometimes "hallucinate" — meaning they make up facts that sound correct but are wrong.

RAG solves two problems:
1. **Outdated knowledge** — The AI can access fresh documents even after training
2. **Hallucinations** — By grounding answers in real documents, the AI is less likely to make things up

## The RAG Workflow

Here is how RAG works step by step:

```
User Question
     ↓
Step 1: RETRIEVE — Search a knowledge base for relevant information
     ↓
Step 2: AUGMENT — Add the retrieved information to the prompt
     ↓
Step 3: GENERATE — The LLM generates an answer using the retrieved context
     ↓
Final Answer
```

### Example

Imagine you ask: "What is the company's refund policy?"

Without RAG:
- The LLM might guess or make up a policy

With RAG:
- The system searches the company's policy documents
- It finds the relevant paragraph about refunds
- It gives the LLM that paragraph as context
- The LLM answers using the real policy text

## Key Concepts

### Documents / Knowledge Base
The knowledge base is a collection of documents that RAG searches through. These can be:
- Company manuals
- Research papers
- Website content
- Product descriptions
- Any text files

### Embeddings
An **embedding** is a list of numbers (called a vector) that represents the meaning of a piece of text.

Simple explanation: Imagine every sentence can be turned into a point in space. Sentences with similar meaning end up near each other in this space. Embeddings allow computers to measure how "similar" two pieces of text are — without understanding human language directly.

Example:
- "How do I reset my password?" and "Steps to change login credentials" would have similar embeddings because they mean similar things.

### Vector Database
A **vector database** stores embeddings and allows very fast similarity searches.

Simple explanation: It is like a library where books are organized by topic (meaning), not by title. When you ask a question, the vector database instantly finds the books most relevant to your question.

Popular vector databases include: FAISS, Pinecone, Weaviate, Chroma.

**FAISS** (Facebook AI Similarity Search) is a free, fast, local vector database that runs on your computer without any cloud service.

### Retrieval
**Retrieval** is the process of finding relevant document chunks from the knowledge base.

How it works:
1. Your question is converted to an embedding (a vector of numbers)
2. This embedding is compared to all document embeddings in the vector database
3. The most similar document chunks are returned (top-k retrieval)
4. These chunks become the "context" for the LLM

### Retrieved Context
The **context** is the relevant information retrieved from the knowledge base. It is inserted into the prompt given to the LLM, along with the original question.

Example prompt with context:
```
Context: [Relevant text retrieved from documents]
Question: [User's original question]
Please answer the question based on the context above.
```

### Generation
**Generation** is the final step where the LLM reads both the question AND the retrieved context, then produces a grounded, accurate answer.

Because the LLM has access to real information (the context), it is much less likely to hallucinate.

## RAG vs Fine-Tuning

Both RAG and fine-tuning are ways to make LLMs more useful for specific tasks, but they work differently.

| | RAG | Fine-Tuning |
|---|---|---|
| How it works | Retrieves information at query time | Bakes knowledge into model weights during training |
| Cost | Low (no retraining) | High (requires GPU training) |
| Knowledge updates | Easy — just update documents | Hard — requires retraining |
| Use case | Dynamic, frequently-updated information | Fixed skills or tone |

**When to use RAG:**
- Your data changes frequently (e.g., company policies, product catalogs)
- You cannot afford to retrain a model
- You need to cite sources

**When to use fine-tuning:**
- You want the model to learn a specific writing style or format
- The knowledge is stable and unlikely to change

> **Important**: RAG does NOT retrain the language model. It only provides external information at query time. The model weights (the model's "memory") remain unchanged.

## Limitations of RAG

1. **Retrieval quality** — If the retriever doesn't find the right document, the answer will be wrong
2. **Context window limits** — Only a limited amount of text can be passed to the LLM at once
3. **Latency** — Adding a retrieval step makes responses slightly slower
4. **Chunking strategy matters** — How you split documents affects retrieval quality

## A Complete Example: Customer Support Bot

**Scenario**: A company wants a chatbot that answers questions about their products using their 500-page manual.

**Without RAG**:
- The LLM answers from its general training — often wrong about specific product details
- Cannot access the 500-page manual

**With RAG**:
1. The 500-page manual is split into chunks and embedded into FAISS
2. A customer asks: "How do I configure the WiFi settings on Model X?"
3. RAG retrieves the 3 most relevant chunks about WiFi configuration from the manual
4. The LLM reads those chunks and gives a specific, accurate answer
5. The customer gets the right answer every time

## Key Takeaways

1. **RAG = Retrieve + Augment + Generate** — a 3-step process
2. **Embeddings** turn text into numbers so computers can find similar content
3. **Vector databases** store and search these embeddings efficiently
4. **RAG does NOT retrain the model** — it provides external context at query time
5. RAG is best for dynamic knowledge that changes frequently
6. RAG reduces hallucinations by grounding answers in real documents
7. The quality of RAG depends heavily on the quality of retrieved documents
