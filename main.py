#!/usr/bin/env python3
"""Автоотклики на hh.ru.

    python main.py                  # Полный прогон
    python main.py --dry-run        # Только поиск, без откликов
    python main.py --limit 5        # Максимум 5 откликов
"""

from __future__ import annotations

import argparse

import yaml
from playwright.sync_api import sync_playwright

from src.auth import create_context, login_if_needed, check_logged_in
from src.search import do_search, collect_vacancy_ids_from_page, go_next_page, Vacancy
from src.apply import apply_to_vacancy, human_delay, STATUS_CAPTCHA
from src.tracker import Tracker


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Автоотклики hh.ru")
    parser.add_argument("--dry-run", action="store_true", help="Только поиск")
    parser.add_argument("--limit", type=int, help="Макс. откликов")
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
    print(f"  Фильтры: {'сброшены' if config.get('reset_filters') else 'по умолчанию'}")
    print(f"  Лимит:   {max_apps}")
    print(f"  Режим:   {'DRY RUN' if args.dry_run else 'БОЕВОЙ'}")
    print(f"  Письмо:  {'да' if use_cover_letter and cover_letter else 'нет'}")
    print("=" * 60)

    with Tracker(config["db_path"]) as tracker:
        with sync_playwright() as pw:
            context = create_context(pw, config)
            try:
                page = context.new_page()

                # Авторизация
                if not login_if_needed(page, config):
                    print("Не авторизован. Запусти: python3 login.py")
                    return

                # Поиск: сброс фильтров → ввод запроса → Найти
                do_search(page, config)

                # Основной цикл: по страницам результатов
                sent = 0
                skipped = 0
                page_num = 0
                session_check_counter = 0

                while sent < max_apps:
                    # Собираем вакансии с текущей страницы
                    vacancies = collect_vacancy_ids_from_page(page)
                    print(f"\n--- Страница {page_num} ({len(vacancies)} вакансий с кнопкой) ---")

                    if not vacancies:
                        print("Вакансий с кнопкой отклика нет")
                        if not go_next_page(page):
                            break
                        page_num += 1
                        continue

                    # Фильтруем уже откликнувшиеся
                    new_vacancies = [v for v in vacancies if not tracker.is_applied(v.vacancy_id)]

                    if args.dry_run:
                        for v in new_vacancies:
                            print(f"  {sent + skipped + 1}. {v.title} — {v.company}")
                            skipped += 1
                    else:
                        for vacancy in new_vacancies:
                            if sent >= max_apps:
                                break

                            # Периодическая проверка сессии (каждые 10 откликов)
                            session_check_counter += 1
                            if session_check_counter % 10 == 0:
                                if not check_logged_in(page):
                                    print("[!] Сессия истекла. Сохраняю и выхожу.")
                                    break

                            print(f"[{sent + 1}/{max_apps}] {vacancy.title} — {vacancy.company}")

                            status = apply_to_vacancy(
                                page, vacancy, cover_letter, use_cover_letter
                            )

                            tracker.record(
                                vacancy.vacancy_id, vacancy.title,
                                vacancy.company, status
                            )

                            if status in ("sent", "cover_letter_sent"):
                                sent += 1
                            else:
                                skipped += 1

                            if status == STATUS_CAPTCHA:
                                # После капчи — страница могла измениться
                                break

                            human_delay(
                                config.get("delay_min", 5),
                                config.get("delay_max", 12),
                            )

                    # Следующая страница
                    if sent >= max_apps:
                        break
                    if not go_next_page(page):
                        print("Страниц больше нет.")
                        break
                    page_num += 1

                # Итоги
                print("\n" + "=" * 60)
                if args.dry_run:
                    print(f"DRY RUN: найдено {skipped} вакансий")
                else:
                    print(f"Отправлено: {sent}")
                    print(f"Пропущено:  {skipped}")
                    print(f"Всего в БД: {tracker.total()}")
                    for st, cnt in tracker.stats().items():
                        print(f"  {st}: {cnt}")
                print("=" * 60)

            finally:
                # Всегда сохраняем сессию и закрываем
                try:
                    context.storage_state(path=config["storage_state_path"])
                except Exception:
                    pass
                context.close()


if __name__ == "__main__":
    main()
