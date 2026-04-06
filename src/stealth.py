"""Anti-detect: stealth-патчи для Playwright.

ВАЖНО: add_init_script должен вызываться ПЕРЕД любой навигацией.
Патчи применяются через Navigator.prototype для устойчивости к iframe-проверкам.
"""

from __future__ import annotations

import random

# Реалистичные UA — должны соответствовать РЕАЛЬНОЙ версии Chromium Playwright
# Обновлять при обновлении Playwright!
USER_AGENTS_MAC = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
]

USER_AGENTS_WIN = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
]


STEALTH_JS = """
// === STEALTH LAYER ===
// Патчим на уровне прототипа — работает в iframe тоже

// 1. navigator.webdriver — удаляем с прототипа
delete Object.getPrototypeOf(navigator).webdriver;
Object.defineProperty(Navigator.prototype, 'webdriver', {
    get: () => undefined,
    configurable: true,
});

// 2. window.chrome — полноценный объект
if (!window.chrome) {
    window.chrome = {};
}
window.chrome.app = {
    isInstalled: false,
    InstallState: {DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed'},
    RunningState: {CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running'},
    getDetails: function() { return null; },
    getIsInstalled: function() { return false; },
    installState: function() { return 'not_installed'; },
};
window.chrome.runtime = {
    OnInstalledReason: {CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update'},
    OnRestartRequiredReason: {APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic'},
    PlatformArch: {ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64'},
    PlatformNaclArch: {ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64'},
    PlatformOs: {ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win'},
    RequestUpdateCheckStatus: {NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available'},
    connect: function() { return {onMessage: {addListener: function(){}, removeListener: function(){}}, postMessage: function(){}}; },
    sendMessage: function() {},
    id: undefined,
    getManifest: function() { return undefined; },
};
window.chrome.csi = function() { return {}; };
window.chrome.loadTimes = function() { return {}; };

// 3. Plugins — современный Chrome (5 PDF-related)
Object.defineProperty(Navigator.prototype, 'plugins', {
    get: function() {
        const makePlugin = (name, filename, desc) => {
            const p = Object.create(Plugin.prototype);
            Object.defineProperties(p, {
                name: {value: name}, filename: {value: filename},
                description: {value: desc}, length: {value: 1},
                0: {value: {type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'}},
            });
            return p;
        };
        const arr = [
            makePlugin('PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
            makePlugin('Chrome PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
            makePlugin('Chromium PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
            makePlugin('Microsoft Edge PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
            makePlugin('WebKit built-in PDF', 'internal-pdf-viewer', 'Portable Document Format'),
        ];
        arr.item = function(i) { return this[i]; };
        arr.namedItem = function(name) { return this.find(p => p.name === name); };
        arr.refresh = function() {};
        Object.setPrototypeOf(arr, PluginArray.prototype);
        return arr;
    },
    configurable: true,
});

// 4. mimeTypes
Object.defineProperty(Navigator.prototype, 'mimeTypes', {
    get: function() {
        const arr = [
            {type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'},
        ];
        arr.item = function(i) { return this[i]; };
        arr.namedItem = function(name) { return this.find(m => m.type === name); };
        Object.setPrototypeOf(arr, MimeTypeArray.prototype);
        return arr;
    },
    configurable: true,
});

// 5. Languages
Object.defineProperty(Navigator.prototype, 'languages', {
    get: () => ['ru-RU', 'ru', 'en-US', 'en'],
    configurable: true,
});

// 6. Permissions
const origQuery = navigator.permissions.query.bind(navigator.permissions);
navigator.permissions.query = (params) => {
    if (params.name === 'notifications') {
        return Promise.resolve({state: Notification.permission});
    }
    return origQuery(params);
};

// 7. Canvas fingerprint noise
const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    if (this.width > 16 && this.height > 16) {
        const ctx = this.getContext('2d');
        if (ctx) {
            const style = ctx.fillStyle;
            ctx.fillStyle = 'rgba(0,0,1,0.003)';
            ctx.fillRect(0, 0, 1, 1);
            ctx.fillStyle = style;
        }
    }
    return origToDataURL.apply(this, arguments);
};

// 8. AudioContext fingerprint noise
const origGetChannelData = AudioBuffer.prototype.getChannelData;
AudioBuffer.prototype.getChannelData = function(channel) {
    const data = origGetChannelData.call(this, channel);
    if (data.length > 100) {
        for (let i = 0; i < Math.min(10, data.length); i++) {
            data[i] += (Math.random() - 0.5) * 0.0001;
        }
    }
    return data;
};

// 9. WebGL vendor/renderer (не трогаем — в headed mode используется реальный GPU)

// 10. CDP detection mitigation
// Удаляем маркеры если есть
delete window.__playwright;
delete window.__pw_1;
"""


def random_viewport() -> dict:
    """Реалистичные размеры экрана (только стандартные разрешения)."""
    options = [
        {"width": 1280, "height": 800},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
        {"width": 1600, "height": 900},
        {"width": 1920, "height": 1080},
    ]
    return random.choice(options)


def random_user_agent() -> str:
    """UA только для macOS (соответствует platform: MacIntel)."""
    return random.choice(USER_AGENTS_MAC)


def get_chromium_version(browser) -> str:
    """Получает реальную версию Chromium из Playwright."""
    version = browser.version
    return version.split(".")[0] if version else "134"


def apply_stealth(context) -> None:
    """Применяет stealth-патчи к browser context. ВЫЗЫВАТЬ ПЕРЕД new_page()."""
    context.add_init_script(STEALTH_JS)
