"""Anti-detect stealth layer.

Patchright уже закрывает главные векторы:
- Нет Runtime.enable (CDP detection bypass)
- Нет --enable-automation
- InitScripts через Route injection

Этот модуль добавляет fingerprint-маскировку поверх Patchright:
- navigator.webdriver (двойная защита)
- window.chrome mock
- Plugins/MimeTypes
- Canvas/Audio noise
- WebGL vendor/renderer
- Permissions API
- Playwright globals cleanup
"""

from __future__ import annotations

import random
import platform

# === User-Agent пулы по платформам ===

USER_AGENTS_MAC = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
]

USER_AGENTS_WIN = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

USER_AGENTS_LINUX = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
]

# === Stealth JS ===
# Patchright убирает CDP-детект, но fingerprint-маскировку делаем сами

STEALTH_JS = """
// === STEALTH FINGERPRINT LAYER ===

// 1. navigator.webdriver — двойная защита (Patchright тоже патчит, но на всякий)
try {
    delete Object.getPrototypeOf(navigator).webdriver;
} catch(e) {}
Object.defineProperty(Navigator.prototype, 'webdriver', {
    get: () => undefined,
    configurable: true,
});

// 2. window.chrome — полный mock
if (!window.chrome) {
    window.chrome = {};
}
if (!window.chrome.app) {
    window.chrome.app = {
        isInstalled: false,
        InstallState: {DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed'},
        RunningState: {CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running'},
        getDetails: function() { return null; },
        getIsInstalled: function() { return false; },
        installState: function() { return 'not_installed'; },
    };
}
if (!window.chrome.runtime) {
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
}
if (!window.chrome.csi) window.chrome.csi = function() { return {}; };
if (!window.chrome.loadTimes) window.chrome.loadTimes = function() { return {}; };

// 3. Plugins — 5 PDF (стандарт Chrome)
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
        const arr = [{type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'}];
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

// 6. Permissions API — нормализуем ответы
const origQuery = navigator.permissions.query.bind(navigator.permissions);
navigator.permissions.query = (params) => {
    if (params.name === 'notifications') {
        return Promise.resolve({state: Notification.permission});
    }
    return origQuery(params);
};

// 7. Canvas fingerprint noise — микро-шум невидимый глазу
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

// 9. WebGL vendor/renderer — реалистичные значения
const webglSpoof = (proto) => {
    const orig = proto.getParameter;
    proto.getParameter = function(param) {
        if (param === 37445) return 'Google Inc. (Intel)';
        if (param === 37446) return 'ANGLE (Intel, Intel(R) Iris(TM) Plus Graphics, OpenGL 4.1)';
        return orig.call(this, param);
    };
};
webglSpoof(WebGLRenderingContext.prototype);
webglSpoof(WebGL2RenderingContext.prototype);

// 10. Screen consistency — headless protection
if (screen.width === 0 || screen.availWidth === 0) {
    Object.defineProperty(screen, 'availWidth', {get: () => screen.width});
    Object.defineProperty(screen, 'availHeight', {get: () => screen.height - 40});
}

// 11. Playwright/automation marker cleanup
try { delete window.__playwright; } catch(e) {}
try { delete window.__pw_1; } catch(e) {}
try { delete window.__pwInitScripts; } catch(e) {}
try { delete window.__playwright__binding__; } catch(e) {}

// 12. Connection type — имитация реальной сети
if (navigator.connection) {
    Object.defineProperty(navigator.connection, 'rtt', {get: () => 50 + Math.floor(Math.random() * 100)});
}

// 13. Hardcoded battery — как у десктопа на зарядке
if (navigator.getBattery) {
    navigator.getBattery = () => Promise.resolve({
        charging: true, chargingTime: 0, dischargingTime: Infinity, level: 1,
        addEventListener: function(){}, removeEventListener: function(){},
    });
}
"""


# === Viewports ===

VIEWPORTS = [
    {"width": 1280, "height": 800},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1600, "height": 900},
    {"width": 1920, "height": 1080},
    {"width": 1680, "height": 1050},
    {"width": 1920, "height": 1200},
]


def random_viewport() -> dict:
    return random.choice(VIEWPORTS)


def random_user_agent() -> str:
    """UA соответствующий текущей платформе."""
    sys_name = platform.system()
    if sys_name == "Darwin":
        return random.choice(USER_AGENTS_MAC)
    elif sys_name == "Windows":
        return random.choice(USER_AGENTS_WIN)
    else:
        return random.choice(USER_AGENTS_LINUX)


def get_chromium_version(browser) -> str:
    version = browser.version
    return version.split(".")[0] if version else "136"


def apply_stealth(context) -> None:
    """Применяет fingerprint-патчи. Вызывать ПЕРЕД new_page()."""
    context.add_init_script(STEALTH_JS)


def human_mouse_move(page, target_x: float, target_y: float) -> None:
    """Плавное движение мыши с Bezier-like траекторией."""
    steps = random.randint(8, 25)
    jitter_x = random.uniform(-5, 5)
    jitter_y = random.uniform(-3, 3)
    page.mouse.move(target_x + jitter_x, target_y + jitter_y, steps=steps)
    page.wait_for_timeout(random.randint(50, 200))
