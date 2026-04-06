#!/usr/bin/env python3
"""Автоотклики на hh.ru.

Гибрид: API-проверка типа (пропуск тестовых) + mouse.click (isTrusted).

    python main.py                  # Полный прогон
    python main.py --dry-run        # Только поиск
    python main.py --limit 5        # Макс. 5 откликов
"""

from __future__ import annotations

import argparse
import sys

import yaml
from playwright.sync_api import sync_playwright

from src.auth import create_context, login_if_needed, check_logged_in
from src.search import do_search, collect_vacancy_ids_from_page, go_next_page
from src.apply import apply_to_vacancy, human_delay, _check_captcha, _handle_captcha
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
            browser, context = create_context(pw, config)
            try:
                page = context.new_page()

                if not login_if_needed(page, config):
                    return

                # Поиск с error handling
                try:
                    do_search(page, config)
                except Exception as e:
                    print(f"[!] Ошибка поиска: {e}")
                    return

                # Проверка капчи после поиска
                if _check_captcha(page):
                    print("[!] Капча на странице поиска!")
                    _handle_captcha(page)

                sent = 0
                skipped = 0
                page_num = 0
                max_pages = 20  # Защита от бесконечного цикла

                while sent < max_apps and page_num < max_pages:
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

                        # Session check каждые 15 откликов
                        if (sent + skipped) > 0 and (sent + skipped) % 15 == 0:
                            if not check_logged_in(page):
                                print("[!] Сессия истекла. Завершаю.")
                                sent = max_apps  # Выход из цикла
                                break

                        if args.dry_run:
                            info = check_vacancy_type(page, vacancy.vacancy_id)
                            print(f"  {vacancy.title[:45]:45s} | {info.get('type','?'):15s} | {info.get('area','?')}")
                            skipped += 1
                            continue

                        # API-проверка типа (пропускаем тестовые)
                        info = check_vacancy_type(page, vacancy.vacancy_id)
                        vtype = info.get("type", "unknown")

                        if vtype == "test-required":
                            print(f"  [skip] {vacancy.title} — тестовое")
                            skipped += 1
                            continue
                        if vtype == "already-applied":
                            skipped += 1
                            continue

                        print(f"[{sent + 1}/{max_apps}] {vacancy.title} — {vacancy.company}")

                        status = apply_to_vacancy(page, vacancy, cover_letter, use_cover_letter)
                        tracker.record(vacancy.vacancy_id, vacancy.title, vacancy.company, status)

                        if status in ("sent", "cover_letter_sent"):
                            sent += 1
                        else:
                            skipped += 1

                        # Капча после отклика
                        if _check_captcha(page):
                            print("[!] Капча!")
                            _handle_captcha(page)

                        human_delay(config.get("delay_min", 5), config.get("delay_max", 12))

                    if sent >= max_apps:
                        break

                    try:
                        if not go_next_page(page):
                            break
                    except Exception as e:
                        print(f"[!] Ошибка пагинации: {e}")
                        break

                    page_num += 1

                    # Капча на странице пагинации
                    if _check_captcha(page):
                        print("[!] Капча на странице!")
                        _handle_captcha(page)

                # Итоги
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
                browser.close()


if __name__ == "__main__":
    main()
