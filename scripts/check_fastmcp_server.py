import asyncio

from fastmcp import Client

from supportcommander.mcp_server.server import mcp


async def main() -> None:
    print("=" * 70)
    print("SupportCommander FastMCP Server Check")
    print("=" * 70)

    async with Client(mcp) as client:

        tools = await client.list_tools()

        print(
            f"Tools discovered: {len(tools)}"
        )

        print()

        for tool in tools:
            print(
                "-",
                tool.name,
            )

        result = await client.call_tool(
            "health",
            {},
        )

        print()
        print(
            "Health result:",
            result.structured_content,
        )

        if (
            result.structured_content["status"]
            != "ok"
        ):
            raise RuntimeError(
                "FastMCP health check failed."
            )

    print()
    print("=" * 70)
    print(
        "FastMCP server check successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
