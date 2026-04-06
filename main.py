#!/usr/bin/env python3
"""Автоотклики на hh.ru — гибрид: API-проверка + mouse click.

    python main.py                  # Полный прогон
    python main.py --dry-run        # Только поиск
    python main.py --limit 5        # Макс. 5 откликов
"""

from __future__ import annotations

import argparse

import yaml
from playwright.sync_api import sync_playwright

from src.auth import create_context, login_if_needed, check_logged_in
from src.search import do_search, collect_vacancy_ids_from_page, go_next_page
from src.apply import apply_to_vacancy, human_delay
from src.api_apply import check_vacancy_type
from src.tracker import Tracker


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Автоотклики hh.ru")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.limit:
        config["max_applications"] = args.limit

    use_cover_letter = config.get("use_cover_letter", True)
    cover_letter = config.get("cover_letter", "").strip() if use_cover_letter else ""
    max_apps = config["max_applications"]

    print("=" * 60)
    print("АВТООТКЛИКИ HH.RU")
    print(f"  Запрос:  {config['search_query']}")
    print(f"  Лимит:   {max_apps}")
    print(f"  Режим:   {'DRY RUN' if args.dry_run else 'БОЕВОЙ'}")
    print("=" * 60)

    with Tracker(config["db_path"]) as tracker:
        with sync_playwright() as pw:
            context = create_context(pw, config)
            try:
                page = context.new_page()

                if not login_if_needed(page, config):
                    return

                do_search(page, config)

                sent = 0
                skipped = 0
                page_num = 0

                while sent < max_apps:
                    vacancies = collect_vacancy_ids_from_page(page)
                    print(f"\n--- Стр. {page_num} ({len(vacancies)} вакансий) ---")

                    if not vacancies:
                        if not go_next_page(page):
                            break
                        page_num += 1
                        continue

                    new = [v for v in vacancies if not tracker.is_applied(v.vacancy_id)]

                    for vacancy in new:
                        if sent >= max_apps:
                            break

                        if args.dry_run:
                            info = check_vacancy_type(page, vacancy.vacancy_id)
                            print(f"  {vacancy.title[:45]:45s} | {info.get('type','?'):15s} | {info.get('area','?')}")
                            skipped += 1
                            continue

                        # Пропускаем тестовые через API-проверку (быстро)
                        info = check_vacancy_type(page, vacancy.vacancy_id)
                        if info.get("type") == "test-required":
                            print(f"  [skip] {vacancy.title} — тестовое")
                            skipped += 1
                            continue
                        if info.get("type") == "already-applied":
                            skipped += 1
                            continue

                        print(f"[{sent + 1}/{max_apps}] {vacancy.title} — {vacancy.company}")

                        # Клик через JS (проверенный подход)
                        status = apply_to_vacancy(page, vacancy, cover_letter, use_cover_letter)
                        tracker.record(vacancy.vacancy_id, vacancy.title, vacancy.company, status)

                        if status in ("sent", "cover_letter_sent"):
                            sent += 1
                        else:
                            skipped += 1

                        human_delay(config.get("delay_min", 5), config.get("delay_max", 12))

                    if sent >= max_apps:
                        break
                    if not go_next_page(page):
                        break
                    page_num += 1

                print("\n" + "=" * 60)
                if args.dry_run:
                    print(f"DRY RUN: {skipped} вакансий")
                else:
                    print(f"Отправлено: {sent}, пропущено: {skipped}")
                    for st, cnt in tracker.stats().items():
                        print(f"  {st}: {cnt}")
                print("=" * 60)

            finally:
                try:
                    context.storage_state(path=config["storage_state_path"])
                except Exception:
                    pass
                context.close()


if __name__ == "__main__":
    main()
