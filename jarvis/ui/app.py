"""The Flet desktop app - the ONLY module that imports Flet (the toolkit stays behind this seam).

Thin by design: it builds widgets, wires them to `AppController` methods, and re-renders the feed
from `Feed.cards` after each action. All capability logic lives in JarvisService; all card shaping
lives in the (Flet-free, unit-tested) controller. Verified manually (a launched window).
"""

from __future__ import annotations

import flet as ft

from jarvis.service import JarvisService
from jarvis.ui.controller import AppController
from jarvis.ui.feed import Card, Feed


def _card_view(card: Card) -> ft.Card:
    return ft.Card(
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(card.title, weight=ft.FontWeight.BOLD),
                    ft.Markdown(card.body, selectable=True),
                ],
                tight=True,
                spacing=4,
            ),
            padding=12,
        )
    )


def launch(service: JarvisService) -> None:
    """Build the controller + feed and run the desktop window. Blocks until the window closes."""
    feed = Feed()
    controller = AppController(service, feed)

    def main(page: ft.Page) -> None:
        page.title = "Jarvis"
        feed_view = ft.ListView(expand=True, spacing=8, auto_scroll=True, padding=12)
        field = ft.TextField(hint_text="Ask Jarvis...", expand=True, on_submit=lambda e: _send())

        def _render() -> None:
            feed_view.controls = [_card_view(card) for card in feed.cards]
            page.update()

        def _send() -> None:
            controller.ask(field.value)
            field.value = ""
            _render()

        def _action(fn) -> None:  # run a shortcut, then re-render the feed
            fn()
            _render()

        def _add_goal() -> None:  # the chat field doubles as the goal text for the shortcut
            controller.add_goal(field.value)
            field.value = ""
            _render()

        shortcuts = ft.Row(
            [
                ft.Button("Briefing", on_click=lambda e: _action(controller.show_briefing)),
                ft.Button("Today's calendar", on_click=lambda e: _action(controller.show_agenda)),
                ft.Button(
                    "Markets / News", on_click=lambda e: _action(controller.ask_markets_news)
                ),
                ft.Button("Add goal", on_click=lambda e: _add_goal()),
            ],
            wrap=True,
        )
        page.add(
            shortcuts,
            feed_view,
            ft.Row([field, ft.Button(content=ft.Text("Send"), on_click=lambda e: _send())]),
        )
        controller.show_briefing()  # today's briefing as the first card
        _render()

    ft.run(main)
