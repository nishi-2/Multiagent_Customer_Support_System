import asyncio

from supportcommander.mcp_client.client import (
    create_mcp_client,
)


async def main() -> None:

    client = create_mcp_client()

    async with client:

        tools = await client.list_tools()

        print(
            "Available FastMCP tools:"
        )

        for tool in tools:
            print(
                "-",
                tool.name,
            )


if __name__ == "__main__":
    asyncio.run(main())
