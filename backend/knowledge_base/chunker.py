"""
Knowledge Base Chunker
Splits Confluence documentation articles into structured, semantically meaningful chunks
with metadata preservation (titles, headers, URLs, section context).
"""
import re
import json
import os

def chunk_markdown_article(title: str, text: str, url: str = "", max_chars: int = 600, overlap: int = 100) -> list[dict]:
    """
    Splits a markdown article into structured chunks preserving section headings.
    """
    sections = re.split(r'(?m)^(?=#{1,3}\s+)', text)
    chunks = []
    chunk_idx = 0

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue

        # Extract section heading if present
        heading_match = re.match(r'^(#{1,3})\s+(.+)$', sec, re.M)
        section_heading = heading_match.group(2).strip() if heading_match else title

        if len(sec) <= max_chars:
            chunks.append({
                "chunk_id": f"{title.lower().replace(' ', '_')}_{chunk_idx}",
                "title": f"{title} - {section_heading}" if section_heading != title else title,
                "url": url,
                "section": section_heading,
                "text": sec
            })
            chunk_idx += 1
        else:
            # Paragraph level split
            paragraphs = sec.split("\n\n")
            curr_chunk = ""
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                if len(curr_chunk) + len(p) + 2 > max_chars and curr_chunk:
                    chunks.append({
                        "chunk_id": f"{title.lower().replace(' ', '_')}_{chunk_idx}",
                        "title": f"{title} - {section_heading}" if section_heading != title else title,
                        "url": url,
                        "section": section_heading,
                        "text": curr_chunk.strip()
                    })
                    chunk_idx += 1
                    curr_chunk = p
                else:
                    curr_chunk = f"{curr_chunk}\n\n{p}" if curr_chunk else p
            if curr_chunk:
                chunks.append({
                    "chunk_id": f"{title.lower().replace(' ', '_')}_{chunk_idx}",
                    "title": f"{title} - {section_heading}" if section_heading != title else title,
                    "url": url,
                    "section": section_heading,
                    "text": curr_chunk.strip()
                })
                chunk_idx += 1
    return chunks

def chunk_all_docs(docs_dir: str, output_json: str) -> list[dict]:
    """Scans all markdown files in docs_dir and builds knowledge_chunks.json."""
    all_chunks = []
    for f in sorted(os.listdir(docs_dir)):
        if f.endswith(".md"):
            path = os.path.join(docs_dir, f)
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            title = f.replace(".md", "").replace("_", " ")
            chunks = chunk_markdown_article(title, content)
            all_chunks.extend(chunks)

    with open(output_json, "w", encoding="utf-8") as out:
        json.dump(all_chunks, out, indent=2)
    print(f"[Chunker] Successfully generated {len(all_chunks)} chunks -> {output_json}")
    return all_chunks

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    docs_p = os.path.join(base, "docs")
    out_p = os.path.join(base, "data", "knowledge_chunks.json")
    chunk_all_docs(docs_p, out_p)
