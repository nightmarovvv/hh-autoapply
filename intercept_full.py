#!/usr/bin/env python3
"""Полный перехват: находим вакансию без теста, делаем отклик, ловим ВСЕ запросы.

Стратегия:
1. Открываем поиск, собираем vacancy_id
2. Для каждой — GET /applicant/vacancy_response/popup чтобы узнать тип
3. Находим первую с type != "test-required"
4. Делаем полный отклик и перехватываем все запросы
"""

import json
import re
import yaml
from playwright.sync_api import sync_playwright
from src.stealth import apply_stealth, random_viewport, random_user_agent


def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    all_captured = []

    def capture_request(request):
        url = request.url
        if any(kw in url for kw in ["vacancy_response", "negotiations", "resume/send",
                                      "letter", "apply", "/response"]):
            entry = {
                "direction": "REQUEST",
                "url": url,
                "method": request.method,
                "headers": dict(request.headers),
                "post_data": request.post_data,
            }
            all_captured.append(entry)
            print(f"  >>> {request.method} {url[:120]}")
            if request.post_data:
                print(f"      POST: {request.post_data[:300]}")

    def capture_response(response):
        url = response.url
        if any(kw in url for kw in ["vacancy_response", "negotiations", "resume/send",
                                      "letter", "apply", "/response"]):
            try:
                body = response.text()
            except Exception:
                body = None
            entry = {
                "direction": "RESPONSE",
                "url": url,
                "status": response.status,
                "headers": dict(response.headers),
                "body": body[:3000] if body else None,
            }
            all_captured.append(entry)
            print(f"  <<< {response.status} {url[:120]}")
            if body:
                print(f"      BODY: {body[:300]}")

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

        # Поиск
        page.goto("https://hh.ru/search/vacancy", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.evaluate('document.querySelector(\'[data-qa="cookies-policy-informer"]\')?.remove()')
        page.evaluate("""() => {
            const spans = document.querySelectorAll('[data-qa="link-text"]');
            for (const span of spans) { if (span.textContent.trim() === 'Сбросить все') { span.click(); return; }}
        }""")
        page.wait_for_timeout(3000)
        page.locator('[data-qa="search-input"]').first.fill("aqa")
        page.wait_for_timeout(500)
        page.locator('[data-qa="search-button"]').first.click()
        page.wait_for_timeout(5000)

        # Собираем все vacancy_id и employer_id с кнопками отклика
        vacancies = page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                return Array.from(cards).map(card => {
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    if (!btn || btn.textContent.includes('отправлен')) return null;

                    const title = card.querySelector('[data-qa="serp-item__title"]');
                    const href = btn.href || '';
                    const vacancyMatch = href.match(/vacancyId=(\\d+)/);
                    const employerMatch = href.match(/employerId=(\\d+)/);

                    return {
                        vacancy_id: vacancyMatch ? vacancyMatch[1] : null,
                        employer_id: employerMatch ? employerMatch[1] : null,
                        title: title ? title.textContent.trim() : 'unknown',
                        btn_href: href,
                    };
                }).filter(v => v && v.vacancy_id);
            }
        """)

        print(f"\nНайдено {len(vacancies)} вакансий с кнопкой отклика\n")

        # Проверяем тип каждой через popup endpoint
        print("=" * 60)
        print("ПРОВЕРЯЮ ТИПЫ ВАКАНСИЙ ЧЕРЕЗ POPUP ENDPOINT")
        print("=" * 60)

        simple_vacancy = None

        for v in vacancies[:20]:  # Проверяем первые 20
            popup_url = f"https://hh.ru/applicant/vacancy_response/popup?vacancyId={v['vacancy_id']}&isTest=no&withoutTest=no&lux=true&alreadyApplied=false"

            try:
                resp = page.request.get(popup_url)
                data = resp.json()
                resp_type = data.get("type", "unknown")
                print(f"  {v['title'][:50]:50s} → type: {resp_type}")

                v["popup_response"] = data

                if resp_type not in ("test-required",):
                    simple_vacancy = v
                    print(f"\n  >>> НАШЁЛ ПРОСТУЮ ВАКАНСИЮ! type={resp_type}")
                    break

            except Exception as e:
                print(f"  {v['title'][:50]:50s} → ОШИБКА: {e}")

        if not simple_vacancy:
            print("\nНе нашёл вакансию без теста в первых 20. Пробую отклик на первую доступную...")
            simple_vacancy = vacancies[0]

        print(f"\n{'='*60}")
        print(f"ВАКАНСИЯ ДЛЯ ОТКЛИКА:")
        print(f"  Название: {simple_vacancy['title']}")
        print(f"  ID: {simple_vacancy['vacancy_id']}")
        print(f"  Popup тип: {simple_vacancy.get('popup_response', {}).get('type', '?')}")
        print(f"  Popup полный: {json.dumps(simple_vacancy.get('popup_response', {}), ensure_ascii=False)[:500]}")
        print(f"{'='*60}\n")

        # Подключаем перехватчики ПЕРЕД кликом
        page.on("request", capture_request)
        page.on("response", capture_response)

        # Делаем отклик через JS click
        vid = simple_vacancy["vacancy_id"]
        print(f">>> КЛИКАЮ ОТКЛИКНУТЬСЯ на vacancy {vid}...")

        page.evaluate(f"""
            () => {{
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                for (const card of cards) {{
                    const link = card.querySelector('[data-qa="serp-item__title"]');
                    if (link && link.href.includes('/vacancy/{vid}')) {{
                        const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                        if (btn) btn.click();
                        return;
                    }}
                }}
            }}
        """)

        # Ждём ответ
        page.wait_for_timeout(6000)

        # Проверяем состояние
        state = page.evaluate("""
            () => ({
                url: location.href,
                has_letter_input: !!document.querySelector('[data-qa="vacancy-response-popup-form-letter-input"]'),
                has_modal: !!document.querySelector('[role="dialog"]'),
                snackbar: document.body.innerText.includes('Отклик отправлен'),
                has_submit_btn: !!document.querySelector('[data-qa="vacancy-response-submit-popup"]'),
            })
        """)
        print(f"\nСостояние после клика: {json.dumps(state, indent=2, ensure_ascii=False)}")

        # Если модалка с письмом — заполняем и отправляем
        if state.get("has_letter_input") or state.get("has_submit_btn"):
            print("\n>>> МОДАЛКА ОБНАРУЖЕНА — заполняю и отправляю...")

            letter = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]')
            if letter.count() > 0:
                letter.fill("Здравствуйте! Ваша вакансия меня заинтересовала.")
                page.wait_for_timeout(500)

            submit = page.locator('[data-qa="vacancy-response-submit-popup"]')
            if submit.count() > 0:
                submit.first.click()
                print(">>> Нажал отправить в модалке")
            else:
                btn = page.locator('button:has-text("Откликнуться")')
                if btn.count() > 0:
                    btn.first.click()
                    print(">>> Нажал откликнуться (альт кнопка)")

            page.wait_for_timeout(6000)

            # Финальное состояние
            final = page.evaluate("""
                () => ({
                    url: location.href,
                    snackbar: document.body.innerText.includes('Отклик отправлен'),
                })
            """)
            print(f"Финальное состояние: {json.dumps(final, indent=2, ensure_ascii=False)}")

        # Если редирект на страницу отклика — проверяем там
        elif "/vacancy_response" in state.get("url", ""):
            print("\n>>> РЕДИРЕКТ НА СТРАНИЦУ ОТКЛИКА")
            # Ждём ещё
            page.wait_for_timeout(5000)

        # Сохраняем результаты
        results = {
            "vacancy": simple_vacancy,
            "captured_requests": all_captured,
            "state_after_click": state,
        }

        with open("data/full_intercept.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n\n{'='*60}")
        print(f"ПЕРЕХВАЧЕНО {len(all_captured)} запросов")
        print(f"Сохранено в data/full_intercept.json")
        print(f"{'='*60}")

        for i, req in enumerate(all_captured):
            d = req.get("direction", "?")
            m = req.get("method", "")
            s = req.get("status", "")
            url = req.get("url", "")[:100]
            print(f"  {i+1}. [{d}] {m}{s} {url}")

        print("\nБраузер открыт 20 сек...")
        page.wait_for_timeout(20000)
        browser.close()


if __name__ == "__main__":
    main()
