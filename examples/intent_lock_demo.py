"""Demonstrate a pure literal-target Intent Lock decision."""

from frontdoor.intent_lock import derive_lock, evaluate_action


ERROR = """\
MCP client for `cloudflare-api` failed to start: OAuth refresh token rejected.
invalid_grant: Grant not found
"""


def main() -> None:
    lock = derive_lock(ERROR)
    assert lock is not None

    for action in (
        "npx wrangler whoami",
        "codex mcp login cloudflare-api",
    ):
        decision = evaluate_action(lock, action)
        print(decision.allowed, decision.code)

    print("No command was executed; an intent match is not authority.")


if __name__ == "__main__":
    main()
