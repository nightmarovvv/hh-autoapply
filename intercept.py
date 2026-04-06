#!/usr/bin/env python3
"""Перехват HTTP-запросов при отклике на hh.ru.

Открывает браузер, ищет вакансии, при отклике логирует ВСЕ network-запросы.
Результат сохраняется в data/intercepted_requests.json
"""

import json
import yaml
from playwright.sync_api import sync_playwright
from src.stealth import apply_stealth, random_viewport, random_user_agent


def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    captured = []

    def on_request(request):
        """Перехватываем ВСЕ запросы."""
        if any(kw in request.url for kw in ["vacancy_response", "vacancy/response",
                                              "negotiations", "resume", "apply",
                                              "response", "letter"]):
            entry = {
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
                "post_data": request.post_data,
                "resource_type": request.resource_type,
            }
            captured.append(entry)
            print(f"\n>>> ПЕРЕХВАЧЕН: {request.method} {request.url}")
            if request.post_data:
                print(f"    POST DATA: {request.post_data[:500]}")
            print(f"    Headers: {json.dumps(dict(request.headers), indent=2, ensure_ascii=False)[:800]}")

    def on_response(response):
        """Перехватываем ответы на ключевые запросы."""
        if any(kw in response.url for kw in ["vacancy_response", "negotiations",
                                               "apply", "response"]):
            try:
                body = response.text()
            except Exception:
                body = "<не удалось прочитать>"

            entry = {
                "url": response.url,
                "status": response.status,
                "headers": dict(response.headers),
                "body_preview": body[:2000] if body else None,
            }
            captured.append(entry)
            print(f"\n<<< ОТВЕТ: {response.status} {response.url}")
            if body:
                print(f"    BODY: {body[:500]}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            storage_state=config["storage_state_path"],
            viewport=random_viewport(),
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            user_agent=random_user_agent(),
        )
        apply_stealth(context)

        page = context.new_page()

        # Подключаем перехватчики
        page.on("request", on_request)
        page.on("response", on_response)

        # Убираем куки-баннер и сбрасываем фильтры
        page.goto("https://hh.ru/search/vacancy", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        page.evaluate('document.querySelector(\'[data-qa="cookies-policy-informer"]\')?.remove()')
        page.evaluate("""() => {
            const spans = document.querySelectorAll('[data-qa="link-text"]');
            for (const span of spans) { if (span.textContent.trim() === 'Сбросить все') { span.click(); return; } }
        }""")
        page.wait_for_timeout(3000)

        # Ищем aqa
        si = page.locator('[data-qa="search-input"]')
        si.first.fill("aqa")
        page.wait_for_timeout(500)
        page.locator('[data-qa="search-button"]').first.click()
        page.wait_for_timeout(5000)

        print("\n" + "=" * 60)
        print("СТРАНИЦА ПОИСКА ЗАГРУЖЕНА")
        print("Сейчас буду кликать на первую кнопку 'Откликнуться'")
        print("Перехватываю все network-запросы...")
        print("=" * 60 + "\n")

        # Скроллим к первой карточке с кнопкой
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)

        # Находим первую вакансию с кнопкой отклика
        first_btn_info = page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                for (const card of cards) {
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    if (btn && !btn.textContent.includes('отправлен')) {
                        const title = card.querySelector('[data-qa="serp-item__title"]');
                        return {
                            title: title ? title.textContent.trim() : 'unknown',
                            btn_href: btn.href,
                            btn_text: btn.textContent.trim(),
                            vacancy_id: (btn.href.match(/vacancyId=(\d+)/) || [])[1],
                        };
                    }
                }
                return null;
            }
        """)

        if not first_btn_info:
            print("Нет доступных кнопок отклика!")
            browser.close()
            return

        print(f"Вакансия: {first_btn_info['title']}")
        print(f"Кнопка href: {first_btn_info['btn_href']}")
        print(f"Vacancy ID: {first_btn_info['vacancy_id']}")
        print()

        # Кликаем на кнопку отклика
        print(">>> КЛИКАЮ НА ОТКЛИКНУТЬСЯ...")
        page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                for (const card of cards) {
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    if (btn && !btn.textContent.includes('отправлен')) {
                        btn.click();
                        return;
                    }
                }
            }
        """)

        # Ждём ответа
        page.wait_for_timeout(6000)

        # Проверяем модалки
        modal_info = page.evaluate("""
            () => {
                const letter = document.querySelector('[data-qa="vacancy-response-popup-form-letter-input"]');
                const modal = document.querySelector('[role="dialog"]');
                const snackbar = document.body.innerText.includes('Отклик отправлен');
                return {
                    has_letter_input: !!letter,
                    has_modal: !!modal,
                    snackbar_sent: snackbar,
                    current_url: location.href,
                };
            }
        """)
        print(f"\nПосле клика: {json.dumps(modal_info, indent=2, ensure_ascii=False)}")

        # Если есть модалка с письмом — заполним и посмотрим запрос
        if modal_info.get("has_letter_input"):
            print("\n>>> МОДАЛКА С ПИСЬМОМ — заполняю и отправляю...")
            letter = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]')
            letter.fill("Здравствуйте! Интересует вакансия.")
            page.wait_for_timeout(500)

            submit = page.locator('[data-qa="vacancy-response-submit-popup"]')
            if submit.count() > 0:
                submit.first.click()
            else:
                page.locator('button:has-text("Откликнуться")').first.click()

            page.wait_for_timeout(5000)

        # Сохраняем
        with open("data/intercepted_requests.json", "w", encoding="utf-8") as f:
            json.dump(captured, f, ensure_ascii=False, indent=2)

        print(f"\n\nПерехвачено {len(captured)} запросов")
        print("Сохранено в data/intercepted_requests.json")

        # Показываем сводку
        print("\n" + "=" * 60)
        print("СВОДКА ПЕРЕХВАЧЕННЫХ ЗАПРОСОВ:")
        for i, req in enumerate(captured):
            method = req.get("method", "RESP")
            url = req.get("url", "")
            status = req.get("status", "")
            print(f"  {i+1}. {method} {status} {url[:100]}")
        print("=" * 60)

        print("\nБраузер открыт 30 сек...")
        page.wait_for_timeout(30000)
        browser.close()


if __name__ == "__main__":
    main()
