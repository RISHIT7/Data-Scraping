def chunk_text(text, max_size=500):
    """
    Splits text into chunks without breaking words or sentences.
    More natural for NLP than a hard character-count split.
    """
    if not text:
        return []

    # 1. Clean up newlines and split by sentences
    # We use '. ' to avoid splitting initials like 'U.S.A.'
    sentences = text.replace('\n', ' ').split('. ')
    
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # Add a period back if it was lost in the split
        if not sentence.endswith('.'):
            sentence += "."

        # 2. If adding this sentence doesn't exceed our limit, keep building
        if len(current_chunk) + len(sentence) < max_size:
            current_chunk += (sentence + " ")
        else:
            # Chunk is full, save it and start a new one
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "

    # Don't forget the last piece!
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks