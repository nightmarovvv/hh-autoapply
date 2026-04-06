"""Anti-detect меры для Playwright.

Патчит navigator.webdriver, добавляет window.chrome,
рандомизирует viewport и user-agent.
"""

from __future__ import annotations

import random

# Реалистичные user-agent строки (Chrome на macOS)
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]

# Стелс-скрипт: патчит все основные маркеры автоматизации
STEALTH_JS = """
// 1. navigator.webdriver = undefined
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// 2. window.chrome — имитируем реальный объект
window.chrome = {
    runtime: {
        onMessage: {addListener: function(){}, removeListener: function(){}},
        sendMessage: function(){},
        connect: function(){return {onMessage: {addListener: function(){}}, postMessage: function(){}}},
    },
    loadTimes: function(){return {}},
    csi: function(){return {}},
};

// 3. Plugins — добавляем фейковые
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'},
            {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: ''},
            {name: 'Native Client', filename: 'internal-nacl-plugin', description: ''},
        ];
        plugins.length = 3;
        return plugins;
    }
});

// 4. Languages — добавляем несколько
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});

// 5. Permissions — патчим query
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({state: Notification.permission}) :
        originalQuery(parameters)
);
"""


def random_viewport() -> dict:
    """Случайный реалистичный размер окна."""
    widths = [1280, 1366, 1440, 1536, 1600, 1920]
    heights = [720, 768, 800, 864, 900, 1080]
    w = random.choice(widths)
    h = random.choice(heights)
    # Небольшой джиттер
    w += random.randint(-20, 20)
    h += random.randint(-10, 10)
    return {"width": w, "height": h}


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def apply_stealth(context) -> None:
    """Применяет стелс-патчи к browser context."""
    context.add_init_script(STEALTH_JS)
