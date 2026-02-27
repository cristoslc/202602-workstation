"""VerifyScreen — post-install verification dashboard."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Static,
    Button,
    TabbedContent,
    TabPane,
)

from ..lib.verify import (
    PHASE_DISPLAY,
    PHASE_ORDER,
    CheckResult,
    StowLayerResult,
    check_all_stow_layers,
    filter_entries,
    load_registry,
    run_check,
)


class VerifyScreen(Screen):
    """Interactive verification dashboard — checks all registered apps."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._pass_count = 0
        self._fail_count = 0
        self._warn_count = 0
        self._total_count = 0
        self._checking = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Verify Installations[/bold]\n",
                id="verify-title",
            )
            yield Static("", id="verify-summary")
            with TabbedContent(id="verify-tabs"):
                for phase_id in PHASE_ORDER:
                    display = PHASE_DISPLAY.get(phase_id, phase_id)
                    with TabPane(display, id=f"verify-tab-{phase_id}"):
                        table = DataTable(id=f"verify-table-{phase_id}")
                        table.add_columns("Name", "Role", "Status", "Detail")
                        yield table
                with TabPane("Stow Health", id="verify-tab-stow"):
                    stow_table = DataTable(id="verify-table-stow")
                    stow_table.add_columns("Layer", "Links", "Status")
                    yield stow_table
            with Horizontal(id="verify-buttons"):
                yield Button("Refresh", id="refresh", variant="primary")
                yield Button("Back", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._run_checks()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        if not self._checking:
            self._run_checks()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "refresh":
            self.action_refresh()

    @work(thread=True)
    def _run_checks(self) -> None:
        """Run all verification checks in a background thread."""
        self._checking = True
        self._pass_count = 0
        self._fail_count = 0
        self._warn_count = 0
        self._total_count = 0

        # Clear tables.
        self.app.call_from_thread(self._clear_tables)
        self.app.call_from_thread(self._update_summary, "Checking...")

        # Load and filter for current platform.
        entries = load_registry()
        entries = filter_entries(entries, platform=self.app.platform)
        self._total_count = len(entries)

        # Run checks one by one (already fast — most are shutil.which).
        for entry in entries:
            result = run_check(entry)
            self.app.call_from_thread(self._add_result, result)

        # Stow health.
        stow_results = check_all_stow_layers(self.app.platform)
        for sr in stow_results:
            self.app.call_from_thread(self._add_stow_result, sr)

        self.app.call_from_thread(self._finalize_summary)
        self._checking = False

    def _clear_tables(self) -> None:
        """Clear all DataTable widgets."""
        for phase_id in PHASE_ORDER:
            try:
                table = self.query_one(
                    f"#verify-table-{phase_id}", DataTable
                )
                table.clear()
            except Exception:
                pass
        try:
            self.query_one("#verify-table-stow", DataTable).clear()
        except Exception:
            pass

    def _add_result(self, result: CheckResult) -> None:
        """Add a single check result to the appropriate table."""
        entry = result.entry
        phase_id = entry.phase

        if result.passed:
            status = "[green]PASS[/green]"
            self._pass_count += 1
        elif entry.optional:
            note = f" — {entry.note}" if entry.note else ""
            status = "[yellow]WARN[/yellow]"
            self._warn_count += 1
            if note:
                result = CheckResult(
                    entry=entry,
                    passed=False,
                    detail=f"{result.detail}{note}",
                )
        else:
            status = "[red]FAIL[/red]"
            self._fail_count += 1

        try:
            table = self.query_one(f"#verify-table-{phase_id}", DataTable)
            table.add_row(entry.name, entry.role, status, result.detail)
        except Exception:
            pass

        done = self._pass_count + self._fail_count + self._warn_count
        self._update_summary(
            f"Checking... {done}/{self._total_count}"
        )

    def _add_stow_result(self, sr: StowLayerResult) -> None:
        """Add a stow layer result to the stow table."""
        try:
            table = self.query_one("#verify-table-stow", DataTable)
        except Exception:
            return

        if sr.total == 0:
            table.add_row(sr.label, "—", "[dim]no packages[/dim]")
        elif len(sr.broken) == 0:
            table.add_row(
                sr.label,
                str(sr.total),
                f"[green]{sr.healthy}/{sr.total} OK[/green]",
            )
        else:
            broken_preview = ", ".join(sr.broken[:5])
            table.add_row(
                sr.label,
                str(sr.total),
                f"[red]{len(sr.broken)} broken[/red]: {broken_preview}",
            )

    def _update_summary(self, text: str) -> None:
        """Update the summary line."""
        try:
            self.query_one("#verify-summary", Static).update(text)
        except Exception:
            pass

    def _finalize_summary(self) -> None:
        """Set the final summary after all checks complete."""
        parts = [f"[green]{self._pass_count} passed[/green]"]
        if self._fail_count:
            parts.append(f"[red]{self._fail_count} failed[/red]")
        if self._warn_count:
            parts.append(f"[yellow]{self._warn_count} warnings[/yellow]")
        self._update_summary(", ".join(parts))
