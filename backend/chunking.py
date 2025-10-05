import logging
import os
from typing import Dict, Optional, List
import instructor
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _load_examples() -> str:
    examples_path = os.path.join(
        os.path.dirname(__file__), "prompt_data", "examples.txt"
    )
    try:
        with open(examples_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Examples file not found at {examples_path}")
        return ""


EXAMPLES = _load_examples()


class TopicAssignment(BaseModel):
    existing_topic_id: Optional[str] = Field(
        None, description="ID of an existing topic if this chunk matches one"
    )
    new_topic_id: Optional[str] = Field(
        None, description="ID for a new topic if this content represents a new topic"
    )
    updated_description: Optional[str] = Field(
        None,
        description="Updated description if the topic has evolved significantly from this chunk",
    )
    chunk_blurb: str = Field(description="A one-point summary of the chunk")
    chunk_content: str = Field(description="The actual text content of the chunk")
    is_complete: bool = Field(
        True, description="Whether this chunk represents a complete thought or topic"
    )


class ChunkingResult(BaseModel):
    assignments: List[TopicAssignment] = Field(
        description="List of topic assignments for chunks"
    )
    incomplete_text: str = Field(
        "", description="Any text that doesn't form a complete chunk yet"
    )


def chunk_transcript_by_topics(
    transcript: str,
    existing_topics: Optional[str] = None,
    project_id: str = None,
    location: str = "us-central1",
) -> Dict[str, any]:
    logger.debug(f"Chunking transcript of length {len(transcript)}")

    client = instructor.from_provider(
        "google/gemini-2.0-flash-exp",
        vertexai=True,
        project=project_id,
        location=location,
    )

    prompt = f"""
    You are a helpful assistant that identifies summary points of chunks from a transcript
    in addition to identifying topics that the chunk belongs to.

    Here are some examples of topics and the chunk blurbs that might belong to those topics:
    {EXAMPLES}

    Here is the transcript to chunk:
    {transcript}

    Here are the existing topics:
    {existing_topics}

    If there are no existing topics, return None for the existing_topic_id parameter
    and create a new topic in the new_topic_id parameter.

    Note that a chunk has to be ENTIRELY unrelated to the topic in order to justify the creation of
    a new topic. 

    Correct typos based on the context of the transcript; the transcript is bad.
    Each chunk should contain one point or idea; a chunk blurb should not involve multiple points.
    """

    logger.info("Calling Gemini via Instructor for chunking")
    try:
        result = client.chat.completions.create(
            response_model=ChunkingResult,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        logger.info(
            f"Successfully got structured response with {len(result.assignments)} assignments"
        )
        logger.debug(f"Incomplete text length: {len(result.incomplete_text)}")

        logger.debug("=" * 70)
        logger.debug("INSTRUCTOR OUTPUT - Raw ChunkingResult:")
        logger.debug(f"  Total assignments: {len(result.assignments)}")
        logger.debug(
            f"  Incomplete text: '{result.incomplete_text[:100]}{'...' if len(result.incomplete_text) > 100 else ''}'"
        )

        for idx, assignment in enumerate(result.assignments, 1):
            logger.debug(f"\n  Assignment #{idx}:")
            logger.debug(f"    existing_topic_id: {assignment.existing_topic_id}")
            logger.debug(f"    new_topic_id: {assignment.new_topic_id}")
            logger.debug(f"    updated_description: {assignment.updated_description}")
            logger.debug(f"    chunk_blurb: {assignment.chunk_blurb}")
            logger.debug(f"    is_complete: {assignment.is_complete}")
            logger.debug(
                f"    chunk_content: '{assignment.chunk_content[:100]}{'...' if len(assignment.chunk_content) > 100 else ''}'"
            )

        logger.debug("=" * 70)

        complete_chunks = {}
        chunk_blurbs = {}
        topic_descriptions = {}

        for assignment in result.assignments:
            if assignment.is_complete:
                topic_id = assignment.existing_topic_id or assignment.new_topic_id
                if topic_id:
                    if topic_id not in complete_chunks:
                        complete_chunks[topic_id] = []
                        chunk_blurbs[topic_id] = []
                    complete_chunks[topic_id].append(assignment.chunk_content)
                    chunk_blurbs[topic_id].append(assignment.chunk_blurb)
                    if assignment.updated_description:
                        topic_descriptions[topic_id] = assignment.updated_description
                    logger.info(f"Assigned chunk to topic: {topic_id}")
            else:
                if result.incomplete_text:
                    result.incomplete_text += " " + assignment.chunk_content
                else:
                    result.incomplete_text = assignment.chunk_content

        logger.debug("\n" + "=" * 70)
        logger.debug("PROCESSED OUTPUT - Final Result Dictionary:")
        logger.debug(f"  complete_chunks: {list(complete_chunks.keys())}")
        for topic_id, chunks in complete_chunks.items():
            logger.debug(f"    [{topic_id}]: {len(chunks)} chunk(s)")
            for i, (blurb, content) in enumerate(
                zip(chunk_blurbs[topic_id], chunks), 1
            ):
                logger.debug(f"      Chunk #{i}:")
                logger.debug(f"        Blurb: '{blurb}'")
                logger.debug(
                    f"        Content: '{content[:80]}{'...' if len(content) > 80 else ''}'"
                )
        logger.debug(f"  topic_descriptions: {list(topic_descriptions.keys())}")
        for topic_id, desc in topic_descriptions.items():
            logger.debug(f"    [{topic_id}]: '{desc}'")
        logger.debug(
            f"  incomplete_text: '{result.incomplete_text[:100]}{'...' if len(result.incomplete_text) > 100 else ''}'"
        )
        logger.debug("=" * 70 + "\n")

        return {
            "complete_chunks": complete_chunks,
            "chunk_blurbs": chunk_blurbs,
            "incomplete_text": result.incomplete_text,
            "topic_descriptions": topic_descriptions,
        }

    except Exception as e:
        logger.error(f"Error calling Instructor: {e}", exc_info=True)
        return {
            "complete_chunks": {},
            "chunk_blurbs": {},
            "incomplete_text": transcript,
            "topic_descriptions": {},
        }
