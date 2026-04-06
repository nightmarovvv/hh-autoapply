#!/usr/bin/env python3
"""v2: Прогоняем ВСЕ вакансии через popup, находим простую российскую, делаем отклик."""

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
        if any(k in url for k in ["vacancy_response", "negotiations", "resume/send"]):
            all_captured.append({
                "d": "REQ", "method": request.method, "url": url,
                "headers": dict(request.headers),
                "post_data": request.post_data,
            })
            print(f"  >>> {request.method} {url[:120]}")
            if request.post_data:
                print(f"      POST: {request.post_data[:500]}")

    def on_resp(response):
        url = response.url
        if any(k in url for k in ["vacancy_response", "negotiations", "resume/send"]):
            try:
                body = response.text()
            except Exception:
                body = None
            all_captured.append({
                "d": "RESP", "status": response.status, "url": url,
                "body": body[:5000] if body else None,
                "headers": dict(response.headers),
            })
            print(f"  <<< {response.status} {url[:120]}")
            if body:
                print(f"      BODY: {body[:400]}")

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

        # Собираем vacancy_id
        vacancies = page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                return Array.from(cards).map(card => {
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    if (!btn || btn.textContent.includes('отправлен')) return null;
                    const title = card.querySelector('[data-qa="serp-item__title"]');
                    const href = btn.href || '';
                    const vm = href.match(/vacancyId=(\\d+)/);
                    const em = href.match(/employerId=(\\d+)/);
                    return {
                        vacancy_id: vm ? vm[1] : null,
                        employer_id: em ? em[1] : null,
                        title: title ? title.textContent.trim() : '?',
                    };
                }).filter(v => v && v.vacancy_id);
            }
        """)

        print(f"\n{'='*60}")
        print(f"СКАНИРУЮ {len(vacancies)} ВАКАНСИЙ ЧЕРЕЗ POPUP API")
        print(f"{'='*60}\n")

        # Проверяем каждую
        vacancy_types = {}
        target = None

        for v in vacancies:
            popup_url = (
                f"https://hh.ru/applicant/vacancy_response/popup"
                f"?vacancyId={v['vacancy_id']}&isTest=no&withoutTest=no&lux=true&alreadyApplied=false"
            )
            try:
                resp = page.request.get(popup_url)
                data = resp.json()
                vtype = data.get("type", "?")
                short = data.get("shortVacancy") or data.get("responsePopup", {}).get("vacancy", {})

                # Проверяем письмо обязательно ли
                letter_req = data.get("shortVacancy", {}).get("@responseLetterRequired", False) if data.get("shortVacancy") else False
                # Проверяем город
                area = ""
                if data.get("shortVacancy", {}).get("area"):
                    area = data["shortVacancy"]["area"].get("name", "")

                vacancy_types[v["vacancy_id"]] = vtype

                marker = ""
                if not target and vtype == "modal" and "Москва" in area:
                    target = {**v, "popup": data, "letter_required": letter_req, "area": area}
                    marker = " <<< ЦЕЛЬ"
                elif not target and vtype not in ("test-required",) and vtype != "already-applied":
                    marker = " (кандидат)"

                print(f"  {v['title'][:45]:45s} | type={vtype:20s} | area={area:15s} | letter={letter_req}{marker}")

            except Exception as e:
                print(f"  {v['title'][:45]:45s} | ОШИБКА: {e}")

        # Если не нашли в Москве — берём первый modal без теста
        if not target:
            for v in vacancies:
                if vacancy_types.get(v["vacancy_id"]) == "modal":
                    popup_url = f"https://hh.ru/applicant/vacancy_response/popup?vacancyId={v['vacancy_id']}&isTest=no&withoutTest=no&lux=true&alreadyApplied=false"
                    resp = page.request.get(popup_url)
                    data = resp.json()
                    target = {**v, "popup": data, "letter_required": False, "area": "any"}
                    break

        if not target:
            print("\nНе нашёл подходящую вакансию для отклика!")
            browser.close()
            return

        print(f"\n{'='*60}")
        print(f"ЦЕЛЬ: {target['title']}")
        print(f"  ID: {target['vacancy_id']}, город: {target['area']}")
        print(f"  Тип: modal, письмо обязательно: {target['letter_required']}")
        print(f"{'='*60}\n")

        # Подключаем перехватчики
        page.on("request", on_req)
        page.on("response", on_resp)

        # ДЕЛАЕМ ОТКЛИК
        vid = target["vacancy_id"]
        print(f">>> КЛИКАЮ ОТКЛИКНУТЬСЯ на {vid}...")

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

        # Проверяем что появилось
        state = page.evaluate("""
            () => ({
                url: location.href,
                has_letter: !!document.querySelector('[data-qa="vacancy-response-popup-form-letter-input"]'),
                has_submit: !!document.querySelector('[data-qa="vacancy-response-submit-popup"]'),
                has_modal: !!document.querySelector('[role="dialog"]'),
                snackbar: document.body.innerText.includes('Отклик отправлен'),
                foreign_warning: document.body.innerText.includes('другой стране') || document.body.innerText.includes('другую страну'),
            })
        """)
        print(f"\nСостояние: {json.dumps(state, indent=2, ensure_ascii=False)}")

        # Если warning про другую страну — подтверждаем
        if state.get("foreign_warning"):
            print(">>> Подтверждаю отклик в другую страну...")
            confirm_btn = page.locator('button:has-text("Всё равно откликнуться")')
            if confirm_btn.count() > 0:
                confirm_btn.first.click()
                page.wait_for_timeout(3000)
            else:
                # Ищем любую кнопку подтверждения
                page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button');
                        for (const b of btns) {
                            if (b.textContent.includes('Всё равно') || b.textContent.includes('Продолжить') || b.textContent.includes('Откликнуться')) {
                                b.click(); return;
                            }
                        }
                    }
                """)
                page.wait_for_timeout(3000)

        # Перепроверяем
        state2 = page.evaluate("""
            () => ({
                url: location.href,
                has_letter: !!document.querySelector('[data-qa="vacancy-response-popup-form-letter-input"]'),
                has_submit: !!document.querySelector('[data-qa="vacancy-response-submit-popup"]'),
                snackbar: document.body.innerText.includes('Отклик отправлен'),
            })
        """)
        print(f"Состояние2: {json.dumps(state2, indent=2, ensure_ascii=False)}")

        # Если модалка с письмом — заполняем
        if state2.get("has_letter") or state2.get("has_submit"):
            print(">>> Заполняю сопроводительное и отправляю...")

            letter = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]')
            if letter.count() > 0:
                letter.fill("Здравствуйте! Интересует вакансия, готов обсудить.")
                page.wait_for_timeout(500)

            submit = page.locator('[data-qa="vacancy-response-submit-popup"]')
            if submit.count() > 0:
                submit.first.click()
                print(">>> Отправлено!")
            else:
                btn = page.locator('button:has-text("Откликнуться")')
                if btn.count() > 0:
                    btn.first.click()

            page.wait_for_timeout(5000)

        elif state2.get("snackbar"):
            print(">>> ОТКЛИК УЖЕ ОТПРАВЛЕН (без модалки)")

        # Финальная проверка
        final = page.evaluate("""
            () => ({
                url: location.href,
                snackbar: document.body.innerText.includes('Отклик отправлен'),
                body_snippet: document.body.innerText.substring(0, 500),
            })
        """)
        print(f"\nФинал: snackbar={final['snackbar']}, url={final['url']}")

        # Сохраняем
        with open("data/full_intercept_v2.json", "w", encoding="utf-8") as f:
            json.dump({
                "target": {k: v for k, v in target.items() if k != "popup"},
                "popup_response": target.get("popup", {}),
                "vacancy_types_summary": vacancy_types,
                "captured_requests": all_captured,
                "final_state": final,
            }, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"ПЕРЕХВАЧЕНО {len(all_captured)} запросов")
        print("ТИПЫ ВАКАНСИЙ:")
        from collections import Counter
        for vtype, count in Counter(vacancy_types.values()).most_common():
            print(f"  {vtype}: {count}")
        print(f"{'='*60}")

        print("\nБраузер открыт 20 сек...")
        page.wait_for_timeout(20000)
        browser.close()


if __name__ == "__main__":
    main()
