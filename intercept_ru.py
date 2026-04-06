#!/usr/bin/env python3
"""Находим РОССИЙСКУЮ quickResponse вакансию и перехватываем полный цикл отклика."""

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
        # Ловим ВСЁ кроме аналитики
        if "anatskytics" in url or "vk.com" in url or "mc.yandex" in url:
            return
        if any(k in url for k in ["vacancy_response", "negotiations", "resume",
                                    "quick", "response", "apply", "letter"]):
            entry = {
                "d": "REQ", "method": request.method, "url": url,
                "headers": dict(request.headers),
                "post_data": request.post_data,
            }
            all_captured.append(entry)
            print(f"\n  >>> {request.method} {url}")
            if request.post_data:
                print(f"      POST: {request.post_data[:1000]}")
            print(f"      HEADERS: {json.dumps({k:v for k,v in request.headers.items() if k.startswith('x-') or k in ('content-type','accept','cookie')}, ensure_ascii=False)[:500]}")

    def on_resp(response):
        url = response.url
        if "anatskytics" in url or "vk.com" in url or "mc.yandex" in url:
            return
        if any(k in url for k in ["vacancy_response", "negotiations", "resume",
                                    "quick", "response", "apply", "letter"]):
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
            print(f"\n  <<< {response.status} {url}")
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

        vacancies = page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                return Array.from(cards).map(card => {
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    if (!btn || btn.textContent.includes('отправлен')) return null;
                    const title = card.querySelector('[data-qa="serp-item__title"]');
                    const href = btn.href || '';
                    const vm = href.match(/vacancyId=(\\d+)/);
                    return { vacancy_id: vm ? vm[1] : null, title: title ? title.textContent.trim() : '?' };
                }).filter(v => v && v.vacancy_id);
            }
        """)

        # Находим РОССИЙСКУЮ quickResponse
        print(f"Сканирую {len(vacancies)} вакансий...\n")
        target = None

        for v in vacancies:
            popup_url = f"https://hh.ru/applicant/vacancy_response/popup?vacancyId={v['vacancy_id']}&isTest=no&withoutTest=no&lux=true&alreadyApplied=false"
            try:
                resp = page.request.get(popup_url)
                data = resp.json()
                vtype = data.get("type", "?")

                if vtype != "quickResponse":
                    continue

                # Проверяем страну
                short = data.get("body", {}).get("responseStatus", {}).get("shortVacancy", {})
                company = short.get("company", {})
                country_id = company.get("@countryId", 0)
                area = short.get("area", {}).get("name", "?")

                print(f"  quickResponse: {v['title'][:40]:40s} | country={country_id} | area={area}")

                if country_id == 113:  # Россия = 113
                    target = {**v, "popup": data}
                    print(f"    >>> РОССИЙСКАЯ! Беру.")
                    break

            except Exception as e:
                pass

        if not target:
            # Если не нашли с countryId=113, берём любую без foreign warning
            print("\nНе нашёл с countryId=113, пробую по area...")
            for v in vacancies:
                popup_url = f"https://hh.ru/applicant/vacancy_response/popup?vacancyId={v['vacancy_id']}&isTest=no&withoutTest=no&lux=true&alreadyApplied=false"
                try:
                    resp = page.request.get(popup_url)
                    data = resp.json()
                    if data.get("type") != "quickResponse":
                        continue
                    short = data.get("body", {}).get("responseStatus", {}).get("shortVacancy", {})
                    area = short.get("area", {}).get("name", "")
                    if "Москва" in area or "Санкт" in area or "Россия" in area:
                        target = {**v, "popup": data}
                        print(f"  Нашёл по area: {v['title']} ({area})")
                        break
                except Exception:
                    pass

        if not target:
            print("Не нашёл российскую quickResponse. Беру первую quickResponse.")
            for v in vacancies:
                popup_url = f"https://hh.ru/applicant/vacancy_response/popup?vacancyId={v['vacancy_id']}&isTest=no&withoutTest=no&lux=true&alreadyApplied=false"
                try:
                    resp = page.request.get(popup_url)
                    data = resp.json()
                    if data.get("type") == "quickResponse":
                        target = {**v, "popup": data}
                        break
                except Exception:
                    pass

        if not target:
            print("Нет quickResponse вообще!")
            browser.close()
            return

        vid = target["vacancy_id"]
        resume_hash = target["popup"].get("body", {}).get("resume_hash", "?")
        print(f"\n{'='*60}")
        print(f"ЦЕЛЬ: {target['title']} (ID: {vid})")
        print(f"resume_hash: {resume_hash}")
        print(f"{'='*60}\n")

        # Подключаем перехватчики
        page.on("request", on_req)
        page.on("response", on_resp)

        # Кликаем
        print(">>> КЛИКАЮ ОТКЛИКНУТЬСЯ...\n")
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

        page.wait_for_timeout(4000)

        # Если foreign warning — подтверждаем
        has_warning = page.evaluate("() => document.body.innerText.includes('другой стране') || document.body.innerText.includes('другую страну')")
        if has_warning:
            print(">>> Подтверждаю foreign employer...")
            page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const t = b.textContent.toLowerCase();
                    if (t.includes('всё равно') || t.includes('продолжить') || t.includes('откликнуться')) {
                        b.click(); return;
                    }
                }
            }""")
            page.wait_for_timeout(4000)

        # Ждём
        page.wait_for_timeout(4000)

        state = page.evaluate(f"""
            () => ({{
                url: location.href,
                snackbar: document.body.innerText.includes('Отклик отправлен'),
                btn: (() => {{
                    const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                    for (const card of cards) {{
                        const link = card.querySelector('[data-qa="serp-item__title"]');
                        if (link && link.href.includes('/vacancy/{vid}')) {{
                            const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                            return btn ? btn.textContent.trim() : 'gone';
                        }}
                    }}
                    return 'not found';
                }})(),
            }})
        """)
        print(f"\nРезультат: {json.dumps(state, indent=2, ensure_ascii=False)}")

        # Сохраняем
        with open("data/ru_intercept.json", "w", encoding="utf-8") as f:
            json.dump({
                "target": {k: v for k, v in target.items() if k != "popup"},
                "popup": target["popup"],
                "resume_hash": resume_hash,
                "captured": all_captured,
                "result": state,
            }, f, ensure_ascii=False, indent=2)

        print(f"\n{len(all_captured)} запросов перехвачено (без аналитики)")
        print("Сохранено в data/ru_intercept.json")

        print("\nБраузер открыт 15 сек...")
        page.wait_for_timeout(15000)
        browser.close()


if __name__ == "__main__":
    main()
