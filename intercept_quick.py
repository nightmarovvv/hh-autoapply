#!/usr/bin/env python3
"""Перехват quickResponse — самый частый тип отклика (37 из 50).

Кликаем на quickResponse вакансию и ловим ВСЕ запросы.
"""

import json
import yaml
from playwright.sync_api import sync_playwright
from src.stealth import apply_stealth, random_viewport, random_user_agent


def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    all_captured = []

    def on_req(request):
        url = request.url
        # Ловим ВСЁ связанное с откликами
        if any(k in url for k in ["vacancy_response", "negotiations", "resume",
                                    "quick", "response", "apply"]):
            entry = {
                "d": "REQ", "method": request.method, "url": url,
                "headers": dict(request.headers),
                "post_data": request.post_data,
            }
            all_captured.append(entry)
            print(f"  >>> {request.method} {url}")
            if request.post_data:
                print(f"      POST DATA: {request.post_data[:1000]}")

    def on_resp(response):
        url = response.url
        if any(k in url for k in ["vacancy_response", "negotiations", "resume",
                                    "quick", "response", "apply"]):
            try:
                body = response.text()
            except Exception:
                body = None
            entry = {
                "d": "RESP", "status": response.status, "url": url,
                "body": body[:5000] if body else None,
                "headers": dict(response.headers),
            }
            all_captured.append(entry)
            print(f"  <<< {response.status} {url}")
            if body:
                print(f"      BODY: {body[:500]}")

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

        # Собираем все vacancy_id
        vacancies = page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                return Array.from(cards).map(card => {
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    if (!btn || btn.textContent.includes('отправлен')) return null;
                    const title = card.querySelector('[data-qa="serp-item__title"]');
                    const href = btn.href || '';
                    const vm = href.match(/vacancyId=(\\d+)/);
                    return {
                        vacancy_id: vm ? vm[1] : null,
                        title: title ? title.textContent.trim() : '?',
                    };
                }).filter(v => v && v.vacancy_id);
            }
        """)

        # Находим quickResponse
        target = None
        for v in vacancies:
            popup_url = f"https://hh.ru/applicant/vacancy_response/popup?vacancyId={v['vacancy_id']}&isTest=no&withoutTest=no&lux=true&alreadyApplied=false"
            try:
                resp = page.request.get(popup_url)
                data = resp.json()
                if data.get("type") == "quickResponse":
                    target = {**v, "popup": data}
                    print(f"НАШЁЛ quickResponse: {v['title']} (ID: {v['vacancy_id']})")
                    break
            except Exception:
                pass

        if not target:
            print("quickResponse не найден!")
            browser.close()
            return

        # Выводим popup данные
        print(f"\nPopup response:")
        print(json.dumps(target["popup"], ensure_ascii=False, indent=2)[:2000])

        # Подключаем перехватчики
        page.on("request", on_req)
        page.on("response", on_resp)

        print(f"\n{'='*60}")
        print(f"КЛИКАЮ quickResponse: {target['title']}")
        print(f"{'='*60}\n")

        vid = target["vacancy_id"]
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

        page.wait_for_timeout(8000)

        # Проверяем
        state = page.evaluate("""
            () => ({
                url: location.href,
                snackbar: document.body.innerText.includes('Отклик отправлен'),
                btn_text: (() => {
                    const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                    for (const card of cards) {
                        const link = card.querySelector('[data-qa="serp-item__title"]');
                        if (link && link.href.includes('/vacancy/""" + vid + """')) {
                            const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                            return btn ? btn.textContent.trim() : 'no btn';
                        }
                    }
                    return 'not found';
                })(),
            })
        """)
        print(f"\nРезультат: {json.dumps(state, indent=2, ensure_ascii=False)}")

        # Сохраняем
        with open("data/quick_response_intercept.json", "w", encoding="utf-8") as f:
            json.dump({
                "target": {k: v for k, v in target.items() if k != "popup"},
                "popup": target["popup"],
                "captured": all_captured,
                "result": state,
            }, f, ensure_ascii=False, indent=2)

        print(f"\n{len(all_captured)} запросов перехвачено")
        print("Сохранено в data/quick_response_intercept.json")

        print("\nБраузер открыт 15 сек...")
        page.wait_for_timeout(15000)
        browser.close()


if __name__ == "__main__":
    main()
