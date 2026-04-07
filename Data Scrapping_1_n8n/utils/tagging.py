from openai import OpenAI
client = OpenAI()

def extract_tags(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": f"Extract 5 topic tags from:\n{text[:2000]}"}
            ]
        )
        tags = response.choices[0].message.content
        return [t.strip() for t in tags.split(",")]
    except:
        return []