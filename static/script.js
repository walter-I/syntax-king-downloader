const form = document.getElementById("downloadForm");
const input = document.getElementById("mediaUrl");
const result = document.getElementById("result");
const button = document.getElementById("downloadButton");
const buttonText = document.getElementById("buttonText");

const platforms = document.querySelectorAll(".platform");

let selectedPlatform = null;

function detectPlatform(value) {
    try {
        const url = new URL(value);
        const host = url.hostname.toLowerCase().replace(/^www\./, "");

        if (
            host === "youtube.com" ||
            host === "m.youtube.com" ||
            host === "youtu.be" ||
            host === "music.youtube.com"
        ) {
            return "youtube";
        }

        if (
            host === "instagram.com" ||
            host === "instagr.am"
        ) {
            return "instagram";
        }

        if (
            host === "facebook.com" ||
            host === "fb.watch" ||
            host === "m.facebook.com" ||
            host === "web.facebook.com"
        ) {
            return "facebook";
        }

        if (
            host === "tiktok.com" ||
            host === "vm.tiktok.com" ||
            host === "vt.tiktok.com"
        ) {
            return "tiktok";
        }

        return null;

    } catch {
        return null;
    }
}

function showResult(message, type = "") {
    result.className = "result";

    if (type) {
        result.classList.add(type);
    }

    result.textContent = message;
}

function updatePlatformSelection(platform) {
    selectedPlatform = platform;

    platforms.forEach(button => {
        button.classList.toggle(
            "active",
            button.dataset.platform === platform
        );
    });
}

input.addEventListener("input", () => {
    const detected = detectPlatform(input.value.trim());

    if (detected) {
        updatePlatformSelection(detected);
    } else {
        updatePlatformSelection(null);
    }
});

platforms.forEach(platformButton => {
    platformButton.addEventListener("click", () => {
        const platform = platformButton.dataset.platform;

        updatePlatformSelection(platform);

        input.focus();
        input.placeholder = `Paste your ${platform} link here...`;
    });
});

document.getElementById("pasteButton").addEventListener(
    "click",
    async () => {
        try {
            input.value = await navigator.clipboard.readText();

            input.dispatchEvent(new Event("input"));

        } catch {
            showResult(
                "Clipboard access is unavailable. Paste your link manually.",
                "error"
            );
        }
    }
);

form.addEventListener("submit", async event => {
    event.preventDefault();

    const url = input.value.trim();
    const detected = detectPlatform(url);

    if (!detected) {
        showResult(
            "Enter a supported YouTube, Instagram, Facebook, or TikTok URL.",
            "error"
        );

        return;
    }

    if (selectedPlatform && selectedPlatform !== detected) {
        showResult(
            "The link does not match the selected platform.",
            "error"
        );

        return;
    }

    button.disabled = true;
    buttonText.textContent = "Checking link...";

    result.className = "result";
    result.textContent = "Contacting the download server...";

    try {
        const response = await fetch("/api/download", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                url: url
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Request failed.");
        }

        result.className = "result success";
        result.replaceChildren();

        const message = document.createElement("p");
        message.textContent = data.message;
        result.appendChild(message);

        if (data.download_url) {
            const link = document.createElement("a");

            link.href = data.download_url;
            link.textContent = "Download media";
            link.download = "";

            result.appendChild(document.createElement("br"));
            result.appendChild(link);
        }

    } catch (error) {
        showResult(
            error.message || "Unable to contact the server.",
            "error"
        );

    } finally {
        button.disabled = false;
        buttonText.textContent = "Check & Download";
    }
});
