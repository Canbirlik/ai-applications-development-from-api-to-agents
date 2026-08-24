import json
import anthropic
from anthropic.lib import files_from_dir
from pathlib import Path

from commons.constants import ANTHROPIC_API_KEY


SKILLS_VERSION = "skills-2025-10-02"

def get_or_create_skill(skill_title: str, skill_dir: Path,  client: anthropic.Anthropic) -> str:
    #TODO:
    # - List all custom skills using the beta skills API (source="custom", betas=[SKILLS_VERSION])
    # - If a skill with matching display_title already exists, print its info and return its ID
    # - Otherwise create a new skill with the title and files from skill_dir (use anthropic.lib.files_from_dir)
    # - Print the new skill ID and return it
    skills = client.beta.skills.list(source="custom", betas=[SKILLS_VERSION])
    for skill in skills:
        if skill.display_title == skill_title:
            print(f"Found existing skill '{skill.display_title}' (id={skill.id})")
            return skill.id

    files = files_from_dir(skill_dir)
    created_skill = client.beta.skills.create(
        files=files,
        display_title=skill_title,
        betas=[SKILLS_VERSION],
    )
    print(f"Created new skill '{skill_title}' (id={created_skill.id})")
    return created_skill.id

def delete_skills(client: anthropic.Anthropic):
    #TODO:
    # - List all custom skills
    # - For each skill, list all its versions and delete each one (print confirmation per version)
    # - Then delete the skill itself (print confirmation)
    skills = client.beta.skills.list(source="custom", betas=[SKILLS_VERSION])
    for skill in skills:
        versions = client.beta.skills.versions.list(skill_id=skill.id, betas=[SKILLS_VERSION])
        for version in versions:
            client.beta.skills.versions.delete(version.version, skill_id=skill.id, betas=[SKILLS_VERSION])
            print(f"Deleted version {version.version} of skill '{skill.display_title}' (id={skill.id})")

        client.beta.skills.delete(skill.id, betas=[SKILLS_VERSION])
        print(f"Deleted skill '{skill.display_title}' (id={skill.id})")

def chat(client: anthropic.Anthropic, skill_id: str, log_request: bool=True, log_response: bool = True):
    """Multi-turn chat loop that reuses the container across turns."""
    messages = []
    container_id = None
    print("\nSkill Agent is ready.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            break

        messages.append({"role": "user", "content": user_input})

        #TODO:
        # - Build a container dict with the skill reference (type "custom", skill_id, version "latest")
        # - If container_id is already set, include it in the container dict to reuse the running container
        # - Build the full request_payload (model, max_tokens, messages, container, betas, tools)
        #   Note: betas must include "code-execution-2025-08-25" and SKILLS_VERSION; tool type is "code_execution_20250825"
        # - If log_request is True, print the request payload as indented JSON
        # - Call client.beta.messages.create with the request payload
        # - If log_response is True, print the full response as indented JSON;
        #   otherwise join all text blocks from response.content and print as "Claude: <text>"
        # - If the response has a container, save its ID to container_id for reuse on next turns
        # - Append the assistant message to messages (role "assistant", content response.content)
        container = {"skills": [{"type": "custom", "skill_id": skill_id, "version": "latest"}]}
        if container_id:
            container["id"] = container_id

        request_payload = {
            "model": "claude-sonnet-4-5",
            "max_tokens": 4096,
            "messages": messages,
            "container": container,
            "betas": ["code-execution-2025-08-25", SKILLS_VERSION],
            "tools": [{"type": "code_execution_20250825", "name": "code_execution"}],
        }

        if log_request:
            print(json.dumps(request_payload, indent=2, default=lambda o: getattr(o, "model_dump", lambda: str(o))()))

        response = client.beta.messages.create(**request_payload)

        if log_response:
            print(response.model_dump_json(indent=2))
        else:
            text = "".join(block.text for block in response.content if block.type == "text")
            print(f"Claude: {text}")

        if response.container:
            container_id = response.container.id

        messages.append({"role": "assistant", "content": response.content})




STYLE_SKILL_TITLE = "style-guide"
STYLE_SKILL_DIR = Path(__file__).parent / "_skills" / STYLE_SKILL_TITLE

CALCULATOR_SKILL_TITLE = "calculator"
CALCULATOR_SKILL_DIR = Path(__file__).parent / "_skills" / CALCULATOR_SKILL_TITLE

def main():
    #TODO:
    # - Create an Anthropic client
    # - Call get_or_create_skill (choose STYLE_SKILL or CALCULATOR_SKILL dir/title to test)
    # - Call chat with the client and skill_id
    # - Call delete_skills to clean up after the session
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    skill_id = get_or_create_skill(CALCULATOR_SKILL_TITLE, CALCULATOR_SKILL_DIR, client)

    try:
        chat(client, skill_id)
    finally:
        delete_skills(client)


if __name__ == "__main__":
    main()