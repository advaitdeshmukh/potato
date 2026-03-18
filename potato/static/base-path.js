(function () {
    if (window.__potatoBasePathInitialized) {
        return;
    }
    window.__potatoBasePathInitialized = true;

    function getBasePath() {
        var root = document.documentElement;
        var raw = root ? (root.getAttribute('data-base-path') || '') : '';

        if (!raw || raw === '/') {
            return '';
        }

        if (raw.charAt(0) !== '/') {
            raw = '/' + raw;
        }

        return raw.endsWith('/') ? raw.slice(0, -1) : raw;
    }

    function shouldSkip(url) {
        var hasScheme = /^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(url);
        if (hasScheme) {
            var scheme = url.split(':', 1)[0].toLowerCase();
            if (scheme !== 'http' && scheme !== 'https') {
                return true;
            }
        }

        return (
            !url ||
            url.startsWith('data:') ||
            url.startsWith('blob:') ||
            url.startsWith('//')
        );
    }

    function withBasePath(url) {
        var basePath = getBasePath();
        if (!basePath) {
            return url;
        }

        if (url instanceof URL) {
            if (url.origin !== window.location.origin) {
                return url;
            }

            if (url.pathname === basePath || url.pathname.startsWith(basePath + '/')) {
                return url;
            }

            return new URL(basePath + url.pathname + url.search + url.hash, url.origin);
        }

        if (typeof url !== 'string') {
            return url;
        }

        if (shouldSkip(url)) {
            return url;
        }

        if (/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(url)) {
            var absoluteUrl = new URL(url);
            if (absoluteUrl.origin !== window.location.origin) {
                return url;
            }

            if (absoluteUrl.pathname === basePath || absoluteUrl.pathname.startsWith(basePath + '/')) {
                return url;
            }

            return absoluteUrl.origin + basePath + absoluteUrl.pathname + absoluteUrl.search + absoluteUrl.hash;
        }

        if (!url.startsWith('/')) {
            return url;
        }

        if (url === basePath || url.startsWith(basePath + '/')) {
            return url;
        }

        return basePath + url;
    }

    window.getBasePath = getBasePath;
    window.withBasePath = withBasePath;

    if (typeof window.fetch === 'function') {
        var originalFetch = window.fetch.bind(window);
        window.fetch = function (input, init) {
            var rewritten = input;

            if (typeof Request !== 'undefined' && input instanceof Request) {
                var rewrittenUrl = withBasePath(input.url);
                rewritten = rewrittenUrl === input.url ? input : new Request(rewrittenUrl, input);
            } else {
                rewritten = withBasePath(input);
            }

            return originalFetch(rewritten, init);
        };
    }

    if (typeof XMLHttpRequest !== 'undefined') {
        var originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function (method, url) {
            arguments[1] = withBasePath(url);
            return originalOpen.apply(this, arguments);
        };
    }

    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
        var originalSendBeacon = navigator.sendBeacon.bind(navigator);
        navigator.sendBeacon = function (url, data) {
            return originalSendBeacon(withBasePath(url), data);
        };
    }
})();
