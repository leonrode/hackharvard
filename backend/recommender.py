import vertexai
from vertexai.generative_models import GenerativeModel, Tool, GenerationConfig
from typing import List
import json

from time import time

from config import (
    GEMINI_MODEL,
    PROJECT_ID,
    LOCATION,
)

class Recommender:

    def __init__(self):

        vertexai.init(project=PROJECT_ID, location=LOCATION)
        self.model = GenerativeModel(GEMINI_MODEL)
        print(f"Using model: {GEMINI_MODEL}")
    
    def recommend(self, topics):
        prompt = f"""You are an AI conversation assistant. You will be given a list of conversation topics. 
        Each topic has:
        topic_key: the main subject of the topic
        summary: a short summary of what was discussed
        content_stack: the full transcript of the conversation related to this topic
 
        For EACH topic, generate a list of recommendations that help the speaker keep the conversation flowing naturally. 
        The recommendations should:
        Be personalized to what has already been said in the transcript.
        Suggest follow-up questions, comments, or related topics the speaker might bring up.
        Avoid repeating exactly what was said before.
        Be concise and practical (1 to 2 sentences each).
        Return results as JSON with the format:

        {{
            "topic_id": [string, string, ...] <recommendations for this particular topic_id>
        }}
        
        Here are the topics:
        {topics}"""

        response = self.model.generate_content(prompt)
        response_text = response.text.strip()

        # parse the ```json `
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
            return json.loads(response_text)
        return response_text





if __name__ == "__main__":
    recommender = Recommender()

    topics = [
        {
            "topic_key": "budget_discussion_50k",
            "summary": "The speakers discussed and agreed on a budget of $50,000 for their project.",
            "content_stack": [
                "I think we should consider the budget for this project.",
                "Yeah, that's a good point. What do you think the budget should be?",
                "Well, I was thinking maybe around fifty thousand dollars?",
                "That sounds reasonable. Let's go with that then.",
                "Great! So we're all set on the budget.",
            ]
        },
        {
            "topic_key": "pet_discussion",
            "summary": "The speakers discussed and agreed on a pet.",
            "content_stack": [
                "I'm thinking about getting a new pet. Maybe a cat?",
                "Cats are great! They're independent and low maintenance.",
                "What breed would you recommend?",
                "I'd suggest a Maine Coon or a British Shorthair. Both are friendly.",
                "Thanks for the advice! I'll look into those breeds.",
                "No problem! Let me know if you need help with anything else.",
            ]
        }
    ]

    print(recommender.recommend(topics))
    
