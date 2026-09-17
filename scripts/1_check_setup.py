import sys
import fastapi
import langgraph
import openai
import pandas
import pymongo

from supportcommander.core.constants import PROJECT_NAME, PROJECT_VERSION

def main() -> None:
    print("=" * 50)
    print(f"{PROJECT_NAME} v{PROJECT_VERSION}")
    print("=" * 50)

    print("Checking setup...")
    print(f"Python: {sys.version.split()[0]}")
    print("OpenAI package: OK")
    print("LangGraph package: OK")
    print("FastAPI package: OK")
    print("PyMongo package: OK")
    print("Pandas package: OK")

    print("=" * 50)
    print("Project bootstrap successful!")
    print("=" * 50)


if __name__ == "__main__":
    main()