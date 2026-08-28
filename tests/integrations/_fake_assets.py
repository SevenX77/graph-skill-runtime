"""Small canonical asset double for installer mechanics."""

from __future__ import annotations


class FakeMoiraiAssets:
    integration_id = "moirai"
    asset_version = "test-assets-v1"

    def skill_ids(self) -> tuple[str, ...]:
        return ("moirai",)

    def role_ids(self) -> tuple[str, ...]:
        return ("moirai",)

    def role_host_name(self, role_id: str) -> str:
        assert role_id == "moirai"
        return "moirai"

    def role_description(self, role_id: str) -> str:
        assert role_id == "moirai"
        return "Coordinate one graph-skill workflow."

    def role_skill_ids(self, role_id: str) -> tuple[str, ...]:
        assert role_id == "moirai"
        return ("moirai",)

    def role_body(self, role_id: str) -> str:
        assert role_id == "moirai"
        return "# MoirAI\n\nUse the installed runtime tools.\n"

    def skill_file(self, skill_id: str) -> bytes:
        assert skill_id == "moirai"
        return (
            b"---\n"
            b"name: moirai\n"
            b"description: Coordinate graph-skill work.\n"
            b"---\n\n"
            b"Read references/KB-00-hub.md when needed.\n"
        )

    def skill_reference_files(self, skill_id: str) -> tuple[tuple[str, bytes], ...]:
        assert skill_id == "moirai"
        return (("KB-00-hub.md", b"# Knowledge hub\n"),)


__all__ = ["FakeMoiraiAssets"]
